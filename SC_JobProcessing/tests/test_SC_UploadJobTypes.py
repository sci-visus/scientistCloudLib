#!/usr/bin/env python3
"""
Test cases for SC_UploadJobTypes module.
Tests upload job type definitions, sensor types, and configurations.
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from typing import Dict, Any

# Import the module under test
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SC_UploadJobTypes import (
    UploadSourceType, UploadStatus, SensorType, UploadJobConfig,
    UploadProgress, UploadJobManager, get_tool_config,
    create_upload_job_config, create_local_upload_job,
    create_google_drive_upload_job, create_s3_upload_job,
    create_url_upload_job
)


class TestUploadSourceType(unittest.TestCase):
    """Test upload source type enum."""
    
    def test_upload_source_type_values(self):
        """Test that all expected source types are defined."""
        expected_types = ['local', 'google_drive', 's3', 'url', 'dropbox', 'onedrive']
        actual_types = [source_type.value for source_type in UploadSourceType]
        
        for expected_type in expected_types:
            self.assertIn(expected_type, actual_types)
    
    def test_upload_source_type_enum(self):
        """Test enum functionality."""
        self.assertEqual(UploadSourceType.LOCAL.value, 'local')
        self.assertEqual(UploadSourceType.GOOGLE_DRIVE.value, 'google_drive')
        self.assertEqual(UploadSourceType.S3.value, 's3')
        self.assertEqual(UploadSourceType.URL.value, 'url')


class TestUploadStatus(unittest.TestCase):
    """Test upload status enum."""
    
    def test_upload_status_values(self):
        """Test that all expected statuses are defined."""
        expected_statuses = [
            'queued', 'initializing', 'uploading', 'processing',
            'verifying', 'completed', 'failed', 'cancelled', 'paused'
        ]
        actual_statuses = [status.value for status in UploadStatus]
        
        for expected_status in expected_statuses:
            self.assertIn(expected_status, actual_statuses)
    
    def test_upload_status_enum(self):
        """Test enum functionality."""
        self.assertEqual(UploadStatus.QUEUED.value, 'queued')
        self.assertEqual(UploadStatus.UPLOADING.value, 'uploading')
        self.assertEqual(UploadStatus.COMPLETED.value, 'completed')
        self.assertEqual(UploadStatus.FAILED.value, 'failed')


class TestSensorType(unittest.TestCase):
    """Test sensor type enum."""
    
    def test_sensor_type_values(self):
        """Test that all expected sensor types are defined."""
        expected_sensors = [
            'IDX', 'TIFF', 'TIFF RGB', 'NETCDF', 'HDF5',
            '4D_NEXUS', 'RGB', 'MAPIR', 'OTHER'
        ]
        actual_sensors = [sensor.value for sensor in SensorType]
        
        for expected_sensor in expected_sensors:
            self.assertIn(expected_sensor, actual_sensors)
    
    def test_sensor_type_enum(self):
        """Test enum functionality."""
        self.assertEqual(SensorType.IDX.value, 'IDX')
        self.assertEqual(SensorType.TIFF.value, 'TIFF')
        self.assertEqual(SensorType.TIFF_RGB.value, 'TIFF RGB')
        self.assertEqual(SensorType.NETCDF.value, 'NETCDF')
        self.assertEqual(SensorType.HDF5.value, 'HDF5')
        self.assertEqual(SensorType.NEXUS_4D.value, '4D_NEXUS')
        self.assertEqual(SensorType.RGB.value, 'RGB')
        self.assertEqual(SensorType.MAPIR.value, 'MAPIR')
        self.assertEqual(SensorType.OTHER.value, 'OTHER')


class TestUploadJobConfig(unittest.TestCase):
    """Test upload job configuration."""
    
    def test_upload_job_config_creation(self):
        """Test creating an upload job configuration."""
        config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path="/mnt/visus_datasets/upload/test_dataset",
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF,
            convert=True,
            is_public=False,
            folder="test_folder",
            team_uuid="team_123"
        )
        
        self.assertEqual(config.source_type, UploadSourceType.LOCAL)
        self.assertEqual(config.source_path, "/tmp/test_file.zip")
        self.assertEqual(config.destination_path, "/mnt/visus_datasets/upload/test_dataset")
        self.assertEqual(config.dataset_uuid, "test_dataset_123")
        self.assertEqual(config.user_email, "user@example.com")
        self.assertEqual(config.dataset_name, "Test Dataset")
        self.assertEqual(config.sensor, SensorType.TIFF)
        self.assertTrue(config.convert)
        self.assertFalse(config.is_public)
        self.assertEqual(config.folder, "test_folder")
        self.assertEqual(config.team_uuid, "team_123")
    
    def test_upload_job_config_defaults(self):
        """Test upload job configuration defaults."""
        config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path="/mnt/visus_datasets/upload/test_dataset",
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.OTHER
        )
        
        # Test defaults
        self.assertTrue(config.convert)
        self.assertFalse(config.is_public)
        self.assertIsNone(config.folder)
        self.assertIsNone(config.team_uuid)
        self.assertEqual(config.chunk_size_mb, 64)
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.retry_delay_seconds, 30)
        self.assertEqual(config.timeout_minutes, 120)
        self.assertTrue(config.auto_convert)
        self.assertTrue(config.auto_extract)
        self.assertTrue(config.verify_checksum)
        self.assertEqual(config.total_size_bytes, 0)
        self.assertEqual(config.uploaded_bytes, 0)
        self.assertEqual(config.progress_percentage, 0.0)
        self.assertEqual(config.retry_count, 0)
        self.assertEqual(config.error_message, "")


class TestUploadProgress(unittest.TestCase):
    """Test upload progress tracking."""
    
    def test_upload_progress_creation(self):
        """Test creating upload progress."""
        progress = UploadProgress(
            job_id="upload_12345",
            status=UploadStatus.UPLOADING,
            progress_percentage=45.2,
            bytes_uploaded=1024000,
            bytes_total=2264000,
            speed_mbps=12.5,
            eta_seconds=120,
            current_file="dataset.zip"
        )
        
        self.assertEqual(progress.job_id, "upload_12345")
        self.assertEqual(progress.status, UploadStatus.UPLOADING)
        self.assertEqual(progress.progress_percentage, 45.2)
        self.assertEqual(progress.bytes_uploaded, 1024000)
        self.assertEqual(progress.bytes_total, 2264000)
        self.assertEqual(progress.speed_mbps, 12.5)
        self.assertEqual(progress.eta_seconds, 120)
        self.assertEqual(progress.current_file, "dataset.zip")
        self.assertEqual(progress.error_message, "")
    
    def test_upload_progress_defaults(self):
        """Test upload progress defaults."""
        progress = UploadProgress(
            job_id="upload_12345",
            status=UploadStatus.QUEUED,
            progress_percentage=0.0,
            bytes_uploaded=0,
            bytes_total=0,
            speed_mbps=0.0,
            eta_seconds=0
        )
        
        self.assertEqual(progress.current_file, "")
        self.assertEqual(progress.error_message, "")


class TestUploadJobManager(unittest.TestCase):
    """Test upload job manager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = UploadJobManager()
    
    def test_create_upload_job(self):
        """Test creating an upload job."""
        config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path="/mnt/visus_datasets/upload/test_dataset",
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        job_id = self.manager.create_upload_job("test_job_123", config)
        
        self.assertEqual(job_id, "test_job_123")
        self.assertIn("test_job_123", self.manager.upload_configs)
        self.assertIn("test_job_123", self.manager.progress_tracking)
        
        # Check progress tracking
        progress = self.manager.progress_tracking["test_job_123"]
        self.assertEqual(progress.job_id, "test_job_123")
        self.assertEqual(progress.status, UploadStatus.QUEUED)
        self.assertEqual(progress.progress_percentage, 0.0)
    
    def test_update_progress(self):
        """Test updating upload progress."""
        config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path="/mnt/visus_datasets/upload/test_dataset",
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        self.manager.create_upload_job("test_job_123", config)
        
        new_progress = UploadProgress(
            job_id="test_job_123",
            status=UploadStatus.UPLOADING,
            progress_percentage=50.0,
            bytes_uploaded=1000000,
            bytes_total=2000000,
            speed_mbps=10.0,
            eta_seconds=60
        )
        
        self.manager.update_progress("test_job_123", new_progress)
        
        progress = self.manager.get_progress("test_job_123")
        self.assertEqual(progress.status, UploadStatus.UPLOADING)
        self.assertEqual(progress.progress_percentage, 50.0)
        self.assertEqual(progress.bytes_uploaded, 1000000)
    
    def test_get_progress(self):
        """Test getting upload progress."""
        config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path="/mnt/visus_datasets/upload/test_dataset",
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        self.manager.create_upload_job("test_job_123", config)
        
        progress = self.manager.get_progress("test_job_123")
        self.assertIsNotNone(progress)
        self.assertEqual(progress.job_id, "test_job_123")
        
        # Test non-existent job
        progress = self.manager.get_progress("non_existent_job")
        self.assertIsNone(progress)
    
    def test_get_job_config(self):
        """Test getting job configuration."""
        config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path="/mnt/visus_datasets/upload/test_dataset",
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        self.manager.create_upload_job("test_job_123", config)
        
        retrieved_config = self.manager.get_job_config("test_job_123")
        self.assertIsNotNone(retrieved_config)
        self.assertEqual(retrieved_config.dataset_uuid, "test_dataset_123")
        self.assertEqual(retrieved_config.user_email, "user@example.com")
        
        # Test non-existent job
        retrieved_config = self.manager.get_job_config("non_existent_job")
        self.assertIsNone(retrieved_config)
    
    def test_cancel_job(self):
        """Test canceling an upload job."""
        config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path="/mnt/visus_datasets/upload/test_dataset",
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        self.manager.create_upload_job("test_job_123", config)
        
        success = self.manager.cancel_job("test_job_123")
        self.assertTrue(success)
        
        progress = self.manager.get_progress("test_job_123")
        self.assertEqual(progress.status, UploadStatus.CANCELLED)
        
        # Test canceling non-existent job
        success = self.manager.cancel_job("non_existent_job")
        self.assertFalse(success)
    
    def test_pause_resume_job(self):
        """Test pausing and resuming an upload job."""
        config = UploadJobConfig(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path="/mnt/visus_datasets/upload/test_dataset",
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF
        )
        
        self.manager.create_upload_job("test_job_123", config)
        
        # Pause job
        success = self.manager.pause_job("test_job_123")
        self.assertTrue(success)
        
        progress = self.manager.get_progress("test_job_123")
        self.assertEqual(progress.status, UploadStatus.PAUSED)
        
        # Resume job
        success = self.manager.resume_job("test_job_123")
        self.assertTrue(success)
        
        progress = self.manager.get_progress("test_job_123")
        self.assertEqual(progress.status, UploadStatus.UPLOADING)
        
        # Test resuming non-paused job
        success = self.manager.resume_job("test_job_123")
        self.assertFalse(success)


