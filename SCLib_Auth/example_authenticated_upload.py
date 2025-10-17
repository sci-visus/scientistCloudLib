#!/usr/bin/env python3
"""
SCLib Authenticated Upload Example
Demonstrates how to use the authenticated upload API with curl commands and Python client.
"""

import requests
import json
import time
from typing import Dict, Any, Optional

class AuthenticatedUploadClient:
    """Client for interacting with the authenticated upload API."""
    
    def __init__(self, auth_server_url: str = "http://localhost:8001", 
                 upload_server_url: str = "http://localhost:5001"):
        """
        Initialize the authenticated upload client.
        
        Args:
            auth_server_url: URL of the authentication server
            upload_server_url: URL of the upload server
        """
        self.auth_server_url = auth_server_url.rstrip('/')
        self.upload_server_url = upload_server_url.rstrip('/')
        self.access_token = None
        self.user_info = None
    
    def login(self, email: str) -> Dict[str, Any]:
        """
        Login to get authentication token.
        
        Args:
            email: User's email address
            
        Returns:
            Login response data
        """
        url = f"{self.auth_server_url}/api/auth/login"
        payload = {"email": email}
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success'):
                self.access_token = data['data']['access_token']
                self.user_info = data['data']['user']
                print(f"✅ Login successful for {email}")
                return data
            else:
                print(f"❌ Login failed: {data.get('message', 'Unknown error')}")
                return data
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Login request failed: {e}")
            return {"success": False, "error": str(e)}
    
    def upload_file(self, file_path: str, dataset_name: str, sensor: str = "TIFF", 
                   convert: bool = True, is_public: bool = False, **kwargs) -> Dict[str, Any]:
        """
        Upload a file using the authenticated upload API.
        
        Args:
            file_path: Path to the file to upload
            dataset_name: Name of the dataset
            sensor: Sensor type (default: TIFF)
            convert: Whether to convert the data (default: True)
            is_public: Whether dataset is public (default: False)
            **kwargs: Additional parameters
            
        Returns:
            Upload response data
        """
        if not self.access_token:
            print("❌ No access token available. Please login first.")
            return {"success": False, "error": "No access token"}
        
        url = f"{self.upload_server_url}/api/upload/upload"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        # Prepare form data
        form_data = {
            "dataset_name": dataset_name,
            "sensor": sensor,
            "convert": convert,
            "is_public": is_public,
            **kwargs
        }
        
        try:
            with open(file_path, 'rb') as file:
                files = {"file": (file_path, file, "application/octet-stream")}
                
                response = requests.post(url, headers=headers, data=form_data, files=files)
                response.raise_for_status()
                
                data = response.json()
                print(f"✅ File upload initiated: {file_path}")
                print(f"   Job ID: {data.get('job_id')}")
                print(f"   Status: {data.get('status')}")
                return data
                
        except FileNotFoundError:
            print(f"❌ File not found: {file_path}")
            return {"success": False, "error": "File not found"}
        except requests.exceptions.RequestException as e:
            print(f"❌ Upload request failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get the status of an upload job (authentication required).
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job status data
        """
        url = f"{self.upload_server_url}/api/upload/status/{job_id}"
        headers = {}
        
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            print(f"📊 Job {job_id} status: {data.get('status')} ({data.get('progress_percentage', 0):.1f}%)")
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Status request failed: {e}")
            return {"error": str(e)}
    
    def list_jobs(self, limit: int = 10) -> Dict[str, Any]:
        """
        List upload jobs for the authenticated user (authentication required).
        
        Args:
            limit: Maximum number of jobs to return
            
        Returns:
            List of jobs
        """
        if not self.access_token:
            print("❌ No access token available. Please login first.")
            return {"success": False, "error": "No access token"}
        
        url = f"{self.upload_server_url}/api/upload/jobs"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        params = {"limit": limit}
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            print(f"📋 Found {data.get('total', 0)} jobs")
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ List jobs request failed: {e}")
            return {"error": str(e)}
    
    def check_auth_status(self) -> Dict[str, Any]:
        """
        Check authentication status on the upload server (authentication required).
        
        Returns:
            Authentication status
        """
        url = f"{self.upload_server_url}/api/auth/status"
        headers = {}
        
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            status = "authenticated" if data.get('is_authenticated') else "not authenticated"
            print(f"🔍 Auth status: {status}")
            if data.get('user_email'):
                print(f"   User: {data.get('user_email')}")
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Auth status check failed: {e}")
            return {"error": str(e)}

def generate_curl_examples():
    """Generate curl command examples for authenticated uploads."""
    
    print("\n" + "="*80)
    print("CURL COMMAND EXAMPLES FOR AUTHENTICATED UPLOADS")
    print("="*80)
    
    print("\n1. Login to get authentication token:")
    print("""
curl -X POST "http://localhost:8001/api/auth/login" \\
     -H "Content-Type: application/json" \\
     -d '{"email": "user@example.com"}'
""")
    
    print("\n2. Upload file with authentication token:")
    print("""
curl -X POST "http://localhost:5001/api/upload/upload" \\
     -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE" \\
     -F "file=@/path/to/your/file.tiff" \\
     -F "dataset_name=Test Dataset" \\
     -F "sensor=TIFF" \\
     -F "convert=true" \\
     -F "is_public=false"
""")
    
    print("\n3. Check job status:")
    print("""
curl -X GET "http://localhost:5001/api/upload/status/JOB_ID_HERE" \\
     -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE"
""")
    
    print("\n4. List user's jobs:")
    print("""
curl -X GET "http://localhost:5001/api/upload/jobs" \\
     -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE" \\
     -G -d "limit=10"
""")
    
    print("\n5. Check authentication status:")
    print("""
curl -X GET "http://localhost:5001/api/auth/status" \\
     -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE"
""")
    
    print("\n6. Upload without authentication (backward compatibility):")
    print("""
curl -X POST "http://localhost:5001/api/upload/upload" \\
     -F "file=@/path/to/your/file.tiff" \\
     -F "user_email=user@example.com" \\
     -F "dataset_name=Test Dataset" \\
     -F "sensor=TIFF"
""")

def main():
    """Main function demonstrating authenticated upload usage."""
    print("🚀 SCLib Authenticated Upload System - Example Usage")
    print("=" * 60)
    
    # Initialize client
    client = AuthenticatedUploadClient()
    
    # Check if servers are running
    print("\n1. Checking server connections...")
    try:
        auth_response = requests.get(f"{client.auth_server_url}/health", timeout=5)
        if auth_response.status_code == 200:
            print("✅ Authentication server is running")
        else:
            print("❌ Authentication server is not responding properly")
    except:
        print("❌ Cannot connect to authentication server. Make sure it's running on http://localhost:8001")
    
    try:
        upload_response = requests.get(f"{client.upload_server_url}/health", timeout=5)
        if upload_response.status_code == 200:
            print("✅ Upload server is running")
        else:
            print("❌ Upload server is not responding properly")
    except:
        print("❌ Cannot connect to upload server. Make sure it's running on http://localhost:5001")
    
    # Login
    print("\n2. Logging in...")
    email = "test@example.com"
    login_result = client.login(email)
    
    if not login_result.get('success'):
        print("❌ Login failed. Please check your authentication server configuration.")
        print("\nTo start the authentication server:")
        print("   cd /path/to/SCLib_Auth")
        print("   python start_auth_server.py --port 8001")
        return
    
    # Check auth status
    print("\n3. Checking authentication status...")
    client.check_auth_status()
    
    # Example file upload (you would need a real file for this)
    print("\n4. Example file upload (requires actual file):")
    print("   # client.upload_file('/path/to/file.tiff', 'Test Dataset', 'TIFF')")
    
    # List jobs
    print("\n5. Listing user's jobs...")
    jobs = client.list_jobs(limit=5)
    
    # Generate curl examples
    generate_curl_examples()
    
    print("\n🎉 Authenticated upload system demonstration complete!")
    print("\nTo start the servers:")
    print("   # Authentication server:")
    print("   cd /path/to/SCLib_Auth")
    print("   python start_auth_server.py --port 8001")
    print("   ")
    print("   # Upload server:")
    print("   cd /path/to/SCLib_JobProcessing")
    print("   python SCLib_UploadAPI_Authenticated.py")

if __name__ == "__main__":
    main()
