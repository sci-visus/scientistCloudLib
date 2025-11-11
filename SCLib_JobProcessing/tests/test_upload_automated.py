#!/usr/bin/env python3
"""
Automated Upload Test Suite for ScientistCloud2.0
==================================================

Comprehensive test suite for file upload functionality using the SCLib upload system.
Tests cover:
- Local file uploads (4D Nexus, TIFF RGB, IDX)
- Remote linked uploads (mod_visus URLs)
- Different sensor types
- Job status tracking and validation

Usage:
    pytest test_upload_automated.py -v
    pytest test_upload_automated.py::TestLocalUploads::test_local_upload_4d_nexus -v
    python test_upload_automated.py  # Run all tests
"""

import os
import sys
import time
import pytest
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from SCLib_UploadClient_Unified import ScientistCloudUploadClient, UploadResult, JobStatus
except ImportError:
    print("Warning: Could not import SCLib_UploadClient_Unified")
    print("Make sure you're running from the correct directory")
    ScientistCloudUploadClient = None

# Import test configuration
try:
    from test_upload_config import TestConfig
except ImportError:
    # Fallback configuration
    class TestConfig:
        # Local test files
        NEXUS_4D_FILE = "/Users/amygooch/GIT/SCI/DATA/waxs/mi_sic_0p33mm_002_PIL11_structured_waxs.nxs"
        TIFF_RGB_FILE = "/Users/amygooch/GIT/SCI/DATA/Sampad/1161_Panel2_7_12.tif"
        IDX_FILE = "/Users/amygooch/GIT/SCI/DATA/turbine/turbin_visus.zip"
        
        # Remote test links
        REMOTE_IDX_URL = "http://atlantis.sci.utah.edu/mod_visus?dataset=BlueMarble&compression=zip"
        
        # Test settings
        USER_EMAIL = "amy@visus.net"
        UPLOAD_API_URL = "http://localhost:5000"  # Default upload API URL
        MAX_WAIT_TIME = 300  # 5 minutes max wait time
        STATUS_CHECK_INTERVAL = 5  # Check status every 5 seconds
        TEST_DATASET_PREFIX = "AUTO_TEST_"


class UploadTestHelper:
    """Helper class for upload testing operations."""
    
    def __init__(self, client: ScientistCloudUploadClient):
        self.client = client
        self.test_results = []
    
    def validate_file_exists(self, file_path: str) -> bool:
        """Validate that a test file exists."""
        if not os.path.exists(file_path):
            pytest.skip(f"Test file not found: {file_path}")
        return True
    
    def wait_for_job_completion(self, job_id: str, 
                                max_wait: int = TestConfig.MAX_WAIT_TIME,
                                check_interval: int = TestConfig.STATUS_CHECK_INTERVAL) -> JobStatus:
        """
        Wait for an upload job to complete.
        
        Args:
            job_id: Upload job ID
            max_wait: Maximum time to wait in seconds
            check_interval: Time between status checks in seconds
            
        Returns:
            Final job status
        """
        start_time = time.time()
        last_status = None
        
        while time.time() - start_time < max_wait:
            try:
                status = self.client.get_upload_status(job_id)
                
                # Log status changes
                if status.status != last_status:
                    print(f"  Status: {last_status} -> {status.status} ({status.progress_percentage:.1f}%)")
                    last_status = status.status
                
                # Check if job is complete
                if status.status in ['completed', 'failed', 'cancelled']:
                    return status
                
                time.sleep(check_interval)
                
            except Exception as e:
                print(f"  Error checking status: {e}")
                time.sleep(check_interval)
        
        # Timeout - get final status
        try:
            final_status = self.client.get_upload_status(job_id)
            raise TimeoutError(
                f"Timeout waiting for job completion. "
                f"Final status: {final_status.status} after {max_wait} seconds"
            )
        except Exception as e:
            raise TimeoutError(f"Timeout waiting for job completion after {max_wait} seconds: {e}")
    
    def verify_job_completion(self, job_id: str) -> JobStatus:
        """Verify that an upload job has completed successfully."""
        status = self.wait_for_job_completion(job_id, max_wait=TestConfig.MAX_WAIT_TIME)
        
        # Verify final state
        assert status.status == 'completed', \
            f"Expected status 'completed', got '{status.status}'. Error: {status.error}"
        assert status.progress_percentage >= 100.0, \
            f"Expected progress >= 100%, got {status.progress_percentage}%"
        
        return status


