#!/usr/bin/env python3
"""
ScientistCloud Upload API Client - FastAPI Compatible
Modern client for interacting with the FastAPI-based ScientistCloud Upload API.
"""

import requests
import json
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
import aiohttp
import asyncio
from dataclasses import dataclass

@dataclass
class UploadResult:
    """Result of an upload operation."""
    job_id: str
    status: str
    message: str
    estimated_duration: Optional[int] = None

@dataclass
class JobStatus:
    """Status of an upload job."""
    job_id: str
    status: str
    progress_percentage: float
    bytes_uploaded: Optional[int] = None
    bytes_total: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None
    created_at: str = None
    updated_at: str = None

class ScientistCloudUploadClient:
    """Modern client for interacting with the ScientistCloud Upload API."""
    
    def __init__(self, base_url: str = "http://localhost:5000", timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ScientistCloud-Upload-Client/2.0.0'
        })
    
    def upload_local_file(self, file_path: str, user_email: str, dataset_name: str, 
                         sensor: str, convert: bool = True, is_public: bool = False,
                         folder: str = None, team_uuid: str = None) -> UploadResult:
        """
        Upload a local file.
        
        Args:
            file_path: Path to the file to upload
            user_email: User email address
            dataset_name: Name of the dataset
            sensor: Sensor type (IDX, TIFF, TIFF RGB, NETCDF, HDF5, 4D_NEXUS, RGB, MAPIR, OTHER)
            convert: Whether to convert the data
            is_public: Whether dataset is public
            folder: Optional folder name
            team_uuid: Optional team UUID
        
        Returns:
            UploadResult with job information
        """
        url = f"{self.base_url}/api/upload/local/upload"
        
        # Prepare form data
        form_data = {
            'user_email': user_email,
            'dataset_name': dataset_name,
            'sensor': sensor,
            'convert': str(convert).lower(),
            'is_public': str(is_public).lower()
        }
        
        if folder:
            form_data['folder'] = folder
        if team_uuid:
            form_data['team_uuid'] = team_uuid
        
        # Prepare file
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, 'rb') as f:
            files = {'file': (file_path_obj.name, f, 'application/octet-stream')}
            response = self.session.post(url, data=form_data, files=files, timeout=self.timeout)
        
        response.raise_for_status()
        data = response.json()
        
        return UploadResult(
            job_id=data['job_id'],
            status=data['status'],
            message=data['message'],
            estimated_duration=data.get('estimated_duration')
        )
    
    def initiate_google_drive_upload(self, file_id: str, service_account_file: str,
                                   user_email: str, dataset_name: str, sensor: str,
                                   convert: bool = True, is_public: bool = False,
                                   folder: str = None, team_uuid: str = None) -> UploadResult:
        """Initiate a Google Drive upload."""
        url = f"{self.base_url}/api/upload/initiate"
        
        data = {
            'source_type': 'google_drive',
            'source_config': {
                'file_id': file_id,
                'service_account_file': service_account_file
            },
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
        
        return UploadResult(
            job_id=result['job_id'],
            status=result['status'],
            message=result['message'],
            estimated_duration=result.get('estimated_duration')
        )
    
    def upload_file_by_path(self, file_path: str, user_email: str, dataset_name: str,
                           sensor: str, convert: bool = True, is_public: bool = False,
                           folder: str = None, team_uuid: str = None, dataset_identifier: str = None,
                           add_to_existing: bool = False,
                           progress_callback: Callable[[float], None] = None) -> UploadResult:
        """
        Upload a file by providing its path instead of uploading the file content.
        This is more efficient for large files as it avoids copying to /tmp.
        
        ⚠️  IMPORTANT: This method requires the file to be accessible from the server.
        It's primarily intended for development use where files are mounted in Docker.
        For production use, prefer upload_file() which works across all environments.
        
        See README_upload_methods.md for detailed documentation.
        """
        url = f"{self.base_url}/api/upload/upload-path"
        
        form_data = {
            'file_path': file_path,
            'user_email': user_email,
            'dataset_name': dataset_name,
            'sensor': sensor,
            'convert': convert,
            'is_public': is_public
        }
        
        if folder:
            form_data['folder'] = folder
        if team_uuid:
            form_data['team_uuid'] = team_uuid
        if dataset_identifier:
            form_data['dataset_identifier'] = dataset_identifier
        if add_to_existing:
            form_data['add_to_existing'] = str(add_to_existing).lower()
        
        # For path-based uploads, we don't need to send file content
        response = self.session.post(url, data=form_data, timeout=self.timeout)
        
        response.raise_for_status()
        data = response.json()
        
        if progress_callback:
            progress_callback(1.0)
        
        return UploadResult(
            job_id=data['job_id'],
            status=data['status'],
            message=data['message'],
            upload_type=data['upload_type'],
            estimated_duration=data.get('estimated_duration')
        )
    
    def initiate_s3_upload(self, bucket_name: str, object_key: str, access_key_id: str,
                          secret_access_key: str, user_email: str, dataset_name: str,
                          sensor: str, convert: bool = True, is_public: bool = False,
                          folder: str = None, team_uuid: str = None) -> UploadResult:
        """Initiate an S3 upload."""
        url = f"{self.base_url}/api/upload/initiate"
        
        data = {
            'source_type': 's3',
            'source_config': {
                'bucket_name': bucket_name,
                'object_key': object_key,
                'access_key_id': access_key_id,
                'secret_access_key': secret_access_key
            },
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
        
        return UploadResult(
            job_id=result['job_id'],
            status=result['status'],
            message=result['message'],
            estimated_duration=result.get('estimated_duration')
        )
    
    def initiate_url_upload(self, url: str, user_email: str, dataset_name: str,
                           sensor: str, convert: bool = True, is_public: bool = False,
                           folder: str = None, team_uuid: str = None) -> UploadResult:
        """Initiate a URL-based upload."""
        api_url = f"{self.base_url}/api/upload/initiate"
        
        data = {
            'source_type': 'url',
            'source_config': {
                'url': url
            },
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
        
        response = self.session.post(api_url, json=data, timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        
        return UploadResult(
            job_id=result['job_id'],
            status=result['status'],
            message=result['message'],
            estimated_duration=result.get('estimated_duration')
        )
    
    def get_upload_status(self, job_id: str) -> JobStatus:
        """Get the status of an upload job."""
        url = f"{self.base_url}/api/upload/status/{job_id}"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        
        return JobStatus(
            job_id=data['job_id'],
            status=data['status'],
            progress_percentage=data['progress_percentage'],
            bytes_uploaded=data.get('bytes_uploaded'),
            bytes_total=data.get('bytes_total'),
            message=data.get('message'),
            error=data.get('error'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def cancel_upload(self, job_id: str) -> Dict[str, str]:
        """Cancel an upload job."""
        url = f"{self.base_url}/api/upload/cancel/{job_id}"
        response = self.session.post(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def list_upload_jobs(self, user_email: str, status: str = None, 
                        limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """List upload jobs for a user."""
        url = f"{self.base_url}/api/upload/jobs"
        params = {
            'user_id': user_email,
            'limit': limit,
            'offset': offset
        }
        if status:
            params['status'] = status
        
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def get_supported_sources(self) -> Dict[str, Any]:
        """Get supported upload sources and their requirements."""
        url = f"{self.base_url}/api/upload/supported-sources"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def estimate_upload_time(self, source_type: str, file_size_mb: float = None) -> Dict[str, Any]:
        """Estimate upload time based on source type and file size."""
        url = f"{self.base_url}/api/upload/estimate-time"
        params = {'source_type': source_type}
        if file_size_mb:
            params['file_size_mb'] = file_size_mb
        
        response = self.session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(self, job_id: str, timeout: int = 3600, 
                           poll_interval: int = 5) -> JobStatus:
        """
        Wait for an upload job to complete.
        
        Args:
            job_id: Upload job ID
            timeout: Maximum time to wait in seconds
            poll_interval: Time between status checks in seconds
        
        Returns:
            Final job status
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_upload_status(job_id)
            
            if status.status in ['completed', 'failed', 'cancelled']:
                return status
            
            print(f"Job {job_id}: {status.status} - {status.progress_percentage:.1f}%")
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Upload job {job_id} did not complete within {timeout} seconds")
    
    def health_check(self) -> Dict[str, str]:
        """Check API health."""
        url = f"{self.base_url}/health"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    def get_api_info(self) -> Dict[str, str]:
        """Get API information."""
        url = f"{self.base_url}/"
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

# Async version for better performance
class AsyncScientistCloudUploadClient:
    """Async version of the upload client for better performance."""
    
    def __init__(self, base_url: str = "http://localhost:5000", timeout: int = 30):
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.headers = {
            'User-Agent': 'ScientistCloud-Upload-Client-Async/2.0.0'
        }
    
    async def upload_local_file(self, file_path: str, user_email: str, dataset_name: str, 
                               sensor: str, convert: bool = True, is_public: bool = False,
                               folder: str = None, team_uuid: str = None) -> UploadResult:
        """Async version of upload_local_file."""
        url = f"{self.base_url}/api/upload/local/upload"
        
        # Prepare form data
        form_data = aiohttp.FormData()
        form_data.add_field('user_email', user_email)
        form_data.add_field('dataset_name', dataset_name)
        form_data.add_field('sensor', sensor)
        form_data.add_field('convert', str(convert).lower())
        form_data.add_field('is_public', str(is_public).lower())
        
        if folder:
            form_data.add_field('folder', folder)
        if team_uuid:
            form_data.add_field('team_uuid', team_uuid)
        
        # Add file
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        form_data.add_field('file', open(file_path, 'rb'), filename=file_path_obj.name)
        
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            async with session.post(url, data=form_data) as response:
                response.raise_for_status()
                data = await response.json()
                
                return UploadResult(
                    job_id=data['job_id'],
                    status=data['status'],
                    message=data['message'],
                    estimated_duration=data.get('estimated_duration')
                )
    
    async def get_upload_status(self, job_id: str) -> JobStatus:
        """Async version of get_upload_status."""
        url = f"{self.base_url}/api/upload/status/{job_id}"
        
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                
                return JobStatus(
                    job_id=data['job_id'],
                    status=data['status'],
                    progress_percentage=data['progress_percentage'],
                    bytes_uploaded=data.get('bytes_uploaded'),
                    bytes_total=data.get('bytes_total'),
                    message=data.get('message'),
                    error=data.get('error'),
                    created_at=data.get('created_at'),
                    updated_at=data.get('updated_at')
                )
    
    async def wait_for_completion(self, job_id: str, timeout: int = 3600, 
                                 poll_interval: int = 5) -> JobStatus:
        """Async version of wait_for_completion."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = await self.get_upload_status(job_id)
            
            if status.status in ['completed', 'failed', 'cancelled']:
                return status
            
            print(f"Job {job_id}: {status.status} - {status.progress_percentage:.1f}%")
            await asyncio.sleep(poll_interval)
        
        raise TimeoutError(f"Upload job {job_id} did not complete within {timeout} seconds")

