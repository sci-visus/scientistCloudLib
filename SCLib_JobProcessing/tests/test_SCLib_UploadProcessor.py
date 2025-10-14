#!/usr/bin/env python3
"""
Test cases for SC_UploadProcessor module.
Tests upload job processing functionality.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import os
import subprocess
import threading
import time
from datetime import datetime

# Import the module under test
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SCLib_UploadProcessor import SC_UploadProcessor
from SCLib_UploadJobTypes import (
    UploadJobConfig, UploadSourceType, UploadStatus, SensorType
)


class TestSC_UploadProcessor(unittest.TestCase):
    """Test SC_UploadProcessor class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock MongoDB operations before creating processor
        self.mongo_patcher = patch('SC_UploadProcessor.mongo_collection_by_type_context')
        self.mock_mongo_context = self.mongo_patcher.start()
        
        # Create mock collection
        self.mock_collection = MagicMock()
        self.mock_mongo_context.return_value.__enter__.return_value = self.mock_collection
        self.mock_mongo_context.return_value.__exit__.return_value = None
        
        self.processor = SC_UploadProcessor()
        
        # Mock the configuration
        with patch('SC_UploadProcessor.get_config') as mock_config:
            mock_config.return_value = MagicMock()
            self.processor.config = mock_config.return_value
    
    def tearDown(self):
        """Clean up test fixtures."""
        if hasattr(self.processor, 'running') and self.processor.running:
            self.processor.stop()
        
        # Stop the MongoDB patcher
        self.mongo_patcher.stop()
    
    def test_processor_initialization(self):
        """Test processor initialization."""
        self.assertIsNotNone(self.processor.job_manager)
        self.assertIsInstance(self.processor.active_jobs, dict)
        self.assertIsInstance(self.processor.progress_callbacks, dict)
        self.assertFalse(self.processor.running)
        self.assertIsNone(self.processor.worker_thread)
    
    @patch('SC_UploadProcessor.get_collection_by_type')
    def test_submit_upload_job(self, mock_get_collection):
        """Test submitting an upload job."""
        # Mock MongoDB collection
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        
        # Create test job config
        job_config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path=os.path.join(tempfile.mkdtemp(), "test_dataset"),
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        # Submit job
        job_id = self.processor.submit_upload_job(job_config)
        
        # Verify job was created
        self.assertIsNotNone(job_id)
        self.assertIn(job_id, self.processor.job_manager.upload_configs)
        self.assertIn(job_id, self.processor.job_manager.progress_tracking)
        
        # Verify database storage
        self.mock_collection.insert_one.assert_called_once()
        call_args = self.mock_collection.insert_one.call_args[0][0]
        self.assertEqual(call_args['job_id'], job_id)
        self.assertEqual(call_args['job_type'], 'upload')
        self.assertEqual(call_args['source_type'], 'local')
        self.assertEqual(call_args['dataset_uuid'], 'test_dataset_123')
        self.assertEqual(call_args['config']['user_email'], 'user@example.com')
    
    def test_get_job_status(self):
        """Test getting job status."""
        # Create test job config
        job_config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path=os.path.join(tempfile.mkdtemp(), "test_dataset"),
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        # Submit job
        job_id = self.processor.submit_upload_job(job_config)
        
        # Get status
        status = self.processor.get_job_status(job_id)
        
        self.assertIsNotNone(status)
        self.assertEqual(status.job_id, job_id)
        self.assertEqual(status.status, UploadStatus.QUEUED)
        
        # Test non-existent job
        status = self.processor.get_job_status("non_existent_job")
        self.assertIsNone(status)
    
    def test_cancel_job(self):
        """Test canceling an upload job."""
        # Create test job config
        job_config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path=os.path.join(tempfile.mkdtemp(), "test_dataset"),
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        # Submit job
        job_id = self.processor.submit_upload_job(job_config)
        
        # Cancel job
        success = self.processor.cancel_job(job_id)
        
        self.assertTrue(success)
        
        # Verify job was cancelled
        status = self.processor.get_job_status(job_id)
        self.assertEqual(status.status, UploadStatus.CANCELLED)
        
        # Test canceling non-existent job
        success = self.processor.cancel_job("non_existent_job")
        self.assertFalse(success)
    
    @patch('SC_UploadProcessor.get_collection_by_type')
    def test_cancel_job_with_active_process(self, mock_get_collection):
        """Test canceling a job with an active process."""
        # Mock MongoDB collection
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        
        # Create test job config
        job_config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path=os.path.join(tempfile.mkdtemp(), "test_dataset"),
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        # Submit job
        job_id = self.processor.submit_upload_job(job_config)
        
        # Mock an active process
        mock_process = MagicMock()
        mock_process.wait.return_value = 0
        self.processor.active_jobs[job_id] = mock_process
        
        # Cancel job
        success = self.processor.cancel_job(job_id)
        
        self.assertTrue(success)
        
        # Verify process was terminated
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=10)
        
        # Verify job was removed from active jobs
        self.assertNotIn(job_id, self.processor.active_jobs)
    
    @patch('SC_UploadProcessor.get_collection_by_type')
    def test_cancel_job_process_timeout(self, mock_get_collection):
        """Test canceling a job when process termination times out."""
        # Mock MongoDB collection
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        
        # Create test job config
        job_config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path=os.path.join(tempfile.mkdtemp(), "test_dataset"),
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        # Submit job
        job_id = self.processor.submit_upload_job(job_config)
        
        # Mock a process that times out on termination
        mock_process = MagicMock()
        mock_process.wait.side_effect = subprocess.TimeoutExpired("test", 10)
        self.processor.active_jobs[job_id] = mock_process
        
        # Cancel job
        success = self.processor.cancel_job(job_id)
        
        self.assertTrue(success)
        
        # Verify process was terminated and killed
        mock_process.terminate.assert_called_once()
        mock_process.wait.assert_called_once_with(timeout=10)
        mock_process.kill.assert_called_once()
        
        # Verify job was removed from active jobs
        self.assertNotIn(job_id, self.processor.active_jobs)
    
    @patch('os.path.exists')
    @patch('os.path.getsize')
    @patch('pathlib.Path.mkdir')
    def test_process_local_upload(self, mock_mkdir, mock_getsize, mock_exists):
        """Test processing local file upload."""
        # Mock file system
        mock_exists.return_value = True
        mock_getsize.return_value = 1024000
        
        # Create test job config
        job_config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path=os.path.join(tempfile.mkdtemp(), "test_dataset"),
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        # Submit job
        job_id = self.processor.submit_upload_job(job_config)
        
        # Mock rclone availability
        with patch.object(self.processor, '_is_tool_available', return_value=True):
            with patch.object(self.processor, '_upload_with_rclone') as mock_rclone:
                # Process the job
                self.processor._process_upload_job(job_id)
                
                # Verify rclone was called
                mock_rclone.assert_called_once()
                
                # Verify file size was set
                self.assertEqual(job_config.total_size_bytes, 1024000)
    
    @patch('os.path.exists')
    def test_process_local_upload_file_not_found(self, mock_exists):
        """Test processing local upload when file doesn't exist."""
        # Mock file not found
        mock_exists.return_value = False
        
        # Create test job config
        job_config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/nonexistent_file.zip",
            destination_path=os.path.join(tempfile.mkdtemp(), "test_dataset"),
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        # Submit job
        job_id = self.processor.submit_upload_job(job_config)
        
        # Process the job (should fail)
        self.processor._process_upload_job(job_id)
        
        # Verify job failed
        status = self.processor.get_job_status(job_id)
        self.assertEqual(status.status, UploadStatus.FAILED)
        self.assertIn("Source file not found", status.error_message)
    
    def test_process_google_drive_upload(self):
        """Test processing Google Drive upload."""
        # Create test job config
        job_config = UploadJobConfig(
            source_type=UploadSourceType.GOOGLE_DRIVE,
            source_path="1ABC123DEF456",
            destination_path=os.path.join(tempfile.mkdtemp(), "test_dataset"),
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.NETCDF,
            source_config={
                "file_id": "1ABC123DEF456",
                "service_account_file": "/path/to/service.json"
            }
        )
        
        # Submit job
        job_id = self.processor.submit_upload_job(job_config)
        
        # Mock rclone availability
        with patch.object(self.processor, '_is_tool_available', return_value=True):
            with patch.object(self.processor, '_download_from_google_drive') as mock_download:
                # Process the job
                self.processor._process_upload_job(job_id)
                
                # Verify download was called
                mock_download.assert_called_once()
    
    def test_process_google_drive_upload_missing_config(self):
        """Test processing Google Drive upload with missing configuration."""
        # Create test job config with missing source config
        job_config = UploadJobConfig(
            source_type=UploadSourceType.GOOGLE_DRIVE,
            source_path="1ABC123DEF456",
            destination_path=os.path.join(tempfile.mkdtemp(), "test_dataset"),
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.NETCDF,
            source_config={}  # Missing required config
        )
        
        # Submit job
        job_id = self.processor.submit_upload_job(job_config)
        
        # Process the job (should fail)
        self.processor._process_upload_job(job_id)
        
        # Verify job failed
        status = self.processor.get_job_status(job_id)
        self.assertEqual(status.status, UploadStatus.FAILED)
        self.assertIn("Google Drive upload requires", status.error_message)
    
    def test_process_s3_upload(self):
        """Test processing S3 upload."""
        # Create test job config
        job_config = UploadJobConfig(
            source_type=UploadSourceType.S3,
            source_path="s3://my-bucket/data/dataset.zip",
            destination_path=os.path.join(tempfile.mkdtemp(), "test_dataset"),
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.HDF5,
            source_config={
                "bucket_name": "my-bucket",
                "object_key": "data/dataset.zip",
                "access_key_id": "AKIA...",
                "secret_access_key": "secret..."
            }
        )
        
        # Submit job
        job_id = self.processor.submit_upload_job(job_config)
        
        # Mock AWS CLI availability
        with patch.object(self.processor, '_is_tool_available', return_value=True):
            with patch.object(self.processor, '_download_from_s3_aws_cli') as mock_download:
                # Process the job
                self.processor._process_upload_job(job_id)
                
                # Verify download was called
                mock_download.assert_called_once()
    
    def test_process_url_upload(self):
        """Test processing URL upload."""
        # Create test job config
        job_config = UploadJobConfig(
            source_type=UploadSourceType.URL,
            source_path="https://example.com/dataset.zip",
            destination_path=os.path.join(tempfile.mkdtemp(), "test_dataset"),
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.OTHER,
            source_config={
                "url": "https://example.com/dataset.zip"
            }
        )
        
        # Submit job
        job_id = self.processor.submit_upload_job(job_config)
        
        # Mock wget availability
        with patch.object(self.processor, '_is_tool_available', return_value=True):
            with patch.object(self.processor, '_download_with_wget') as mock_download:
                # Process the job
                self.processor._process_upload_job(job_id)
                
                # Verify download was called
                mock_download.assert_called_once()
    
    def test_is_tool_available(self):
        """Test checking tool availability."""
        # Test with available tool
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock()
            mock_run.return_value.returncode = 0
            
            result = self.processor._is_tool_available("test_tool")
            self.assertTrue(result)
            
            mock_run.assert_called_once_with(
                ["test_tool", "--version"],
                capture_output=True,
                check=True,
                timeout=5
            )
        
        # Test with unavailable tool
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError()
            
            result = self.processor._is_tool_available("nonexistent_tool")
            self.assertFalse(result)
    
    def test_create_google_drive_rclone_config(self):
        """Test creating Google Drive rclone configuration."""
        service_account_file = "/path/to/service.json"
        config = self.processor._create_google_drive_rclone_config(service_account_file)
        
        self.assertIn("[gdrive]", config)
        self.assertIn("type = drive", config)
        self.assertIn(f"service_account_file = {service_account_file}", config)
        self.assertIn("scope = drive", config)
    
    @patch('SC_UploadProcessor.get_collection_by_type')
    def test_store_job_in_db(self, mock_get_collection):
        """Test storing job in database."""
        # Mock MongoDB collection
        mock_collection = MagicMock()
        mock_get_collection.return_value = mock_collection
        
        # Create test job config
        job_config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path=os.path.join(tempfile.mkdtemp(), "test_dataset"),
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        # Store job
        self.processor._store_job_in_db("test_job_123", job_config)
        
        # Verify database call
        self.mock_collection.insert_one.assert_called_once()
        call_args = self.mock_collection.insert_one.call_args[0][0]
        self.assertEqual(call_args['job_id'], "test_job_123")
        self.assertEqual(call_args['job_type'], 'upload')
        self.assertEqual(call_args['source_type'], 'local')
        self.assertEqual(call_args['dataset_uuid'], 'test_dataset_123')
        # user_email is stored in config section
        self.assertEqual(call_args['config']['user_email'], 'user@example.com')
    
    def test_get_queued_jobs(self):
        """Test getting queued jobs from database."""
        # Mock database query result
        self.mock_collection.find.return_value = [
            {"job_id": "job_1"},
            {"job_id": "job_2"},
            {"job_id": "job_3"}
        ]
        
        # Get queued jobs
        jobs = self.processor._get_queued_jobs()
        
        # Verify result
        self.assertEqual(jobs, ["job_1", "job_2", "job_3"])
        
        # Verify database query
        self.mock_collection.find.assert_called_once_with({
            "job_type": "upload",
            "status": "queued"
        }, {"job_id": 1})
    
    def test_update_job_in_db(self):
        """Test updating job in database."""
        # Update job
        update_data = {
            "status": "uploading",
            "progress_percentage": 50.0,
            "updated_at": datetime.utcnow()
        }
        self.processor._update_job_in_db("test_job_123", update_data)
        
        # Verify database call
        self.mock_collection.update_one.assert_called_once_with(
            {"job_id": "test_job_123"},
            {"$set": update_data}
        )
    
    def test_update_job_status(self):
        """Test updating job status."""
        # Create test job config
        job_config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path=os.path.join(tempfile.mkdtemp(), "test_dataset"),
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        # Submit job
        job_id = self.processor.submit_upload_job(job_config)
        
        # Update status
        with patch.object(self.processor, '_update_job_in_db') as mock_update_db:
            self.processor._update_job_status(job_id, UploadStatus.UPLOADING, "Test error")
            
            # Verify status was updated
            status = self.processor.get_job_status(job_id)
            self.assertEqual(status.status, UploadStatus.UPLOADING)
            self.assertEqual(status.error_message, "Test error")
            
            # Verify database was updated
            mock_update_db.assert_called_once()
    
    def test_update_job_progress(self):
        """Test updating job progress."""
        # Create test job config
        job_config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path=os.path.join(tempfile.mkdtemp(), "test_dataset"),
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        # Submit job
        job_id = self.processor.submit_upload_job(job_config)
        
        # Update progress
        with patch.object(self.processor, '_update_job_in_db') as mock_update_db:
            self.processor._update_job_progress(job_id, 75.0, 1500000, 2000000)
            
            # Verify progress was updated
            status = self.processor.get_job_status(job_id)
            self.assertEqual(status.progress_percentage, 75.0)
            self.assertEqual(status.bytes_uploaded, 1500000)
            self.assertEqual(status.bytes_total, 2000000)
            
            # Verify database was updated
            mock_update_db.assert_called_once()


# The TestSC_UploadProcessor class is already defined above


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
