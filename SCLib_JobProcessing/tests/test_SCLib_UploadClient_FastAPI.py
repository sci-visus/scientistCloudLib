#!/usr/bin/env python3
"""
Test cases for SCLib_UploadClient_FastAPI module.
Tests the FastAPI client for upload operations.
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import tempfile
import os
from io import BytesIO
import requests

# Import the module under test
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SCLib_UploadClient_FastAPI import ScientistCloudUploadClient, AsyncScientistCloudUploadClient


class TestScientistCloudUploadClient(unittest.TestCase):
    """Test ScientistCloudUploadClient."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = ScientistCloudUploadClient("http://localhost:5000")
    
    @patch('requests.Session.get')
    def test_health_check(self, mock_get):
        """Test health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy", "timestamp": "2023-01-01T00:00:00Z"}
        mock_get.return_value = mock_response
        
        result = self.client.health_check()
        
        self.assertEqual(result['status'], 'healthy')
        mock_get.assert_called_once_with("http://localhost:5000/health", timeout=30)
    
    @patch('requests.Session.get')
    def test_get_api_info(self, mock_get):
        """Test getting API information."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "ScientistCloud Upload API",
            "version": "2.0.0",
            "docs": "/docs"
        }
        mock_get.return_value = mock_response
        
        result = self.client.get_api_info()
        
        self.assertEqual(result['message'], 'ScientistCloud Upload API')
        self.assertEqual(result['version'], '2.0.0')
        mock_get.assert_called_once_with("http://localhost:5000/", timeout=30)
    
    @patch('requests.Session.get')
    def test_get_supported_sources(self, mock_get):
        """Test getting supported sources."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "source_types": ["local", "google_drive", "s3", "url"],
            "sensor_types": ["IDX", "TIFF", "NETCDF"],
            "required_parameters": {
                "google_drive": ["file_id", "service_account_file"],
                "s3": ["bucket_name", "object_key", "access_key_id", "secret_access_key"]
            }
        }
        mock_get.return_value = mock_response
        
        result = self.client.get_supported_sources()
        
        self.assertIn('source_types', result)
        self.assertIn('sensor_types', result)
        self.assertIn('required_parameters', result)
        mock_get.assert_called_once_with("http://localhost:5000/api/upload/supported-sources", timeout=30)
    
    @patch('requests.Session.post')
    def test_upload_local_file_success(self, mock_post):
        """Test successful local file upload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "upload_12345",
            "status": "queued",
            "message": "Local file upload initiated: test.txt",
            "estimated_duration": 120
        }
        mock_post.return_value = mock_response
        
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test content")
            temp_file = f.name
        
        try:
            result = self.client.upload_local_file(
                file_path=temp_file,
                user_email="user@example.com",
                dataset_name="Test Dataset",
                sensor="TIFF"
            )
            
            self.assertEqual(result.job_id, "upload_12345")
            self.assertEqual(result.status, "queued")
            self.assertIn("test.txt", result.message)
            self.assertEqual(result.estimated_duration, 120)
            
            # Verify the request was made correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            self.assertEqual(call_args[0][0], "http://localhost:5000/api/upload/local/upload")
            
        finally:
            os.unlink(temp_file)
    
    @patch('requests.Session.post')
    def test_upload_local_file_not_found(self, mock_post):
        """Test local file upload with non-existent file."""
        with self.assertRaises(FileNotFoundError):
            self.client.upload_local_file(
                file_path="/non/existent/file.txt",
                user_email="user@example.com",
                dataset_name="Test Dataset",
                sensor="TIFF"
            )
    
    @patch('requests.Session.post')
    def test_initiate_google_drive_upload(self, mock_post):
        """Test initiating Google Drive upload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "upload_gd_123",
            "status": "queued",
            "message": "Upload job initiated for google_drive",
            "estimated_duration": 600
        }
        mock_post.return_value = mock_response
        
        result = self.client.initiate_google_drive_upload(
            file_id="1ABC123DEF456",
            service_account_file="/path/to/service.json",
            user_email="user@example.com",
            dataset_name="Google Drive Dataset",
            sensor="NETCDF"
        )
        
        self.assertEqual(result.job_id, "upload_gd_123")
        self.assertEqual(result.status, "queued")
        self.assertEqual(result.estimated_duration, 600)
        
        # Verify the request data
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        request_data = call_args[1]['json']
        self.assertEqual(request_data['source_type'], 'google_drive')
        self.assertEqual(request_data['source_config']['file_id'], '1ABC123DEF456')
        self.assertEqual(request_data['user_email'], 'user@example.com')
    
    @patch('requests.Session.post')
    def test_initiate_s3_upload(self, mock_post):
        """Test initiating S3 upload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "upload_s3_123",
            "status": "queued",
            "message": "Upload job initiated for s3",
            "estimated_duration": 300
        }
        mock_post.return_value = mock_response
        
        result = self.client.initiate_s3_upload(
            bucket_name="my-bucket",
            object_key="data/dataset.zip",
            access_key_id="AKIA...",
            secret_access_key="secret...",
            user_email="user@example.com",
            dataset_name="S3 Dataset",
            sensor="HDF5"
        )
        
        self.assertEqual(result.job_id, "upload_s3_123")
        self.assertEqual(result.status, "queued")
        
        # Verify the request data
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        request_data = call_args[1]['json']
        self.assertEqual(request_data['source_type'], 's3')
        self.assertEqual(request_data['source_config']['bucket_name'], 'my-bucket')
        self.assertEqual(request_data['source_config']['object_key'], 'data/dataset.zip')
    
    @patch('requests.Session.post')
    def test_initiate_url_upload(self, mock_post):
        """Test initiating URL upload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "upload_url_123",
            "status": "queued",
            "message": "Upload job initiated for url",
            "estimated_duration": 180
        }
        mock_post.return_value = mock_response
        
        result = self.client.initiate_url_upload(
            url="https://example.com/dataset.zip",
            user_email="user@example.com",
            dataset_name="URL Dataset",
            sensor="OTHER"
        )
        
        self.assertEqual(result.job_id, "upload_url_123")
        self.assertEqual(result.status, "queued")
        
        # Verify the request data
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        request_data = call_args[1]['json']
        self.assertEqual(request_data['source_type'], 'url')
        self.assertEqual(request_data['source_config']['url'], 'https://example.com/dataset.zip')
    
    @patch('requests.Session.get')
    def test_get_upload_status(self, mock_get):
        """Test getting upload status."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "upload_12345",
            "status": "uploading",
            "progress_percentage": 45.2,
            "bytes_uploaded": 1024000,
            "bytes_total": 2264000,
            "message": "Uploading file...",
            "created_at": "2023-01-01T00:00:00Z",
            "updated_at": "2023-01-01T00:05:00Z"
        }
        mock_get.return_value = mock_response
        
        result = self.client.get_upload_status("upload_12345")
        
        self.assertEqual(result.job_id, "upload_12345")
        self.assertEqual(result.status, "uploading")
        self.assertEqual(result.progress_percentage, 45.2)
        self.assertEqual(result.bytes_uploaded, 1024000)
        self.assertEqual(result.bytes_total, 2264000)
        mock_get.assert_called_once_with("http://localhost:5000/api/upload/status/upload_12345", timeout=30)
    
    @patch('requests.Session.post')
    def test_cancel_upload(self, mock_post):
        """Test canceling upload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "Job upload_12345 cancelled successfully"}
        mock_post.return_value = mock_response
        
        result = self.client.cancel_upload("upload_12345")
        
        self.assertEqual(result['message'], "Job upload_12345 cancelled successfully")
        mock_post.assert_called_once_with("http://localhost:5000/api/upload/cancel/upload_12345", timeout=30)
    
    @patch('requests.Session.get')
    def test_list_upload_jobs(self, mock_get):
        """Test listing upload jobs."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jobs": [
                {
                    "job_id": "upload_1",
                    "status": "completed",
                    "progress_percentage": 100.0,
                    "created_at": "2023-01-01T00:00:00Z",
                    "updated_at": "2023-01-01T00:10:00Z"
                },
                {
                    "job_id": "upload_2",
                    "status": "uploading",
                    "progress_percentage": 45.2,
                    "created_at": "2023-01-02T00:00:00Z",
                    "updated_at": "2023-01-02T00:05:00Z"
                }
            ],
            "total": 2,
            "limit": 50,
            "offset": 0
        }
        mock_get.return_value = mock_response
        
        result = self.client.list_upload_jobs("user@example.com")
        
        self.assertEqual(len(result['jobs']), 2)
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['jobs'][0]['job_id'], 'upload_1')
        self.assertEqual(result['jobs'][1]['job_id'], 'upload_2')
        
        # Verify the request parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], "http://localhost:5000/api/upload/jobs")
        self.assertEqual(call_args[1]['params']['user_id'], 'user@example.com')
    
    @patch('requests.Session.get')
    def test_estimate_upload_time(self, mock_get):
        """Test estimating upload time."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "source_type": "local",
            "estimated_seconds": 300,
            "estimated_minutes": 5.0,
            "file_size_mb": 100
        }
        mock_get.return_value = mock_response
        
        result = self.client.estimate_upload_time("local", 100)
        
        self.assertEqual(result['source_type'], 'local')
        self.assertEqual(result['estimated_seconds'], 300)
        self.assertEqual(result['estimated_minutes'], 5.0)
        self.assertEqual(result['file_size_mb'], 100)
        
        # Verify the request parameters
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], "http://localhost:5000/api/upload/estimate-time")
        self.assertEqual(call_args[1]['params']['source_type'], 'local')
        self.assertEqual(call_args[1]['params']['file_size_mb'], 100)
    
    @patch('requests.Session.get')
    def test_wait_for_completion_success(self, mock_get):
        """Test waiting for completion - success case."""
        # Mock responses for status checks
        responses = [
            # First check - still uploading
            MagicMock(status_code=200, json=lambda: {
                "job_id": "upload_12345",
                "status": "uploading",
                "progress_percentage": 50.0
            }),
            # Second check - completed
            MagicMock(status_code=200, json=lambda: {
                "job_id": "upload_12345",
                "status": "completed",
                "progress_percentage": 100.0
            })
        ]
        mock_get.side_effect = responses
        
        result = self.client.wait_for_completion("upload_12345", timeout=10, poll_interval=1)
        
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.progress_percentage, 100.0)
        self.assertEqual(mock_get.call_count, 2)
    
    @patch('requests.Session.get')
    def test_wait_for_completion_timeout(self, mock_get):
        """Test waiting for completion - timeout case."""
        # Mock response that never completes
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "upload_12345",
            "status": "uploading",
            "progress_percentage": 50.0
        }
        mock_get.return_value = mock_response
        
        with self.assertRaises(TimeoutError):
            self.client.wait_for_completion("upload_12345", timeout=1, poll_interval=0.5)
    
    @patch('requests.Session.post')
    def test_http_error_handling(self, mock_post):
        """Test HTTP error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.raise_for_status.side_effect = requests.HTTPError("400 Client Error")
        mock_post.return_value = mock_response
        
        with self.assertRaises(requests.HTTPError):
            self.client.initiate_google_drive_upload(
                file_id="invalid_id",
                service_account_file="/invalid/path",
                user_email="user@example.com",
                dataset_name="Test Dataset",
                sensor="TIFF"
            )


