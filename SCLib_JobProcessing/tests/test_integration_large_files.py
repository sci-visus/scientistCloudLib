#!/usr/bin/env python3
"""
Integration tests for TB-scale file uploads.
Tests the complete workflow from client to server for large file operations.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import tempfile
import os
import hashlib
from io import BytesIO
import time
import threading
from concurrent.futures import ThreadPoolExecutor

# Import the modules under test
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SCLib_UploadClient_LargeFiles import LargeFileUploadClient
from SCLib_UploadAPI_LargeFiles import app, upload_sessions
from fastapi.testclient import TestClient
from SCLib_UploadJobTypes import UploadSourceType, SensorType


class TestLargeFileIntegration(unittest.TestCase):
    """Integration tests for large file uploads."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = TestClient(app)
        self.upload_client = LargeFileUploadClient("http://localhost:5001")
        upload_sessions.clear()
    
    def tearDown(self):
        """Clean up after each test."""
        upload_sessions.clear()
    
    def test_complete_chunked_upload_workflow(self):
        """Test complete workflow: initiate -> upload chunks -> complete."""
        # Create a test file
        test_file_size = 2 * 1024 * 1024  # 2MB (small for testing)
        test_content = b"test content " * (test_file_size // 12)  # Fill to approximate size
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.dat') as f:
            f.write(test_content)
            temp_file = f.name
        
        try:
            # Step 1: Initiate upload
            file_hash = hashlib.sha256(test_content).hexdigest()
            
            initiate_data = {
                "filename": "test_large_file.dat",
                "file_size": len(test_content),
                "file_hash": file_hash,
                "user_email": "test@example.com",
                "dataset_name": "Integration Test Dataset",
                "sensor": "IDX",
                "convert": True,
                "is_public": False
            }
            
            response = self.client.post("/api/upload/large/initiate", json=initiate_data)
            self.assertEqual(response.status_code, 200)
            
            result = response.json()
            upload_id = result['upload_id']
            total_chunks = result['total_chunks']
            chunk_size = result['chunk_size']
            
            self.assertIn(upload_id, upload_sessions)
            self.assertGreater(total_chunks, 0)
            
            # Step 2: Upload chunks
            uploaded_chunks = 0
            with open(temp_file, 'rb') as f:
                for chunk_index in range(total_chunks):
                    f.seek(chunk_index * chunk_size)
                    chunk_data = f.read(chunk_size)
                    
                    if not chunk_data:
                        break
                    
                    chunk_hash = hashlib.sha256(chunk_data).hexdigest()
                    
                    # Mock file operations for chunk upload
                    with patch('SCLib_UploadAPI_LargeFiles.os.makedirs'), \
                         patch('SCLib_UploadAPI_LargeFiles.aiofiles.open') as mock_aiofiles:
                        
                        mock_file = MagicMock()
                        mock_aiofiles.return_value.__aenter__.return_value = mock_file
                        
                        response = self.client.post(
                            f"/api/upload/large/chunk/{upload_id}/{chunk_index}",
                            files={"chunk": (f"chunk_{chunk_index}", chunk_data, "application/octet-stream")},
                            data={"chunk_hash": chunk_hash}
                        )
                        
                        self.assertEqual(response.status_code, 200)
                        uploaded_chunks += 1
            
            # Step 3: Check status
            response = self.client.get(f"/api/upload/large/status/{upload_id}")
            self.assertEqual(response.status_code, 200)
            
            status = response.json()
            self.assertEqual(len(status['uploaded_chunks']), uploaded_chunks)
            self.assertTrue(status['is_complete'])
            self.assertEqual(status['progress_percentage'], 100.0)
            
            # Step 4: Complete upload
            with patch('SCLib_UploadAPI_LargeFiles.upload_processor') as mock_processor, \
                 patch('SCLib_UploadAPI_LargeFiles.os.path.exists', return_value=True), \
                 patch('SCLib_UploadAPI_LargeFiles.open', mock_open(read_data=test_content)), \
                 patch('SCLib_UploadAPI_LargeFiles.hashlib.sha256') as mock_sha256, \
                 patch('SCLib_UploadAPI_LargeFiles.os.remove'):
                
                # Mock hash calculation
                mock_hash = MagicMock()
                mock_hash.hexdigest.return_value = file_hash
                mock_sha256.return_value = mock_hash
                
                response = self.client.post(f"/api/upload/large/complete/{upload_id}")
                self.assertEqual(response.status_code, 200)
                
                result = response.json()
                self.assertIn("completed successfully", result['message'])
                self.assertTrue(result['job_submitted'])
                
                # Verify job was submitted
                mock_processor.submit_upload_job.assert_called_once()
        
        finally:
            os.unlink(temp_file)
    
    def test_resumable_upload_workflow(self):
        """Test resumable upload workflow."""
        # Create a test file
        test_file_size = 1 * 1024 * 1024  # 1MB
        test_content = b"test content " * (test_file_size // 12)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.dat') as f:
            f.write(test_content)
            temp_file = f.name
        
        try:
            # Step 1: Initiate upload
            file_hash = hashlib.sha256(test_content).hexdigest()
            
            initiate_data = {
                "filename": "test_resumable_file.dat",
                "file_size": len(test_content),
                "file_hash": file_hash,
                "user_email": "test@example.com",
                "dataset_name": "Resumable Test Dataset",
                "sensor": "TIFF",
                "convert": True,
                "is_public": False
            }
            
            response = self.client.post("/api/upload/large/initiate", json=initiate_data)
            self.assertEqual(response.status_code, 200)
            
            result = response.json()
            upload_id = result['upload_id']
            total_chunks = result['total_chunks']
            chunk_size = result['chunk_size']
            
            # Step 2: Upload only some chunks (simulate interruption)
            uploaded_chunks = []
            with open(temp_file, 'rb') as f:
                for chunk_index in range(0, total_chunks, 2):  # Upload every other chunk
                    f.seek(chunk_index * chunk_size)
                    chunk_data = f.read(chunk_size)
                    
                    if not chunk_data:
                        break
                    
                    chunk_hash = hashlib.sha256(chunk_data).hexdigest()
                    
                    with patch('SCLib_UploadAPI_LargeFiles.os.makedirs'), \
                         patch('SCLib_UploadAPI_LargeFiles.aiofiles.open') as mock_aiofiles:
                        
                        mock_file = MagicMock()
                        mock_aiofiles.return_value.__aenter__.return_value = mock_file
                        
                        response = self.client.post(
                            f"/api/upload/large/chunk/{upload_id}/{chunk_index}",
                            files={"chunk": (f"chunk_{chunk_index}", chunk_data, "application/octet-stream")},
                            data={"chunk_hash": chunk_hash}
                        )
                        
                        self.assertEqual(response.status_code, 200)
                        uploaded_chunks.append(chunk_index)
            
            # Step 3: Check status (should be incomplete)
            response = self.client.get(f"/api/upload/large/status/{upload_id}")
            self.assertEqual(response.status_code, 200)
            
            status = response.json()
            self.assertEqual(status['uploaded_chunks'], uploaded_chunks)
            self.assertFalse(status['is_complete'])
            self.assertLess(status['progress_percentage'], 100.0)
            
            # Step 4: Get resume info
            response = self.client.get(f"/api/upload/large/resume/{upload_id}")
            self.assertEqual(response.status_code, 200)
            
            resume_info = response.json()
            self.assertTrue(resume_info['can_resume'])
            self.assertEqual(len(resume_info['missing_chunks']), total_chunks - len(uploaded_chunks))
            
            # Step 5: Resume upload (upload missing chunks)
            with open(temp_file, 'rb') as f:
                for chunk_index in resume_info['missing_chunks']:
                    f.seek(chunk_index * chunk_size)
                    chunk_data = f.read(chunk_size)
                    
                    if not chunk_data:
                        break
                    
                    chunk_hash = hashlib.sha256(chunk_data).hexdigest()
                    
                    with patch('SCLib_UploadAPI_LargeFiles.os.makedirs'), \
                         patch('SCLib_UploadAPI_LargeFiles.aiofiles.open') as mock_aiofiles:
                        
                        mock_file = MagicMock()
                        mock_aiofiles.return_value.__aenter__.return_value = mock_file
                        
                        response = self.client.post(
                            f"/api/upload/large/chunk/{upload_id}/{chunk_index}",
                            files={"chunk": (f"chunk_{chunk_index}", chunk_data, "application/octet-stream")},
                            data={"chunk_hash": chunk_hash}
                        )
                        
                        self.assertEqual(response.status_code, 200)
            
            # Step 6: Check final status (should be complete)
            response = self.client.get(f"/api/upload/large/status/{upload_id}")
            self.assertEqual(response.status_code, 200)
            
            status = response.json()
            self.assertTrue(status['is_complete'])
            self.assertEqual(status['progress_percentage'], 100.0)
        
        finally:
            os.unlink(temp_file)
    
    def test_parallel_chunk_upload(self):
        """Test parallel chunk upload simulation."""
        # Create a test file
        test_file_size = 5 * 1024 * 1024  # 5MB
        test_content = b"test content " * (test_file_size // 12)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.dat') as f:
            f.write(test_content)
            temp_file = f.name
        
        try:
            # Step 1: Initiate upload
            file_hash = hashlib.sha256(test_content).hexdigest()
            
            initiate_data = {
                "filename": "test_parallel_file.dat",
                "file_size": len(test_content),
                "file_hash": file_hash,
                "user_email": "test@example.com",
                "dataset_name": "Parallel Test Dataset",
                "sensor": "NETCDF",
                "convert": True,
                "is_public": False
            }
            
            response = self.client.post("/api/upload/large/initiate", json=initiate_data)
            self.assertEqual(response.status_code, 200)
            
            result = response.json()
            upload_id = result['upload_id']
            total_chunks = result['total_chunks']
            chunk_size = result['chunk_size']
            
            # Step 2: Upload chunks in parallel
            def upload_chunk(chunk_index):
                with open(temp_file, 'rb') as f:
                    f.seek(chunk_index * chunk_size)
                    chunk_data = f.read(chunk_size)
                    
                    if not chunk_data:
                        return None
                    
                    chunk_hash = hashlib.sha256(chunk_data).hexdigest()
                    
                    with patch('SCLib_UploadAPI_LargeFiles.os.makedirs'), \
                         patch('SCLib_UploadAPI_LargeFiles.aiofiles.open') as mock_aiofiles:
                        
                        mock_file = MagicMock()
                        mock_aiofiles.return_value.__aenter__.return_value = mock_file
                        
                        response = self.client.post(
                            f"/api/upload/large/chunk/{upload_id}/{chunk_index}",
                            files={"chunk": (f"chunk_{chunk_index}", chunk_data, "application/octet-stream")},
                            data={"chunk_hash": chunk_hash}
                        )
                        
                        return response.status_code
            
            # Upload chunks in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(upload_chunk, i) for i in range(total_chunks)]
                results = [future.result() for future in futures if future.result() is not None]
            
            # All chunks should have been uploaded successfully
            self.assertEqual(len(results), total_chunks)
            self.assertTrue(all(status == 200 for status in results))
            
            # Step 3: Check final status
            response = self.client.get(f"/api/upload/large/status/{upload_id}")
            self.assertEqual(response.status_code, 200)
            
            status = response.json()
            self.assertTrue(status['is_complete'])
            self.assertEqual(status['progress_percentage'], 100.0)
        
        finally:
            os.unlink(temp_file)
    
    def test_upload_cancellation_workflow(self):
        """Test upload cancellation workflow."""
        # Create a test file
        test_file_size = 1 * 1024 * 1024  # 1MB
        test_content = b"test content " * (test_file_size // 12)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.dat') as f:
            f.write(test_content)
            temp_file = f.name
        
        try:
            # Step 1: Initiate upload
            file_hash = hashlib.sha256(test_content).hexdigest()
            
            initiate_data = {
                "filename": "test_cancel_file.dat",
                "file_size": len(test_content),
                "file_hash": file_hash,
                "user_email": "test@example.com",
                "dataset_name": "Cancel Test Dataset",
                "sensor": "HDF5",
                "convert": True,
                "is_public": False
            }
            
            response = self.client.post("/api/upload/large/initiate", json=initiate_data)
            self.assertEqual(response.status_code, 200)
            
            result = response.json()
            upload_id = result['upload_id']
            
            # Step 2: Upload a few chunks
            total_chunks = result['total_chunks']
            chunk_size = result['chunk_size']
            
            with open(temp_file, 'rb') as f:
                for chunk_index in range(min(2, total_chunks)):  # Upload first 2 chunks
                    f.seek(chunk_index * chunk_size)
                    chunk_data = f.read(chunk_size)
                    
                    if not chunk_data:
                        break
                    
                    chunk_hash = hashlib.sha256(chunk_data).hexdigest()
                    
                    with patch('SCLib_UploadAPI_LargeFiles.os.makedirs'), \
                         patch('SCLib_UploadAPI_LargeFiles.aiofiles.open') as mock_aiofiles:
                        
                        mock_file = MagicMock()
                        mock_aiofiles.return_value.__aenter__.return_value = mock_file
                        
                        response = self.client.post(
                            f"/api/upload/large/chunk/{upload_id}/{chunk_index}",
                            files={"chunk": (f"chunk_{chunk_index}", chunk_data, "application/octet-stream")},
                            data={"chunk_hash": chunk_hash}
                        )
                        
                        self.assertEqual(response.status_code, 200)
            
            # Step 3: Cancel upload
            with patch('SCLib_UploadAPI_LargeFiles.shutil.rmtree') as mock_rmtree:
                response = self.client.delete(f"/api/upload/large/cancel/{upload_id}")
                self.assertEqual(response.status_code, 200)
                
                result = response.json()
                self.assertIn("cancelled and cleaned up", result['message'])
                
                # Verify cleanup was called
                mock_rmtree.assert_called_once()
            
            # Step 4: Verify session was removed
            self.assertNotIn(upload_id, upload_sessions)
            
            # Step 5: Try to access cancelled upload (should fail)
            response = self.client.get(f"/api/upload/large/status/{upload_id}")
            self.assertEqual(response.status_code, 404)
        
        finally:
            os.unlink(temp_file)
    
    def test_error_handling_workflow(self):
        """Test error handling in upload workflow."""
        # Test 1: Invalid upload ID
        response = self.client.get("/api/upload/large/status/invalid_upload_id")
        self.assertEqual(response.status_code, 404)
        
        # Test 2: File too large
        initiate_data = {
            "filename": "huge_file.dat",
            "file_size": 11 * 1024 * 1024 * 1024 * 1024,  # 11TB (exceeds 10TB limit)
            "file_hash": "abc123",
            "user_email": "test@example.com",
            "dataset_name": "Huge Dataset",
            "sensor": "IDX",
            "convert": True,
            "is_public": False
        }
        
        response = self.client.post("/api/upload/large/initiate", json=initiate_data)
        self.assertEqual(response.status_code, 413)  # Payload too large
        
        # Test 3: Hash mismatch
        initiate_data = {
            "filename": "test_file.dat",
            "file_size": 1000000,
            "file_hash": "valid_hash",
            "user_email": "test@example.com",
            "dataset_name": "Test Dataset",
            "sensor": "TIFF",
            "convert": True,
            "is_public": False
        }
        
        response = self.client.post("/api/upload/large/initiate", json=initiate_data)
        self.assertEqual(response.status_code, 200)
        
        result = response.json()
        upload_id = result['upload_id']
        
        # Upload chunk with wrong hash
        chunk_data = b"test chunk data"
        wrong_hash = "wrong_hash_123"
        
        response = self.client.post(
            f"/api/upload/large/chunk/{upload_id}/0",
            files={"chunk": ("chunk_0", chunk_data, "application/octet-stream")},
            data={"chunk_hash": wrong_hash}
        )
        
        self.assertEqual(response.status_code, 400)  # Bad request due to hash mismatch
    
    def test_cloud_upload_integration(self):
        """Test cloud upload integration."""
        # Test Google Drive upload
        cloud_data = {
            "source_type": "google_drive",
            "source_config": {
                "file_id": "1ABC123DEF456",
                "service_account_file": "/path/to/service.json"
            },
            "user_email": "test@example.com",
            "dataset_name": "Cloud Test Dataset",
            "sensor": "NETCDF",
            "convert": False,
            "is_public": True,
            "folder": "cloud_data",
            "team_uuid": "team_123"
        }
        
        with patch('SCLib_UploadAPI_LargeFiles.upload_processor') as mock_processor:
            response = self.client.post("/api/upload/cloud/large", json=cloud_data)
            self.assertEqual(response.status_code, 200)
            
            result = response.json()
            self.assertIn('job_id', result)
            self.assertEqual(result['status'], 'queued')
            self.assertIn('Large cloud upload initiated', result['message'])
            
            # Verify job was submitted
            mock_processor.submit_upload_job.assert_called_once()
        
        # Test S3 upload
        s3_data = {
            "source_type": "s3",
            "source_config": {
                "bucket_name": "my-large-bucket",
                "object_key": "data/large_dataset.zip",
                "access_key_id": "AKIA...",
                "secret_access_key": "secret..."
            },
            "user_email": "test@example.com",
            "dataset_name": "S3 Large Dataset",
            "sensor": "HDF5",
            "convert": True,
            "is_public": False
        }
        
        with patch('SCLib_UploadAPI_LargeFiles.upload_processor') as mock_processor:
            response = self.client.post("/api/upload/cloud/large", json=s3_data)
            self.assertEqual(response.status_code, 200)
            
            result = response.json()
            self.assertIn('job_id', result)
            self.assertEqual(result['status'], 'queued')
            
            # Verify job was submitted
            mock_processor.submit_upload_job.assert_called_once()


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)

