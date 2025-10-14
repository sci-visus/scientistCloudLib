"""
Test cases for SC_BackgroundService
Tests job processing, error handling, and worker management.
"""

import unittest
import os
import tempfile
import shutil
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
import subprocess

from SCLib_BackgroundService import SCLib_BackgroundService
from SCLib_JobQueueManager import SCLib_JobQueueManager


class TestSCLib_BackgroundService(unittest.TestCase):
    """Test cases for SC_BackgroundService."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.settings = {
            'db_name': 'test_db',
            'in_data_dir': '/tmp/test/upload',
            'out_data_dir': '/tmp/test/converted',
            'sync_data_dir': '/tmp/test/sync',
            'auth_dir': '/tmp/test/auth'
        }
        
        # Create temporary directories
        self.temp_dirs = []
        for key in ['in_data_dir', 'out_data_dir', 'sync_data_dir', 'auth_dir']:
            temp_dir = tempfile.mkdtemp()
            self.temp_dirs.append(temp_dir)
            self.settings[key] = temp_dir
        
        # Mock MongoDB connection
        self.mock_mongo_client = Mock()
        self.mock_job_queue = Mock(spec=SCLib_JobQueueManager)
        
        with patch('SCLib_BackgroundService.SCLib_JobQueueManager') as mock_job_queue_class:
            mock_job_queue_class.return_value = self.mock_job_queue
            
            with patch('SCLib_MongoConnection.get_mongo_connection') as mock_get_connection:
                mock_get_connection.return_value = self.mock_mongo_client
                
                self.service = SCLib_BackgroundService(self.settings)
    
    def tearDown(self):
        """Clean up test fixtures."""
        # Remove temporary directories
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    def test_initialization(self):
        """Test service initialization."""
        self.assertEqual(self.service.settings, self.settings)
        self.assertEqual(self.service.job_queue, self.mock_job_queue)
        self.assertIn('sc_worker_', self.service.worker_id)
        self.assertFalse(self.service.running)
        
        # Verify job handlers are registered
        expected_handlers = [
            'google_sync', 'dataset_conversion', 'file_upload',
            'file_extraction', 'data_compression', 'rsync_transfer'
        ]
        for handler in expected_handlers:
            self.assertIn(handler, self.service.job_handlers)
    
    @patch('SCLib_BackgroundService.time.sleep')
    def test_process_jobs_no_jobs(self, mock_sleep):
        """Test job processing when no jobs are available."""
        # Mock no jobs available
        self.mock_job_queue.get_next_job.return_value = None
        
        # Mock cleanup method
        with patch.object(self.service, '_cleanup_old_jobs') as mock_cleanup:
            self.service._process_jobs()
            
            # Verify cleanup was called
            mock_cleanup.assert_called_once()
    
    @patch('SCLib_BackgroundService.time.sleep')
    def test_process_jobs_with_job(self, mock_sleep):
        """Test job processing with available job."""
        # Mock job
        mock_job = {
            'job_id': 'job-123',
            'job_type': 'dataset_conversion',
            'dataset_uuid': 'dataset-123',
            'parameters': {
                'input_path': '/test/input',
                'output_path': '/test/output',
                'sensor_type': '4D_Probe'
            }
        }
        
        self.mock_job_queue.get_next_job.return_value = mock_job
        
        # Mock job processing
        with patch.object(self.service, '_process_job') as mock_process_job:
            self.service._process_jobs()
            
            # Verify job was processed
            mock_process_job.assert_called_once_with(mock_job)
    
    @patch('builtins.open', create=True)
    @patch('os.getpid')
    def test_process_job_success(self, mock_getpid, mock_open):
        """Test successful job processing."""
        mock_getpid.return_value = 12345
        
        # Mock job
        mock_job = {
            'job_id': 'job-123',
            'job_type': 'dataset_conversion',
            'dataset_uuid': 'dataset-123',
            'parameters': {
                'input_path': '/test/input',
                'output_path': '/test/output',
                'sensor_type': '4D_Probe'
            }
        }
        
        # Mock file operations
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Mock job handler - patch before calling the method
        with patch.object(self.service, '_handle_dataset_conversion') as mock_handler:
            mock_handler.return_value = {'status': 'success'}
            
            # Update the job_handlers dictionary to use the mocked method
            self.service.job_handlers['dataset_conversion'] = mock_handler
            
            # Mock cleanup
            with patch.object(self.service, '_cleanup_job') as mock_cleanup:
                self.service._process_job(mock_job)
                
                # Verify lock file was created
                mock_open.assert_called_with('/tmp/sc_job_job-123.lock', 'w')
                mock_file.write.assert_called_with('12345')
                
                # Verify job status updates
                self.assertEqual(self.mock_job_queue.update_job_status.call_count, 2)
                
                # First call: status to running
                first_call = self.mock_job_queue.update_job_status.call_args_list[0]
                self.assertEqual(first_call[0][0], 'job-123')
                self.assertEqual(first_call[0][1], 'running')
                
                # Second call: status to completed
                second_call = self.mock_job_queue.update_job_status.call_args_list[1]
                self.assertEqual(second_call[0][0], 'job-123')
                self.assertEqual(second_call[0][1], 'completed')
                
                # Verify dataset status update
                self.mock_job_queue.update_dataset_status.assert_called_once_with('dataset-123', 'done')
                
                # Verify cleanup
                mock_cleanup.assert_called_once_with(mock_job, '/tmp/sc_job_job-123.lock')
    
    @patch('builtins.open', create=True)
    @patch('os.getpid')
    def test_process_job_failure(self, mock_getpid, mock_open):
        """Test job processing with failure."""
        mock_getpid.return_value = 12345
        
        # Mock job
        mock_job = {
            'job_id': 'job-123',
            'job_type': 'dataset_conversion',
            'dataset_uuid': 'dataset-123',
            'parameters': {}
        }
        
        # Mock file operations
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Mock job handler to raise exception
        with patch.object(self.service, '_handle_dataset_conversion') as mock_handler:
            mock_handler.side_effect = Exception("Conversion failed")
            
            # Mock failure handling
            with patch.object(self.service, '_handle_job_failure') as mock_handle_failure:
                # Mock cleanup
                with patch.object(self.service, '_cleanup_job') as mock_cleanup:
                    self.service._process_job(mock_job)
                    
                    # Verify failure was handled
                    mock_handle_failure.assert_called_once_with(mock_job, unittest.mock.ANY)
                    
                    # Verify cleanup was called
                    mock_cleanup.assert_called_once()
    
    @patch('subprocess.Popen')
    def test_handle_google_sync_success(self, mock_popen):
        """Test successful Google Drive sync."""
        # Mock subprocess
        mock_process = Mock()
        mock_process.communicate.return_value = ("stdout", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        # Mock job
        mock_job = {
            'dataset_uuid': 'dataset-123',
            'parameters': {
                'user_email': 'test@example.com',
                'input_dir': '/test/input',
                'data_url': 'https://drive.google.com/file/123'
            }
        }
        
        with patch('os.path.exists', return_value=True):
            result = self.service._handle_google_sync(mock_job)
            
            # Verify subprocess was called correctly
            mock_popen.assert_called_once()
            call_args = mock_popen.call_args[0][0]
            self.assertEqual(call_args[0], 'python3')
            self.assertIn('syncGoogleUser.py', call_args[1])
            self.assertEqual(call_args[2], 'test@example.com')
            self.assertEqual(call_args[3], '/test/input')
            self.assertEqual(call_args[4], 'https://drive.google.com/file/123')
            
            # Verify result
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['message'], 'Google Drive sync completed')
    
    @patch('subprocess.Popen')
    def test_handle_google_sync_failure(self, mock_popen):
        """Test Google Drive sync failure."""
        # Mock subprocess failure
        mock_process = Mock()
        mock_process.communicate.return_value = ("", "Error message")
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        
        mock_job = {
            'dataset_uuid': 'dataset-123',
            'parameters': {
                'user_email': 'test@example.com',
                'input_dir': '/test/input',
                'data_url': 'https://drive.google.com/file/123'
            }
        }
        
        with patch('os.path.exists', return_value=True):
            with self.assertRaises(Exception) as context:
                self.service._handle_google_sync(mock_job)
            
            self.assertIn("Google Drive sync failed", str(context.exception))
    
    @patch('subprocess.Popen')
    def test_handle_dataset_conversion_success(self, mock_popen):
        """Test successful dataset conversion."""
        # Mock subprocess
        mock_process = Mock()
        mock_process.communicate.return_value = ("stdout", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        mock_job = {
            'dataset_uuid': 'dataset-123',
            'parameters': {
                'input_path': '/test/input',
                'output_path': '/test/output',
                'sensor_type': '4D_Probe',
                'conversion_params': {
                    'Xs_dataset': 'path/to/Xs',
                    'Ys_dataset': 'path/to/Ys'
                }
            }
        }
        
        with patch('os.path.exists', return_value=True):
            result = self.service._handle_dataset_conversion(mock_job)
            
            # Verify subprocess was called correctly
            mock_popen.assert_called_once()
            call_args = mock_popen.call_args[0][0]
            self.assertEqual(call_args[0], '/bin/bash')
            self.assertIn('run_slampy.sh', call_args[1])
            self.assertEqual(call_args[2], '/test/input')
            self.assertEqual(call_args[3], '/test/output')
            self.assertEqual(call_args[4], '4D_Probe')
            
            # Verify result
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['message'], 'Dataset conversion completed')
    
    @patch('subprocess.Popen')
    def test_handle_file_extraction_success(self, mock_popen):
        """Test successful file extraction."""
        # Mock subprocess
        mock_process = Mock()
        mock_process.communicate.return_value = ("stdout", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        mock_job = {
            'dataset_uuid': 'dataset-123',
            'parameters': {
                'zip_file': '/test/archive.zip',
                'extract_dir': '/test/extracted'
            }
        }
        
        with patch('os.makedirs'), \
             patch('os.path.exists', return_value=True), \
             patch.object(self.service, '_list_extracted_files', return_value=['/test/extracted/file1.txt']):
            
            result = self.service._handle_file_extraction(mock_job)
            
            # Verify subprocess was called correctly
            mock_popen.assert_called_once()
            call_args = mock_popen.call_args[0][0]
            self.assertEqual(call_args[0], 'unzip')
            self.assertEqual(call_args[1], '-o')
            self.assertEqual(call_args[2], '/test/archive.zip')
            self.assertEqual(call_args[3], '-d')
            self.assertEqual(call_args[4], '/test/extracted')
            
            # Verify result
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['message'], 'File extraction completed')
            self.assertEqual(result['extracted_files'], ['/test/extracted/file1.txt'])
    
    @patch('subprocess.Popen')
    def test_handle_data_compression_success(self, mock_popen):
        """Test successful data compression."""
        # Mock subprocess
        mock_process = Mock()
        mock_process.communicate.return_value = ("stdout", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        mock_job = {
            'dataset_uuid': 'dataset-123',
            'parameters': {
                'source_dir': '/test/source',
                'compression_type': 'lz4'
            }
        }
        
        with patch('os.path.exists', return_value=True):
            result = self.service._handle_data_compression(mock_job)
            
            # Verify subprocess was called correctly
            mock_popen.assert_called_once()
            call_args = mock_popen.call_args[0][0]
            self.assertEqual(call_args[0], 'python3')
            self.assertIn('compressDatasets.py', call_args[1])
            self.assertEqual(call_args[2], '/test/source')
            
            # Verify result
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['message'], 'Data compression completed')
    
    def test_handle_file_upload_success(self):
        """Test successful file upload."""
        mock_job = {
            'dataset_uuid': 'dataset-123',
            'parameters': {
                'files': ['/test/file1.txt', '/test/file2.txt'],
                'destination': '/test/destination'
            }
        }
        
        with patch('os.path.exists', return_value=True):
            result = self.service._handle_file_upload(mock_job)
            
            # Verify result
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['message'], 'Uploaded 2 files')
            self.assertEqual(result['uploaded_files'], ['/test/file1.txt', '/test/file2.txt'])
    
    def test_handle_file_upload_missing_files(self):
        """Test file upload with missing files."""
        mock_job = {
            'dataset_uuid': 'dataset-123',
            'parameters': {
                'files': ['/test/existing.txt', '/test/missing.txt'],
                'destination': '/test/destination'
            }
        }
        
        def mock_exists(path):
            return path == '/test/existing.txt'
        
        with patch('os.path.exists', side_effect=mock_exists):
            result = self.service._handle_file_upload(mock_job)
            
            # Verify result
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['message'], 'Uploaded 1 files')
            self.assertEqual(result['uploaded_files'], ['/test/existing.txt'])
    
    def test_format_conversion_params(self):
        """Test conversion parameter formatting."""
        # Test with parameters
        params = {
            'Xs_dataset': 'path/to/Xs',
            'Ys_dataset': 'path/to/Ys',
            'presample_dataset': 'path/to/presample',
            'empty_param': ''
        }
        
        result = self.service._format_conversion_params(params)
        
        # Should only include non-empty values
        self.assertIn('Xs_dataset=path/to/Xs', result)
        self.assertIn('Ys_dataset=path/to/Ys', result)
        self.assertIn('presample_dataset=path/to/presample', result)
        self.assertNotIn('empty_param=', result)
    
    def test_format_conversion_params_empty(self):
        """Test conversion parameter formatting with empty params."""
        result = self.service._format_conversion_params({})
        self.assertEqual(result, "")
    
    def test_list_extracted_files(self):
        """Test listing extracted files."""
        # Create temporary directory structure
        extract_dir = tempfile.mkdtemp()
        try:
            # Create test files
            os.makedirs(os.path.join(extract_dir, 'subdir'))
            with open(os.path.join(extract_dir, 'file1.txt'), 'w') as f:
                f.write('test')
            with open(os.path.join(extract_dir, 'subdir', 'file2.txt'), 'w') as f:
                f.write('test')
            
            result = self.service._list_extracted_files(extract_dir)
            
            # Verify files were found
            self.assertEqual(len(result), 2)
            self.assertTrue(any('file1.txt' in path for path in result))
            self.assertTrue(any('file2.txt' in path for path in result))
            
        finally:
            shutil.rmtree(extract_dir)
    
    def test_handle_job_failure_with_retry(self):
        """Test job failure handling with retry."""
        mock_job = {
            'job_id': 'job-123',
            'dataset_uuid': 'dataset-123',
            'attempts': 1,
            'max_attempts': 3
        }
        
        # Mock retry success
        self.mock_job_queue.retry_job.return_value = True
        
        self.service._handle_job_failure(mock_job, Exception("Test error"))
        
        # Verify error was logged
        self.mock_job_queue.update_job_status.assert_called_once_with(
            'job-123', 'failed',
            error='Test error',
            log_message='Job failed: Test error'
        )
        
        # Verify retry was attempted
        self.mock_job_queue.retry_job.assert_called_once_with('job-123')
        
        # Verify dataset status was updated to retrying
        self.mock_job_queue.update_dataset_status.assert_called_once_with('dataset-123', 'retrying')
    
    def test_handle_job_failure_max_retries(self):
        """Test job failure handling when max retries reached."""
        mock_job = {
            'job_id': 'job-123',
            'dataset_uuid': 'dataset-123',
            'attempts': 3,
            'max_attempts': 3
        }
        
        # Mock retry failure
        self.mock_job_queue.retry_job.return_value = False
        
        self.service._handle_job_failure(mock_job, Exception("Test error"))
        
        # Verify dataset status was updated to failed
        self.mock_job_queue.update_dataset_status.assert_called_once_with('dataset-123', 'failed')
    
    @patch('os.remove')
    def test_cleanup_job(self, mock_remove):
        """Test job cleanup."""
        mock_job = {'job_id': 'job-123'}
        lock_file = '/tmp/sc_job_job-123.lock'
        
        with patch('os.path.exists', return_value=True):
            self.service._cleanup_job(mock_job, lock_file)
            
            # Verify lock file was removed
            mock_remove.assert_called_once_with(lock_file)
    
    @patch('os.remove')
    def test_cleanup_job_file_not_exists(self, mock_remove):
        """Test job cleanup when lock file doesn't exist."""
        mock_job = {'job_id': 'job-123'}
        lock_file = '/tmp/sc_job_job-123.lock'
        
        with patch('os.path.exists', return_value=False):
            self.service._cleanup_job(mock_job, lock_file)
            
            # Verify remove was not called
            mock_remove.assert_not_called()
    
    @patch('psutil.Process')
    def test_is_process_running_true(self, mock_process_class):
        """Test process running check when process is running."""
        mock_process = Mock()
        mock_process.is_running.return_value = True
        mock_process.status.return_value = 'running'
        mock_process_class.return_value = mock_process
        
        result = self.service._is_process_running(12345)
        
        self.assertTrue(result)
        mock_process_class.assert_called_once_with(12345)
    
    @patch('psutil.Process')
    def test_is_process_running_false(self, mock_process_class):
        """Test process running check when process is not running."""
        import psutil
        mock_process_class.side_effect = psutil.NoSuchProcess(12345)
        
        result = self.service._is_process_running(12345)
        
        self.assertFalse(result)
    
    def test_check_stale_jobs(self):
        """Test stale job checking."""
        # Mock stale jobs
        stale_jobs = [
            {'job_id': 'job-1', 'pid': 12345},
            {'job_id': 'job-2', 'pid': 67890}
        ]
        
        self.mock_job_queue.get_stale_jobs.return_value = stale_jobs
        
        # Mock process running checks
        with patch.object(self.service, '_is_process_running') as mock_is_running:
            mock_is_running.side_effect = [False, True]  # First job not running, second is
            
            # Mock retry
            self.mock_job_queue.retry_job.return_value = True
            
            self.service._check_stale_jobs()
            
            # Verify retry was called for first job only
            self.mock_job_queue.retry_job.assert_called_once_with('job-1')
    
    def test_cleanup_old_jobs(self):
        """Test cleanup of old jobs."""
        self.mock_job_queue.cleanup_completed_jobs.return_value = 5
        
        self.service._cleanup_old_jobs()
        
        # Verify cleanup was called
        self.mock_job_queue.cleanup_completed_jobs.assert_called_once_with(days_old=30)
    
    def test_get_queue_stats(self):
        """Test getting queue statistics."""
        mock_stats = {'total_jobs': 100, 'pending_jobs': 10}
        self.mock_job_queue.get_queue_stats.return_value = mock_stats
        
        result = self.service.get_queue_stats()
        
        self.assertEqual(result, mock_stats)
    
    def test_submit_job(self):
        """Test job submission."""
        self.mock_job_queue.create_job.return_value = 'job-123'
        
        result = self.service.submit_job(
            dataset_uuid='dataset-123',
            job_type='dataset_conversion',
            parameters={'input_path': '/test/input'},
            priority=1
        )
        
        self.assertEqual(result, 'job-123')
        self.mock_job_queue.create_job.assert_called_once_with(
            'dataset-123', 'dataset_conversion', {'input_path': '/test/input'}, 1
        )


if __name__ == '__main__':
    unittest.main()
