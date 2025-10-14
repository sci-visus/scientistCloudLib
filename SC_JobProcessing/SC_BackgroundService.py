"""
ScientistCloud Enhanced Background Service
Handles job processing with improved reliability, monitoring, and error handling.
"""

import os
import sys
import time
import json
import subprocess
import traceback
import psutil
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pymongo import MongoClient

# Import our job queue manager
from SC_JobQueueManager import SC_JobQueueManager


class SC_BackgroundService:
    """
    Enhanced background service for processing ScientistCloud jobs.
    Handles job execution, monitoring, and error recovery.
    """
    
    def __init__(self, settings: Dict[str, Any]):
        """
        Initialize the background service.
        
        Args:
            settings: Configuration settings dictionary
        """
        self.settings = settings
        self.mongo_client = self._get_mongo_connection()
        self.job_queue = SC_JobQueueManager(self.mongo_client, settings.get('db_name', 'scientistcloud'))
        self.worker_id = f"sc_worker_{os.getpid()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.running = False
        
        # Job type handlers
        self.job_handlers = {
            'google_sync': self._handle_google_sync,
            'dataset_conversion': self._handle_dataset_conversion,
            'file_upload': self._handle_file_upload,
            'file_extraction': self._handle_file_extraction,
            'data_compression': self._handle_data_compression,
            'rsync_transfer': self._handle_rsync_transfer
        }
        
        print(f"SC_BackgroundService initialized with worker ID: {self.worker_id}")
    
    def _get_mongo_connection(self) -> MongoClient:
        """Get MongoDB connection."""
        try:
            from SC_MongoConnection import get_mongo_connection
            return get_mongo_connection()
        except ImportError:
            # Fallback for direct connection
            mongo_url = os.getenv('MONGO_URL')
            if not mongo_url:
                raise ValueError("MONGO_URL environment variable is required")
            return MongoClient(mongo_url)
    
    def start(self):
        """Start the background service."""
        self.running = True
        print(f"Starting SC_BackgroundService worker {self.worker_id}")
        
        try:
            while self.running:
                self._process_jobs()
                self._check_stale_jobs()
                time.sleep(5)  # Check for jobs every 5 seconds
        except KeyboardInterrupt:
            print("Received interrupt signal, shutting down...")
            self.stop()
        except Exception as e:
            print(f"Fatal error in background service: {e}")
            print(traceback.format_exc())
            self.stop()
    
    def stop(self):
        """Stop the background service."""
        self.running = False
        print("SC_BackgroundService stopped")
    
    def _process_jobs(self):
        """Main job processing loop."""
        try:
            # Get next job
            job = self.job_queue.get_next_job(self.worker_id)
            
            if job:
                self._process_job(job)
            else:
                # No jobs available, do maintenance
                self._cleanup_old_jobs()
                
        except Exception as e:
            print(f"Error in job processing: {e}")
            print(traceback.format_exc())
    
    def _process_job(self, job: Dict[str, Any]):
        """Process a single job."""
        job_id = job['job_id']
        job_type = job['job_type']
        dataset_uuid = job['dataset_uuid']
        
        print(f"Processing job {job_id} of type {job_type} for dataset {dataset_uuid}")
        
        # Create lock file
        lock_file = f"/tmp/sc_job_{job_id}.lock"
        try:
            with open(lock_file, 'w') as f:
                f.write(str(os.getpid()))
            
            # Update job with PID
            self.job_queue.update_job_status(
                job_id, 'running', 
                log_message=f"Started processing {job_type}"
            )
            
            # Execute job based on type
            handler = self.job_handlers.get(job_type)
            if not handler:
                raise ValueError(f"Unknown job type: {job_type}")
            
            result = handler(job)
            
            # Mark as completed
            self.job_queue.update_job_status(
                job_id, 'completed', 
                result=result,
                log_message=f"Completed {job_type} successfully"
            )
            
            # Update dataset status
            self.job_queue.update_dataset_status(dataset_uuid, 'done')
            
            print(f"Job {job_id} completed successfully")
            
        except Exception as e:
            # Handle failure
            self._handle_job_failure(job, e)
        finally:
            # Cleanup
            self._cleanup_job(job, lock_file)
    
    def _handle_google_sync(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Google Drive sync job."""
        parameters = job['parameters']
        user_email = parameters['user_email']
        input_dir = parameters['input_dir']
        data_url = parameters['data_url']
        
        print(f"Starting Google Drive sync for {user_email}")
        
        # Run sync process
        sync_script = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'syncGoogleUser.py')
        if not os.path.exists(sync_script):
            sync_script = 'syncGoogleUser.py'  # Fallback
        
        process = subprocess.Popen([
            'python3', sync_script,
            user_email, input_dir, data_url
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            return {
                'status': 'success',
                'message': 'Google Drive sync completed',
                'stdout': stdout
            }
        else:
            raise Exception(f"Google Drive sync failed with return code {process.returncode}: {stderr}")
    
    def _handle_dataset_conversion(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Handle dataset conversion job."""
        parameters = job['parameters']
        conversion_input = parameters['input_path']
        output_dir = parameters['output_path']
        sensor = parameters['sensor_type']
        conversion_params = parameters.get('conversion_params', {})
        
        print(f"Starting dataset conversion: {conversion_input} -> {output_dir}")
        
        # Format conversion parameters
        param_string = self._format_conversion_params(conversion_params)
        
        # Run conversion process
        conversion_script = 'run_slampy.sh'
        if not os.path.exists(conversion_script):
            conversion_script = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'run_slampy.sh')
        
        cmd = ['/bin/bash', conversion_script, conversion_input, output_dir, sensor]
        if param_string:
            cmd.append(param_string)
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            return {
                'status': 'success',
                'message': 'Dataset conversion completed',
                'stdout': stdout
            }
        else:
            raise Exception(f"Dataset conversion failed with return code {process.returncode}: {stderr}")
    
    def _handle_file_upload(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file upload job."""
        parameters = job['parameters']
        files = parameters.get('files', [])
        destination = parameters['destination']
        
        print(f"Starting file upload to {destination}")
        
        uploaded_files = []
        for file_path in files:
            if os.path.exists(file_path):
                # Implement your upload logic here
                # This is a placeholder - implement based on your upload requirements
                uploaded_files.append(file_path)
            else:
                print(f"Warning: File {file_path} not found")
        
        return {
            'status': 'success',
            'message': f'Uploaded {len(uploaded_files)} files',
            'uploaded_files': uploaded_files
        }
    
    def _handle_file_extraction(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Handle file extraction (unzipping) job."""
        parameters = job['parameters']
        zip_file = parameters['zip_file']
        extract_dir = parameters['extract_dir']
        
        print(f"Starting file extraction: {zip_file} -> {extract_dir}")
        
        # Create extract directory
        os.makedirs(extract_dir, exist_ok=True)
        
        # Run unzip
        process = subprocess.Popen([
            'unzip', '-o', zip_file, '-d', extract_dir
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            return {
                'status': 'success',
                'message': 'File extraction completed',
                'extracted_files': self._list_extracted_files(extract_dir)
            }
        else:
            raise Exception(f"File extraction failed with return code {process.returncode}: {stderr}")
    
    def _handle_data_compression(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Handle data compression job."""
        parameters = job['parameters']
        source_dir = parameters['source_dir']
        compression_type = parameters.get('compression_type', 'lz4')
        
        print(f"Starting data compression: {source_dir}")
        
        # Run compression
        compression_script = 'compressDatasets.py'
        if not os.path.exists(compression_script):
            compression_script = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'compressDatasets.py')
        
        process = subprocess.Popen([
            'python3', compression_script, source_dir
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            return {
                'status': 'success',
                'message': 'Data compression completed',
                'stdout': stdout
            }
        else:
            raise Exception(f"Data compression failed with return code {process.returncode}: {stderr}")
    
    def _handle_rsync_transfer(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Handle rsync transfer job."""
        parameters = job['parameters']
        source = parameters['source']
        destination = parameters['destination']
        rsync_options = parameters.get('rsync_options', ['-avz'])
        
        print(f"Starting rsync transfer: {source} -> {destination}")
        
        cmd = ['rsync'] + rsync_options + [source, destination]
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            return {
                'status': 'success',
                'message': 'Rsync transfer completed',
                'stdout': stdout
            }
        else:
            raise Exception(f"Rsync transfer failed with return code {process.returncode}: {stderr}")
    
    def _format_conversion_params(self, conversion_params: Dict[str, Any]) -> str:
        """Format conversion parameters for the conversion script."""
        if not conversion_params:
            return ""
        
        param_parts = []
        for key, value in conversion_params.items():
            if value:  # Only include non-empty values
                param_parts.append(f"{key}={value}")
        
        return ",".join(param_parts)
    
    def _list_extracted_files(self, extract_dir: str) -> List[str]:
        """List files in the extraction directory."""
        extracted_files = []
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                extracted_files.append(os.path.join(root, file))
        return extracted_files
    
    def _handle_job_failure(self, job: Dict[str, Any], error: Exception):
        """Handle job failure with retry logic."""
        job_id = job['job_id']
        dataset_uuid = job['dataset_uuid']
        
        print(f"Job {job_id} failed: {error}")
        
        # Log error
        self.job_queue.update_job_status(
            job_id, 'failed',
            error=str(error),
            log_message=f"Job failed: {str(error)}"
        )
        
        # Try to retry
        if self.job_queue.retry_job(job_id):
            print(f"Job {job_id} will be retried")
            # Update dataset status to indicate retry
            self.job_queue.update_dataset_status(dataset_uuid, 'retrying')
        else:
            print(f"Job {job_id} has reached max retry attempts")
            # Mark dataset as failed
            self.job_queue.update_dataset_status(dataset_uuid, 'failed')
    
    def _cleanup_job(self, job: Dict[str, Any], lock_file: str):
        """Clean up job resources."""
        # Remove lock file
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
            except OSError as e:
                print(f"Warning: Could not remove lock file {lock_file}: {e}")
    
    def _check_stale_jobs(self):
        """Check for stale jobs and restart them."""
        try:
            stale_jobs = self.job_queue.get_stale_jobs(timeout_hours=1)
            
            for job in stale_jobs:
                job_id = job['job_id']
                pid = job.get('pid')
                
                if pid and self._is_process_running(pid):
                    print(f"Job {job_id} is still running (PID: {pid})")
                    continue
                
                print(f"Job {job_id} appears to be stale, attempting restart")
                
                if self.job_queue.retry_job(job_id):
                    print(f"Restarted stale job: {job_id}")
                else:
                    print(f"Could not restart job {job_id} (max retries reached)")
                    
        except Exception as e:
            print(f"Error checking stale jobs: {e}")
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process is still running."""
        try:
            process = psutil.Process(pid)
            return process.is_running() and process.status() != 'zombie'
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def _cleanup_old_jobs(self):
        """Clean up old completed jobs."""
        try:
            # Clean up jobs older than 30 days
            deleted_count = self.job_queue.cleanup_completed_jobs(days_old=30)
            if deleted_count > 0:
                print(f"Cleaned up {deleted_count} old completed jobs")
        except Exception as e:
            print(f"Error cleaning up old jobs: {e}")
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """Get current queue statistics."""
        return self.job_queue.get_queue_stats()
    
    def submit_job(self, dataset_uuid: str, job_type: str, parameters: Dict[str, Any], 
                   priority: int = 2) -> str:
        """Submit a new job to the queue."""
        return self.job_queue.create_job(dataset_uuid, job_type, parameters, priority)


def main():
    """Main entry point for the background service."""
    if len(sys.argv) != 2:
        print("Usage: SC_BackgroundService.py <settings.json>")
        sys.exit(1)
    
    try:
        # Load settings
        with open(sys.argv[1]) as f:
            settings = json.load(f)
        
        # Create and start service
        service = SC_BackgroundService(settings)
        service.start()
        
    except FileNotFoundError:
        print(f"Settings file not found: {sys.argv[1]}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in settings file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting background service: {e}")
        print(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
