#!/usr/bin/env python3
"""
Example: Large File Upload (TB-scale)
Demonstrates how to upload enormous datasets using chunked transfers and resumable uploads.
"""

import os
import time
from pathlib import Path
from SCLib_UploadClient_LargeFiles import LargeFileUploadClient, AsyncLargeFileUploadClient

def progress_callback(progress: float):
    """Simple progress callback."""
    print(f"Progress: {progress * 100:.1f}%")

def main():
    """Main example function."""
    print("=== ScientistCloud Large File Upload Example ===\n")
    
    # Initialize client
    client = LargeFileUploadClient(
        base_url="http://localhost:5001",  # Large file API endpoint
        timeout=600,  # 10 minute timeout
        chunk_size=100 * 1024 * 1024,  # 100MB chunks
        max_workers=4  # 4 parallel uploads
    )
    
    # Check API health and limits
    print("1. Checking API health and limits...")
    try:
        health = client.health_check()
        print(f"   API Status: {health['status']}")
        print(f"   Max file size: {health['max_file_size_tb']:.1f} TB")
        print(f"   Chunk size: {health['chunk_size_mb']:.0f} MB")
        print(f"   Active uploads: {health['active_uploads']}")
        
        limits = client.get_upload_limits()
        print(f"   Recommended for files > {limits['recommended_for_files_larger_than_mb']} MB")
        print()
    except Exception as e:
        print(f"   Error checking API: {e}")
        return
    
    # Example 1: Upload a large file (simulated)
    print("2. Example: Uploading a large file...")
    
    # Create a test file (in real usage, this would be your actual data file)
    test_file_path = "/tmp/large_test_file.dat"
    file_size_gb = 2  # 2GB test file
    
    if not os.path.exists(test_file_path):
        print(f"   Creating {file_size_gb}GB test file...")
        with open(test_file_path, 'wb') as f:
            # Write 1GB chunks
            chunk_size = 1024 * 1024 * 1024  # 1GB
            for i in range(file_size_gb):
                f.write(b'0' * chunk_size)
                print(f"   Created {i + 1}/{file_size_gb} GB")
    
    try:
        # Upload the file
        print(f"   Uploading {file_size_gb}GB file...")
        upload_id = client.upload_file_chunked(
            file_path=test_file_path,
            user_email="scientist@example.com",
            dataset_name="Large Test Dataset",
            sensor="OTHER",
            convert=True,
            is_public=False,
            progress_callback=progress_callback
        )
        
        print(f"   Upload completed! Upload ID: {upload_id}")
        
        # Wait for processing to complete
        print("   Waiting for processing to complete...")
        final_status = client.wait_for_completion(upload_id, timeout=1800)  # 30 minutes
        print(f"   Final status: {final_status}")
        
    except Exception as e:
        print(f"   Error during upload: {e}")
    
    # Example 2: Parallel upload for maximum speed
    print("\n3. Example: Parallel upload for maximum speed...")
    
    try:
        upload_id = client.upload_file_parallel(
            file_path=test_file_path,
            user_email="scientist@example.com",
            dataset_name="Parallel Test Dataset",
            sensor="OTHER",
            convert=True,
            is_public=False,
            progress_callback=progress_callback
        )
        
        print(f"   Parallel upload completed! Upload ID: {upload_id}")
        
    except Exception as e:
        print(f"   Error during parallel upload: {e}")
    
    # Example 3: Resume interrupted upload
    print("\n4. Example: Resume interrupted upload...")
    
    try:
        # Simulate an interrupted upload by starting one and then checking resume info
        print("   Starting upload...")
        upload_id = client.initiate_large_upload(
            file_path=test_file_path,
            user_email="scientist@example.com",
            dataset_name="Resume Test Dataset",
            sensor="OTHER"
        )
        
        print(f"   Upload initiated: {upload_id}")
        
        # Get resume information
        resume_info = client.get_resume_info(upload_id)
        print(f"   Can resume: {resume_info.can_resume}")
        print(f"   Missing chunks: {len(resume_info.missing_chunks)}")
        
        # Cancel the upload for demo purposes
        client.cancel_upload(upload_id)
        print("   Upload cancelled for demo")
        
    except Exception as e:
        print(f"   Error during resume demo: {e}")
    
    # Clean up test file
    if os.path.exists(test_file_path):
        os.remove(test_file_path)
        print(f"\n   Cleaned up test file: {test_file_path}")