class TestAsyncScientistCloudUploadClient(unittest.TestCase):
    """Test AsyncScientistCloudUploadClient."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = AsyncScientistCloudUploadClient("http://localhost:5000")
    
    @patch('aiohttp.ClientSession.post')
    def test_upload_local_file_async(self, mock_post):
        """Test async local file upload."""
        # This is a simplified test - in practice, you'd need to mock aiohttp more thoroughly
        import asyncio
        
        async def run_test():
            # Create a temporary test file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write("test content")
                temp_file = f.name
            
            try:
                # Mock the aiohttp response
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.json.return_value = {
                    "job_id": "upload_async_123",
                    "status": "queued",
                    "message": "Local file upload initiated: test.txt",
                    "estimated_duration": 120
                }
                mock_post.return_value.__aenter__.return_value = mock_response
                
                result = await self.client.upload_local_file_async(
                    file_path=temp_file,
                    user_email="user@example.com",
                    dataset_name="Test Dataset",
                    sensor="TIFF"
                )
                
                self.assertEqual(result.job_id, "upload_async_123")
                self.assertEqual(result.status, "queued")
                
            finally:
                os.unlink(temp_file)
        
        # Run the async test
        asyncio.run(run_test())
    
    @patch('aiohttp.ClientSession.get')
    def test_get_upload_status_async(self, mock_get):
        """Test async get upload status."""
        import asyncio
        
        async def run_test():
            # Mock the aiohttp response
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                "job_id": "upload_12345",
                "status": "uploading",
                "progress_percentage": 45.2,
                "bytes_uploaded": 1024000,
                "bytes_total": 2264000
            }
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await self.client.get_upload_status("upload_12345")
            
            self.assertEqual(result.job_id, "upload_12345")
            self.assertEqual(result.status, "uploading")
            self.assertEqual(result.progress_percentage, 45.2)
        
        # Run the async test
        asyncio.run(run_test())


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)

