#!/usr/bin/env python3
"""
ScientistCloud Upload Client - Large Files (TB-scale)
Client for handling enormous datasets with chunked uploads, resumable transfers, and progress tracking.
"""

import requests
import json
import time
import hashlib
import os
import math
from typing import Dict, Any, Optional, List, Callable
from pathlib import Path
import aiohttp
import asyncio
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

@dataclass
class ChunkUploadResult:
    """Result of a chunked upload operation."""
    upload_id: str
    chunk_size: int
    total_chunks: int
    message: str

@dataclass
class ChunkStatus:
    """Status of a chunked upload."""
    upload_id: str
    uploaded_chunks: List[int]
    total_chunks: int
    is_complete: bool
    progress_percentage: float

@dataclass
class ResumeInfo:
    """Information for resuming an upload."""
    upload_id: str
    missing_chunks: List[int]
    total_chunks: int
    can_resume: bool

class LargeFileUploadClient:
    """Client for uploading TB-scale files with chunked uploads and resumable transfers."""
    
    def __init__(self, base_url: str = "http://localhost:5001", timeout: int = 300, 
                 chunk_size: int = 100 * 1024 * 1024, max_workers: int = 4):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.chunk_size = chunk_size
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ScientistCloud-LargeFile-Client/2.0.0'
        })
    
    def calculate_file_hash(self, file_path: str, progress_callback: Callable[[float], None] = None) -> str:
        """Calculate SHA-256 hash of a file with progress tracking."""
        file_size = os.path.getsize(file_path)
        file_hash = hashlib.sha256()
        bytes_read = 0
        
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                file_hash.update(chunk)
                bytes_read += len(chunk)
                
                if progress_callback:
                    progress_callback(bytes_read / file_size)
        
        return file_hash.hexdigest()
    
    def initiate_large_upload(self, file_path: str, user_email: str, dataset_name: str,
                             sensor: str, convert: bool = True, is_public: bool = False,
                             folder: str = None, team_uuid: str = None,
                             progress_callback: Callable[[float], None] = None) -> ChunkUploadResult:
        """
        Initiate a large file upload with chunked transfer.
        
        Args:
            file_path: Path to the file to upload
            user_email: User email address
            dataset_name: Name of the dataset
            sensor: Sensor type
            convert: Whether to convert the data
            is_public: Whether dataset is public
            folder: Optional folder name
            team_uuid: Optional team UUID
            progress_callback: Callback for hash calculation progress
        
        Returns:
            ChunkUploadResult with upload session information
        """
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size = file_path_obj.stat().st_size
        
        # Calculate file hash with progress tracking
        print(f"Calculating hash for {file_size / (1024**3):.2f} GB file...")
        file_hash = self.calculate_file_hash(file_path, progress_callback)
        print(f"File hash: {file_hash}")
        
        # Initiate upload session
        url = f"{self.base_url}/api/upload/large/initiate"
        
        data = {
            'filename': file_path_obj.name,
            'file_size': file_size,
            'file_hash': file_hash,
            'user_email': user_email,
            'dataset_name': dataset_name,
            'sensor': sensor,
            'convert': convert,
            'is_public': is_public
        }
        
        if folder:
            data['folder'] = folder
        if team_uuid:
            data['team_uuid'] = team_uuid
        
        response = self.session.post(url, json=data, timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        
        return ChunkUploadResult(
            upload_id=result['upload_id'],
            chunk_size=result['chunk_size'],
            total_chunks=result['total_chunks'],
            message=result['message']
        )
    
    def upload_chunk(self, upload_id: str, chunk_index: int, chunk_data: bytes) -> Dict[str, Any]:
        """Upload a single chunk."""
        url = f"{self.base_url}/api/upload/large/chunk/{upload_id}/{chunk_index}"
        
        # Calculate chunk hash
        chunk_hash = hashlib.sha256(chunk_data).hexdigest()
        
        # Prepare form data
        files = {'chunk': (f'chunk_{chunk_index}', chunk_data, 'application/octet-stream')}
        data = {'chunk_hash': chunk_hash}
        
        response = self.session.post(url, data=data, files=files, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def upload_file_chunked(self, file_path: str, user_email: str, dataset_name: str,
                           sensor: str, convert: bool = True, is_public: bool = False,
                           folder: str = None, team_uuid: str = None,
                           progress_callback: Callable[[float], None] = None,
                           resume_upload_id: str = None) -> str:
        """
        Upload a large file using chunked transfer with resumable capability.
        
        Returns:
            Upload ID for tracking
        """
        file_path_obj = Path(file_path)
        file_size = file_path_obj.stat().st_size
        
        # Check if this is a resume operation
        if resume_upload_id:
            print(f"Resuming upload: {resume_upload_id}")
            upload_id = resume_upload_id
            resume_info = self.get_resume_info(upload_id)
            if not resume_info.can_resume:
                raise ValueError("Upload cannot be resumed")
            missing_chunks = resume_info.missing_chunks
        else:
            # Initiate new upload
            print(f"Initiating large file upload: {file_size / (1024**3):.2f} GB")
            result = self.initiate_large_upload(
                file_path, user_email, dataset_name, sensor, convert, is_public, folder, team_uuid
            )
            upload_id = result.upload_id
            total_chunks = result.total_chunks
            missing_chunks = list(range(total_chunks))
            print(f"Upload ID: {upload_id}, Total chunks: {total_chunks}")
        
        # Upload chunks
        with open(file_path, 'rb') as f:
            for chunk_index in missing_chunks:
                # Seek to chunk position
                f.seek(chunk_index * self.chunk_size)
                
                # Read chunk data
                chunk_data = f.read(self.chunk_size)
                if not chunk_data:
                    break
                
                # Upload chunk with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        result = self.upload_chunk(upload_id, chunk_index, chunk_data)
                        print(f"Uploaded chunk {chunk_index + 1}/{len(missing_chunks)}: {result['message']}")
                        
                        if progress_callback:
                            progress = (chunk_index + 1) / len(missing_chunks)
                            progress_callback(progress)
                        break
                    except Exception as e:
                        if attempt == max_retries - 1:
                            raise
                        print(f"Retrying chunk {chunk_index} (attempt {attempt + 1}): {e}")
                        time.sleep(2 ** attempt)  # Exponential backoff
        
        # Complete upload
        print("Completing upload...")
        self.complete_upload(upload_id)
        
        return upload_id
    
    def upload_file_parallel(self, file_path: str, user_email: str, dataset_name: str,
                            sensor: str, convert: bool = True, is_public: bool = False,
                            folder: str = None, team_uuid: str = None,
                            progress_callback: Callable[[float], None] = None) -> str:
        """
        Upload a large file using parallel chunked transfer for maximum speed.
        
        This method uploads multiple chunks simultaneously for faster transfer.
        """
        file_path_obj = Path(file_path)
        file_size = file_path_obj.stat().st_size
        
        # Initiate upload
        print(f"Initiating parallel large file upload: {file_size / (1024**3):.2f} GB")
        result = self.initiate_large_upload(
            file_path, user_email, dataset_name, sensor, convert, is_public, folder, team_uuid
        )
        upload_id = result.upload_id
        total_chunks = result.total_chunks
        
        print(f"Upload ID: {upload_id}, Total chunks: {total_chunks}, Workers: {self.max_workers}")
        
        # Upload chunks in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            
            with open(file_path, 'rb') as f:
                for chunk_index in range(total_chunks):
                    # Seek to chunk position
                    f.seek(chunk_index * self.chunk_size)
                    
                    # Read chunk data
                    chunk_data = f.read(self.chunk_size)
                    if not chunk_data:
                        break
                    
                    # Submit chunk upload
                    future = executor.submit(self.upload_chunk, upload_id, chunk_index, chunk_data)
                    futures.append((chunk_index, future))
            
            # Process completed uploads
            completed_chunks = 0
            for chunk_index, future in futures:
                try:
                    result = future.result()
                    completed_chunks += 1
                    print(f"Completed chunk {completed_chunks}/{total_chunks}: {result['message']}")
                    
                    if progress_callback:
                        progress = completed_chunks / total_chunks
                        progress_callback(progress)
                except Exception as e:
                    print(f"Error uploading chunk {chunk_index}: {e}")
                    raise
        
        # Complete upload
        print("Completing upload...")
        self.complete_upload(upload_id)
        
        return upload_id
    
    def get_chunk_status(self, upload_id: str) -> ChunkStatus:
        """Get the status of a chunked upload."""
        url = f"{self.base_url}/api/upload/large/status/{upload_id}"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        
        return ChunkStatus(
            upload_id=data['upload_id'],
            uploaded_chunks=data['uploaded_chunks'],
            total_chunks=data['total_chunks'],
            is_complete=data['is_complete'],
            progress_percentage=data['progress_percentage']
        )
    
    def get_resume_info(self, upload_id: str) -> ResumeInfo:
        """Get information needed to resume an interrupted upload."""
        url = f"{self.base_url}/api/upload/large/resume/{upload_id}"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        
        return ResumeInfo(
            upload_id=data['upload_id'],
            missing_chunks=data['missing_chunks'],
            total_chunks=data['total_chunks'],
            can_resume=data['can_resume']
        )
    
    def complete_upload(self, upload_id: str) -> Dict[str, Any]:
        """Complete a chunked upload."""
        url = f"{self.base_url}/api/upload/large/complete/{upload_id}"
        response = self.session.post(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def cancel_upload(self, upload_id: str) -> Dict[str, str]:
        """Cancel a large file upload."""
        url = f"{self.base_url}/api/upload/large/cancel/{upload_id}"
        response = self.session.delete(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def get_upload_limits(self) -> Dict[str, Any]:
        """Get current upload limits and configuration."""
        url = f"{self.base_url}/api/upload/large/limits"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health with large file information."""
        url = f"{self.base_url}/health/large-files"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(self, upload_id: str, timeout: int = 3600, 
                           poll_interval: int = 10) -> ChunkStatus:
        """
        Wait for a chunked upload to complete.
        
        Args:
            upload_id: Upload session ID
            timeout: Maximum time to wait in seconds
            poll_interval: Time between status checks in seconds
        
        Returns:
            Final chunk status
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_chunk_status(upload_id)
            
            if status.is_complete:
                return status
            
            print(f"Upload {upload_id}: {status.progress_percentage:.1f}% complete")
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Upload {upload_id} did not complete within {timeout} seconds")

# Async version for even better performance
class AsyncLargeFileUploadClient:
    """Async version of the large file upload client."""
    
    def __init__(self, base_url: str = "http://localhost:5001", timeout: int = 300,
                 chunk_size: int = 100 * 1024 * 1024, max_concurrent: int = 8):
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.chunk_size = chunk_size
        self.max_concurrent = max_concurrent
        self.headers = {
            'User-Agent': 'ScientistCloud-LargeFile-Client-Async/2.0.0'
        }
    
    async def upload_file_async(self, file_path: str, user_email: str, dataset_name: str,
                               sensor: str, convert: bool = True, is_public: bool = False,
                               folder: str = None, team_uuid: str = None,
                               progress_callback: Callable[[float], None] = None) -> str:
        """Async version of large file upload with concurrent chunk transfers."""
        file_path_obj = Path(file_path)
        file_size = file_path_obj.stat().st_size
        
        # Initiate upload
        print(f"Initiating async large file upload: {file_size / (1024**3):.2f} GB")
        
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            # Initiate upload session
            url = f"{self.base_url}/api/upload/large/initiate"
            data = {
                'filename': file_path_obj.name,
                'file_size': file_size,
                'file_hash': await self._calculate_file_hash_async(file_path),
                'user_email': user_email,
                'dataset_name': dataset_name,
                'sensor': sensor,
                'convert': convert,
                'is_public': is_public
            }
            
            if folder:
                data['folder'] = folder
            if team_uuid:
                data['team_uuid'] = team_uuid
            
            async with session.post(url, json=data) as response:
                response.raise_for_status()
                result = await response.json()
                upload_id = result['upload_id']
                total_chunks = result['total_chunks']
        
        print(f"Upload ID: {upload_id}, Total chunks: {total_chunks}")
        
        # Upload chunks concurrently
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def upload_chunk_async(chunk_index: int, chunk_data: bytes):
            async with semaphore:
                url = f"{self.base_url}/api/upload/large/chunk/{upload_id}/{chunk_index}"
                chunk_hash = hashlib.sha256(chunk_data).hexdigest()
                
                form_data = aiohttp.FormData()
                form_data.add_field('chunk_hash', chunk_hash)
                form_data.add_field('chunk', chunk_data, filename=f'chunk_{chunk_index}')
                
                async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
                    async with session.post(url, data=form_data) as response:
                        response.raise_for_status()
                        return await response.json()
        
        # Read and upload chunks
        tasks = []
        with open(file_path, 'rb') as f:
            for chunk_index in range(total_chunks):
                f.seek(chunk_index * self.chunk_size)
                chunk_data = f.read(self.chunk_size)
                if not chunk_data:
                    break
                
                task = upload_chunk_async(chunk_index, chunk_data)
                tasks.append(task)
        
        # Execute uploads with progress tracking
        completed = 0
        for coro in asyncio.as_completed(tasks):
            result = await coro
            completed += 1
            print(f"Completed chunk {completed}/{len(tasks)}")
            
            if progress_callback:
                progress = completed / len(tasks)
                progress_callback(progress)
        
        # Complete upload
        print("Completing upload...")
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            url = f"{self.base_url}/api/upload/large/complete/{upload_id}"
            async with session.post(url) as response:
                response.raise_for_status()
                result = await response.json()
        
        return upload_id
    
    async def _calculate_file_hash_async(self, file_path: str) -> str:
        """Calculate file hash asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._calculate_file_hash_sync, file_path)
    
    def _calculate_file_hash_sync(self, file_path: str) -> str:
        """Synchronous file hash calculation."""
        file_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b""):
                file_hash.update(chunk)
        return file_hash.hexdigest()