@pytest.fixture(scope="module")
def upload_client():
    """Fixture providing upload client."""
    if ScientistCloudUploadClient is None:
        pytest.skip("ScientistCloudUploadClient not available")
    
    base_url = os.getenv('UPLOAD_API_URL', TestConfig.UPLOAD_API_URL)
    client = ScientistCloudUploadClient(base_url=base_url)
    
    # Test connection
    try:
        client.health_check()
        print(f"✅ Connected to upload API at {base_url}")
    except Exception as e:
        pytest.skip(f"Could not connect to upload API at {base_url}: {e}")
    
    return client


@pytest.fixture(scope="module")
def test_helper(upload_client):
    """Fixture providing test helper."""
    return UploadTestHelper(upload_client)


class TestLocalUploads:
    """Test suite for local file uploads."""
    
    def test_local_upload_4d_nexus(self, test_helper, upload_client):
        """Test uploading a 4D Nexus file."""
        print(f"\n{'='*60}")
        print(f"Test: 4D Nexus Upload")
        print(f"File: {TestConfig.NEXUS_4D_FILE}")
        print(f"{'='*60}")
        
        # Validate file exists
        test_helper.validate_file_exists(TestConfig.NEXUS_4D_FILE)
        
        # Create dataset name
        dataset_name = f"{TestConfig.TEST_DATASET_PREFIX}4D_NEXUS_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Upload file
            print("Uploading file...")
            result = upload_client.upload_file(
                file_path=TestConfig.NEXUS_4D_FILE,
                user_email=TestConfig.USER_EMAIL,
                dataset_name=dataset_name,
                sensor="4D_NEXUS",
                convert=True,
                is_public=False
            )
            
            assert result.job_id is not None, "Upload should return a job_id"
            print(f"✅ Upload initiated successfully!")
            print(f"   Job ID: {result.job_id}")
            print(f"   Status: {result.status}")
            print(f"   Upload Type: {result.upload_type}")
            
            # Wait for completion
            print("Waiting for upload and conversion to complete...")
            status = test_helper.verify_job_completion(result.job_id)
            
            print(f"✅ 4D Nexus upload completed successfully!")
            print(f"   Dataset: {dataset_name}")
            print(f"   Final Status: {status.status}")
            print(f"   Progress: {status.progress_percentage:.1f}%")
            if status.message:
                print(f"   Message: {status.message}")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            raise
    
    def test_local_upload_tiff_rgb(self, test_helper, upload_client):
        """Test uploading a TIFF RGB file."""
        print(f"\n{'='*60}")
        print(f"Test: TIFF RGB Upload")
        print(f"File: {TestConfig.TIFF_RGB_FILE}")
        print(f"{'='*60}")
        
        # Validate file exists
        test_helper.validate_file_exists(TestConfig.TIFF_RGB_FILE)
        
        # Create dataset name
        dataset_name = f"{TestConfig.TEST_DATASET_PREFIX}TIFF_RGB_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Upload file
            print("Uploading file...")
            result = upload_client.upload_file(
                file_path=TestConfig.TIFF_RGB_FILE,
                user_email=TestConfig.USER_EMAIL,
                dataset_name=dataset_name,
                sensor="TIFF RGB",
                convert=True,
                is_public=False
            )
            
            assert result.job_id is not None, "Upload should return a job_id"
            print(f"✅ Upload initiated successfully!")
            print(f"   Job ID: {result.job_id}")
            print(f"   Status: {result.status}")
            
            # Wait for completion
            print("Waiting for upload and conversion to complete...")
            status = test_helper.verify_job_completion(result.job_id)
            
            print(f"✅ TIFF RGB upload completed successfully!")
            print(f"   Dataset: {dataset_name}")
            print(f"   Final Status: {status.status}")
            print(f"   Progress: {status.progress_percentage:.1f}%")
            if status.message:
                print(f"   Message: {status.message}")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            raise
    
    def test_local_upload_idx(self, test_helper, upload_client):
        """Test uploading an IDX file (zip)."""
        print(f"\n{'='*60}")
        print(f"Test: IDX Upload (ZIP)")
        print(f"File: {TestConfig.IDX_FILE}")
        print(f"{'='*60}")
        
        # Validate file exists
        test_helper.validate_file_exists(TestConfig.IDX_FILE)
        
        # Create dataset name
        dataset_name = f"{TestConfig.TEST_DATASET_PREFIX}IDX_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Upload file (IDX files typically don't need conversion)
            print("Uploading file...")
            result = upload_client.upload_file(
                file_path=TestConfig.IDX_FILE,
                user_email=TestConfig.USER_EMAIL,
                dataset_name=dataset_name,
                sensor="IDX",
                convert=False,  # IDX files typically don't need conversion
                is_public=False
            )
            
            assert result.job_id is not None, "Upload should return a job_id"
            print(f"✅ Upload initiated successfully!")
            print(f"   Job ID: {result.job_id}")
            print(f"   Status: {result.status}")
            
            # Wait for completion
            print("Waiting for upload to complete...")
            status = test_helper.verify_job_completion(result.job_id)
            
            print(f"✅ IDX upload completed successfully!")
            print(f"   Dataset: {dataset_name}")
            print(f"   Final Status: {status.status}")
            print(f"   Progress: {status.progress_percentage:.1f}%")
            if status.message:
                print(f"   Message: {status.message}")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            raise


