#!/usr/bin/env python3
"""
Test cases for SCLib_UploadClient_LargeFiles module.
Tests the large files client for TB-scale upload operations.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
import json
import tempfile
import os
import hashlib
from io import BytesIO
import requests

# Import the module under test
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SCLib_UploadClient_LargeFiles import (
    LargeFileUploadClient, AsyncLargeFileUploadClient,
    ChunkUploadResult, ChunkStatus, ResumeInfo
)


class TestLargeFileUploadClient(unittest.TestCase):
    """Test LargeFileUploadClient."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = LargeFileUploadClient("http://localhost:5001")
    
    @patch('requests.Session.get')
    def test_health_check(self, mock_get):
        """Test health check."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "healthy",
            "timestamp": "2023-01-01T00:00:00Z",
            "active_uploads": 0,
            "temp_directory_size_mb": 0,
            "max_file_size_tb": 10,
            "chunk_size_mb": 100
        }
        mock_get.return_value = mock_response
        
        result = self.client.health_check()
        
        self.assertEqual(result['status'], 'healthy')
        self.assertEqual(result['active_uploads'], 0)
        self.assertEqual(result['max_file_size_tb'], 10)
        mock_get.assert_called_once_with("http://localhost:5001/health/large-files", timeout=300)
    
    @patch('requests.Session.get')
    def test_get_upload_limits(self, mock_get):
        """Test getting upload limits."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "max_file_size_bytes": 10995116277760,  # 10TB
            "max_file_size_tb": 10,
            "chunk_size_bytes": 104857600,  # 100MB
            "chunk_size_mb": 100,
            "resumable_upload_timeout_days": 7,
            "supported_source_types": ["local", "google_drive", "s3", "url"],
            "recommended_for_files_larger_than_mb": 100,
            "temp_directory": "/tmp/scientistcloud_uploads"
        }
        mock_get.return_value = mock_response
        
        result = self.client.get_upload_limits()
        
        self.assertEqual(result['max_file_size_tb'], 10)
        self.assertEqual(result['chunk_size_mb'], 100)
        self.assertEqual(result['recommended_for_files_larger_than_mb'], 100)
        mock_get.assert_called_once_with("http://localhost:5001/api/upload/large/limits", timeout=300)
    
    def test_calculate_file_hash(self):
        """Test file hash calculation."""
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test content for hashing")
            temp_file = f.name
        
        try:
            # Calculate hash
            file_hash = self.client.calculate_file_hash(temp_file)
            
            # Verify it's a valid SHA-256 hash
            self.assertEqual(len(file_hash), 64)  # SHA-256 hex length
            self.assertTrue(all(c in '0123456789abcdef' for c in file_hash))
            
        finally:
            os.unlink(temp_file)
    
    def test_calculate_file_hash_with_progress(self):
        """Test file hash calculation with progress callback."""
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test content for hashing with progress")
            temp_file = f.name
        
        try:
            progress_values = []
            
            def progress_callback(progress):
                progress_values.append(progress)
            
            # Calculate hash
            file_hash = self.client.calculate_file_hash(temp_file, progress_callback)
            
            # Verify progress was called
            self.assertGreater(len(progress_values), 0)
            self.assertEqual(progress_values[-1], 1.0)  # Final progress should be 1.0
            
        finally:
            os.unlink(temp_file)
    
    @patch('requests.Session.post')
    def test_initiate_large_upload_success(self, mock_post):
        """Test successful large upload initiation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "upload_id": "large_upload_123",
            "chunk_size": 104857600,  # 100MB
            "total_chunks": 50,
            "message": "Upload session created for large_dataset.idx"
        }
        mock_post.return_value = mock_response
        
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.idx') as f:
            f.write("test content" * 1000)  # Make it reasonably sized
            temp_file = f.name
        
        try:
            result = self.client.initiate_large_upload(
                file_path=temp_file,
                user_email="user@example.com",
                dataset_name="Large Dataset",
                sensor="IDX"
            )
            
            self.assertEqual(result.upload_id, "large_upload_123")
            self.assertEqual(result.chunk_size, 104857600)
            self.assertEqual(result.total_chunks, 50)
            self.assertIn("large_dataset.idx", result.message)
            
            # Verify the request was made correctly
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            self.assertEqual(call_args[0][0], "http://localhost:5001/api/upload/large/initiate")
            
            request_data = call_args[1]['json']
            self.assertEqual(request_data['filename'], 'large_dataset.idx')
            self.assertEqual(request_data['user_email'], 'user@example.com')
            self.assertEqual(request_data['sensor'], 'IDX')
            self.assertIn('file_hash', request_data)
            
        finally:
            os.unlink(temp_file)
    
    @patch('requests.Session.post')
    def test_initiate_large_upload_file_not_found(self, mock_post):
        """Test large upload initiation with non-existent file."""
        with self.assertRaises(FileNotFoundError):
            self.client.initiate_large_upload(
                file_path="/non/existent/file.idx",
                user_email="user@example.com",
                dataset_name="Large Dataset",
                sensor="IDX"
            )
    
    @patch('requests.Session.post')
    def test_upload_chunk_success(self, mock_post):
        """Test successful chunk upload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "Chunk 0 uploaded successfully",
            "uploaded_chunks": 1,
            "total_chunks": 50
        }
        mock_post.return_value = mock_response
        
        chunk_data = b"chunk data content"
        result = self.client.upload_chunk("upload_123", 0, chunk_data)
        
        self.assertEqual(result['message'], "Chunk 0 uploaded successfully")
        self.assertEqual(result['uploaded_chunks'], 1)
        self.assertEqual(result['total_chunks'], 50)
        
        # Verify the request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "http://localhost:5001/api/upload/large/chunk/upload_123/0")
        
        # Check that files and data were passed correctly
        self.assertIn('files', call_args[1])
        self.assertIn('data', call_args[1])
        self.assertIn('chunk_hash', call_args[1]['data'])
    
    @patch('requests.Session.get')
    def test_get_chunk_status(self, mock_get):
        """Test getting chunk status."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "upload_id": "upload_123",
            "uploaded_chunks": [0, 1, 2, 5, 7],
            "total_chunks": 10,
            "is_complete": False,
            "progress_percentage": 50.0
        }
        mock_get.return_value = mock_response
        
        result = self.client.get_chunk_status("upload_123")
        
        self.assertEqual(result.upload_id, "upload_123")
        self.assertEqual(result.uploaded_chunks, [0, 1, 2, 5, 7])
        self.assertEqual(result.total_chunks, 10)
        self.assertFalse(result.is_complete)
        self.assertEqual(result.progress_percentage, 50.0)
        mock_get.assert_called_once_with("http://localhost:5001/api/upload/large/status/upload_123", timeout=300)
    
    @patch('requests.Session.get')
    def test_get_resume_info(self, mock_get):
        """Test getting resume information."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "upload_id": "upload_123",
            "missing_chunks": [3, 4, 6, 8, 9],
            "total_chunks": 10,
            "can_resume": True
        }
        mock_get.return_value = mock_response
        
        result = self.client.get_resume_info("upload_123")
        
        self.assertEqual(result.upload_id, "upload_123")
        self.assertEqual(result.missing_chunks, [3, 4, 6, 8, 9])
        self.assertEqual(result.total_chunks, 10)
        self.assertTrue(result.can_resume)
        mock_get.assert_called_once_with("http://localhost:5001/api/upload/large/resume/upload_123", timeout=300)
    
    @patch('requests.Session.post')
    def test_complete_upload(self, mock_post):
        """Test completing upload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": "Upload completed successfully: large_dataset.idx",
            "file_path": "/tmp/upload_123/large_dataset.idx",
            "file_size": 5242880000,  # 5GB
            "job_submitted": True
        }
        mock_post.return_value = mock_response
        
        result = self.client.complete_upload("upload_123")
        
        self.assertIn("completed successfully", result['message'])
        self.assertIn("large_dataset.idx", result['file_path'])
        self.assertEqual(result['file_size'], 5242880000)
        self.assertTrue(result['job_submitted'])
        mock_post.assert_called_once_with("http://localhost:5001/api/upload/large/complete/upload_123", timeout=300)
    
    @patch('requests.Session.delete')
    def test_cancel_upload(self, mock_delete):
        """Test canceling upload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "Upload session upload_123 cancelled and cleaned up"}
        mock_delete.return_value = mock_response
        
        result = self.client.cancel_upload("upload_123")
        
        self.assertIn("cancelled and cleaned up", result['message'])
        mock_delete.assert_called_once_with("http://localhost:5001/api/upload/large/cancel/upload_123", timeout=300)
    
    @patch('requests.Session.get')
    def test_wait_for_completion_success(self, mock_get):
        """Test waiting for completion - success case."""
        # Mock responses for status checks
        responses = [
            # First check - still uploading
            MagicMock(status_code=200, json=lambda: {
                "upload_id": "upload_123",
                "uploaded_chunks": [0, 1, 2, 3, 4],
                "total_chunks": 10,
                "is_complete": False,
                "progress_percentage": 50.0
            }),
            # Second check - completed
            MagicMock(status_code=200, json=lambda: {
                "upload_id": "upload_123",
                "uploaded_chunks": list(range(10)),
                "total_chunks": 10,
                "is_complete": True,
                "progress_percentage": 100.0
            })
        ]
        mock_get.side_effect = responses
        
        result = self.client.wait_for_completion("upload_123", timeout=10, poll_interval=1)
        
        self.assertTrue(result.is_complete)
        self.assertEqual(result.progress_percentage, 100.0)
        self.assertEqual(mock_get.call_count, 2)
    
    @patch('requests.Session.get')
    def test_wait_for_completion_timeout(self, mock_get):
        """Test waiting for completion - timeout case."""
        # Mock response that never completes
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "upload_id": "upload_123",
            "uploaded_chunks": [0, 1, 2],
            "total_chunks": 10,
            "is_complete": False,
            "progress_percentage": 30.0
        }
        mock_get.return_value = mock_response
        
        with self.assertRaises(TimeoutError):
            self.client.wait_for_completion("upload_123", timeout=1, poll_interval=0.5)
    
    @patch('requests.Session.post')
    def test_upload_file_chunked_success(self, mock_post):
        """Test successful chunked file upload."""
        # Mock responses for initiate and complete
        initiate_response = MagicMock()
        initiate_response.status_code = 200
        initiate_response.json.return_value = {
            "upload_id": "chunked_upload_123",
            "chunk_size": 104857600,  # 100MB
            "total_chunks": 2,
            "message": "Upload session created for test_file.txt"
        }
        
        complete_response = MagicMock()
        complete_response.status_code = 200
        complete_response.json.return_value = {
            "message": "Upload completed successfully: test_file.txt",
            "file_path": "/tmp/chunked_upload_123/test_file.txt",
            "file_size": 200000000,  # 200MB
            "job_submitted": True
        }
        
        # Mock chunk upload responses
        chunk_responses = [
            MagicMock(status_code=200, json=lambda: {
                "message": f"Chunk {i} uploaded successfully",
                "uploaded_chunks": i + 1,
                "total_chunks": 2
            }) for i in range(2)
        ]
        
        # Set up mock responses
        mock_post.side_effect = [initiate_response] + chunk_responses + [complete_response]
        
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test content" * 10000)  # Make it reasonably sized
            temp_file = f.name
        
        try:
            result = self.client.upload_file_chunked(
                file_path=temp_file,
                user_email="user@example.com",
                dataset_name="Chunked Dataset",
                sensor="TIFF"
            )
            
            self.assertEqual(result, "chunked_upload_123")
            
            # Verify all requests were made
            self.assertEqual(mock_post.call_count, 4)  # initiate + 2 chunks + complete
            
        finally:
            os.unlink(temp_file)
    
    @patch('requests.Session.post')
    def test_upload_file_parallel_success(self, mock_post):
        """Test successful parallel file upload."""
        # Mock responses for initiate and complete
        initiate_response = MagicMock()
        initiate_response.status_code = 200
        initiate_response.json.return_value = {
            "upload_id": "parallel_upload_123",
            "chunk_size": 104857600,  # 100MB
            "total_chunks": 2,
            "message": "Upload session created for test_file.txt"
        }
        
        complete_response = MagicMock()
        complete_response.status_code = 200
        complete_response.json.return_value = {
            "message": "Upload completed successfully: test_file.txt",
            "file_path": "/tmp/parallel_upload_123/test_file.txt",
            "file_size": 200000000,  # 200MB
            "job_submitted": True
        }
        
        # Mock chunk upload responses
        chunk_responses = [
            MagicMock(status_code=200, json=lambda: {
                "message": f"Chunk {i} uploaded successfully",
                "uploaded_chunks": i + 1,
                "total_chunks": 2
            }) for i in range(2)
        ]
        
        # Set up mock responses
        mock_post.side_effect = [initiate_response] + chunk_responses + [complete_response]
        
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test content" * 10000)  # Make it reasonably sized
            temp_file = f.name
        
        try:
            result = self.client.upload_file_parallel(
                file_path=temp_file,
                user_email="user@example.com",
                dataset_name="Parallel Dataset",
                sensor="TIFF"
            )
            
            self.assertEqual(result, "parallel_upload_123")
            
            # Verify all requests were made
            self.assertEqual(mock_post.call_count, 4)  # initiate + 2 chunks + complete
            
        finally:
            os.unlink(temp_file)
    
    @patch('requests.Session.post')
    def test_http_error_handling(self, mock_post):
        """Test HTTP error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 413  # Payload too large
        mock_response.raise_for_status.side_effect = requests.HTTPError("413 Payload Too Large")
        mock_post.return_value = mock_response
        
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test content")
            temp_file = f.name
        
        try:
            with self.assertRaises(requests.HTTPError):
                self.client.initiate_large_upload(
                    file_path=temp_file,
                    user_email="user@example.com",
                    dataset_name="Test Dataset",
                    sensor="TIFF"
                )
        finally:
            os.unlink(temp_file)


class TestAsyncLargeFileUploadClient(unittest.TestCase):
    """Test AsyncLargeFileUploadClient."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = AsyncLargeFileUploadClient("http://localhost:5001")
    
    def test_calculate_file_hash_sync(self):
        """Test synchronous file hash calculation."""
        # Create a temporary test file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test content for async hashing")
            temp_file = f.name
        
        try:
            # Calculate hash using the sync method
            file_hash = self.client._calculate_file_hash_sync(temp_file)
            
            # Verify it's a valid SHA-256 hash
            self.assertEqual(len(file_hash), 64)  # SHA-256 hex length
            self.assertTrue(all(c in '0123456789abcdef' for c in file_hash))
            
        finally:
            os.unlink(temp_file)
    
    @patch('aiohttp.ClientSession.post')
    def test_upload_file_async(self, mock_post):
        """Test async file upload."""
        import asyncio
        
        async def run_test():
            # Create a temporary test file
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
                f.write("test content for async upload")
                temp_file = f.name
            
            try:
                # Mock the aiohttp response
                mock_response = MagicMock()
                mock_response.status = 200
                mock_response.json.return_value = {
                    "upload_id": "async_upload_123",
                    "chunk_size": 104857600,  # 100MB
                    "total_chunks": 1,
                    "message": "Upload session created for test_file.txt"
                }
                mock_post.return_value.__aenter__.return_value = mock_response
                
                result = await self.client.upload_file_async(
                    file_path=temp_file,
                    user_email="user@example.com",
                    dataset_name="Async Dataset",
                    sensor="TIFF"
                )
                
                self.assertEqual(result, "async_upload_123")
                
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
                "upload_id": "upload_123",
                "uploaded_chunks": [0, 1, 2],
                "total_chunks": 5,
                "is_complete": False,
                "progress_percentage": 60.0
            }
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await self.client.get_upload_status("upload_123")
            
            self.assertEqual(result.upload_id, "upload_123")
            self.assertEqual(result.uploaded_chunks, [0, 1, 2])
            self.assertEqual(result.total_chunks, 5)
            self.assertFalse(result.is_complete)
            self.assertEqual(result.progress_percentage, 60.0)
        
        # Run the async test
        asyncio.run(run_test())
    
    @patch('aiohttp.ClientSession.get')
    def test_wait_for_completion_async(self, mock_get):
        """Test async wait for completion."""
        import asyncio
        
        async def run_test():
            # Mock responses for status checks
            responses = [
                # First check - still uploading
                MagicMock(status=200, json=lambda: {
                    "upload_id": "upload_123",
                    "uploaded_chunks": [0, 1, 2],
                    "total_chunks": 5,
                    "is_complete": False,
                    "progress_percentage": 60.0
                }),
                # Second check - completed
                MagicMock(status=200, json=lambda: {
                    "upload_id": "upload_123",
                    "uploaded_chunks": [0, 1, 2, 3, 4],
                    "total_chunks": 5,
                    "is_complete": True,
                    "progress_percentage": 100.0
                })
            ]
            
            # Set up mock responses
            mock_get.side_effect = [r.__aenter__.return_value for r in responses]
            
            result = await self.client.wait_for_completion("upload_123", timeout=10, poll_interval=1)
            
            self.assertTrue(result.is_complete)
            self.assertEqual(result.progress_percentage, 100.0)
        
        # Run the async test
        asyncio.run(run_test())


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)




