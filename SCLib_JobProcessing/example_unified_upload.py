#!/usr/bin/env python3
"""
Example: Unified Upload API
Demonstrates how the unified API automatically handles both regular and TB-scale uploads.
"""

import os
import tempfile
from pathlib import Path
from SCLib_UploadClient_Unified import ScientistCloudUploadClient, AsyncScientistCloudUploadClient
import asyncio

def progress_callback(progress: float):
    """Simple progress callback."""
    print(f"Progress: {progress * 100:.1f}%")

def main():
    """Main example function."""
    print("=== ScientistCloud Unified Upload API Example ===\n")
    
    # Initialize unified client
    client = ScientistCloudUploadClient("http://localhost:5000")
    
    # Check API health and limits
    print("1. Checking API health and limits...")
    try:
        health = client.health_check()
        print(f"   API Status: {health['status']}")
        print(f"   Upload Type: {health['upload_type']}")
        print(f"   Large File Threshold: {health['large_file_threshold_mb']} MB")
        print(f"   Max File Size: {health['max_file_size_tb']} TB")
        
        limits = client.get_upload_limits()
        print(f"   Chunk Size: {limits['chunk_size_mb']} MB")
        print()
    except Exception as e:
        print(f"   Error checking API: {e}")
        return
    
    # Example 1: Small file upload (will use standard upload)
    print("2. Example: Small file upload (standard method)...")
    
    # Create a small test file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        f.write(b"Small test file content" * 100)  # ~2KB
        small_file = f.name
    
    try:
        result = client.upload_file(
            file_path=small_file,
            user_email="scientist@example.com",
            dataset_name="Small Test Dataset",
            sensor="OTHER",
            progress_callback=progress_callback
        )
        
        print(f"   Upload Type: {result.upload_type}")
        print(f"   Job ID: {result.job_id}")
        print(f"   Message: {result.message}")
        
    except Exception as e:
        print(f"   Error uploading small file: {e}")
    finally:
        os.unlink(small_file)
    
    # Example 2: Large file upload (will use chunked upload)
    print("\n3. Example: Large file upload (chunked method)...")
    
    # Create a large test file (simulate large file)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.dat') as f:
        # Write 150MB of data (above 100MB threshold)
        chunk = b"Large file content " * 1000  # ~18KB per chunk
        for i in range(8500):  # 8500 * 18KB ≈ 150MB
            f.write(chunk)
        large_file = f.name
    
    try:
        file_size_mb = os.path.getsize(large_file) / (1024 * 1024)
        print(f"   File size: {file_size_mb:.1f} MB")
        
        result = client.upload_file(
            file_path=large_file,
            user_email="scientist@example.com",
            dataset_name="Large Test Dataset",
            sensor="IDX",
            progress_callback=progress_callback
        )
        
        print(f"   Upload Type: {result.upload_type}")
        print(f"   Job ID: {result.job_id}")
        print(f"   Message: {result.message}")
        print(f"   Estimated Duration: {result.estimated_duration} seconds")
        
        # Wait for completion
        print("   Waiting for completion...")
        final_status = client.wait_for_completion(result.job_id, timeout=300)
        print(f"   Final Status: {final_status.status}")
        
    except Exception as e:
        print(f"   Error uploading large file: {e}")
    finally:
        os.unlink(large_file)
    
    # Example 3: Cloud upload (Google Drive)
    print("\n4. Example: Cloud upload (Google Drive)...")
    
    try:
        result = client.initiate_google_drive_upload(
            file_id="1ABC123DEF456",
            service_account_file="/path/to/service.json",
            user_email="scientist@example.com",
            dataset_name="Google Drive Dataset",
            sensor="NETCDF"
        )
        
        print(f"   Upload Type: {result.upload_type}")
        print(f"   Job ID: {result.job_id}")
        print(f"   Message: {result.message}")
        
    except Exception as e:
        print(f"   Error initiating Google Drive upload: {e}")
    
    # Example 4: Check upload status
    print("\n5. Example: Check upload status...")
    
    try:
        # Use a dummy job ID for demonstration
        status = client.get_upload_status("demo_job_123")
        print(f"   Job Status: {status.status}")
        print(f"   Progress: {status.progress_percentage}%")
        
    except Exception as e:
        print(f"   Error checking status (expected for demo job): {e}")