async def async_example():
    """Async example for maximum performance."""
    print("\n=== Async Large File Upload Example ===\n")
    
    # Initialize async client
    client = AsyncLargeFileUploadClient(
        base_url="http://localhost:5001",
        timeout=600,
        chunk_size=100 * 1024 * 1024,
        max_concurrent=8  # 8 concurrent uploads
    )
    
    # Create a test file
    test_file_path = "/tmp/async_test_file.dat"
    file_size_gb = 1  # 1GB test file
    
    if not os.path.exists(test_file_path):
        print(f"Creating {file_size_gb}GB test file...")
        with open(test_file_path, 'wb') as f:
            chunk_size = 1024 * 1024 * 1024  # 1GB
            for i in range(file_size_gb):
                f.write(b'0' * chunk_size)
                print(f"Created {i + 1}/{file_size_gb} GB")
    
    try:
        # Upload with async client
        print(f"Uploading {file_size_gb}GB file with async client...")
        upload_id = await client.upload_file_async(
            file_path=test_file_path,
            user_email="scientist@example.com",
            dataset_name="Async Test Dataset",
            sensor="OTHER",
            convert=True,
            is_public=False,
            progress_callback=progress_callback
        )
        
        print(f"Async upload completed! Upload ID: {upload_id}")
        
    except Exception as e:
        print(f"Error during async upload: {e}")
    
    # Clean up
    if os.path.exists(test_file_path):
        os.remove(test_file_path)
        print(f"Cleaned up test file: {test_file_path}")

def real_world_example():
    """Real-world example with actual file paths and configurations."""
    print("\n=== Real-World Large File Upload Example ===\n")
    
    # Configuration for real-world usage
    config = {
        'api_url': 'https://your-scientistcloud-api.com',  # Your actual API URL
        'user_email': 'your-email@institution.edu',
        'dataset_name': 'Massive_Imaging_Dataset_2024',
        'sensor': 'IDX',  # or 'TIFF', 'NETCDF', etc.
        'convert': True,
        'is_public': False,
        'folder': 'Research/Imaging/2024',
        'team_uuid': 'your-team-uuid-here'  # Optional
    }
    
    # Example file paths (replace with your actual data)
    large_files = [
        '/path/to/your/10TB/dataset.idx',
        '/path/to/your/5TB/sequence.tiff',
        '/path/to/your/2TB/volume.netcdf'
    ]
    
    client = LargeFileUploadClient(
        base_url=config['api_url'],
        timeout=3600,  # 1 hour timeout for very large files
        chunk_size=200 * 1024 * 1024,  # 200MB chunks for better performance
        max_workers=6  # 6 parallel uploads
    )
    
    print("Real-world upload configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    print()
    
    for file_path in large_files:
        if os.path.exists(file_path):
            file_size_gb = os.path.getsize(file_path) / (1024**3)
            print(f"Uploading {file_size_gb:.1f} GB file: {Path(file_path).name}")
            
            try:
                upload_id = client.upload_file_parallel(
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
                
                print(f"  Upload completed! ID: {upload_id}")
                
                # Wait for processing
                print("  Waiting for processing...")
                final_status = client.wait_for_completion(upload_id, timeout=7200)  # 2 hours
                print(f"  Processing completed: {final_status.is_complete}")
                
            except Exception as e:
                print(f"  Error uploading {file_path}: {e}")
        else:
            print(f"File not found: {file_path}")

if __name__ == "__main__":
    # Run synchronous example
    main()
    
    # Run async example
    import asyncio
    asyncio.run(async_example())
    
    # Show real-world example (commented out - uncomment and configure for actual use)
    # real_world_example()
    
    print("\n=== Large File Upload Examples Complete ===")
    print("\nKey points for TB-scale uploads:")
    print("1. Use chunked uploads for files > 100MB")
    print("2. Use parallel uploads for maximum speed")
    print("3. Implement resume capability for reliability")
    print("4. Monitor progress and handle timeouts")
    print("5. Consider cloud storage integration for very large files")
    print("6. Configure appropriate chunk sizes based on network")
    print("7. Use async clients for maximum performance")




