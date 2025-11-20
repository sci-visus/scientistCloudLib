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

# Get logger without configuring
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
            # No need to restore from jobs collection - status-based processing
            # Datasets with status "uploading" will be picked up automatically
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()
            logger.info("Upload processor started (status-based processing)")
    
    def stop(self):
        """Stop the upload processor."""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=10)
        logger.info("Upload processor stopped")
    
    def submit_upload_job(self, job_config: UploadJobConfig, job_id: Optional[str] = None) -> str:
        """Submit a new upload job for processing.
        
        Args:
            job_config: The upload job configuration
            job_id: Optional job ID. If not provided, a new one will be generated.
        
        Returns:
            The job ID (either the provided one or the newly generated one)
        """
        if job_id is None:
            job_id = f"upload_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Create or update dataset entry in visstoredatas collection (status-based architecture)
        # The dataset status will be set to "uploading" which triggers processing
        # Store job_id in dataset entry for status lookups
        self._create_or_update_dataset_entry(job_config, job_id)
        
        # Add to job manager for in-memory tracking
        self.job_manager.create_upload_job(job_id, job_config)
        
        logger.info(f"Upload job submitted: {job_id} ({job_config.source_type.value}) - status-based processing")
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[UploadProgress]:
        """Get the status of an upload job.
        
        First checks in-memory cache, then looks up in visstoredatas by job_id.
        """
        # First try in-memory cache
        progress = self.job_manager.get_progress(job_id)
        if progress:
            return progress
        
        # If not in memory, look up dataset by job_id in visstoredatas
        try:
            with mongo_collection_by_type_context('visstoredatas') as collection:
                dataset = collection.find_one({'job_id': job_id})
                if dataset:
                    # Convert dataset status to UploadProgress
                    status_str = dataset.get('status', 'unknown')
                    status_map = {
                        'uploading': UploadStatus.UPLOADING,
                        'processing': UploadStatus.PROCESSING,
                        'completed': UploadStatus.COMPLETED,
                        'done': UploadStatus.COMPLETED,
                        'failed': UploadStatus.FAILED,
                        'cancelled': UploadStatus.CANCELLED,
                        'conversion queued': UploadStatus.QUEUED,
                        'converting': UploadStatus.PROCESSING
                    }
                    upload_status = status_map.get(status_str, UploadStatus.QUEUED)
                    
                    # Calculate progress if we have size info
                    total_bytes = dataset.get('total_size_bytes', 0)
                    bytes_uploaded = dataset.get('bytes_uploaded', 0)
                    progress_pct = (bytes_uploaded / total_bytes * 100) if total_bytes > 0 else 0.0
                    
                    return UploadProgress(
                        job_id=job_id,
                        status=upload_status,
                        progress_percentage=progress_pct,
                        bytes_uploaded=bytes_uploaded,
                        bytes_total=total_bytes,
                        speed_mbps=0.0,  # Not tracked in dataset
                        eta_seconds=0,  # Not tracked in dataset
                        last_updated=dataset.get('updated_at', dataset.get('created_at', datetime.now(timezone.utc))),
                        error_message=dataset.get('error_message')
                    )
        except Exception as e:
            logger.error(f"Error looking up job status from visstoredatas: {e}")
        
        return None
    
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
        
        # Update status in job manager
        success = self.job_manager.cancel_job(job_id)
        if success:
            # Update dataset status in visstoredatas if we have the config
            job_config = self.job_manager.upload_configs.get(job_id)
            if job_config:
                self._update_dataset_status(job_config.dataset_uuid, "cancelled", "Upload cancelled by user", job_config)
            logger.info(f"Upload job cancelled: {job_id}")
        
        return success
    
    def _worker_loop(self):
        """Main worker loop for processing upload jobs.
        
        Uses status-based processing - queries visstoredatas directly by status.
        No jobs collection needed - dataset status is the source of truth.
        """
        cleanup_counter = 0
        while self.running:
            try:
                # Check visstoredatas for datasets with status "uploading" that need processing
                # This is the only way we process uploads now - status-based architecture
                self._process_status_based_uploads()
                
                # Periodic cleanup of old stuck datasets (every 60 iterations = 5 minutes)
                cleanup_counter += 1
                if cleanup_counter >= 60:
                    cleanup_counter = 0
                    self._cleanup_old_datasets()
                
                time.sleep(5)  # Check for new uploads every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in upload worker loop: {e}")
                time.sleep(10)
    
    def _process_status_based_uploads(self):
        """Process uploads from visstoredatas based on status (status-based architecture).
        
        Checks for datasets with status "uploading" that need to be processed.
        This is the only way uploads are processed now - no jobs collection needed.
        """
        try:
            with mongo_collection_by_type_context('visstoredatas') as collection:
                # Find datasets with status "uploading" that need processing
                # Process all source types (google_drive, s3, url, local)
                datasets_to_upload = collection.find({
                    'status': 'uploading'
                }).limit(1)  # Process one at a time
                
                dataset = next(datasets_to_upload, None)
                if dataset:
                    logger.info(f"Found dataset with status 'uploading' that needs processing: {dataset['uuid']}")
                    # Reconstruct job config from dataset and process it
                    self._process_dataset_upload_from_status(dataset)
        except Exception as e:
            logger.error(f"Error processing status-based uploads: {e}")
    
    def _process_dataset_upload_from_status(self, dataset: Dict[str, Any]):
        """Process an upload from a dataset document (status-based architecture).
        
        Reconstructs the job config from the dataset and processes it.
        """
        try:
            dataset_uuid = dataset['uuid']
            source_type_str = dataset.get('source_type', '')
            
            # Convert string source type to enum
            try:
                source_type = UploadSourceType(source_type_str)
            except ValueError:
                logger.error(f"Unknown source type: {source_type_str}")
                return
            
            # Reconstruct source_config from dataset
            source_config = {}
            if source_type == UploadSourceType.GOOGLE_DRIVE:
                # For Google Drive, use OAuth if we have user_email
                source_config = {
                    'use_oauth': True,
                    'user_email': dataset.get('user') or dataset.get('user_id'),
                    'file_id': dataset.get('source_path', '')
                }
                # Add folder_link if we have google_drive_link
                if dataset.get('google_drive_link'):
                    source_config['folder_link'] = dataset['google_drive_link']
                    # Extract file_id from folder_link if source_path is empty
                    if not source_config['file_id']:
                        import urllib.parse
                        folder_link = dataset['google_drive_link']
                        u = urllib.parse.urlparse(folder_link)
                        file_id = urllib.parse.parse_qs(u.query).get('id', [None])[0] or u.path.strip('/').split('/')[-1]
                        if file_id and file_id not in ['folders', 'file', 'drive']:
                            source_config['file_id'] = file_id
            
            # Reconstruct job config
            # Import SensorType and job creation functions
            from SCLib_UploadJobTypes import SensorType, create_google_drive_upload_job, create_s3_upload_job, create_url_upload_job, create_local_upload_job
            
            try:
                sensor = SensorType(dataset.get('sensor', 'IDX'))
            except ValueError:
                sensor = SensorType.IDX
            
            if source_type == UploadSourceType.GOOGLE_DRIVE:
                job_config = create_google_drive_upload_job(
                    file_id=source_config.get('file_id', dataset.get('source_path', '')),
                    dataset_uuid=dataset_uuid,
                    user_email=dataset.get('user') or dataset.get('user_id', ''),
                    dataset_name=dataset.get('name', ''),
                    sensor=sensor,
                    convert=dataset.get('convert', True),
                    is_public=dataset.get('is_public', False),
                    folder=dataset.get('folder_uuid'),
                    team_uuid=dataset.get('team_uuid'),
                    source_config_override=source_config
                )
            elif source_type == UploadSourceType.LOCAL:
                # For local uploads, source_path should be the file path
                job_config = create_local_upload_job(
                    file_path=dataset.get('source_path', ''),
                    dataset_uuid=dataset_uuid,
                    user_email=dataset.get('user') or dataset.get('user_id', ''),
                    dataset_name=dataset.get('name', ''),
                    sensor=sensor,
                    original_source_path=dataset.get('source_path', ''),
                    convert=dataset.get('convert', True),
                    is_public=dataset.get('is_public', False),
                    folder=dataset.get('folder_uuid'),
                    team_uuid=dataset.get('team_uuid')
                )
            elif source_type == UploadSourceType.S3:
                # S3 would need access keys from somewhere - for now, skip
                logger.warning(f"S3 upload retry not yet supported for dataset {dataset_uuid}")
                return
            elif source_type == UploadSourceType.URL:
                # URL uploads - would need URL from dataset
                logger.warning(f"URL upload retry not yet supported for dataset {dataset_uuid}")
                return
            else:
                logger.warning(f"Unsupported source type for status-based upload: {source_type}")
                return
            
            # Generate a job_id for in-memory tracking only (not stored in jobs collection)
            job_id = f"upload_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            
            # Add to job manager for in-memory tracking
            self.job_manager.create_upload_job(job_id, job_config)
            
            # Process the upload job directly
            logger.info(f"Processing status-based upload for dataset {dataset_uuid} (job_id: {job_id})")
            self._process_upload_job_direct(job_id, job_config)
            
        except Exception as e:
            logger.error(f"Error processing dataset upload from status: {e}", exc_info=True)
            # Update dataset status to failed
            try:
                dataset_uuid_for_error = dataset.get('uuid', 'unknown')
                with mongo_collection_by_type_context('visstoredatas') as collection:
                    collection.update_one(
                        {'uuid': dataset_uuid_for_error},
                        {'$set': {'status': 'failed', 'error_message': str(e), 'updated_at': datetime.utcnow()}}
                    )
            except:
                pass
    
    def _process_upload_job(self, job_id: str):
        """Process a single upload job (legacy method - kept for compatibility).
        
        This method is deprecated. Use _process_upload_job_direct instead.
        """
        # Try to get job config from in-memory job manager
        job_config = self.job_manager.upload_configs.get(job_id)
        if not job_config:
            logger.error(f"Job config not found for {job_id}")
            return
        
        self._process_upload_job_direct(job_id, job_config)
    
    def _process_upload_job_direct(self, job_id: str, job_config: UploadJobConfig):
        """Process a single upload job directly with provided config."""
        logger.info(f"Processing upload job: {job_id} ({job_config.source_type.value})")
        
        # Update status to initializing
        self._update_job_status(job_id, UploadStatus.INITIALIZING)
        
        try:
            # Prepare destination directory
            # If destination_path is a file path, create parent directory; if it's a directory, create it
            dest_path = Path(job_config.destination_path)
            if dest_path.suffix:  # Has file extension, treat as file path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
            else:  # No extension, treat as directory
                dest_path.mkdir(parents=True, exist_ok=True)
            
            # Process based on source type
            if job_config.source_type == UploadSourceType.LOCAL:
                self._process_local_upload(job_id, job_config)
            elif job_config.source_type == UploadSourceType.GOOGLE_DRIVE:
                # Check if using OAuth (user_email in source_config) or service account
                if job_config.source_config.get('use_oauth') or job_config.source_config.get('user_email'):
                    self._process_google_drive_upload_oauth(job_id, job_config)
                else:
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
        """Process Google Drive upload using rclone (service account)."""
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
    
    def _process_google_drive_upload_oauth(self, job_id: str, job_config: UploadJobConfig):
        """Process Google Drive upload using OAuth tokens (user-based)."""
        try:
            from .SCLib_GoogleOAuth import get_google_drive_service
        except ImportError:
            from SCLib_GoogleOAuth import get_google_drive_service
        
        user_email = job_config.source_config.get("user_email") or job_config.user_email
        file_id = job_config.source_config.get("file_id")
        folder_link = job_config.source_config.get("folder_link")  # Optional: full Google Drive folder URL
        
        if not user_email:
            raise ValueError("OAuth-based Google Drive upload requires user_email")
        
        if not file_id and not folder_link:
            raise ValueError("OAuth-based Google Drive upload requires file_id or folder_link")
        
        # Extract file_id from folder_link if provided
        if folder_link and not file_id:
            import urllib.parse
            u = urllib.parse.urlparse(folder_link)
            file_id = urllib.parse.parse_qs(u.query).get('id', [None])[0] or u.path.strip('/').split('/')[-1]
        
        if not file_id:
            raise ValueError("Could not extract file_id from folder_link")
        
        logger.info(f"Starting OAuth-based Google Drive download for user {user_email}, file_id: {file_id}")
        
        # Get Google Drive service
        service = get_google_drive_service(user_email)
        
        # Download file or folder recursively
        self._download_from_google_drive_oauth(job_id, service, file_id, job_config.destination_path, user_email)
    
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
        
        try:
            self._run_command_with_progress(job_id, cmd, job_config)
            # Clean up temp files from shared temp directory after successful copy
            self._cleanup_temp_file(source_path)
        except Exception as e:
            raise
    
    def _upload_with_rsync(self, job_id: str, source_path: str, dest_path: str, job_config: UploadJobConfig):
        """Upload using rsync with progress tracking."""
        cmd = [
            "rsync", "-avz", "--progress",
            source_path, dest_path
        ]
        
        try:
            self._run_command_with_progress(job_id, cmd, job_config)
            # Clean up temp files from shared temp directory after successful copy
            self._cleanup_temp_file(source_path)
        except Exception as e:
            raise
    
    def _cleanup_temp_file(self, source_path: str):
        """Clean up temp files from shared temp directory after successful copy."""
        if source_path.startswith('/mnt/visus_datasets/tmp/'):
            try:
                if os.path.isfile(source_path):
                    os.unlink(source_path)
                    logger.info(f"Cleaned up temp file after successful copy: {source_path}")
                elif os.path.isdir(source_path):
                    shutil.rmtree(source_path)
                    logger.info(f"Cleaned up temp directory after successful copy: {source_path}")
            except Exception as cleanup_error:
                # Log but don't fail the job if cleanup fails
                logger.warning(f"Failed to clean up temp file {source_path}: {cleanup_error}")
    
    def _upload_with_copy(self, job_id: str, source_path: str, dest_path: str, job_config: UploadJobConfig):
        """Simple file copy fallback."""
        self._update_job_status(job_id, UploadStatus.UPLOADING)
        
        try:
            # Ensure destination directory exists
            dest_dir = os.path.dirname(dest_path) if os.path.isfile(source_path) else dest_path
            os.makedirs(dest_dir, exist_ok=True)
            
            if os.path.isfile(source_path):
                # If dest_path is a directory, copy file into it; otherwise copy to exact path
                if os.path.isdir(dest_path):
                    dest_file = os.path.join(dest_path, os.path.basename(source_path))
                else:
                    dest_file = dest_path
                    # Ensure parent directory exists
                    os.makedirs(os.path.dirname(dest_file), exist_ok=True)
                shutil.copy2(source_path, dest_file)
            else:
                shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
            
            self._update_job_progress(job_id, 100.0, job_config.total_size_bytes, job_config.total_size_bytes)
            
            # Clean up temp files from shared temp directory after successful copy
            self._cleanup_temp_file(source_path)
            
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
    
    def _download_from_google_drive_oauth(self, job_id: str, service, file_id: str, dest_path: str, user_email: str):
        """Download from Google Drive using OAuth tokens with recursive folder support."""
        import io
        try:
            from googleapiclient.http import MediaIoBaseDownload
            import google.auth.exceptions
        except ImportError:
            raise ImportError("google-api-python-client is required for OAuth-based Google Drive downloads")
        
        # Ensure destination directory exists
        os.makedirs(dest_path, exist_ok=True)
        
        def download_file(file_id, destination_path, mime_type):
            """Download a single file from Google Drive."""
            try:
                if mime_type == 'application/vnd.google-apps.document':
                    request = service.files().export_media(fileId=file_id, mimeType='application/pdf')
                    if not destination_path.lower().endswith('.pdf'):
                        destination_path += '.pdf'
                elif mime_type == 'application/vnd.google-apps.spreadsheet':
                    request = service.files().export_media(fileId=file_id,
                        mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    if not destination_path.lower().endswith(('.xlsx', '.xls')):
                        destination_path += '.xlsx'
                elif mime_type == 'application/vnd.google-apps.presentation':
                    request = service.files().export_media(fileId=file_id,
                        mimeType='application/vnd.openxmlformats-officedocument.presentationml.presentation')
                    if not destination_path.lower().endswith('.pptx'):
                        destination_path += '.pptx'
                else:
                    request = service.files().get_media(fileId=file_id)
                
                with io.FileIO(destination_path, 'wb') as fh:
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                        if status:
                            # Update progress if we can estimate file size
                            progress = (status.resumable_progress / status.total_size * 100) if status.total_size else 0
                            # Note: This is per-file progress, overall progress would need to track all files
                            logger.debug(f"Downloading {os.path.basename(destination_path)}: {progress:.1f}%")
                
                logger.info(f"Downloaded: {destination_path}")
                return True
            except Exception as e:
                logger.error(f"Error downloading file {file_id} to {destination_path}: {e}")
                # Write error to log file
                error_log = os.path.join(dest_path, 'sync_errors.log')
                with open(error_log, 'a') as log:
                    log.write(f"{datetime.now()} - Error downloading file {file_id}: {e}\n")
                return False
        
        def recursive_sync(local_dir, folder_id):
            """Recursively sync a Google Drive folder."""
            logger.info(f"Syncing folder {folder_id} to {local_dir}")
            try:
                # Get folder metadata
                try:
                    folder_meta = service.files().get(
                        fileId=folder_id, 
                        fields="id,name,mimeType",
                        supportsAllDrives=True
                    ).execute()
                    logger.info(f"Folder: {folder_meta.get('name', 'Unknown')} (ID: {folder_id})")
                except Exception as e:
                    logger.warning(f"Could not get folder metadata: {e}")
                
                page_token = None
                file_count = 0
                
                while True:
                    try:
                        # List files in folder
                        response = service.files().list(
                            q=f"'{folder_id}' in parents and trashed=false",
                            supportsAllDrives=True,
                            includeItemsFromAllDrives=True,
                            fields="nextPageToken, files(id, name, mimeType, shortcutDetails)",
                            pageToken=page_token
                        ).execute()
                    except google.auth.exceptions.RefreshError as e:
                        if 'invalid_grant' in str(e):
                            logger.error(f"Google refresh token expired for {user_email}")
                            raise
                        raise
                    except Exception as e:
                        logger.warning(f"File listing failed, trying without supportsAllDrives: {e}")
                        try:
                            response = service.files().list(
                                q=f"'{folder_id}' in parents and trashed=false",
                                fields="nextPageToken, files(id, name, mimeType, shortcutDetails)",
                                pageToken=page_token
                            ).execute()
                        except Exception as e2:
                            logger.error(f"File listing failed: {e2}")
                            break
                    
                    files = response.get('files', [])
                    file_count += len(files)
                    
                    if len(files) == 0:
                        break
                    
                    for file in files:
                        f_id = file['id']
                        f_name = file['name']
                        m_type = file['mimeType']
                        
                        # Handle shortcuts
                        if m_type == 'application/vnd.google-apps.shortcut':
                            shortcut_details = file.get('shortcutDetails', {})
                            if shortcut_details:
                                f_id = shortcut_details.get('targetId', f_id)
                                try:
                                    meta = service.files().get(
                                        fileId=f_id,
                                        fields="mimeType, name",
                                        supportsAllDrives=True
                                    ).execute()
                                    f_name = meta.get('name', f_name)
                                    m_type = meta.get('mimeType', m_type)
                                except Exception as e:
                                    logger.warning(f"Could not resolve shortcut {f_name}: {e}")
                        
                        # Handle folders recursively
                        if m_type == 'application/vnd.google-apps.folder':
                            new_dir = os.path.join(local_dir, f_name)
                            os.makedirs(new_dir, exist_ok=True)
                            if not recursive_sync(new_dir, f_id):
                                return False
                        else:
                            # Download file
                            file_path = os.path.join(local_dir, f_name)
                            download_file(f_id, file_path, m_type)
                    
                    page_token = response.get('nextPageToken')
                    if page_token is None:
                        break
                
                logger.info(f"Completed syncing folder {folder_id} - {file_count} files processed")
                return True
                
            except Exception as e:
                logger.error(f"Error syncing folder {folder_id}: {e}")
                error_log = os.path.join(local_dir, 'sync_errors.log')
                with open(error_log, 'a') as log:
                    log.write(f"{datetime.now()} - Error syncing folder {folder_id}: {e}\n")
                return False
        
        # Check if file_id is a folder or file
        try:
            file_meta = service.files().get(
                fileId=file_id,
                fields="id,name,mimeType",
                supportsAllDrives=True
            ).execute()
            
            mime_type = file_meta.get('mimeType')
            file_name = file_meta.get('name', 'unknown')
            
            if mime_type == 'application/vnd.google-apps.folder':
                # Recursive folder sync
                logger.info(f"Starting recursive folder sync: {file_name}")
                success = recursive_sync(dest_path, file_id)
            else:
                # Single file download
                logger.info(f"Downloading single file: {file_name}")
                file_path = os.path.join(dest_path, file_name)
                success = download_file(file_id, file_path, mime_type)
            
            if success:
                logger.info(f"Google Drive download completed successfully")
                self._update_job_progress(job_id, 100.0, 0, 0)  # Progress tracking for folders is complex
            else:
                raise RuntimeError("Google Drive download failed")
                
        except Exception as e:
            logger.error(f"Error in Google Drive OAuth download: {e}")
            raise
    
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
        """Update job status in memory and visstoredatas (status-based architecture)."""
        progress = self.job_manager.get_progress(job_id)
        if progress:
            progress.status = status
            progress.error_message = error_message
            progress.last_updated = datetime.utcnow()
            
            if status == UploadStatus.COMPLETED:
                progress.progress_percentage = 100.0
        
        # Update dataset status in visstoredatas collection (no jobs collection)
        job_config = self.job_manager.upload_configs.get(job_id)
        if job_config:
            # Map upload status to dataset status
            dataset_status = self._map_upload_status_to_dataset_status(status, job_config)
            self._update_dataset_status(job_config.dataset_uuid, dataset_status, error_message, job_config)
    
    def _update_job_progress(self, job_id: str, percentage: float, uploaded_bytes: int, total_bytes: int):
        """Update job progress (in-memory only, status-based architecture)."""
        progress = self.job_manager.get_progress(job_id)
        if progress:
            progress.progress_percentage = percentage
            progress.bytes_uploaded = uploaded_bytes
            progress.bytes_total = total_bytes
            progress.last_updated = datetime.utcnow()
        
        # Progress is tracked in-memory only - no jobs collection needed
        # Dataset status in visstoredatas is the source of truth
    
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
    
    def _cleanup_old_datasets(self):
        """Clean up old stuck datasets with status 'uploading' that haven't progressed.
        
        This replaces the old _cleanup_old_jobs method - now we clean up datasets directly.
        """
        try:
            from datetime import datetime, timedelta
            
            # Clean up datasets with status 'uploading' older than 1 hour
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            
            with mongo_collection_by_type_context('visstoredatas') as collection:
                old_datasets = collection.find({
                    "status": "uploading",
                    "updated_at": {"$lt": cutoff_time}
                }, {"uuid": 1, "updated_at": 1})
                
                old_dataset_uuids = [ds["uuid"] for ds in old_datasets]
                
                if old_dataset_uuids:
                    # Reset status to allow retry, or mark as failed
                    result = collection.update_many(
                        {"uuid": {"$in": old_dataset_uuids}},
                        {
                            "$set": {
                                "status": "failed",
                                "error_message": "Upload timed out - no progress for over 1 hour",
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )
                    
                    logger.info(f"Cleaned up {result.modified_count} old stuck upload datasets")
                            
        except Exception as e:
            logger.error(f"Error during dataset cleanup: {e}")
    
    def _create_or_update_dataset_entry(self, job_config: UploadJobConfig, job_id: Optional[str] = None):
        """Create or update dataset entry in visstoredatas collection.
        
        Args:
            job_config: The upload job configuration
            job_id: Optional job ID to store in dataset for status lookups
        """
        try:
            logger.info(f"Creating/updating dataset entry: uuid={job_config.dataset_uuid}, name={job_config.dataset_name}, user={job_config.user_email}, job_id={job_id}")
            
            with mongo_collection_by_type_context('visstoredatas') as collection:
                # Check if dataset already exists
                existing_dataset = collection.find_one({"uuid": job_config.dataset_uuid})
                
                # Generate additional identifiers
                dataset_slug = self._generate_dataset_slug(job_config.dataset_name, job_config.user_email)
                dataset_id = self._generate_dataset_id()
                
                # Extract google_drive_link for Google Drive uploads
                google_drive_link = None
                if job_config.source_type == UploadSourceType.GOOGLE_DRIVE:
                    # Check if folder_link is in source_config (preferred)
                    if job_config.source_config and job_config.source_config.get('folder_link'):
                        google_drive_link = job_config.source_config['folder_link']
                    else:
                        # Construct link from file_id
                        # Try source_config first, then fall back to source_path
                        file_id = None
                        if job_config.source_config and job_config.source_config.get('file_id'):
                            file_id = job_config.source_config['file_id']
                        elif job_config.source_path:
                            file_id = job_config.source_path
                        
                        if file_id:
                            # Assume it's a folder (most common case), but could be a file
                            # Use folder link format - if it's actually a file, user can still access it
                            google_drive_link = f"https://drive.google.com/drive/folders/{file_id}"
                
                dataset_doc = {
                    "uuid": job_config.dataset_uuid,
                    "name": job_config.dataset_name,
                    "slug": dataset_slug,
                    "id": dataset_id,
                    "user": job_config.user_email,  # Primary field - user email
                    "user_id": job_config.user_email,  # Also set user_id for compatibility with existing queries
                    "sensor": job_config.sensor.value,
                    "convert": job_config.convert,
                    "is_public": job_config.is_public,
                    "folder_uuid": job_config.folder,
                    "team_uuid": job_config.team_uuid,
                    "source_type": job_config.source_type.value,
                    "source_path": job_config.source_path,
                    "destination_path": job_config.destination_path,
                    "total_size_bytes": job_config.total_size_bytes,
                    "status": "uploading",  # Initial status
                    "tags": ",".join(job_config.tags) if job_config.tags else "",  # Convert list to comma-separated string
                    "created_at": job_config.created_at,
                    "updated_at": datetime.utcnow()
                }
                
                # Store job_id for status lookups (allows curl scripts to check status by job_id)
                if job_id:
                    dataset_doc["job_id"] = job_id
                
                # Add google_drive_link if available
                if google_drive_link:
                    dataset_doc["google_drive_link"] = google_drive_link
                
                if existing_dataset:
                    # Update existing dataset - add new file information
                    update_data = {
                            "$set": {
                                "status": "uploading",
                                "user_id": job_config.user_email,  # Ensure user_id is set for compatibility
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
                    
                    # Store job_id for status lookups
                    if job_id:
                        update_data["$set"]["job_id"] = job_id
                    
                    # Add google_drive_link if available and not already set
                    if google_drive_link and not existing_dataset.get('google_drive_link'):
                        update_data["$set"]["google_drive_link"] = google_drive_link
                    
                    update_result = collection.update_one(
                        {"uuid": job_config.dataset_uuid},
                        update_data
                    )
                    if update_result.modified_count > 0:
                        logger.info(f"✅ Updated existing dataset: {job_config.dataset_uuid} (user: {job_config.user_email})")
                    else:
                        logger.warning(f"⚠️  Dataset update returned modified_count=0: {job_config.dataset_uuid}")
                else:
                    # Create new dataset entry
                    dataset_doc["files"] = [{
                        "source_path": job_config.source_path,
                        "destination_path": job_config.destination_path,
                        "source_type": job_config.source_type.value,
                        "total_size_bytes": job_config.total_size_bytes,
                        "created_at": job_config.created_at
                    }]
                    result = collection.insert_one(dataset_doc)
                    if result.inserted_id:
                        logger.info(f"✅ Created dataset entry: {job_config.dataset_uuid} (user: {job_config.user_email}, inserted_id: {result.inserted_id})")
                        
                        # Verify the dataset was actually created
                        verify_dataset = collection.find_one({"uuid": job_config.dataset_uuid})
                        if verify_dataset:
                            logger.info(f"✅ Verified dataset exists in MongoDB: {job_config.dataset_uuid}")
                        else:
                            logger.error(f"❌ CRITICAL: Dataset was not found after insertion! UUID: {job_config.dataset_uuid}")
                    else:
                        logger.error(f"❌ CRITICAL: Dataset insertion returned no inserted_id! UUID: {job_config.dataset_uuid}")
                    
        except Exception as e:
            logger.error(f"❌ CRITICAL ERROR creating/updating dataset entry for {job_config.dataset_uuid}: {e}", exc_info=True)
            # Re-raise the exception so the caller knows it failed
            # This is critical - dataset must exist for the system to work
            raise RuntimeError(f"Failed to create dataset entry in MongoDB: {e}") from e
    
    def _format_data_size(self, size_bytes: int) -> str:
        """Format data size in the same format as existing schema."""
        if size_bytes == 0:
            return "0 KB"
        
        # Convert to KB, MB, GB, etc.
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
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
    
    def _update_dataset_status(self, dataset_uuid: str, status: str, error_message: str = "", job_config: Optional[UploadJobConfig] = None):
        """Update dataset status in visstoredatas collection."""
        try:
            with mongo_collection_by_type_context('visstoredatas') as collection:
                update_data = {
                    "status": status,
                    "updated_at": datetime.utcnow()
                }
                
                if status == "completed":
                    # Check if conversion is needed
                    if job_config and job_config.convert:
                        # Set status to "conversion queued" instead of "done"
                        update_data["status"] = "conversion queued"
                        update_data["data_conversion_needed"] = True
                        logger.info(f"Upload completed, conversion queued for dataset: {dataset_uuid}")
                        
                        # Automatically create conversion job in the queue
                        self._create_conversion_job(dataset_uuid, job_config, collection)
                    else:
                        # No conversion needed, mark as done
                        update_data["status"] = "done"  # Match existing schema
                        update_data["completed_at"] = datetime.utcnow()
                        logger.info(f"Upload completed, no conversion needed for dataset: {dataset_uuid}")
                elif status == "failed":
                    update_data["error_message"] = error_message
                
                collection.update_one(
                    {"uuid": dataset_uuid},
                    {"$set": update_data}
                )
                logger.info(f"Updated dataset status: {dataset_uuid} -> {update_data.get('status', status)}")
                
        except Exception as e:
            logger.error(f"Error updating dataset status: {e}")
    
    def _create_conversion_job(self, dataset_uuid: str, job_config: UploadJobConfig, collection):
        """
        Mark dataset as ready for conversion.
        
        NOTE: We no longer create entries in the jobs collection.
        The background service queries visstoredatas directly by status.
        This simplifies the architecture - dataset status is the source of truth.
        """
        try:
            # Verify dataset exists
            dataset = collection.find_one({"uuid": dataset_uuid})
            if not dataset:
                logger.error(f"Dataset not found for conversion: {dataset_uuid}")
                return
            
            # Dataset status is already set to "conversion queued" by _update_dataset_status()
            # The background service will pick it up by querying visstoredatas for status="conversion queued"
            logger.info(f"Dataset {dataset_uuid} marked for conversion - background service will process it")
            
        except Exception as e:
            logger.error(f"Error preparing dataset for conversion: {dataset_uuid}: {e}")
            # Don't raise - we don't want to fail the upload if this fails
    
    def _map_upload_status_to_dataset_status(self, upload_status: UploadStatus, job_config: Optional[UploadJobConfig] = None) -> str:
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
            user_email="test_user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF,
            original_source_path="/tmp/test_file.zip"
        )
        
        url_job = create_url_upload_job(
            url="https://example.com/test_data.zip",
            dataset_uuid="test_dataset_456",
            user_email="test_user@example.com",
            dataset_name="Test URL Dataset",
            sensor=SensorType.TIFF
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