class TestToolConfig(unittest.TestCase):
    """Test tool configuration."""
    
    def test_get_tool_config(self):
        """Test getting tool configuration for different source types."""
        # Test local source type
        config = get_tool_config(UploadSourceType.LOCAL)
        self.assertIn('primary_tool', config)
        self.assertIn('fallback_tool', config)
        self.assertIn('chunk_size_mb', config)
        self.assertIn('max_retries', config)
        self.assertIn('resume_support', config)
        
        # Test Google Drive source type
        config = get_tool_config(UploadSourceType.GOOGLE_DRIVE)
        self.assertIn('primary_tool', config)
        self.assertIn('fallback_tool', config)
        
        # Test S3 source type
        config = get_tool_config(UploadSourceType.S3)
        self.assertIn('primary_tool', config)
        self.assertIn('fallback_tool', config)
        
        # Test URL source type
        config = get_tool_config(UploadSourceType.URL)
        self.assertIn('primary_tool', config)
        self.assertIn('fallback_tool', config)
    
    def test_tool_config_values(self):
        """Test specific tool configuration values."""
        # Test local configuration
        config = get_tool_config(UploadSourceType.LOCAL)
        self.assertEqual(config['primary_tool'], 'rclone')
        self.assertEqual(config['fallback_tool'], 'rsync')
        self.assertEqual(config['chunk_size_mb'], 64)
        self.assertEqual(config['max_retries'], 3)
        self.assertTrue(config['resume_support'])
        
        # Test Google Drive configuration
        config = get_tool_config(UploadSourceType.GOOGLE_DRIVE)
        self.assertEqual(config['primary_tool'], 'rclone')
        self.assertEqual(config['fallback_tool'], 'gdrive')
        self.assertEqual(config['chunk_size_mb'], 32)
        self.assertEqual(config['max_retries'], 5)
        self.assertTrue(config['resume_support'])


