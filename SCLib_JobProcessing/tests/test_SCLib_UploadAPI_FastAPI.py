#!/usr/bin/env python3
"""
Test cases for SCLib_UploadAPI_FastAPI module.
Tests the FastAPI RESTful API endpoints for upload operations.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import tempfile
import os
from io import BytesIO
import pytest
from fastapi.testclient import TestClient

# Import the module under test
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SCLib_UploadAPI_FastAPI import app
from SCLib_UploadJobTypes import UploadSourceType, SensorType, UploadStatus


class TestSCLib_UploadAPI_FastAPI(unittest.TestCase):
    """Test SCLib_UploadAPI_FastAPI FastAPI application."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
    
    def test_root_endpoint(self):
        """Test root endpoint with API information."""
        response = self.client.get("/")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['message'], 'ScientistCloud Upload API')
        self.assertEqual(data['version'], '2.0.0')
        self.assertIn('docs', data)
        self.assertIn('redoc', data)
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('timestamp', data)
    
    def test_get_supported_sources(self):
        """Test getting supported upload sources."""
        response = self.client.get("/api/upload/supported-sources")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Check source types
        self.assertIn('source_types', data)
        expected_types = ['local', 'google_drive', 's3', 'url']
        for expected_type in expected_types:
            self.assertIn(expected_type, data['source_types'])
        
        # Check sensor types
        self.assertIn('sensor_types', data)
        expected_sensors = ['IDX', 'TIFF', 'TIFF RGB', 'NETCDF', 'HDF5', '4D_NEXUS', 'RGB', 'MAPIR', 'OTHER']
        for expected_sensor in expected_sensors:
            self.assertIn(expected_sensor, data['sensor_types'])
        
        # Check required parameters
        self.assertIn('required_parameters', data)
        self.assertIn('google_drive', data['required_parameters'])
        self.assertIn('s3', data['required_parameters'])
        self.assertIn('url', data['required_parameters'])
    
    def test_initiate_upload_validation_error(self):
        """Test initiating upload with validation errors."""
        # Test with missing required fields
        data = {
            "source_type": "url",
            "source_config": {"url": "https://example.com/file.zip"},
            "dataset_name": "Test Dataset",
            "sensor": "TIFF",
            "convert": True,
            "is_public": False
            # Missing user_email
        }
        
        response = self.client.post("/api/upload/initiate", json=data)
        
        self.assertEqual(response.status_code, 422)  # FastAPI validation error
        response_data = response.json()
        self.assertIn('detail', response_data)
    
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
        
        response = self.client.post("/api/upload/initiate", json=data)
        
        self.assertEqual(response.status_code, 422)  # FastAPI validation error
        response_data = response.json()
        self.assertIn('detail', response_data)
    
    def test_initiate_upload_invalid_source_type(self):
        """Test initiating upload with invalid source type."""
        data = {
            "source_type": "unsupported_source",
            "source_config": {},
            "user_email": "user@example.com",
            "dataset_name": "Test Dataset",
            "sensor": "TIFF",
            "convert": True,
            "is_public": False
        }
        
        response = self.client.post("/api/upload/initiate", json=data)
        
        self.assertEqual(response.status_code, 422)  # FastAPI validation error
        response_data = response.json()
        self.assertIn('detail', response_data)
    
    @patch('SCLib_UploadAPI_FastAPI.upload_processor')
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
        
        response = self.client.post("/api/upload/initiate", json=data)
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertIn('job_id', response_data)
        self.assertEqual(response_data['status'], 'queued')
        self.assertIn('message', response_data)
        self.assertIn('estimated_duration', response_data)
        
        # Verify job was submitted
        mock_processor.submit_upload_job.assert_called_once()
    
    @patch('SCLib_UploadAPI_FastAPI.upload_processor')
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
        
        response = self.client.post("/api/upload/initiate", json=data)
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertIn('job_id', response_data)
        self.assertEqual(response_data['status'], 'queued')
        self.assertIn('message', response_data)
        
        # Verify job was submitted
        mock_processor.submit_upload_job.assert_called_once()
    
    @patch('SCLib_UploadAPI_FastAPI.upload_processor')
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
        
        response = self.client.post("/api/upload/initiate", json=data)
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertIn('job_id', response_data)
        self.assertEqual(response_data['status'], 'queued')
        self.assertIn('message', response_data)
        
        # Verify job was submitted
        mock_processor.submit_upload_job.assert_called_once()
    
    def test_upload_local_file_missing_file(self):
        """Test local file upload with missing file."""
        response = self.client.post("/api/upload/local/upload")
        
        self.assertEqual(response.status_code, 422)  # FastAPI validation error
        response_data = response.json()
        self.assertIn('detail', response_data)
    
    def test_upload_local_file_validation_error(self):
        """Test local file upload with validation errors."""
        # Create a test file
        test_file = BytesIO(b"test file content")
        
        # Test with missing user_email
        response = self.client.post("/api/upload/local/upload",
                                   files={"file": ("test.txt", test_file, "text/plain")},
                                   data={
                                       "dataset_name": "Test Dataset",
                                       "sensor": "TIFF",
                                       "convert": "true",
                                       "is_public": "false"
                                   })
        
        self.assertEqual(response.status_code, 422)  # FastAPI validation error
        response_data = response.json()
        self.assertIn('detail', response_data)
    
    def test_upload_local_file_invalid_sensor(self):
        """Test local file upload with invalid sensor type."""
        test_file = BytesIO(b"test file content")
        
        response = self.client.post("/api/upload/local/upload",
                                   files={"file": ("test.txt", test_file, "text/plain")},
                                   data={
                                       "user_email": "user@example.com",
                                       "dataset_name": "Test Dataset",
                                       "sensor": "INVALID_SENSOR",
                                       "convert": "true",
                                       "is_public": "false"
                                   })
        
        self.assertEqual(response.status_code, 422)  # FastAPI validation error
        response_data = response.json()
        self.assertIn('detail', response_data)
    
    @patch('SCLib_UploadAPI_FastAPI.upload_processor')
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
        
        response = self.client.post("/api/upload/local/upload",
                                   files={"file": ("test.txt", test_file, "text/plain")},
                                   data={
                                       "user_email": "user@example.com",
                                       "dataset_name": "Test Dataset",
                                       "sensor": "TIFF",
                                       "convert": "true",
                                       "is_public": "false",
                                       "folder": "test_folder",
                                       "team_uuid": "team_123"
                                   })
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertIn('job_id', response_data)
        self.assertEqual(response_data['status'], 'queued')
        self.assertIn('message', response_data)
        self.assertIn('estimated_duration', response_data)
        
        # Verify job was submitted
        mock_processor.submit_upload_job.assert_called_once()
    
    @patch('SCLib_UploadAPI_FastAPI.upload_processor')
    def test_get_upload_status(self, mock_processor):
        """Test getting upload status."""
        # Mock status data
        mock_status = {
            'job_id': 'upload_12345',
            'status': 'uploading',
            'progress_percentage': 45.2,
            'bytes_uploaded': 1024000,
            'bytes_total': 2264000,
            'message': 'Uploading file...',
            'created_at': '2023-01-01T00:00:00Z',
            'updated_at': '2023-01-01T00:05:00Z'
        }
        
        mock_processor.get_job_status.return_value = mock_status
        
        response = self.client.get("/api/upload/status/upload_12345")
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['job_id'], 'upload_12345')
        self.assertEqual(response_data['status'], 'uploading')
        self.assertEqual(response_data['progress_percentage'], 45.2)
        self.assertEqual(response_data['bytes_uploaded'], 1024000)
        self.assertEqual(response_data['bytes_total'], 2264000)
    
    @patch('SCLib_UploadAPI_FastAPI.upload_processor')
    def test_get_upload_status_not_found(self, mock_processor):
        """Test getting upload status for non-existent job."""
        mock_processor.get_job_status.return_value = None
        
        response = self.client.get("/api/upload/status/non_existent_job")
        
        self.assertEqual(response.status_code, 404)
        response_data = response.json()
        self.assertIn('detail', response_data)
        self.assertIn('Job not found', response_data['detail'])
    
    @patch('SCLib_UploadAPI_FastAPI.upload_processor')
    def test_cancel_upload(self, mock_processor):
        """Test canceling an upload."""
        mock_processor.cancel_job.return_value = True
        
        response = self.client.post("/api/upload/cancel/upload_12345")
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertIn('message', response_data)
        self.assertIn('cancelled successfully', response_data['message'])
        
        # Verify cancel was called
        mock_processor.cancel_job.assert_called_once_with('upload_12345')
    
    @patch('SCLib_UploadAPI_FastAPI.upload_processor')
    def test_cancel_upload_not_found(self, mock_processor):
        """Test canceling a non-existent upload."""
        mock_processor.cancel_job.return_value = False
        
        response = self.client.post("/api/upload/cancel/non_existent_job")
        
        self.assertEqual(response.status_code, 404)
        response_data = response.json()
        self.assertIn('detail', response_data)
        self.assertIn('Job not found or already completed', response_data['detail'])
    
    @patch('SCLib_UploadAPI_FastAPI.upload_processor')
    def test_list_upload_jobs(self, mock_processor):
        """Test listing upload jobs."""
        # Mock job list
        mock_jobs = {
            'jobs': [
                {
                    'job_id': 'upload_1',
                    'status': 'completed',
                    'progress_percentage': 100.0,
                    'created_at': '2023-01-01T00:00:00Z',
                    'updated_at': '2023-01-01T00:10:00Z'
                },
                {
                    'job_id': 'upload_2',
                    'status': 'uploading',
                    'progress_percentage': 45.2,
                    'created_at': '2023-01-02T00:00:00Z',
                    'updated_at': '2023-01-02T00:05:00Z'
                }
            ],
            'total': 2
        }
        
        mock_processor.get_queued_jobs.return_value = mock_jobs
        
        response = self.client.get("/api/upload/jobs?user_id=user@example.com")
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        self.assertIn('jobs', response_data)
        self.assertEqual(len(response_data['jobs']), 2)
        self.assertEqual(response_data['jobs'][0]['job_id'], 'upload_1')
        self.assertEqual(response_data['jobs'][1]['job_id'], 'upload_2')
        self.assertEqual(response_data['total'], 2)
        self.assertEqual(response_data['limit'], 50)
        self.assertEqual(response_data['offset'], 0)
    
    def test_list_upload_jobs_missing_user_id(self):
        """Test listing upload jobs without user_id."""
        response = self.client.get("/api/upload/jobs")
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('detail', response_data)
        self.assertIn('user_id parameter is required', response_data['detail'])
    
    def test_estimate_upload_time(self):
        """Test upload time estimation."""
        response = self.client.get("/api/upload/estimate-time?source_type=local&file_size_mb=100")
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(response_data['source_type'], 'local')
        self.assertIn('estimated_seconds', response_data)
        self.assertIn('estimated_minutes', response_data)
        self.assertEqual(response_data['file_size_mb'], 100)
    
    def test_estimate_upload_time_missing_source_type(self):
        """Test upload time estimation with missing source type."""
        response = self.client.get("/api/upload/estimate-time")
        
        self.assertEqual(response.status_code, 422)  # FastAPI validation error
        response_data = response.json()
        self.assertIn('detail', response_data)
    
    def test_error_handlers(self):
        """Test error handlers."""
        # Test 404 error handler
        response = self.client.get("/api/upload/status/non_existent_job")
        self.assertEqual(response.status_code, 404)
        
        # Test 422 error handler (validation error)
        response = self.client.post("/api/upload/initiate", json={})
        self.assertEqual(response.status_code, 422)
        
        # Note: Background task error testing is not applicable in FastAPI
        # Background tasks run asynchronously and don't affect HTTP responses
        # Error handling is tested through other endpoints that don't use background tasks


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
