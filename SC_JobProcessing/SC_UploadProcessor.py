#!/usr/bin/env python3
"""
ScientistCloud Upload Processor
Handles asynchronous upload jobs using rclone, rsync, and other tools.
"""

import os
import subprocess
import json
import time
import logging
import threading
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

from SC_Config import get_config, get_collection_name, get_database_name
from SC_MongoConnection import get_collection_by_type, mongo_collection_by_type_context
from SC_UploadJobTypes import (
    UploadJobConfig, UploadSourceType, UploadStatus, UploadProgress,
    UploadJobManager, get_tool_config
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SC_UploadProcessor:
    """
    Processes upload jobs asynchronously using various tools.
    Integrates with the SC_JobProcessing system.
    """
    
    def __init__(self):
        self.config = get_config()
        self.job_manager = UploadJobManager()
        self.active_jobs: Dict[str, subprocess.Popen] = {}
        self.progress_callbacks: Dict[str, Callable] = {}
        self.running = False
        self.worker_thread = None
    
    def start(self):
        """Start the upload processor."""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()
            logger.info("Upload processor started")
    
    def stop(self):
        """Stop the upload processor."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=10)
        logger.info("Upload processor stopped")
    
    def submit_upload_job(self, job_config: UploadJobConfig) -> str:
        """Submit a new upload job for processing."""
        job_id = f"upload_{int(time.time())}_{job_config.dataset_uuid[:8]}"
        
        # Store job in database
        self._store_job_in_db(job_id, job_config)
        
        # Add to job manager
        self.job_manager.create_upload_job(job_id, job_config)
        
        logger.info(f"Upload job submitted: {job_id} ({job_config.source_type.value})")
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[UploadProgress]:
        """Get the status of an upload job."""
        return self.job_manager.get_progress(job_id)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel an upload job."""
        # Stop the process if running
        if job_id in self.active_jobs:
            process = self.active_jobs[job_id]
            try:
                process.terminate()
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            del self.active_jobs[job_id]
        
        # Update status
        success = self.job_manager.cancel_job(job_id)
        if success:
            self._update_job_in_db(job_id, {"status": UploadStatus.CANCELLED.value})
            logger.info(f"Upload job cancelled: {job_id}")
        
        return success
    
    def _worker_loop(self):
        """Main worker loop for processing upload jobs."""
        while self.running:
            try:
                # Get queued jobs from database
                queued_jobs = self._get_queued_jobs()
                
                for job_id in queued_jobs:
                    if not self.running:
                        break
                    
                    try:
                        self._process_upload_job(job_id)
                    except Exception as e:
                        logger.error(f"Error processing upload job {job_id}: {e}")
                        self._update_job_status(job_id, UploadStatus.FAILED, str(e))
                
                time.sleep(5)  # Check for new jobs every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in upload worker loop: {e}")
                time.sleep(10)
    
    def _process_upload_job(self, job_id: str):
        """Process a single upload job."""
        job_config = self.job_manager.get_job_config(job_id)
        if not job_config:
            logger.error(f"Job config not found for {job_id}")
            return
        
        logger.info(f"Processing upload job: {job_id} ({job_config.source_type.value})")
        
        # Update status to initializing
        self._update_job_status(job_id, UploadStatus.INITIALIZING)
        
        try:
            # Prepare destination directory
            dest_dir = Path(job_config.destination_path)
            dest_dir.mkdir(parents=True, exist_ok=True)
            
            # Process based on source type
            if job_config.source_type == UploadSourceType.LOCAL:
                self._process_local_upload(job_id, job_config)
            elif job_config.source_type == UploadSourceType.GOOGLE_DRIVE:
                self._process_google_drive_upload(job_id, job_config)
            elif job_config.source_type == UploadSourceType.S3:
                self._process_s3_upload(job_id, job_config)
            elif job_config.source_type == UploadSourceType.URL:
                self._process_url_upload(job_id, job_config)
            else:
                raise ValueError(f"Unsupported source type: {job_config.source_type}")
            
            # Mark as completed
            self._update_job_status(job_id, UploadStatus.COMPLETED)
            logger.info(f"Upload job completed: {job_id}")
            
        except Exception as e:
            logger.error(f"Upload job failed {job_id}: {e}")
            self._update_job_status(job_id, UploadStatus.FAILED, str(e))
    
    def _process_local_upload(self, job_id: str, job_config: UploadJobConfig):
        """Process local file upload using rclone or rsync."""
        source_path = job_config.source_path
        dest_path = job_config.destination_path
        
        # Check if source exists
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        # Get file size for progress tracking
        total_size = os.path.getsize(source_path)
        job_config.total_size_bytes = total_size
        
        # Try rclone first, fallback to rsync
        tool_config = get_tool_config(UploadSourceType.LOCAL)
        
        if self._is_tool_available("rclone"):
            self._upload_with_rclone(job_id, source_path, dest_path, job_config)
        elif self._is_tool_available("rsync"):
            self._upload_with_rsync(job_id, source_path, dest_path, job_config)
        else:
            # Fallback to simple copy
            self._upload_with_copy(job_id, source_path, dest_path, job_config)
    
    def _process_google_drive_upload(self, job_id: str, job_config: UploadJobConfig):
        """Process Google Drive upload using rclone."""
        if not self._is_tool_available("rclone"):
            raise RuntimeError("rclone is required for Google Drive uploads")
        
        file_id = job_config.source_config.get("file_id")
        service_account_file = job_config.source_config.get("service_account_file")
        
        if not file_id or not service_account_file:
            raise ValueError("Google Drive upload requires file_id and service_account_file")
        
        # Create rclone config for Google Drive
        rclone_config = self._create_google_drive_rclone_config(service_account_file)
        
        # Download from Google Drive
        self._download_from_google_drive(job_id, file_id, job_config.destination_path, rclone_config)
    
    def _process_s3_upload(self, job_id: str, job_config: UploadJobConfig):
        """Process S3 upload using AWS CLI or rclone."""
        bucket_name = job_config.source_config.get("bucket_name")
        object_key = job_config.source_config.get("object_key")
        access_key_id = job_config.source_config.get("access_key_id")
        secret_access_key = job_config.source_config.get("secret_access_key")
        
        if not all([bucket_name, object_key, access_key_id, secret_access_key]):
            raise ValueError("S3 upload requires bucket_name, object_key, access_key_id, and secret_access_key")
        
        # Try AWS CLI first, fallback to rclone
        if self._is_tool_available("aws"):
            self._download_from_s3_aws_cli(job_id, bucket_name, object_key, job_config.destination_path)
        elif self._is_tool_available("rclone"):
            self._download_from_s3_rclone(job_id, bucket_name, object_key, job_config.destination_path)
        else:
            raise RuntimeError("AWS CLI or rclone is required for S3 uploads")
    
    def _process_url_upload(self, job_id: str, job_config: UploadJobConfig):
        """Process URL-based upload using wget or curl."""
        url = job_config.source_config.get("url")
        if not url:
            raise ValueError("URL upload requires url in source_config")
        
        # Try wget first, fallback to curl
        if self._is_tool_available("wget"):
            self._download_with_wget(job_id, url, job_config.destination_path)
        elif self._is_tool_available("curl"):
            self._download_with_curl(job_id, url, job_config.destination_path)
        else:
            raise RuntimeError("wget or curl is required for URL uploads")
    
    def _upload_with_rclone(self, job_id: str, source_path: str, dest_path: str, job_config: UploadJobConfig):
        """Upload using rclone with progress tracking."""
        cmd = [
            "rclone", "copy",
            source_path, dest_path,
            "--progress",
            "--stats", "5s",
            "--log-level", "INFO",
            "--log-file", f"/tmp/rclone_{job_id}.log"
        ]
        
        self._run_command_with_progress(job_id, cmd, job_config)
    
    def _upload_with_rsync(self, job_id: str, source_path: str, dest_path: str, job_config: UploadJobConfig):
        """Upload using rsync with progress tracking."""
        cmd = [
            "rsync", "-avz", "--progress",
            source_path, dest_path
        ]
        
        self._run_command_with_progress(job_id, cmd, job_config)
    
    def _upload_with_copy(self, job_id: str, source_path: str, dest_path: str, job_config: UploadJobConfig):
        """Simple file copy fallback."""
        self._update_job_status(job_id, UploadStatus.UPLOADING)
        
        try:
            if os.path.isfile(source_path):
                shutil.copy2(source_path, dest_path)
            else:
                shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
            
            self._update_job_progress(job_id, 100.0, job_config.total_size_bytes, job_config.total_size_bytes)
            
        except Exception as e:
            raise RuntimeError(f"Copy failed: {e}")
    
    def _download_from_google_drive(self, job_id: str, file_id: str, dest_path: str, rclone_config: str):
        """Download from Google Drive using rclone."""
        # Create temporary rclone config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write(rclone_config)
            config_file = f.name
        
        try:
            cmd = [
                "rclone", "copy",
                f"gdrive:{file_id}", dest_path,
                "--config", config_file,
                "--progress",
                "--stats", "5s",
                "--log-level", "INFO",
                "--log-file", f"/tmp/rclone_{job_id}.log"
            ]
            
            # Get job config for progress tracking
            job_config = self.job_manager.get_job_config(job_id)
            self._run_command_with_progress(job_id, cmd, job_config)
            
        finally:
            os.unlink(config_file)
    
    def _download_from_s3_aws_cli(self, job_id: str, bucket_name: str, object_key: str, dest_path: str):
        """Download from S3 using AWS CLI."""
        cmd = [
            "aws", "s3", "cp",
            f"s3://{bucket_name}/{object_key}", dest_path,
            "--cli-read-timeout", "0",
            "--cli-connect-timeout", "60"
        ]
        
        # Get job config for progress tracking
        job_config = self.job_manager.get_job_config(job_id)
        self._run_command_with_progress(job_id, cmd, job_config)
    
    def _download_with_wget(self, job_id: str, url: str, dest_path: str):
        """Download using wget."""
        filename = os.path.basename(url) or "downloaded_file"
        dest_file = os.path.join(dest_path, filename)
        
        cmd = [
            "wget", "-O", dest_file,
            "--progress=bar:force",
            "--timeout=60",
            "--tries=3",
            url
        ]
        
        # Get job config for progress tracking
        job_config = self.job_manager.get_job_config(job_id)
        self._run_command_with_progress(job_id, cmd, job_config)
    
    def _download_with_curl(self, job_id: str, url: str, dest_path: str):
        """Download using curl."""
        filename = os.path.basename(url) or "downloaded_file"
        dest_file = os.path.join(dest_path, filename)
        
        cmd = [
            "curl", "-L", "-o", dest_file,
            "--progress-bar",
            "--connect-timeout", "60",
            "--max-time", "3600",
            url
        ]
        
        # Get job config for progress tracking
        job_config = self.job_manager.get_job_config(job_id)
        self._run_command_with_progress(job_id, cmd, job_config)
    
    def _run_command_with_progress(self, job_id: str, cmd: List[str], job_config: UploadJobConfig):
        """Run a command with progress tracking."""
        self._update_job_status(job_id, UploadStatus.UPLOADING)
        
        logger.info(f"Running command: {' '.join(cmd)}")
        
        # Start the process
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        self.active_jobs[job_id] = process
        
        try:
            # Monitor progress
            while process.poll() is None:
                if not self.running:
                    process.terminate()
                    break
                
                # Read output and parse progress
                output = process.stdout.readline()
                if output:
                    self._parse_progress_output(job_id, output.strip(), job_config)
                
                time.sleep(0.1)
            
            # Wait for completion
            return_code = process.wait()
            
            if return_code != 0:
                raise RuntimeError(f"Command failed with return code {return_code}")
            
        finally:
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
    
    def _parse_progress_output(self, job_id: str, output: str, job_config: UploadJobConfig):
        """Parse progress output from various tools."""
        # This is a simplified progress parser
        # In practice, you'd want more sophisticated parsing for each tool
        
        if "rclone" in ' '.join(output.split()[:2]):
            self._parse_rclone_progress(job_id, output, job_config)
        elif "rsync" in output:
            self._parse_rsync_progress(job_id, output, job_config)
        elif "wget" in output:
            self._parse_wget_progress(job_id, output, job_config)
        elif "curl" in output:
            self._parse_curl_progress(job_id, output, job_config)
    
    def _parse_rclone_progress(self, job_id: str, output: str, job_config: UploadJobConfig):
        """Parse rclone progress output."""
        # Simplified rclone progress parsing
        # Real implementation would parse the actual rclone output format
        if "Transferred:" in output:
            # Extract progress information
            # This is a placeholder - real implementation needed
            pass
    
    def _parse_rsync_progress(self, job_id: str, output: str, job_config: UploadJobConfig):
        """Parse rsync progress output."""
        # Simplified rsync progress parsing
        if "%" in output:
            # Extract percentage
            # This is a placeholder - real implementation needed
            pass
    
    def _parse_wget_progress(self, job_id: str, output: str, job_config: UploadJobConfig):
        """Parse wget progress output."""
        # Simplified wget progress parsing
        if "%" in output:
            # Extract percentage
            # This is a placeholder - real implementation needed
            pass
    
    def _parse_curl_progress(self, job_id: str, output: str, job_config: UploadJobConfig):
        """Parse curl progress output."""
        # Simplified curl progress parsing
        if "%" in output:
            # Extract percentage
            # This is a placeholder - real implementation needed
            pass
    
    def _update_job_status(self, job_id: str, status: UploadStatus, error_message: str = ""):
        """Update job status in memory and database."""
        progress = self.job_manager.get_progress(job_id)
        if progress:
            progress.status = status
            progress.error_message = error_message
            progress.last_updated = datetime.utcnow()
            
            if status == UploadStatus.COMPLETED:
                progress.progress_percentage = 100.0
        
        # Update in database
        self._update_job_in_db(job_id, {
            "status": status.value,
            "error_message": error_message,
            "updated_at": datetime.utcnow()
        })
    
    def _update_job_progress(self, job_id: str, percentage: float, uploaded_bytes: int, total_bytes: int):
        """Update job progress."""
        progress = self.job_manager.get_progress(job_id)
        if progress:
            progress.progress_percentage = percentage
            progress.bytes_uploaded = uploaded_bytes
            progress.bytes_total = total_bytes
            progress.last_updated = datetime.utcnow()
        
        # Update in database
        self._update_job_in_db(job_id, {
            "progress_percentage": percentage,
            "uploaded_bytes": uploaded_bytes,
            "total_bytes": total_bytes,
            "updated_at": datetime.utcnow()
        })
    
    def _is_tool_available(self, tool_name: str) -> bool:
        """Check if a tool is available in the system."""
        try:
            subprocess.run([tool_name, "--version"], 
                         capture_output=True, check=True, timeout=5)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def _create_google_drive_rclone_config(self, service_account_file: str) -> str:
        """Create rclone configuration for Google Drive."""
        return f"""
[gdrive]
type = drive
client_id = 
client_secret = 
service_account_file = {service_account_file}
scope = drive
"""
    
    def _store_job_in_db(self, job_id: str, job_config: UploadJobConfig):
        """Store upload job in database."""
        with mongo_collection_by_type_context('jobs') as collection:
            job_doc = {
                "job_id": job_id,
                "job_type": "upload",
                "source_type": job_config.source_type.value,
                "source_path": job_config.source_path,
                "destination_path": job_config.destination_path,
                "dataset_uuid": job_config.dataset_uuid,
                "user_id": job_config.user_id,
                "status": UploadStatus.QUEUED.value,
                "created_at": job_config.created_at,
                "config": job_config.__dict__
            }
            collection.insert_one(job_doc)
    
    def _get_queued_jobs(self) -> List[str]:
        """Get queued upload jobs from database."""
        with mongo_collection_by_type_context('jobs') as collection:
            jobs = collection.find({
                "job_type": "upload",
                "status": UploadStatus.QUEUED.value
            }, {"job_id": 1})
            return [job["job_id"] for job in jobs]
    
    def _update_job_in_db(self, job_id: str, update_data: Dict[str, Any]):
        """Update job in database."""
        with mongo_collection_by_type_context('jobs') as collection:
            collection.update_one(
                {"job_id": job_id},
                {"$set": update_data}
            )


# Global upload processor instance
_upload_processor: Optional[SC_UploadProcessor] = None


def get_upload_processor() -> SC_UploadProcessor:
    """Get global upload processor instance."""
    global _upload_processor
    if _upload_processor is None:
        _upload_processor = SC_UploadProcessor()
    return _upload_processor


def start_upload_processor():
    """Start the global upload processor."""
    processor = get_upload_processor()
    processor.start()


def stop_upload_processor():
    """Stop the global upload processor."""
    global _upload_processor
    if _upload_processor:
        _upload_processor.stop()
        _upload_processor = None


if __name__ == '__main__':
    # Example usage
    print("SC_UploadProcessor - Upload Job Processing Example")
    print("=" * 60)
    
    try:
        # Create upload processor
        processor = get_upload_processor()
        processor.start()
        
        # Create example upload jobs
        from SC_UploadJobTypes import create_local_upload_job, create_url_upload_job
        
        local_job = create_local_upload_job(
            file_path="/tmp/test_file.zip",
            dataset_uuid="test_dataset_123",
            user_id="test_user"
        )
        
        url_job = create_url_upload_job(
            url="https://example.com/test_data.zip",
            dataset_uuid="test_dataset_456",
            user_id="test_user"
        )
        
        # Submit jobs
        job_id_1 = processor.submit_upload_job(local_job)
        job_id_2 = processor.submit_upload_job(url_job)
        
        print(f"Submitted jobs: {job_id_1}, {job_id_2}")
        
        # Monitor progress
        for i in range(10):
            status_1 = processor.get_job_status(job_id_1)
            status_2 = processor.get_job_status(job_id_2)
            
            print(f"Job 1: {status_1.status.value if status_1 else 'Unknown'}")
            print(f"Job 2: {status_2.status.value if status_2 else 'Unknown'}")
            
            time.sleep(2)
        
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        stop_upload_processor()
        print("Upload processor stopped")
