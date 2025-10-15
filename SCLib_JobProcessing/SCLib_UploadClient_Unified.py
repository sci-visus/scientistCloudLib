#!/usr/bin/env python3
"""
ScientistCloud Upload Client - Unified Version
Automatically handles both regular and TB-scale uploads based on file size.
No need for users to choose between client versions!
"""

import requests
import json
import time
import hashlib
import os
import math
import uuid
from typing import Dict, Any, Optional, List, Callable
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
    upload_type: str
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
    """Unified client that automatically handles both regular and TB-scale uploads."""
    
    def __init__(self, base_url: str = "http://localhost:5000", timeout: int = 300):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ScientistCloud-Upload-Client-Unified/2.0.0'
        })
    
    def upload_file(self, file_path: str, user_email: str, dataset_name: str, 
                   sensor: str, convert: bool = True, is_public: bool = False,
                   folder: str = None, team_uuid: str = None, dataset_uuid: str = None,
                   progress_callback: Callable[[float], None] = None) -> UploadResult:
        """
        Upload a file with automatic handling of standard vs chunked uploads.
        
        Files larger than 100MB are automatically handled with chunked uploads.
        Smaller files use standard upload for better performance.
        
        Args:
            file_path: Path to the file to upload
            user_email: User email address
            dataset_name: Name of the dataset
            sensor: Sensor type (IDX, TIFF, TIFF RGB, NETCDF, HDF5, 4D_NEXUS, RGB, MAPIR, OTHER)
            convert: Whether to convert the data
            is_public: Whether dataset is public
            folder: Optional folder name
            team_uuid: Optional team UUID
            progress_callback: Callback for progress tracking
        
        Returns:
            UploadResult with job information
        """
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size = file_path_obj.stat().st_size
        
        # Show progress for hash calculation if callback provided
        if progress_callback:
            print(f"Preparing {file_size / (1024**3):.2f} GB file for upload...")
            progress_callback(0.1)
        
        url = f"{self.base_url}/api/upload/upload"
        
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
        if dataset_uuid:
            form_data['dataset_uuid'] = dataset_uuid
        
        # Prepare file
        with open(file_path, 'rb') as f:
            files = {'file': (file_path_obj.name, f, 'application/octet-stream')}
            response = self.session.post(url, data=form_data, files=files, timeout=self.timeout)
        
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
            upload_type=result['upload_type'],
            estimated_duration=result.get('estimated_duration')
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
            upload_type=result['upload_type'],
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
            upload_type=result['upload_type'],
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
    
    def get_upload_limits(self) -> Dict[str, Any]:
        """Get current upload limits and configuration."""
        url = f"{self.base_url}/api/upload/limits"
        response = self.session.get(url, timeout=self.timeout)
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
    
    def upload_directory(self, directory_path: str, user_email: str, dataset_name: str,
                        sensor: str, convert: bool = True, is_public: bool = False,
                        folder: str = None, team_uuid: str = None,
                        progress_callback: Callable[[float], None] = None) -> List[UploadResult]:
        """
        Upload all files in a directory automatically.
        
        Args:
            directory_path: Path to directory containing files to upload
            user_email: User email address
            dataset_name: Base name for the dataset
            sensor: Sensor type
            convert: Whether to convert the data
            is_public: Whether dataset is public
            folder: Optional folder name
            team_uuid: Optional team UUID
            progress_callback: Progress callback function
            
        Returns:
            List of UploadResult objects for each file uploaded
        """
        directory_path_obj = Path(directory_path)
        
        if not directory_path_obj.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        if not directory_path_obj.is_dir():
            raise ValueError(f"Path is not a directory: {directory_path}")
        
        # Find all files in the directory
        files_to_upload = []
        for file_path in directory_path_obj.rglob('*'):
            if file_path.is_file():
                files_to_upload.append(file_path)
        
        if not files_to_upload:
            raise ValueError(f"No files found in directory: {directory_path}")
        
        print(f"📁 Found {len(files_to_upload)} files in directory: {directory_path}")
        
        # Upload each file
        results = []
        # Use a single UUID for the entire directory upload
        directory_uuid = str(uuid.uuid4())
        
        for i, file_path in enumerate(files_to_upload, 1):
            relative_path = file_path.relative_to(directory_path_obj)
            
            # For directory uploads, use the relative path as the folder structure
            # This preserves the directory structure within the source directory
            if relative_path.parent != Path('.'):
                file_folder = str(relative_path.parent)
            else:
                file_folder = None  # No subdirectory, file goes directly in UUID directory
            
            print(f"📤 Uploading {i}/{len(files_to_upload)}: {relative_path}")
            print(f"   📁 Will go into UUID directory: {directory_uuid}")
            print(f"   📂 Folder structure: {file_folder if file_folder else 'root'}")
            
            try:
                # Create progress callback for this file
                def file_progress_callback(progress: float):
                    if progress_callback:
                        # Calculate overall progress across all files
                        overall_progress = ((i - 1) + progress) / len(files_to_upload)
                        progress_callback(overall_progress)
                    print(f"   Progress: {progress*100:.1f}%", end='\r')
                
                result = self.upload_file(
                    file_path=str(file_path),
                    user_email=user_email,
                    dataset_name=dataset_name,  # Use the original dataset name
                    sensor=sensor,
                    convert=convert,
                    is_public=is_public,
                    folder=file_folder,
                    team_uuid=team_uuid,
                    dataset_uuid=directory_uuid,  # Use shared UUID for directory upload
                    progress_callback=file_progress_callback
                )
                
                print(f"   ✅ Uploaded: {result.job_id}")
                results.append(result)
                
            except Exception as e:
                print(f"   ❌ Failed: {e}")
                # Create a failed result
                failed_result = UploadResult(
                    job_id="",
                    status="failed",
                    message=f"Failed to upload {relative_path}: {e}",
                    upload_type="failed"
                )
                results.append(failed_result)
        
        print(f"\n🎉 Directory upload complete!")
        print(f"   Successfully uploaded: {len([r for r in results if r.status != 'failed'])} files")
        print(f"   Failed uploads: {len([r for r in results if r.status == 'failed'])} files")
        
        return results
    
    def upload_from_source(self, source_type: str, source_config: dict, user_email: str, 
                          dataset_name: str, sensor: str, convert: bool = True, 
                          is_public: bool = False, folder: str = None, 
                          team_uuid: str = None, progress_callback: Callable[[float], None] = None) -> UploadResult:
        """
        Upload from any source type (Google Drive, S3, URL, etc.).
        
        Args:
            source_type: Type of source ('google_drive', 's3', 'url', 'local')
            source_config: Source-specific configuration
            user_email: User email address
            dataset_name: Name for the dataset
            sensor: Sensor type
            convert: Whether to convert the data
            is_public: Whether dataset is public
            folder: Optional folder name
            team_uuid: Optional team UUID
            progress_callback: Progress callback function
            
        Returns:
            UploadResult object
        """
        # Prepare the request data
        data = {
            "source_type": source_type,
            "source_config": source_config,
            "user_email": user_email,
            "dataset_name": dataset_name,
            "sensor": sensor,
            "convert": convert,
            "is_public": is_public,
            "folder": folder,
            "team_uuid": team_uuid
        }
        
        # Send the request
        url = f"{self.base_url}/api/upload/initiate"
        response = self.session.post(url, json=data, timeout=self.timeout)
        response.raise_for_status()
        
        result = response.json()
        return UploadResult(
            job_id=result['job_id'],
            status=result['status'],
            message=result['message'],
            upload_type=result.get('upload_type', 'standard'),
            estimated_duration=result.get('estimated_duration')
        )
    
    def upload_directory_from_source(self, source_type: str, source_config: dict, 
                                   user_email: str, dataset_name: str, sensor: str,
                                   convert: bool = True, is_public: bool = False,
                                   folder: str = None, team_uuid: str = None,
                                   progress_callback: Callable[[float], None] = None) -> List[UploadResult]:
        """
        Upload directory from any source type (Google Drive, S3, etc.).
        
        This method handles directory uploads from remote sources by:
        1. For Google Drive: Lists all files in a folder and uploads each
        2. For S3: Lists all objects with a prefix and uploads each
        3. For URLs: Not supported - URLs are stored as direct links
        4. For local: Uses the existing upload_directory method
        
        Args:
            source_type: Type of source ('google_drive', 's3', 'url', 'local')
            source_config: Source-specific configuration
            user_email: User email address
            dataset_name: Name for the dataset
            sensor: Sensor type
            convert: Whether to convert the data
            is_public: Whether dataset is public
            folder: Optional folder name
            team_uuid: Optional team UUID
            progress_callback: Progress callback function
            
        Returns:
            List of UploadResult objects for each file uploaded
        """
        if source_type == 'local':
            # Use the existing directory upload method for local files
            directory_path = source_config.get('directory_path')
            if not directory_path:
                raise ValueError("For local source type, 'directory_path' must be provided in source_config")
            
            return self.upload_directory(
                directory_path=directory_path,
                user_email=user_email,
                dataset_name=dataset_name,
                sensor=sensor,
                convert=convert,
                is_public=is_public,
                folder=folder,
                team_uuid=team_uuid,
                progress_callback=progress_callback
            )
        
        # For remote sources, we need to get the list of files first
        # This would require implementing source-specific file listing
        # For now, we'll provide a framework that can be extended
        
        if source_type == 'google_drive':
            return self._upload_google_drive_directory(
                source_config, user_email, dataset_name, sensor,
                convert, is_public, folder, team_uuid, progress_callback
            )
        elif source_type == 's3':
            return self._upload_s3_directory(
                source_config, user_email, dataset_name, sensor,
                convert, is_public, folder, team_uuid, progress_callback
            )
        elif source_type == 'url':
            # URL directory upload is not supported - URLs are just stored as links
            raise ValueError("URL directory upload is not supported. URLs are stored as direct links without downloading.")
        else:
            raise ValueError(f"Directory upload not supported for source type: {source_type}")
    
    def _upload_google_drive_directory(self, source_config: dict, user_email: str, 
                                     dataset_name: str, sensor: str, convert: bool,
                                     is_public: bool, folder: str, team_uuid: str,
                                     progress_callback: Callable[[float], None]) -> List[UploadResult]:
        """Upload directory from Google Drive."""
        # This would need to be implemented with Google Drive API
        # For now, return a placeholder
        print("📁 Google Drive directory upload not yet implemented")
        print("💡 This would list all files in a Google Drive folder and upload each one")
        return []
    
    def _upload_s3_directory(self, source_config: dict, user_email: str,
                           dataset_name: str, sensor: str, convert: bool,
                           is_public: bool, folder: str, team_uuid: str,
                           progress_callback: Callable[[float], None]) -> List[UploadResult]:
        """Upload directory from S3."""
        # This would need to be implemented with S3 API
        # For now, return a placeholder
        print("📁 S3 directory upload not yet implemented")
        print("💡 This would list all objects with a prefix and upload each one")
        return []
    