class TestRemoteUploads:
    """Test suite for remote linked uploads."""
    
    def test_remote_link_idx(self, test_helper, upload_client):
        """Test uploading a remote IDX link (mod_visus)."""
        print(f"\n{'='*60}")
        print(f"Test: Remote IDX Link (mod_visus)")
        print(f"URL: {TestConfig.REMOTE_IDX_URL}")
        print(f"{'='*60}")
        
        # Create dataset name
        dataset_name = f"{TestConfig.TEST_DATASET_PREFIX}REMOTE_IDX_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Initiate remote upload
            print("Initiating remote upload...")
            result = upload_client.initiate_url_upload(
                url=TestConfig.REMOTE_IDX_URL,
                user_email=TestConfig.USER_EMAIL,
                dataset_name=dataset_name,
                sensor="IDX",
                convert=False,  # Remote links typically don't need conversion
                is_public=False
            )
            
            assert result.job_id is not None, "Upload should return a job_id"
            print(f"✅ Remote upload initiated successfully!")
            print(f"   Job ID: {result.job_id}")
            print(f"   Status: {result.status}")
            
            # Wait for completion
            print("Waiting for remote link processing to complete...")
            status = test_helper.verify_job_completion(result.job_id)
            
            print(f"✅ Remote IDX link upload completed successfully!")
            print(f"   Dataset: {dataset_name}")
            print(f"   Final Status: {status.status}")
            print(f"   Progress: {status.progress_percentage:.1f}%")
            if status.message:
                print(f"   Message: {status.message}")
            
        except Exception as e:
            print(f"❌ Test failed: {e}")
            raise


def run_all_tests():
    """Run all tests and generate a report."""
    print("\n" + "="*60)
    print("Automated Upload Test Suite for ScientistCloud2.0")
    print("="*60)
    print(f"Upload API: {TestConfig.UPLOAD_API_URL}")
    print(f"Test files:")
    print(f"  4D Nexus: {TestConfig.NEXUS_4D_FILE}")
    print(f"  TIFF RGB: {TestConfig.TIFF_RGB_FILE}")
    print(f"  IDX: {TestConfig.IDX_FILE}")
    print(f"  Remote IDX: {TestConfig.REMOTE_IDX_URL}")
    print("="*60 + "\n")
    
    # Run pytest
    pytest.main([__file__, "-v", "--tb=short"])


if __name__ == "__main__":
    run_all_tests()

