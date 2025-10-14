#!/usr/bin/env python3
"""
ScientistCloud Upload API Examples
Demonstrates how to use the asynchronous upload API with all required parameters.
"""

import requests
import json
import time
from typing import Dict, Any


class ScientistCloudUploadClient:
    """Client for interacting with the ScientistCloud Upload API."""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def upload_local_file(self, file_path: str, user_email: str, dataset_name: str, 
                         sensor: str, convert: bool = True, is_public: bool = False,
                         folder: str = None, team_uuid: str = None) -> Dict[str, Any]:
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
            Upload job information
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
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = self.session.post(url, data=form_data, files=files)
        
        response.raise_for_status()
        return response.json()
    
    def initiate_google_drive_upload(self, file_id: str, service_account_file: str,
                                   user_email: str, dataset_name: str, sensor: str,
                                   convert: bool = True, is_public: bool = False,
                                   folder: str = None, team_uuid: str = None) -> Dict[str, Any]:
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
        
        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()
    
    def initiate_s3_upload(self, bucket_name: str, object_key: str, access_key_id: str,
                          secret_access_key: str, user_email: str, dataset_name: str,
                          sensor: str, convert: bool = True, is_public: bool = False,
                          folder: str = None, team_uuid: str = None) -> Dict[str, Any]:
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
        
        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()
    
    def initiate_url_upload(self, url: str, user_email: str, dataset_name: str,
                           sensor: str, convert: bool = True, is_public: bool = False,
                           folder: str = None, team_uuid: str = None) -> Dict[str, Any]:
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
        
        response = self.session.post(api_url, json=data)
        response.raise_for_status()
        return response.json()
    
    def get_upload_status(self, job_id: str) -> Dict[str, Any]:
        """Get the status of an upload job."""
        url = f"{self.base_url}/api/upload/status/{job_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def cancel_upload(self, job_id: str) -> Dict[str, Any]:
        """Cancel an upload job."""
        url = f"{self.base_url}/api/upload/cancel/{job_id}"
        response = self.session.post(url)
        response.raise_for_status()
        return response.json()
    
    def list_upload_jobs(self, user_email: str, status: str = None, 
                        limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """List upload jobs for a user."""
        url = f"{self.base_url}/api/upload/jobs"
        params = {
            'user_id': user_email,  # API uses user_id but expects user_email
            'limit': limit,
            'offset': offset
        }
        if status:
            params['status'] = status
        
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()
    
    def get_supported_sources(self) -> Dict[str, Any]:
        """Get supported upload sources and their requirements."""
        url = f"{self.base_url}/api/upload/supported-sources"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()
    
    def wait_for_completion(self, job_id: str, timeout: int = 3600, 
                           poll_interval: int = 5) -> Dict[str, Any]:
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
            
            if status['status'] in ['completed', 'failed', 'cancelled']:
                return status
            
            print(f"Job {job_id}: {status['status']} - {status.get('progress_percentage', 0):.1f}%")
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Upload job {job_id} did not complete within {timeout} seconds")


def main():
    """Example usage of the ScientistCloud Upload API."""
    print("ScientistCloud Upload API Examples")
    print("=" * 50)
    
    # Initialize client
    client = ScientistCloudUploadClient()
    
    try:
        # Get supported sources
        print("\n1. Getting supported sources...")
        sources = client.get_supported_sources()
        print(f"Supported sensor types: {sources['sensor_types']}")
        print(f"Required parameters: {list(sources['required_parameters'].keys())}")
        print(f"Optional parameters: {list(sources['optional_parameters'].keys())}")
        
        # Example 1: Local file upload
        print("\n2. Example: Local file upload")
        print("Note: This would require an actual file to upload")
        
        # Example upload parameters
        upload_params = {
            'user_email': 'user@example.com',
            'dataset_name': 'My Test Dataset',
            'sensor': 'TIFF',
            'convert': True,
            'is_public': False,
            'folder': 'research_data',
            'team_uuid': 'team_123'
        }
        
        print(f"Upload parameters: {upload_params}")
        
        # Example 2: Google Drive upload
        print("\n3. Example: Google Drive upload")
        gdrive_params = {
            'file_id': '1ABC123DEF456',
            'service_account_file': '/path/to/service.json',
            'user_email': 'user@example.com',
            'dataset_name': 'Google Drive Dataset',
            'sensor': 'NETCDF',
            'convert': False,
            'is_public': True,
            'folder': 'cloud_data'
        }
        
        print(f"Google Drive parameters: {gdrive_params}")
        
        # Example 3: S3 upload
        print("\n4. Example: S3 upload")
        s3_params = {
            'bucket_name': 'my-bucket',
            'object_key': 'data/dataset.zip',
            'access_key_id': 'AKIA...',
            'secret_access_key': 'secret...',
            'user_email': 'user@example.com',
            'dataset_name': 'S3 Dataset',
            'sensor': 'HDF5',
            'convert': True,
            'is_public': False,
            'folder': 's3_imports'
        }
        
        print(f"S3 parameters: {s3_params}")
        
        # Example 4: URL upload
        print("\n5. Example: URL upload")
        url_params = {
            'url': 'https://example.com/dataset.zip',
            'user_email': 'user@example.com',
            'dataset_name': 'URL Dataset',
            'sensor': 'OTHER',
            'convert': True,
            'is_public': False
        }
        
        print(f"URL parameters: {url_params}")
        
        # Example 5: Job monitoring
        print("\n6. Example: Job monitoring workflow")
        print("""
        # After initiating an upload:
        job_info = client.initiate_url_upload(**url_params)
        job_id = job_info['job_id']
        
        # Monitor progress:
        while True:
            status = client.get_upload_status(job_id)
            print(f"Status: {status['status']}, Progress: {status.get('progress_percentage', 0):.1f}%")
            
            if status['status'] in ['completed', 'failed', 'cancelled']:
                break
            
            time.sleep(5)
        
        # Or use the convenience method:
        final_status = client.wait_for_completion(job_id, timeout=1800)
        print(f"Final status: {final_status['status']}")
        """)
        
        # Example 6: List user's jobs
        print("\n7. Example: List user's upload jobs")
        print("""
        # List all jobs for a user:
        jobs = client.list_upload_jobs('user@example.com')
        print(f"User has {len(jobs['jobs'])} upload jobs")
        
        # List only completed jobs:
        completed_jobs = client.list_upload_jobs('user@example.com', status='completed')
        print(f"User has {len(completed_jobs['jobs'])} completed jobs")
        """)
        
        print("\n" + "=" * 50)
        print("✅ Examples completed successfully!")
        print("\nTo test with real data:")
        print("1. Start the upload API server: python SC_UploadAPI.py")
        print("2. Use the client methods above with real file paths and parameters")
        print("3. Monitor job progress using the status endpoints")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == '__main__':
    main()