async def async_example():
    """Async example for maximum performance."""
    print("\n=== Async Unified Upload Example ===\n")
    
    # Initialize async client
    client = AsyncScientistCloudUploadClient("http://localhost:5000")
    
    # Create a test file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:
        f.write(b"Async test file content" * 1000)  # ~20KB
        test_file = f.name
    
    try:
        # Upload with async client
        result = await client.upload_file(
            file_path=test_file,
            user_email="scientist@example.com",
            dataset_name="Async Test Dataset",
            sensor="TIFF",
            progress_callback=progress_callback
        )
        
        print(f"Async Upload Type: {result.upload_type}")
        print(f"Async Job ID: {result.job_id}")
        
        # Check status
        status = await client.get_upload_status(result.job_id)
        print(f"Async Status: {status.status}")
        
    except Exception as e:
        print(f"Error in async upload: {e}")
    finally:
        os.unlink(test_file)

def real_world_example():
    """Real-world example with actual file paths."""
    print("\n=== Real-World Unified Upload Example ===\n")
    
    # Configuration for real-world usage
    config = {
        'api_url': 'https://your-scientistcloud-api.com',
        'user_email': 'your-email@institution.edu',
        'dataset_name': 'Research_Dataset_2024',
        'sensor': 'IDX',
        'convert': True,
        'is_public': False,
        'folder': 'Research/2024',
        'team_uuid': 'your-team-uuid-here'
    }
    
    # Example file paths (replace with your actual data)
    files_to_upload = [
        '/path/to/your/small/dataset.txt',      # Will use standard upload
        '/path/to/your/medium/dataset.idx',     # Will use standard upload
        '/path/to/your/large/dataset.tiff',     # Will use chunked upload
        '/path/to/your/huge/dataset.netcdf'     # Will use chunked upload
    ]
    
    client = ScientistCloudUploadClient(config['api_url'])
    
    print("Real-world upload configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    print()
    
    for file_path in files_to_upload:
        if os.path.exists(file_path):
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            print(f"Uploading {file_size_mb:.1f} MB file: {Path(file_path).name}")
            
            try:
                result = client.upload_file(
                    file_path=file_path,
                    user_email=config['user_email'],
                    dataset_name=f"{config['dataset_name']}_{Path(file_path).stem}",
                    sensor=config['sensor'],
                    convert=config['convert'],
                    is_public=config['is_public'],
                    folder=config['folder'],
                    team_uuid=config['team_uuid'],
                    progress_callback=lambda p: print(f"  Progress: {p*100:.1f}%")
                )
                
                print(f"  Upload Type: {result.upload_type}")
                print(f"  Job ID: {result.job_id}")
                
                # Wait for completion
                final_status = client.wait_for_completion(result.job_id, timeout=3600)
                print(f"  Final Status: {final_status.status}")
                
            except Exception as e:
                print(f"  Error uploading {file_path}: {e}")
        else:
            print(f"File not found: {file_path}")

if __name__ == "__main__":
    # Run synchronous example
    main()
    
    # Run async example
    asyncio.run(async_example())
    
    # Show real-world example (commented out - uncomment and configure for actual use)
    # real_world_example()
    
    print("\n=== Unified Upload Examples Complete ===")
    print("\nKey benefits of the Unified API:")
    print("1. No need to choose between standard and large file APIs")
    print("2. Automatic file size detection and method selection")
    print("3. Single client for all upload types")
    print("4. Seamless handling of files from KB to TB")
    print("5. Progress tracking for all upload types")
    print("6. Consistent API interface regardless of file size")
    print("7. Automatic optimization for each file size")

