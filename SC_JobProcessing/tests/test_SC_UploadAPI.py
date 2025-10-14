#!/usr/bin/env python3
"""
Test cases for SC_UploadAPI module.
Tests the RESTful API endpoints for upload operations.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import tempfile
import os
from io import BytesIO

# Import the module under test
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SC_UploadAPI import app
from SC_UploadJobTypes import UploadSourceType, SensorType


class TestSC_UploadAPI(unittest.TestCase):
    """Test SC_UploadAPI Flask application."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.app = app.test_client()
        self.app.testing = True
    
    def test_health_check(self):
        """Test upload health check endpoint."""
        with patch('SC_UploadAPI.upload_processor') as mock_processor:
            mock_processor.running = True
            
            with patch('SC_UploadAPI._check_available_tools') as mock_tools:
                mock_tools.return_value = {
                    'rclone': True,
                    'rsync': True,
                    'aws': True,
                    'wget': True,
                    'curl': True
                }
                
                response = self.app.get('/api/upload/health')
                
                self.assertEqual(response.status_code, 200)
                data = json.loads(response.data)
                self.assertEqual(data['status'], 'healthy')
                self.assertEqual(data['processor_status'], 'running')
                self.assertIn('available_tools', data)
    
    def test_get_supported_sources(self):
        """Test getting supported upload sources."""
        response = self.app.get('/api/upload/supported-sources')
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        
        # Check that all expected sources are present
        source_types = [source['type'] for source in data['sources']]
        expected_types = ['local', 'google_drive', 's3', 'url']
        for expected_type in expected_types:
            self.assertIn(expected_type, source_types)
        
        # Check that sensor types are included
        self.assertIn('sensor_types', data)
        expected_sensors = ['IDX', 'TIFF', 'TIFF RGB', 'NETCDF', 'HDF5', '4D_NEXUS', 'RGB', 'MAPIR', 'OTHER']
        for expected_sensor in expected_sensors:
            self.assertIn(expected_sensor, data['sensor_types'])
        
        # Check required parameters
        self.assertIn('required_parameters', data)
        required_params = list(data['required_parameters'].keys())
        expected_required = ['user_email', 'dataset_name', 'sensor', 'convert', 'is_public']
        for expected_param in expected_required:
            self.assertIn(expected_param, required_params)
    
    def test_initiate_upload_missing_fields(self):
        """Test initiating upload with missing required fields."""
        # Test with missing user_email
        data = {
            "source_type": "url",
            "source_config": {"url": "https://example.com/file.zip"},
            "dataset_name": "Test Dataset",
            "sensor": "TIFF",
            "convert": True,
            "is_public": False
        }
        
        response = self.app.post('/api/upload/initiate',
                               data=json.dumps(data),
                               content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('Missing required field: user_email', response_data['error'])
    
    def test_initiate_upload_invalid_sensor(self):
        """Test initiating upload with invalid sensor type."""
        data = {
            "source_type": "url",
            "source_config": {"url": "https://example.com/file.zip"},
            "user_email": "user@example.com",
            "dataset_name": "Test Dataset",
            "sensor": "INVALID_SENSOR",
            "convert": True,
            "is_public": False
        }
        
        response = self.app.post('/api/upload/initiate',
                               data=json.dumps(data),
                               content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('Invalid sensor type', response_data['error'])
    
    def test_initiate_upload_unsupported_source_type(self):
        """Test initiating upload with unsupported source type."""
        data = {
            "source_type": "unsupported_source",
            "source_config": {},
            "user_email": "user@example.com",
            "dataset_name": "Test Dataset",
            "sensor": "TIFF",
            "convert": True,
            "is_public": False
        }
        
        response = self.app.post('/api/upload/initiate',
                               data=json.dumps(data),
                               content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('Invalid source type', response_data['error'])
    
    @patch('SC_UploadAPI.upload_processor')
    def test_initiate_google_drive_upload(self, mock_processor):
        """Test initiating Google Drive upload."""
        mock_processor.submit_upload_job.return_value = "upload_12345"
        
        data = {
            "source_type": "google_drive",
            "source_config": {
                "file_id": "1ABC123DEF456",
                "service_account_file": "/path/to/service.json"
            },
            "user_email": "user@example.com",
            "dataset_name": "Google Drive Dataset",
            "sensor": "NETCDF",
            "convert": False,
            "is_public": True,
            "folder": "cloud_data",
            "team_uuid": "team_456"
        }
        
        response = self.app.post('/api/upload/initiate',
                               data=json.dumps(data),
                               content_type='application/json')
        
        self.assertEqual(response.status_code, 202)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['job_id'], 'upload_12345')
        self.assertIn('dataset_uuid', response_data)
        self.assertEqual(response_data['status'], 'queued')
        self.assertIn('progress_url', response_data)
        self.assertIn('cancel_url', response_data)
        
        # Verify job was submitted
        mock_processor.submit_upload_job.assert_called_once()
    
    @patch('SC_UploadAPI.upload_processor')
    def test_initiate_s3_upload(self, mock_processor):
        """Test initiating S3 upload."""
        mock_processor.submit_upload_job.return_value = "upload_67890"
        
        data = {
            "source_type": "s3",
            "source_config": {
                "bucket_name": "my-bucket",
                "object_key": "data/dataset.zip",
                "access_key_id": "AKIA...",
                "secret_access_key": "secret..."
            },
            "user_email": "user@example.com",
            "dataset_name": "S3 Dataset",
            "sensor": "HDF5",
            "convert": True,
            "is_public": False,
            "folder": "s3_imports"
        }
        
        response = self.app.post('/api/upload/initiate',
                               data=json.dumps(data),
                               content_type='application/json')
        
        self.assertEqual(response.status_code, 202)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['job_id'], 'upload_67890')
        self.assertIn('dataset_uuid', response_data)
        self.assertEqual(response_data['status'], 'queued')
        
        # Verify job was submitted
        mock_processor.submit_upload_job.assert_called_once()
    
    @patch('SC_UploadAPI.upload_processor')
    def test_initiate_url_upload(self, mock_processor):
        """Test initiating URL upload."""
        mock_processor.submit_upload_job.return_value = "upload_11111"
        
        data = {
            "source_type": "url",
            "source_config": {
                "url": "https://example.com/dataset.zip"
            },
            "user_email": "user@example.com",
            "dataset_name": "URL Dataset",
            "sensor": "OTHER",
            "convert": True,
            "is_public": False
        }
        
        response = self.app.post('/api/upload/initiate',
                               data=json.dumps(data),
                               content_type='application/json')
        
        self.assertEqual(response.status_code, 202)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['job_id'], 'upload_11111')
        self.assertIn('dataset_uuid', response_data)
        self.assertEqual(response_data['status'], 'queued')
        
        # Verify job was submitted
        mock_processor.submit_upload_job.assert_called_once()
    
    def test_upload_local_file_missing_file(self):
        """Test local file upload with missing file."""
        response = self.app.post('/api/upload/local/upload')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('No file provided', response_data['error'])
    
    def test_upload_local_file_missing_required_fields(self):
        """Test local file upload with missing required fields."""
        # Create a test file
        test_file = BytesIO(b"test file content")
        
        # Test with missing user_email
        response = self.app.post('/api/upload/local/upload',
                               data={
                                   'file': (test_file, 'test.txt'),
                                   'dataset_name': 'Test Dataset',
                                   'sensor': 'TIFF',
                                   'convert': 'true',
                                   'is_public': 'false'
                               })
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('user_email is required', response_data['error'])
    
    def test_upload_local_file_invalid_sensor(self):
        """Test local file upload with invalid sensor type."""
        test_file = BytesIO(b"test file content")
        
        response = self.app.post('/api/upload/local/upload',
                               data={
                                   'file': (test_file, 'test.txt'),
                                   'user_email': 'user@example.com',
                                   'dataset_name': 'Test Dataset',
                                   'sensor': 'INVALID_SENSOR',
                                   'convert': 'true',
                                   'is_public': 'false'
                               })
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('Invalid sensor type', response_data['error'])
    
    def test_upload_local_file_invalid_boolean(self):
        """Test local file upload with invalid boolean values."""
        test_file = BytesIO(b"test file content")
        
        response = self.app.post('/api/upload/local/upload',
                               data={
                                   'file': (test_file, 'test.txt'),
                                   'user_email': 'user@example.com',
                                   'dataset_name': 'Test Dataset',
                                   'sensor': 'TIFF',
                                   'convert': 'invalid_boolean',
                                   'is_public': 'false'
                               })
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('convert and is_public must be boolean values', response_data['error'])
    
    @patch('SC_UploadAPI.upload_processor')
    @patch('tempfile.mkdtemp')
    @patch('builtins.open', new_callable=mock_open)
    def test_upload_local_file_success(self, mock_file, mock_mkdtemp, mock_processor):
        """Test successful local file upload."""
        # Mock temporary directory
        mock_mkdtemp.return_value = "/tmp/test_upload_dir"
        
        # Mock processor
        mock_processor.submit_upload_job.return_value = "upload_local_123"
        
        # Create test file
        test_file = BytesIO(b"test file content")
        
        response = self.app.post('/api/upload/local/upload',
                               data={
                                   'file': (test_file, 'test.txt'),
                                   'user_email': 'user@example.com',
                                   'dataset_name': 'Test Dataset',
                                   'sensor': 'TIFF',
                                   'convert': 'true',
                                   'is_public': 'false',
                                   'folder': 'test_folder',
                                   'team_uuid': 'team_123'
                               })
        
        self.assertEqual(response.status_code, 202)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['job_id'], 'upload_local_123')
        self.assertIn('dataset_uuid', response_data)
        self.assertEqual(response_data['status'], 'queued')
        self.assertIn('progress_url', response_data)
        self.assertIn('cancel_url', response_data)
        
        # Verify job was submitted
        mock_processor.submit_upload_job.assert_called_once()
    
    @patch('SC_UploadAPI.upload_processor')
    def test_get_upload_status(self, mock_processor):
        """Test getting upload status."""
        from SC_UploadJobTypes import UploadProgress, UploadStatus
        
        # Mock progress object
        mock_progress = UploadProgress(
            job_id="upload_12345",
            status=UploadStatus.UPLOADING,
            progress_percentage=45.2,
            bytes_uploaded=1024000,
            bytes_total=2264000,
            speed_mbps=12.5,
            eta_seconds=120,
            current_file="dataset.zip"
        )
        
        mock_processor.get_job_status.return_value = mock_progress
        
        response = self.app.get('/api/upload/status/upload_12345')
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['job_id'], 'upload_12345')
        self.assertEqual(response_data['status'], 'uploading')
        self.assertEqual(response_data['progress_percentage'], 45.2)
        self.assertEqual(response_data['bytes_uploaded'], 1024000)
        self.assertEqual(response_data['bytes_total'], 2264000)
        self.assertEqual(response_data['speed_mbps'], 12.5)
        self.assertEqual(response_data['eta_seconds'], 120)
        self.assertEqual(response_data['current_file'], 'dataset.zip')
    
    @patch('SC_UploadAPI.upload_processor')
    def test_get_upload_status_not_found(self, mock_processor):
        """Test getting upload status for non-existent job."""
        mock_processor.get_job_status.return_value = None
        
        response = self.app.get('/api/upload/status/non_existent_job')
        
        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.data)
        self.assertIn('Job not found', response_data['error'])
    
    @patch('SC_UploadAPI.upload_processor')
    def test_cancel_upload(self, mock_processor):
        """Test canceling an upload."""
        mock_processor.cancel_job.return_value = True
        
        response = self.app.post('/api/upload/cancel/upload_12345')
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['job_id'], 'upload_12345')
        self.assertEqual(response_data['status'], 'cancelled')
        self.assertIn('cancelled successfully', response_data['message'])
        
        # Verify cancel was called
        mock_processor.cancel_job.assert_called_once_with('upload_12345')
    
    @patch('SC_UploadAPI.upload_processor')
    def test_cancel_upload_not_found(self, mock_processor):
        """Test canceling a non-existent upload."""
        mock_processor.cancel_job.return_value = False
        
        response = self.app.post('/api/upload/cancel/non_existent_job')
        
        self.assertEqual(response.status_code, 404)
        response_data = json.loads(response.data)
        self.assertIn('Job not found or already completed', response_data['error'])
    
    @patch('SC_MongoConnection.execute_collection_query')
    def test_list_upload_jobs(self, mock_execute_query):
        """Test listing upload jobs."""
        # Mock database query result
        mock_execute_query.return_value = [
            {
                'job_id': 'upload_1',
                'dataset_uuid': 'dataset_1',
                'source_type': 'local',
                'status': 'completed',
                'created_at': '2023-01-01T00:00:00Z'
            },
            {
                'job_id': 'upload_2',
                'dataset_uuid': 'dataset_2',
                'source_type': 'google_drive',
                'status': 'uploading',
                'created_at': '2023-01-02T00:00:00Z'
            }
        ]
        
        response = self.app.get('/api/upload/jobs?user_id=user@example.com')
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        
        self.assertIn('jobs', response_data)
        self.assertEqual(len(response_data['jobs']), 2)
        self.assertEqual(response_data['jobs'][0]['job_id'], 'upload_1')
        self.assertEqual(response_data['jobs'][1]['job_id'], 'upload_2')
        self.assertIn('progress_url', response_data['jobs'][0])
        self.assertIn('cancel_url', response_data['jobs'][0])
    
    def test_list_upload_jobs_missing_user_id(self):
        """Test listing upload jobs without user_id."""
        response = self.app.get('/api/upload/jobs')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('user_id (user_email) is required', response_data['error'])
    
    def test_estimate_upload_time(self):
        """Test upload time estimation."""
        data = {
            "source_type": "local",
            "source_config": {}
        }
        
        response = self.app.post('/api/upload/estimate',
                               data=json.dumps(data),
                               content_type='application/json')
        
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.data)
        self.assertEqual(response_data['source_type'], 'local')
        self.assertIn('estimated_time_minutes', response_data)
        self.assertIn('estimated_time_human', response_data)
    
    def test_estimate_upload_time_missing_source_type(self):
        """Test upload time estimation with missing source type."""
        data = {
            "source_config": {}
        }
        
        response = self.app.post('/api/upload/estimate',
                               data=json.dumps(data),
                               content_type='application/json')
        
        self.assertEqual(response.status_code, 400)
        response_data = json.loads(response.data)
        self.assertIn('source_type is required', response_data['error'])
    
    def test_error_handlers(self):
        """Test error handlers."""
        # Test 400 error handler - POST with missing data
        response = self.app.post('/api/upload/initiate',
                               data=json.dumps({}),
                               content_type='application/json')
        self.assertEqual(response.status_code, 400)
        
        # Test 500 error handler (simulated)
        with patch('SC_UploadAPI.upload_processor') as mock_processor:
            mock_processor.submit_upload_job.side_effect = Exception("Test error")
            
            data = {
                "source_type": "url",
                "source_config": {"url": "https://example.com/file.zip"},
                "user_email": "user@example.com",
                "dataset_name": "Test Dataset",
                "sensor": "TIFF",
                "convert": True,
                "is_public": False
            }
            
            response = self.app.post('/api/upload/initiate',
                                   data=json.dumps(data),
                                   content_type='application/json')
            
            self.assertEqual(response.status_code, 500)
            response_data = json.loads(response.data)
            self.assertIn('error', response_data)


# The TestSC_UploadAPI class is already defined above


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
