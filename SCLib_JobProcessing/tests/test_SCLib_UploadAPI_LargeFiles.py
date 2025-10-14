#!/usr/bin/env python3
"""
Test cases for SCLib_UploadAPI_LargeFiles module.
Tests the FastAPI RESTful API endpoints for TB-scale upload operations.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import tempfile
import os
import hashlib
from io import BytesIO
import pytest
from fastapi.testclient import TestClient

# Import the module under test
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SCLib_UploadAPI_LargeFiles import app, upload_sessions, create_upload_session, update_upload_session
from SCLib_UploadJobTypes import UploadSourceType, SensorType, UploadStatus


class TestSCLib_UploadAPI_LargeFiles(unittest.TestCase):
    """Test SCLib_UploadAPI_LargeFiles FastAPI application."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        # Clear upload sessions before each test
        upload_sessions.clear()
    
    def tearDown(self):
        """Clean up after each test."""
        upload_sessions.clear()
    
    def test_get_upload_limits(self):
        """Test getting upload limits and configuration."""
        response = self.client.get("/api/upload/large/limits")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn('max_file_size_bytes', data)
        self.assertIn('max_file_size_tb', data)
        self.assertIn('chunk_size_bytes', data)
        self.assertIn('chunk_size_mb', data)
        self.assertIn('resumable_upload_timeout_days', data)
        self.assertIn('supported_source_types', data)
        self.assertIn('recommended_for_files_larger_than_mb', data)
        self.assertIn('temp_directory', data)
        
        # Check reasonable values
        self.assertGreater(data['max_file_size_tb'], 1)  # At least 1TB
        self.assertGreater(data['chunk_size_mb'], 50)    # At least 50MB chunks
    
    def test_health_check_large_files(self):
        """Test health check with large file information."""
        response = self.client.get("/health/large-files")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data['status'], 'healthy')
        self.assertIn('timestamp', data)
        self.assertIn('active_uploads', data)
        self.assertIn('temp_directory_size_mb', data)
        self.assertIn('max_file_size_tb', data)
        self.assertIn('chunk_size_mb', data)
    
    def test_initiate_large_upload_validation_error(self):
        """Test initiating large upload with validation errors."""
        # Test with missing required fields
        data = {
            "filename": "test.dat",
            "file_size": 1000000,
            "file_hash": "abc123",
            "dataset_name": "Test Dataset",
            "sensor": "TIFF",
            "convert": True,
            "is_public": False
            # Missing user_email
        }
        
        response = self.client.post("/api/upload/large/initiate", json=data)
        
        self.assertEqual(response.status_code, 422)  # FastAPI validation error
        response_data = response.json()
        self.assertIn('detail', response_data)
    
    def test_initiate_large_upload_file_too_large(self):
        """Test initiating large upload with file exceeding maximum size."""
        data = {
            "filename": "huge.dat",
            "file_size": 11 * 1024 * 1024 * 1024 * 1024,  # 11TB (exceeds 10TB limit)
            "file_hash": "abc123",
            "user_email": "user@example.com",
            "dataset_name": "Huge Dataset",
            "sensor": "TIFF",
            "convert": True,
            "is_public": False
        }
        
        response = self.client.post("/api/upload/large/initiate", json=data)
        
        self.assertEqual(response.status_code, 413)  # Payload too large
        response_data = response.json()
        self.assertIn('detail', response_data)
        self.assertIn('exceeds maximum allowed size', response_data['detail'])
    
    @patch('SCLib_UploadAPI_LargeFiles.upload_processor')
    def test_initiate_large_upload_success(self, mock_processor):
        """Test successful large upload initiation."""
        data = {
            "filename": "large_dataset.idx",
            "file_size": 5 * 1024 * 1024 * 1024,  # 5GB
            "file_hash": "sha256hash123",
            "user_email": "user@example.com",
            "dataset_name": "Large Dataset",
            "sensor": "IDX",
            "convert": True,
            "is_public": False,
            "folder": "large_files",
            "team_uuid": "team_123"
        }
        
        response = self.client.post("/api/upload/large/initiate", json=data)
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        self.assertIn('upload_id', response_data)
        self.assertIn('chunk_size', response_data)
        self.assertIn('total_chunks', response_data)
        self.assertIn('message', response_data)
        
        # Verify upload session was created
        upload_id = response_data['upload_id']
        self.assertIn(upload_id, upload_sessions)
        
        # Check session data
        session = upload_sessions[upload_id]
        self.assertEqual(session['filename'], 'large_dataset.idx')
        self.assertEqual(session['file_size'], 5 * 1024 * 1024 * 1024)
        self.assertEqual(session['user_email'], 'user@example.com')
        self.assertEqual(session['total_chunks'], response_data['total_chunks'])
    
    def test_upload_chunk_invalid_upload_id(self):
        """Test uploading chunk with invalid upload ID."""
        test_file = BytesIO(b"chunk data")
        
        response = self.client.post("/api/upload/large/chunk/invalid_id/0",
                                   files={"chunk": ("chunk_0", test_file, "application/octet-stream")},
                                   data={"chunk_hash": "abc123"})
        
        self.assertEqual(response.status_code, 404)
        response_data = response.json()
        self.assertIn('detail', response_data)
        self.assertIn('Upload session not found', response_data['detail'])
    
    def test_upload_chunk_invalid_chunk_index(self):
        """Test uploading chunk with invalid chunk index."""
        # Create a test upload session
        upload_id = "test_upload_123"
        create_upload_session(upload_id, {
            'filename': 'test.dat',
            'file_size': 1000000,
            'file_hash': 'abc123',
            'user_email': 'user@example.com',
            'dataset_name': 'Test Dataset',
            'sensor': 'TIFF',
            'total_chunks': 5,
            'chunk_size': 200000
        })
        
        test_file = BytesIO(b"chunk data")
        
        # Test with chunk index >= total_chunks
        response = self.client.post(f"/api/upload/large/chunk/{upload_id}/10",
                                   files={"chunk": ("chunk_10", test_file, "application/octet-stream")},
                                   data={"chunk_hash": "abc123"})
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('detail', response_data)
        self.assertIn('Invalid chunk index', response_data['detail'])
    
    def test_upload_chunk_hash_mismatch(self):
        """Test uploading chunk with hash mismatch."""
        # Create a test upload session
        upload_id = "test_upload_123"
        create_upload_session(upload_id, {
            'filename': 'test.dat',
            'file_size': 1000000,
            'file_hash': 'abc123',
            'user_email': 'user@example.com',
            'dataset_name': 'Test Dataset',
            'sensor': 'TIFF',
            'total_chunks': 5,
            'chunk_size': 200000
        })
        
        test_file = BytesIO(b"chunk data")
        actual_hash = hashlib.sha256(b"chunk data").hexdigest()
        wrong_hash = "wrong_hash_123"
        
        response = self.client.post(f"/api/upload/large/chunk/{upload_id}/0",
                                   files={"chunk": ("chunk_0", test_file, "application/octet-stream")},
                                   data={"chunk_hash": wrong_hash})
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('detail', response_data)
        self.assertIn('Chunk hash mismatch', response_data['detail'])
    
    @patch('SCLib_UploadAPI_LargeFiles.os.makedirs')
    @patch('SCLib_UploadAPI_LargeFiles.aiofiles.open')
    def test_upload_chunk_success(self, mock_aiofiles_open, mock_makedirs):
        """Test successful chunk upload."""
        # Create a test upload session
        upload_id = "test_upload_123"
        create_upload_session(upload_id, {
            'filename': 'test.dat',
            'file_size': 1000000,
            'file_hash': 'abc123',
            'user_email': 'user@example.com',
            'dataset_name': 'Test Dataset',
            'sensor': 'TIFF',
            'total_chunks': 5,
            'chunk_size': 200000
        })
        
        # Mock aiofiles
        mock_file = MagicMock()
        mock_aiofiles_open.return_value.__aenter__.return_value = mock_file
        
        test_file = BytesIO(b"chunk data")
        chunk_hash = hashlib.sha256(b"chunk data").hexdigest()
        
        response = self.client.post(f"/api/upload/large/chunk/{upload_id}/0",
                                   files={"chunk": ("chunk_0", test_file, "application/octet-stream")},
                                   data={"chunk_hash": chunk_hash})
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        self.assertIn('message', response_data)
        self.assertIn('uploaded_chunks', response_data)
        self.assertIn('total_chunks', response_data)
        
        # Verify chunk was added to session
        session = upload_sessions[upload_id]
        self.assertIn(0, session['uploaded_chunks'])
        self.assertEqual(session['chunk_hashes'][0], chunk_hash)
    
    def test_get_chunk_upload_status_invalid_upload_id(self):
        """Test getting chunk status with invalid upload ID."""
        response = self.client.get("/api/upload/large/status/invalid_id")
        
        self.assertEqual(response.status_code, 404)
        response_data = response.json()
        self.assertIn('detail', response_data)
        self.assertIn('Upload session not found', response_data['detail'])
    
    def test_get_chunk_upload_status_success(self):
        """Test getting chunk upload status."""
        # Create a test upload session with some uploaded chunks
        upload_id = "test_upload_123"
        create_upload_session(upload_id, {
            'filename': 'test.dat',
            'file_size': 1000000,
            'file_hash': 'abc123',
            'user_email': 'user@example.com',
            'dataset_name': 'Test Dataset',
            'sensor': 'TIFF',
            'total_chunks': 5,
            'chunk_size': 200000
        })
        
        # Add some uploaded chunks
        update_upload_session(upload_id, 0, "hash0")
        update_upload_session(upload_id, 2, "hash2")
        update_upload_session(upload_id, 4, "hash4")
        
        response = self.client.get(f"/api/upload/large/status/{upload_id}")
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        self.assertEqual(response_data['upload_id'], upload_id)
        self.assertEqual(response_data['uploaded_chunks'], [0, 2, 4])
        self.assertEqual(response_data['total_chunks'], 5)
        self.assertFalse(response_data['is_complete'])
        self.assertEqual(response_data['progress_percentage'], 60.0)  # 3/5 * 100
    
    def test_get_resume_info_invalid_upload_id(self):
        """Test getting resume info with invalid upload ID."""
        response = self.client.get("/api/upload/large/resume/invalid_id")
        
        self.assertEqual(response.status_code, 404)
        response_data = response.json()
        self.assertIn('detail', response_data)
        self.assertIn('Upload session not found', response_data['detail'])
    
    def test_get_resume_info_success(self):
        """Test getting resume information."""
        # Create a test upload session with some uploaded chunks
        upload_id = "test_upload_123"
        create_upload_session(upload_id, {
            'filename': 'test.dat',
            'file_size': 1000000,
            'file_hash': 'abc123',
            'user_email': 'user@example.com',
            'dataset_name': 'Test Dataset',
            'sensor': 'TIFF',
            'total_chunks': 5,
            'chunk_size': 200000
        })
        
        # Add some uploaded chunks
        update_upload_session(upload_id, 0, "hash0")
        update_upload_session(upload_id, 2, "hash2")
        
        response = self.client.get(f"/api/upload/large/resume/{upload_id}")
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        self.assertEqual(response_data['upload_id'], upload_id)
        self.assertEqual(response_data['missing_chunks'], [1, 3, 4])
        self.assertEqual(response_data['total_chunks'], 5)
        self.assertTrue(response_data['can_resume'])
    
    def test_complete_large_upload_missing_chunks(self):
        """Test completing upload with missing chunks."""
        # Create a test upload session with incomplete chunks
        upload_id = "test_upload_123"
        create_upload_session(upload_id, {
            'filename': 'test.dat',
            'file_size': 1000000,
            'file_hash': 'abc123',
            'user_email': 'user@example.com',
            'dataset_name': 'Test Dataset',
            'sensor': 'TIFF',
            'total_chunks': 5,
            'chunk_size': 200000
        })
        
        # Add only some chunks
        update_upload_session(upload_id, 0, "hash0")
        update_upload_session(upload_id, 2, "hash2")
        
        response = self.client.post(f"/api/upload/large/complete/{upload_id}")
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('detail', response_data)
        self.assertIn('Missing chunks', response_data['detail'])
    
    @patch('SCLib_UploadAPI_LargeFiles.upload_processor')
    @patch('SCLib_UploadAPI_LargeFiles.os.path.exists')
    @patch('SCLib_UploadAPI_LargeFiles.open')
    @patch('SCLib_UploadAPI_LargeFiles.hashlib.sha256')
    @patch('SCLib_UploadAPI_LargeFiles.os.remove')
    def test_complete_large_upload_success(self, mock_remove, mock_sha256, mock_open, 
                                         mock_exists, mock_processor):
        """Test successful large upload completion."""
        # Create a test upload session with all chunks
        upload_id = "test_upload_123"
        create_upload_session(upload_id, {
            'filename': 'test.dat',
            'file_size': 1000000,
            'file_hash': 'expected_hash',
            'user_email': 'user@example.com',
            'dataset_name': 'Test Dataset',
            'sensor': 'TIFF',
            'total_chunks': 2,
            'chunk_size': 500000
        })
        
        # Add all chunks
        update_upload_session(upload_id, 0, "hash0")
        update_upload_session(upload_id, 1, "hash1")
        
        # Mock file operations
        mock_exists.return_value = True
        mock_file = MagicMock()
        mock_file.read.return_value = b"chunk data"
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Mock hash calculation
        mock_hash = MagicMock()
        mock_hash.hexdigest.return_value = 'expected_hash'
        mock_sha256.return_value = mock_hash
        
        response = self.client.post(f"/api/upload/large/complete/{upload_id}")
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        self.assertIn('message', response_data)
        self.assertIn('file_path', response_data)
        self.assertIn('file_size', response_data)
        self.assertTrue(response_data['job_submitted'])
        
        # Verify job was submitted
        mock_processor.submit_upload_job.assert_called_once()
    
    def test_cancel_large_upload_invalid_upload_id(self):
        """Test canceling upload with invalid upload ID."""
        response = self.client.delete("/api/upload/large/cancel/invalid_id")
        
        self.assertEqual(response.status_code, 404)
        response_data = response.json()
        self.assertIn('detail', response_data)
        self.assertIn('Upload session not found', response_data['detail'])
    
    @patch('SCLib_UploadAPI_LargeFiles.shutil.rmtree')
    @patch('SCLib_UploadAPI_LargeFiles.os.path.exists')
    def test_cancel_large_upload_success(self, mock_exists, mock_rmtree):
        """Test successful large upload cancellation."""
        # Mock that the upload directory exists so rmtree gets called
        mock_exists.return_value = True
        
        # Create a test upload session
        upload_id = "test_upload_123"
        create_upload_session(upload_id, {
            'filename': 'test.dat',
            'file_size': 1000000,
            'file_hash': 'abc123',
            'user_email': 'user@example.com',
            'dataset_name': 'Test Dataset',
            'sensor': 'TIFF',
            'total_chunks': 5,
            'chunk_size': 200000
        })
        
        response = self.client.delete(f"/api/upload/large/cancel/{upload_id}")
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        self.assertIn('message', response_data)
        self.assertIn('cancelled and cleaned up', response_data['message'])
        
        # Verify session was removed
        self.assertNotIn(upload_id, upload_sessions)
        
        # Verify cleanup was called
        mock_rmtree.assert_called_once()
    
    @patch('SCLib_UploadAPI_LargeFiles.upload_processor')
    def test_initiate_cloud_large_upload_google_drive(self, mock_processor):
        """Test initiating cloud large upload for Google Drive."""
        data = {
            "source_type": "google_drive",
            "source_config": {
                "file_id": "1ABC123DEF456",
                "service_account_file": "/path/to/service.json"
            },
            "user_email": "user@example.com",
            "dataset_name": "Google Drive Large Dataset",
            "sensor": "NETCDF",
            "convert": False,
            "is_public": True,
            "folder": "cloud_data",
            "team_uuid": "team_456"
        }
        
        response = self.client.post("/api/upload/cloud/large", json=data)
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        self.assertIn('job_id', response_data)
        self.assertEqual(response_data['status'], 'queued')
        self.assertIn('message', response_data)
        self.assertIn('Large cloud upload initiated', response_data['message'])
        
        # Verify job was submitted
        mock_processor.submit_upload_job.assert_called_once()
    
    @patch('SCLib_UploadAPI_LargeFiles.upload_processor')
    def test_initiate_cloud_large_upload_s3(self, mock_processor):
        """Test initiating cloud large upload for S3."""
        data = {
            "source_type": "s3",
            "source_config": {
                "bucket_name": "my-large-bucket",
                "object_key": "data/large_dataset.zip",
                "access_key_id": "AKIA...",
                "secret_access_key": "secret..."
            },
            "user_email": "user@example.com",
            "dataset_name": "S3 Large Dataset",
            "sensor": "HDF5",
            "convert": True,
            "is_public": False,
            "folder": "s3_imports"
        }
        
        response = self.client.post("/api/upload/cloud/large", json=data)
        
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        
        self.assertIn('job_id', response_data)
        self.assertEqual(response_data['status'], 'queued')
        self.assertIn('message', response_data)
        self.assertIn('Large cloud upload initiated', response_data['message'])
        
        # Verify job was submitted
        mock_processor.submit_upload_job.assert_called_once()
    
    def test_initiate_cloud_large_upload_unsupported_source(self):
        """Test initiating cloud large upload with unsupported source type."""
        data = {
            "source_type": "url",  # URL not supported for large files
            "source_config": {
                "url": "https://example.com/large_file.zip"
            },
            "user_email": "user@example.com",
            "dataset_name": "URL Large Dataset",
            "sensor": "OTHER",
            "convert": True,
            "is_public": False
        }
        
        response = self.client.post("/api/upload/cloud/large", json=data)
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('detail', response_data)
        self.assertIn('Unsupported source type for large files', response_data['detail'])


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)