class TestUploadJobCreationFunctions(unittest.TestCase):
    """Test upload job creation helper functions."""
    
    def test_create_upload_job_config(self):
        """Test creating upload job configuration."""
        config = create_upload_job_config(
            source_type=UploadSourceType.LOCAL,
            source_path="/tmp/test_file.zip",
            destination_path="/mnt/visus_datasets/upload/test_dataset",
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF,
            convert=True,
            is_public=False,
            folder="test_folder",
            team_uuid="team_123"
        )
        
        self.assertEqual(config.source_type, UploadSourceType.LOCAL)
        self.assertEqual(config.source_path, "/tmp/test_file.zip")
        self.assertEqual(config.destination_path, "/mnt/visus_datasets/upload/test_dataset")
        self.assertEqual(config.dataset_uuid, "test_dataset_123")
        self.assertEqual(config.user_email, "user@example.com")
        self.assertEqual(config.dataset_name, "Test Dataset")
        self.assertEqual(config.sensor, SensorType.TIFF)
        self.assertTrue(config.convert)
        self.assertFalse(config.is_public)
        self.assertEqual(config.folder, "test_folder")
        self.assertEqual(config.team_uuid, "team_123")
    
    def test_create_local_upload_job(self):
        """Test creating local upload job."""
        config = create_local_upload_job(
            file_path="/tmp/test_file.zip",
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.TIFF,
            convert=True,
            is_public=False,
            folder="test_folder",
            team_uuid="team_123"
        )
        
        self.assertEqual(config.source_type, UploadSourceType.LOCAL)
        self.assertEqual(config.source_path, "/tmp/test_file.zip")
        self.assertEqual(config.destination_path, "/mnt/visus_datasets/upload/test_dataset_123")
        self.assertEqual(config.dataset_uuid, "test_dataset_123")
        self.assertEqual(config.user_email, "user@example.com")
        self.assertEqual(config.dataset_name, "Test Dataset")
        self.assertEqual(config.sensor, SensorType.TIFF)
        self.assertTrue(config.convert)
        self.assertFalse(config.is_public)
        self.assertEqual(config.folder, "test_folder")
        self.assertEqual(config.team_uuid, "team_123")
    
    def test_create_google_drive_upload_job(self):
        """Test creating Google Drive upload job."""
        config = create_google_drive_upload_job(
            file_id="1ABC123DEF456",
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.NETCDF,
            service_account_file="/path/to/service.json",
            convert=False,
            is_public=True,
            folder="cloud_data",
            team_uuid="team_456"
        )
        
        self.assertEqual(config.source_type, UploadSourceType.GOOGLE_DRIVE)
        self.assertEqual(config.source_path, "1ABC123DEF456")
        self.assertEqual(config.destination_path, "/mnt/visus_datasets/upload/test_dataset_123")
        self.assertEqual(config.dataset_uuid, "test_dataset_123")
        self.assertEqual(config.user_email, "user@example.com")
        self.assertEqual(config.dataset_name, "Test Dataset")
        self.assertEqual(config.sensor, SensorType.NETCDF)
        self.assertFalse(config.convert)
        self.assertTrue(config.is_public)
        self.assertEqual(config.folder, "cloud_data")
        self.assertEqual(config.team_uuid, "team_456")
        
        # Check source config
        self.assertIn('service_account_file', config.source_config)
        self.assertIn('file_id', config.source_config)
        self.assertEqual(config.source_config['service_account_file'], "/path/to/service.json")
        self.assertEqual(config.source_config['file_id'], "1ABC123DEF456")
    
    def test_create_s3_upload_job(self):
        """Test creating S3 upload job."""
        config = create_s3_upload_job(
            bucket_name="my-bucket",
            object_key="data/dataset.zip",
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.HDF5,
            access_key_id="AKIA...",
            secret_access_key="secret...",
            convert=True,
            is_public=False,
            folder="s3_imports",
            team_uuid="team_789"
        )
        
        self.assertEqual(config.source_type, UploadSourceType.S3)
        self.assertEqual(config.source_path, "s3://my-bucket/data/dataset.zip")
        self.assertEqual(config.destination_path, "/mnt/visus_datasets/upload/test_dataset_123")
        self.assertEqual(config.dataset_uuid, "test_dataset_123")
        self.assertEqual(config.user_email, "user@example.com")
        self.assertEqual(config.dataset_name, "Test Dataset")
        self.assertEqual(config.sensor, SensorType.HDF5)
        self.assertTrue(config.convert)
        self.assertFalse(config.is_public)
        self.assertEqual(config.folder, "s3_imports")
        self.assertEqual(config.team_uuid, "team_789")
        
        # Check source config
        self.assertIn('bucket_name', config.source_config)
        self.assertIn('object_key', config.source_config)
        self.assertIn('access_key_id', config.source_config)
        self.assertIn('secret_access_key', config.source_config)
        self.assertEqual(config.source_config['bucket_name'], "my-bucket")
        self.assertEqual(config.source_config['object_key'], "data/dataset.zip")
        self.assertEqual(config.source_config['access_key_id'], "AKIA...")
        self.assertEqual(config.source_config['secret_access_key'], "secret...")
    
    def test_create_url_upload_job(self):
        """Test creating URL upload job."""
        config = create_url_upload_job(
            url="https://example.com/dataset.zip",
            dataset_uuid="test_dataset_123",
            user_email="user@example.com",
            dataset_name="Test Dataset",
            sensor=SensorType.OTHER,
            convert=True,
            is_public=False
        )
        
        self.assertEqual(config.source_type, UploadSourceType.URL)
        self.assertEqual(config.source_path, "https://example.com/dataset.zip")
        self.assertEqual(config.destination_path, "/mnt/visus_datasets/upload/test_dataset_123")
        self.assertEqual(config.dataset_uuid, "test_dataset_123")
        self.assertEqual(config.user_email, "user@example.com")
        self.assertEqual(config.dataset_name, "Test Dataset")
        self.assertEqual(config.sensor, SensorType.OTHER)
        self.assertTrue(config.convert)
        self.assertFalse(config.is_public)
        self.assertIsNone(config.folder)
        self.assertIsNone(config.team_uuid)
        
        # Check source config
        self.assertIn('url', config.source_config)
        self.assertEqual(config.source_config['url'], "https://example.com/dataset.zip")


class TestSC_UploadJobTypes(unittest.TestCase):
    """Combined test suite for all SC_UploadJobTypes tests."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create test suite with all test classes
        self.test_suite = unittest.TestSuite()
        
        # Add all test classes
        test_classes = [
            TestUploadSourceType,
            TestUploadStatus,
            TestSensorType,
            TestUploadJobConfig,
            TestUploadProgress,
            TestUploadJobManager,
            TestToolConfig,
            TestUploadJobCreationFunctions
        ]
        
        for test_class in test_classes:
            tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
            self.test_suite.addTests(tests)
    
    def test_all_upload_job_types(self):
        """Run all upload job types tests."""
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(self.test_suite)
        
        # Assert that all tests passed
        self.assertEqual(len(result.failures), 0, f"Test failures: {result.failures}")
        self.assertEqual(len(result.errors), 0, f"Test errors: {result.errors}")


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