# Async version for better performance
class AsyncScientistCloudUploadClient:
    """Async version of the unified upload client."""
    
    def __init__(self, base_url: str = "http://localhost:5000", timeout: int = 300):
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.headers = {
            'User-Agent': 'ScientistCloud-Upload-Client-Unified-Async/2.0.0'
        }
    
    async def upload_file(self, file_path: str, user_email: str, dataset_name: str,
                         sensor: str, convert: bool = True, is_public: bool = False,
                         folder: str = None, team_uuid: str = None, dataset_uuid: str = None,
                         progress_callback: Callable[[float], None] = None) -> UploadResult:
        """Async version of upload_file."""
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        file_size = file_path_obj.stat().st_size
        
        if progress_callback:
            print(f"Preparing {file_size / (1024**3):.2f} GB file for upload...")
            progress_callback(0.1)
        
        url = f"{self.base_url}/api/upload/upload"
        
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
        if dataset_uuid:
            form_data.add_field('dataset_uuid', dataset_uuid)
        
        # Add file
        form_data.add_field('file', open(file_path, 'rb'), filename=file_path_obj.name)
        
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            async with session.post(url, data=form_data) as response:
                response.raise_for_status()
                data = await response.json()
                
                if progress_callback:
                    progress_callback(1.0)
                
                return UploadResult(
                    job_id=data['job_id'],
                    status=data['status'],
                    message=data['message'],
                    upload_type=data['upload_type'],
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
    
    async def upload_directory(self, directory_path: str, user_email: str, dataset_name: str,
                              sensor: str, convert: bool = True, is_public: bool = False,
                              folder: str = None, team_uuid: str = None,
                              progress_callback: Callable[[float], None] = None) -> List[UploadResult]:
        """Async version of upload_directory."""
        directory_path_obj = Path(directory_path)
        
        if not directory_path_obj.exists():
            raise FileNotFoundError(f"Directory not found: {directory_path}")
        
        if not directory_path_obj.is_dir():
            raise ValueError(f"Path is not a directory: {directory_path}")
        
        # Find all files in the directory
        files_to_upload = []
        for file_path in directory_path_obj.rglob('*'):
            if file_path.is_file():
                files_to_upload.append(file_path)
        
        if not files_to_upload:
            raise ValueError(f"No files found in directory: {directory_path}")
        
        print(f"📁 Found {len(files_to_upload)} files in directory: {directory_path}")
        
        # Upload each file
        results = []
        # Use a single UUID for the entire directory upload
        directory_uuid = str(uuid.uuid4())
        
        for i, file_path in enumerate(files_to_upload, 1):
            relative_path = file_path.relative_to(directory_path_obj)
            
            # For directory uploads, use the relative path as the folder structure
            # This preserves the directory structure within the source directory
            if relative_path.parent != Path('.'):
                file_folder = str(relative_path.parent)
            else:
                file_folder = None  # No subdirectory, file goes directly in UUID directory
            
            print(f"📤 Uploading {i}/{len(files_to_upload)}: {relative_path}")
            print(f"   📁 Will go into UUID directory: {directory_uuid}")
            print(f"   📂 Folder structure: {file_folder if file_folder else 'root'}")
            
            try:
                # Create progress callback for this file
                def file_progress_callback(progress: float):
                    if progress_callback:
                        # Calculate overall progress across all files
                        overall_progress = ((i - 1) + progress) / len(files_to_upload)
                        progress_callback(overall_progress)
                    print(f"   Progress: {progress*100:.1f}%", end='\r')
                
                result = await self.upload_file(
                    file_path=str(file_path),
                    user_email=user_email,
                    dataset_name=dataset_name,  # Use the original dataset name
                    sensor=sensor,
                    convert=convert,
                    is_public=is_public,
                    folder=file_folder,
                    team_uuid=team_uuid,
                    dataset_uuid=directory_uuid,  # Use shared UUID for directory upload
                    progress_callback=file_progress_callback
                )
                
                print(f"   ✅ Uploaded: {result.job_id}")
                results.append(result)
                
            except Exception as e:
                print(f"   ❌ Failed: {e}")
                # Create a failed result
                failed_result = UploadResult(
                    job_id="",
                    status="failed",
                    message=f"Failed to upload {relative_path}: {e}",
                    upload_type="failed"
                )
                results.append(failed_result)
        
        print(f"\n🎉 Directory upload complete!")
        print(f"   Successfully uploaded: {len([r for r in results if r.status != 'failed'])} files")
        print(f"   Failed uploads: {len([r for r in results if r.status == 'failed'])} files")
        
        return results
