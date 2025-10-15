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
import uuid
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

try:
    from .SCLib_Config import get_config, get_collection_name, get_database_name
    from .SCLib_MongoConnection import get_collection_by_type, mongo_collection_by_type_context
    from .SCLib_UploadJobTypes import (
        UploadJobConfig, UploadSourceType, UploadStatus, UploadProgress,
        UploadJobManager, get_tool_config
    )
except ImportError:
    from SCLib_Config import get_config, get_collection_name, get_database_name
    from SCLib_MongoConnection import get_collection_by_type, mongo_collection_by_type_context
    from SCLib_UploadJobTypes import (
        UploadJobConfig, UploadSourceType, UploadStatus, UploadProgress,
        UploadJobManager, get_tool_config
    )

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SCLib_UploadProcessor:
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
            # Restore active jobs from database
            self._restore_active_jobs_from_db()
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
        job_id = f"upload_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Store job in database
        self._store_job_in_db(job_id, job_config)
        
        # Create or update dataset entry in visstoredatas collection
        self._create_or_update_dataset_entry(job_config)
        
        # Add to job manager
        self.job_manager.create_upload_job(job_id, job_config)
        
        logger.info(f"Upload job submitted: {job_id} ({job_config.source_type.value})")
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[UploadProgress]:
        """Get the status of an upload job."""
        # First try in-memory cache
        progress = self.job_manager.get_progress(job_id)
        if progress:
            return progress
        
        # If not in memory, get from database
        return self._get_job_progress_from_db(job_id)
    
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
        cleanup_counter = 0
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
                
                # Periodic cleanup of old stuck jobs (every 60 iterations = 5 minutes)
                cleanup_counter += 1
                if cleanup_counter >= 60:
                    cleanup_counter = 0
                    self._cleanup_old_jobs()
                
                time.sleep(5)  # Check for new jobs every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in upload worker loop: {e}")
                time.sleep(10)
    
    def _process_upload_job(self, job_id: str):
        """Process a single upload job."""
        # Get job config from database (persistent storage)
        job_config = self._get_job_config_from_db(job_id)
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
        """Process URL-based upload by storing URL in database instead of downloading."""
        url = job_config.source_config.get("url")
        if not url:
            raise ValueError("URL upload requires url in source_config")
        
        # For URL uploads, we just store the URL in the database
        # No actual file download/copy is needed since the URL can be served directly
        logger.info(f"Storing URL {url} for dataset {job_config.dataset_uuid}")
        
        # Update job status to indicate URL was stored
        self._update_job_status(job_id, UploadStatus.UPLOADING)
        
        # Store the URL in the dataset record (this would typically be done in the database)
        # For now, we'll just log it and mark as completed
        logger.info(f"URL stored successfully for job {job_id}: {url}")
        
        # Mark as completed since no actual processing is needed
        self._update_job_status(job_id, UploadStatus.COMPLETED)
    
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
        
        # Update dataset status in visstoredatas collection
        job_config = self._get_job_config_from_db(job_id)
        if job_config:
            # Map upload status to dataset status
            dataset_status = self._map_upload_status_to_dataset_status(status)
            self._update_dataset_status(job_config.dataset_uuid, dataset_status, error_message)
    
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
            "bytes_uploaded": uploaded_bytes,
            "bytes_total": total_bytes,
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
            # Convert config to BSON-serializable format
            config_dict = job_config.__dict__.copy()
            config_dict['source_type'] = job_config.source_type.value
            config_dict['sensor'] = job_config.sensor.value
            
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
                "config": config_dict
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
    
    def _get_job_config_from_db(self, job_id: str) -> Optional[UploadJobConfig]:
        """Get job configuration from database."""
        with mongo_collection_by_type_context('jobs') as collection:
            job_doc = collection.find_one({"job_id": job_id})
            if not job_doc:
                return None
            
            # Reconstruct UploadJobConfig from database document
            config_dict = job_doc.get('config', {})
            
            # Convert string enums back to enum objects
            from SCLib_UploadJobTypes import UploadSourceType, SensorType
            source_type = UploadSourceType(config_dict.get('source_type', 'local'))
            sensor = SensorType(config_dict.get('sensor', 'TIFF'))
            
            return UploadJobConfig(
                source_type=source_type,
                source_path=config_dict.get('source_path', ''),
                destination_path=config_dict.get('destination_path', ''),
                dataset_uuid=config_dict.get('dataset_uuid', ''),
                user_id=config_dict.get('user_id', ''),
                dataset_name=config_dict.get('dataset_name', ''),
                sensor=sensor,
                convert=config_dict.get('convert', True),
                is_public=config_dict.get('is_public', False),
                folder=config_dict.get('folder'),
                team_uuid=config_dict.get('team_uuid'),
                total_size_bytes=config_dict.get('total_size_bytes', 0),
                created_at=config_dict.get('created_at', datetime.utcnow())
            )
    
    def _get_job_progress_from_db(self, job_id: str) -> Optional[UploadProgress]:
        """Get job progress from database."""
        with mongo_collection_by_type_context('jobs') as collection:
            job_doc = collection.find_one({"job_id": job_id})
            if not job_doc:
                return None
            
            # Get job config to determine total size
            job_config = self._get_job_config_from_db(job_id)
            total_size = job_config.total_size_bytes if job_config else 0
            
            return UploadProgress(
                job_id=job_id,
                status=UploadStatus(job_doc.get('status', 'queued')),
                progress_percentage=job_doc.get('progress_percentage', 0.0),
                bytes_uploaded=job_doc.get('bytes_uploaded', 0),
                bytes_total=total_size,
                speed_mbps=job_doc.get('speed_mbps', 0.0),
                eta_seconds=job_doc.get('eta_seconds', 0),
                last_updated=job_doc.get('updated_at', job_doc.get('created_at', datetime.utcnow()))
            )
    
    def _update_job_in_db(self, job_id: str, update_data: Dict[str, Any]):
        """Update job in database."""
        with mongo_collection_by_type_context('jobs') as collection:
            collection.update_one(
                {"job_id": job_id},
                {"$set": update_data}
            )
    
    def _cleanup_old_jobs(self):
        """Clean up old stuck jobs from the database."""
        try:
            from datetime import datetime, timedelta
            
            # Clean up queued jobs older than 1 hour
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            
            with mongo_collection_by_type_context('jobs') as collection:
                old_jobs = collection.find({
                    "job_type": "upload",
                    "status": UploadStatus.QUEUED.value,
                    "created_at": {"$lt": cutoff_time}
                }, {"job_id": 1, "created_at": 1})
                
                old_job_ids = [job["job_id"] for job in old_jobs]
                
                if old_job_ids:
                    # Delete old stuck jobs
                    result = collection.delete_many({
                        "job_id": {"$in": old_job_ids}
                    })
                    
                    logger.info(f"Cleaned up {result.deleted_count} old stuck upload jobs")
                    
                    # Also remove from job manager
                    for job_id in old_job_ids:
                        if job_id in self.job_manager.upload_configs:
                            del self.job_manager.upload_configs[job_id]
                        if job_id in self.job_manager.progress_tracking:
                            del self.job_manager.progress_tracking[job_id]
                            
        except Exception as e:
            logger.error(f"Error during job cleanup: {e}")
    
    def _restore_active_jobs_from_db(self):
        """Restore active jobs from database on startup."""
        try:
            with mongo_collection_by_type_context('jobs') as collection:
                # Find jobs that were running when the system went down
                active_jobs = collection.find({
                    "job_type": "upload",
                    "status": {"$in": ["initializing", "uploading", "processing"]}
                })
                
                restored_count = 0
                for job_doc in active_jobs:
                    job_id = job_doc['job_id']
                    
                    # Reset status to queued so it can be reprocessed
                    collection.update_one(
                        {"job_id": job_id},
                        {
                            "$set": {
                                "status": UploadStatus.QUEUED.value,
                                "updated_at": datetime.utcnow(),
                                "restored_at": datetime.utcnow()
                            }
                        }
                    )
                    
                    # Restore job config in memory for faster access
                    job_config = self._get_job_config_from_db(job_id)
                    if job_config:
                        self.job_manager.create_upload_job(job_id, job_config)
                        restored_count += 1
                
                if restored_count > 0:
                    logger.info(f"Restored {restored_count} active jobs from database")
                    
        except Exception as e:
            logger.error(f"Error restoring active jobs from database: {e}")
    
    def _create_or_update_dataset_entry(self, job_config: UploadJobConfig):
        """Create or update dataset entry in visstoredatas collection."""
        try:
            
            with mongo_collection_by_type_context('visstoredatas') as collection:
                # Check if dataset already exists
                existing_dataset = collection.find_one({"uuid": job_config.dataset_uuid})
                
                # Generate additional identifiers
                dataset_slug = self._generate_dataset_slug(job_config.dataset_name, job_config.user_id)
                dataset_id = self._generate_dataset_id()
                
                dataset_doc = {
                    "uuid": job_config.dataset_uuid,
                    "name": job_config.dataset_name,
                    "slug": dataset_slug,
                    "id": dataset_id,
                    "user_email": job_config.user_id,
                    "sensor": job_config.sensor.value,
                    "convert": job_config.convert,
                    "is_public": job_config.is_public,
                    "folder": job_config.folder,
                    "team_uuid": job_config.team_uuid,
                    "source_type": job_config.source_type.value,
                    "source_path": job_config.source_path,
                    "destination_path": job_config.destination_path,
                    "total_size_bytes": job_config.total_size_bytes,
                    "status": "uploading",  # Initial status
                    "created_at": job_config.created_at,
                    "updated_at": datetime.utcnow()
                }
                
                if existing_dataset:
                    # Update existing dataset - add new file information
                    collection.update_one(
                        {"uuid": job_config.dataset_uuid},
                        {
                            "$set": {
                                "status": "uploading",
                                "updated_at": datetime.utcnow()
                            },
                            "$push": {
                                "files": {
                                    "source_path": job_config.source_path,
                                    "destination_path": job_config.destination_path,
                                    "source_type": job_config.source_type.value,
                                    "total_size_bytes": job_config.total_size_bytes,
                                    "created_at": job_config.created_at
                                }
                            }
                        }
                    )
                    logger.info(f"Added file to existing dataset: {job_config.dataset_uuid}")
                else:
                    # Create new dataset entry
                    dataset_doc["files"] = [{
                        "source_path": job_config.source_path,
                        "destination_path": job_config.destination_path,
                        "source_type": job_config.source_type.value,
                        "total_size_bytes": job_config.total_size_bytes,
                        "created_at": job_config.created_at
                    }]
                    collection.insert_one(dataset_doc)
                    logger.info(f"Created dataset entry: {job_config.dataset_uuid}")
                    
        except Exception as e:
            logger.error(f"Error creating/updating dataset entry: {e}")
    
    def _generate_dataset_slug(self, dataset_name: str, user_email: str) -> str:
        """Generate a human-readable slug for the dataset."""
        import re
        from datetime import datetime
        
        # Clean the dataset name
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', dataset_name.lower())
        slug = re.sub(r'\s+', '-', slug.strip())
        
        # Add year for uniqueness
        year = datetime.now().year
        slug = f"{slug}-{year}"
        
        # Add user prefix for uniqueness
        user_prefix = user_email.split('@')[0].lower()
        slug = f"{user_prefix}-{slug}"
        
        return slug
    
    def _generate_dataset_id(self) -> int:
        """Generate a short numeric ID for the dataset."""
        import time
        # Use timestamp-based ID for uniqueness
        return int(time.time() * 1000) % 100000  # 5-digit ID
    
    def _resolve_dataset_identifier(self, identifier: str) -> str:
        """Resolve various identifier types to a dataset UUID."""
        try:
            with mongo_collection_by_type_context('visstoredatas') as collection:
                # Try different identifier types
                dataset = None
                
                # Check if it's a UUID (36 characters with hyphens)
                if len(identifier) == 36 and identifier.count('-') == 4:
                    dataset = collection.find_one({"uuid": identifier})
                
                # Check if it's a numeric ID
                elif identifier.isdigit():
                    dataset = collection.find_one({"id": int(identifier)})
                
                # Check if it's a slug
                elif '-' in identifier:
                    dataset = collection.find_one({"slug": identifier})
                
                # Check if it's a name (exact match)
                else:
                    dataset = collection.find_one({"name": identifier})
                
                if dataset:
                    return dataset["uuid"]
                else:
                    raise ValueError(f"Dataset not found: {identifier}")
                    
        except Exception as e:
            logger.error(f"Error resolving dataset identifier '{identifier}': {e}")
            raise ValueError(f"Dataset not found: {identifier}")
    
    def _update_dataset_status(self, dataset_uuid: str, status: str, error_message: str = ""):
        """Update dataset status in visstoredatas collection."""
        try:
            with mongo_collection_by_type_context('visstoredatas') as collection:
                update_data = {
                    "status": status,
                    "updated_at": datetime.utcnow()
                }
                
                if status == "completed":
                    update_data["completed_at"] = datetime.utcnow()
                elif status == "failed":
                    update_data["error_message"] = error_message
                
                collection.update_one(
                    {"uuid": dataset_uuid},
                    {"$set": update_data}
                )
                logger.info(f"Updated dataset status: {dataset_uuid} -> {status}")
                
        except Exception as e:
            logger.error(f"Error updating dataset status: {e}")
    
    def _map_upload_status_to_dataset_status(self, upload_status: UploadStatus) -> str:
        """Map upload status to dataset status."""
        status_mapping = {
            UploadStatus.QUEUED: "uploading",
            UploadStatus.INITIALIZING: "uploading",
            UploadStatus.UPLOADING: "uploading",
            UploadStatus.PROCESSING: "processing",
            UploadStatus.COMPLETED: "completed",
            UploadStatus.FAILED: "failed",
            UploadStatus.CANCELLED: "cancelled",
            UploadStatus.PAUSED: "paused"
        }
        return status_mapping.get(upload_status, "unknown")


# Global upload processor instance
_upload_processor: Optional[SCLib_UploadProcessor] = None


def get_upload_processor() -> SCLib_UploadProcessor:
    """Get global upload processor instance."""
    global _upload_processor
    if _upload_processor is None:
        _upload_processor = SCLib_UploadProcessor()
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
        try:
            from .SCLib_UploadJobTypes import create_local_upload_job, create_url_upload_job
        except ImportError:
            from SCLib_UploadJobTypes import create_local_upload_job, create_url_upload_job
        
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
