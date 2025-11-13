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
try:
    from .SCLib_JobQueueManager import SCLib_JobQueueManager
except ImportError:
    from SCLib_JobQueueManager import SCLib_JobQueueManager


class SCLib_BackgroundService:
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
        self.job_queue = SCLib_JobQueueManager(self.mongo_client, settings.get('db_name', 'scientistcloud'))
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
            from SCLib_MongoConnection import get_mongo_connection
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
        """
        Main job processing loop.
        Queries visstoredatas collection directly by status - no jobs collection needed.
        """
        try:
            # Query datasets that need processing directly from visstoredatas
            db_name = self.settings.get('db_name', 'scientistcloud')
            db = self.mongo_client[db_name]
            datasets_collection = db['visstoredatas']
            
            # Find datasets that need conversion (status-based processing)
            datasets_to_convert = datasets_collection.find({
                'status': 'conversion queued'
            }).limit(1)  # Process one at a time
            
            dataset = next(datasets_to_convert, None)
            
            if dataset:
                self._process_dataset_conversion(dataset)
            else:
                # No datasets need processing, do maintenance
                # Only log every 12 iterations (once per minute) to reduce noise
                if not hasattr(self, '_check_counter'):
                    self._check_counter = 0
                self._check_counter += 1
                if self._check_counter >= 12:
                    print(f"⏳ No datasets queued for conversion (checked {self._check_counter * 5}s ago)")
                    self._check_counter = 0
                self._cleanup_old_datasets()
                
        except Exception as e:
            print(f"Error in job processing: {e}")
            print(traceback.format_exc())
    
    def _process_dataset_conversion(self, dataset: Dict[str, Any]):
        """
        Process a dataset conversion directly from visstoredatas collection.
        No jobs collection needed - dataset status is the source of truth.
        """
        dataset_uuid = dataset['uuid']
        dataset_name = dataset.get('name', 'Unnamed Dataset')
        
        print(f"Processing conversion for dataset {dataset_uuid} ({dataset_name})")
        
        # Create lock file based on dataset UUID
        lock_file = f"/tmp/sc_conversion_{dataset_uuid}.lock"
        
        # Check if already processing (lock file exists and process is running)
        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    pid = int(f.read().strip())
                if self._is_process_running(pid):
                    print(f"Dataset {dataset_uuid} is already being processed (PID: {pid})")
                    return
            except (ValueError, OSError):
                # Lock file exists but invalid, remove it
                os.remove(lock_file)
        
        try:
            # Create lock file
            with open(lock_file, 'w') as f:
                f.write(str(os.getpid()))
            
            # Update dataset status to "converting"
            db_name = self.settings.get('db_name', 'scientistcloud')
            db = self.mongo_client[db_name]
            datasets_collection = db['visstoredatas']
            
            datasets_collection.update_one(
                {'uuid': dataset_uuid},
                {'$set': {'status': 'converting', 'updated_at': datetime.utcnow()}}
            )
            
            # Get paths from dataset or environment
            config = self._get_config()
            input_dir = os.getenv('JOB_IN_DATA_DIR', '/mnt/visus_datasets/upload')
            output_dir = os.getenv('JOB_OUT_DATA_DIR', '/mnt/visus_datasets/converted')
            
            input_path = os.path.join(input_dir, dataset_uuid)
            output_path = os.path.join(output_dir, dataset_uuid)
            
            # Get sensor type from dataset
            sensor = dataset.get('sensor', 'OTHER')
            conversion_params = dataset.get('conversion_parameters', {})
            
            # Execute conversion
            result = self._handle_dataset_conversion_direct(
                dataset_uuid=dataset_uuid,
                input_path=input_path,
                output_path=output_path,
                sensor=sensor,
                conversion_params=conversion_params
            )
            
            # Mark as completed
            datasets_collection.update_one(
                {'uuid': dataset_uuid},
                {'$set': {
                    'status': 'done',
                    'updated_at': datetime.utcnow(),
                    'completed_at': datetime.utcnow()
                }}
            )
            
            print(f"✅ Dataset {dataset_uuid} conversion completed successfully")
            
        except Exception as e:
            # Handle failure - update dataset status
            print(f"❌ Dataset {dataset_uuid} conversion failed: {e}")
            self._handle_conversion_failure(dataset_uuid, e)
        finally:
            # Cleanup lock file
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                except OSError:
                    pass
    
    def _get_config(self):
        """Get configuration."""
        try:
            from SCLib_Config import get_config
            return get_config()
        except ImportError:
            # Return minimal config
            class MinimalConfig:
                class server:
                    visus_datasets = '/mnt/visus_datasets'
            return MinimalConfig()
    
    def _handle_dataset_conversion_direct(self, dataset_uuid: str, input_path: str, 
                                         output_path: str, sensor: str, 
                                         conversion_params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle dataset conversion directly (no job wrapper)."""
        import json
        
        print(f"Starting dataset conversion: {input_path} -> {output_path} (sensor: {sensor})")
        
        # Use Python conversion script (preferred) or fallback to shell script
        conversion_script = os.path.join(os.path.dirname(__file__), 'scripts', 'run_conversion.py')
        if not os.path.exists(conversion_script):
            # Fallback to shell script for backward compatibility
            conversion_script = os.path.join(os.path.dirname(__file__), 'scripts', 'run_slampy.sh')
            if not os.path.exists(conversion_script):
                conversion_script = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'run_slampy.sh')
        
        # Determine if using Python or shell script
        is_python_script = conversion_script.endswith('.py')
        
        if is_python_script:
            # Use Python script
            cmd = ['python3', conversion_script, input_path, output_path, sensor]
            if conversion_params:
                # Format as JSON string
                params_json = json.dumps(conversion_params)
                cmd.extend(['--params', params_json])
        else:
            # Use shell script (legacy)
            param_string = self._format_conversion_params(conversion_params)
            cmd = ['/bin/bash', conversion_script, input_path, output_path, sensor]
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
    
    def _handle_conversion_failure(self, dataset_uuid: str, error: Exception):
        """Handle conversion failure - update dataset status."""
        try:
            db_name = self.settings.get('db_name', 'scientistcloud')
            db = self.mongo_client[db_name]
            datasets_collection = db['visstoredatas']
            
            # Get current dataset to check retry count
            dataset = datasets_collection.find_one({'uuid': dataset_uuid})
            if not dataset:
                return
            
            # Check retry count (store in dataset document)
            retry_count = dataset.get('conversion_retry_count', 0)
            max_retries = 3
            
            if retry_count < max_retries:
                # Retry - set back to "conversion queued"
                datasets_collection.update_one(
                    {'uuid': dataset_uuid},
                    {'$set': {
                        'status': 'conversion queued',
                        'conversion_retry_count': retry_count + 1,
                        'conversion_last_error': str(error),
                        'updated_at': datetime.utcnow()
                    }}
                )
                print(f"Dataset {dataset_uuid} will be retried (attempt {retry_count + 1}/{max_retries})")
            else:
                # Max retries reached - mark as failed
                datasets_collection.update_one(
                    {'uuid': dataset_uuid},
                    {'$set': {
                        'status': 'conversion failed',
                        'conversion_last_error': str(error),
                        'updated_at': datetime.utcnow()
                    }}
                )
                print(f"Dataset {dataset_uuid} conversion failed after {max_retries} attempts")
        except Exception as e:
            print(f"Error handling conversion failure: {e}")
    
    def _cleanup_old_datasets(self):
        """Clean up old processing locks and check for stale conversions."""
        try:
            # Check for datasets stuck in "converting" status for too long (>2 hours)
            db_name = self.settings.get('db_name', 'scientistcloud')
            db = self.mongo_client[db_name]
            datasets_collection = db['visstoredatas']
            
            two_hours_ago = datetime.utcnow() - timedelta(hours=2)
            
            stale_datasets = datasets_collection.find({
                'status': 'converting',
                'updated_at': {'$lt': two_hours_ago}
            })
            
            for dataset in stale_datasets:
                dataset_uuid = dataset['uuid']
                print(f"Found stale conversion for dataset {dataset_uuid}, resetting to queued")
                
                # Reset to queued so it can be retried
                datasets_collection.update_one(
                    {'uuid': dataset_uuid},
                    {'$set': {
                        'status': 'conversion queued',
                        'updated_at': datetime.utcnow()
                    }}
                )
                
                # Remove lock file if it exists
                lock_file = f"/tmp/sc_conversion_{dataset_uuid}.lock"
                if os.path.exists(lock_file):
                    try:
                        os.remove(lock_file)
                    except OSError:
                        pass
                        
        except Exception as e:
            print(f"Error cleaning up old datasets: {e}")
    
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
        """
        Legacy handler for job-based conversion (kept for backward compatibility).
        New code should use _process_dataset_conversion() which works directly with datasets.
        """
        import json
        
        parameters = job['parameters']
        conversion_input = parameters['input_path']
        output_dir = parameters['output_path']
        sensor = parameters['sensor_type']
        conversion_params = parameters.get('conversion_params', {})
        
        return self._handle_dataset_conversion_direct(
            dataset_uuid=job.get('dataset_uuid', 'unknown'),
            input_path=conversion_input,
            output_path=output_dir,
            sensor=sensor,
            conversion_params=conversion_params
        )
    
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
        """
        Check for stale conversions (handled in _cleanup_old_datasets now).
        Kept for backward compatibility but functionality moved to dataset-based processing.
        """
        # Stale job checking is now handled in _cleanup_old_datasets()
        pass
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process is still running."""
        try:
            process = psutil.Process(pid)
            return process.is_running() and process.status() != 'zombie'
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def _cleanup_old_jobs(self):
        """
        Legacy method - cleanup is now handled in _cleanup_old_datasets().
        Kept for backward compatibility.
        """
        # Cleanup is handled in _cleanup_old_datasets()
        pass
    
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
        print("Usage: SCLib_BackgroundService.py <settings.json>")
        sys.exit(1)
    
    try:
        # Load settings
        with open(sys.argv[1]) as f:
            settings = json.load(f)
        
        # Create and start service
        service = SCLib_BackgroundService(settings)
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
