#!/usr/bin/env python3
"""
Example usage of the SCLib_JobProcessing library with the new API structure.
This demonstrates how to use the library as a proper Python package.
"""

from SCLib_JobProcessing import (
    ScientistCloudUploadClient,
    SCLib_JobQueueManager, 
    SCLib_JobType,
    SCLib_JobStatus,
    SCLib_DatasetStatus,
    get_config
)
from pymongo import MongoClient

def main():
    print("SCLib_JobProcessing Library Examples")
    print("=" * 50)
    
    # Example 1: Using the Upload Client (Recommended)
    print("\n1. Upload Client Example")
    print("-" * 30)
    
    # Initialize the upload client
    client = ScientistCloudUploadClient("http://localhost:5000")
    print("✅ Upload client initialized")
    
    # Example upload parameters (would work with real server)
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
    print("Note: This would upload a file if the server was running")
    
    # Example 2: Direct Job Queue Usage
    print("\n2. Direct Job Queue Example")
    print("-" * 30)
    
    try:
        # Get configuration
        config = get_config()
        print("✅ Configuration loaded")
        
        # Initialize MongoDB connection
        mongo_client = MongoClient(config.mongo_url)
        print("✅ MongoDB connection established")
        
        # Create job queue manager
        job_queue = SCLib_JobQueueManager(mongo_client, config.db_name)
        print("✅ Job queue manager created")
        
        # Example job creation
        job_id = job_queue.create_job(
            job_type=SCLib_JobType.DATASET_CONVERSION,
            dataset_uuid="example-dataset-123",
            parameters={
                "input_path": "/path/to/input",
                "output_path": "/path/to/output"
            }
        )
        print(f"✅ Job created with ID: {job_id}")
        
        # Get job status
        status = job_queue.get_job_status(job_id)
        print(f"✅ Job status: {status['status']}")
        
    except Exception as e:
        print(f"❌ Error with direct job queue: {e}")
        print("This is expected if MongoDB is not running")
    
    # Example 3: Enum Usage
    print("\n3. Enum Usage Examples")
    print("-" * 30)
    
    print(f"Available job types: {list(SCLib_JobType)}")
    print(f"Available job statuses: {list(SCLib_JobStatus)}")
    print(f"Available dataset statuses: {list(SCLib_DatasetStatus)}")
    
    # Example usage of specific enums
    print(f"\nExample job type: {SCLib_JobType.GOOGLE_SYNC}")
    print(f"Example job status: {SCLib_JobStatus.PENDING}")
    print(f"Example dataset status: {SCLib_DatasetStatus.SUBMITTED}")
    
    # Example 4: Upload Client Methods
    print("\n4. Upload Client Methods")
    print("-" * 30)
    
    print("Available upload client methods:")
    print("- upload_local_file()")
    print("- initiate_google_drive_upload()")
    print("- initiate_s3_upload()")
    print("- initiate_url_upload()")
    print("- get_upload_status()")
    print("- cancel_upload()")
    print("- list_upload_jobs()")
    print("- get_supported_sources()")
    print("- wait_for_completion()")
    
    print("\n" + "=" * 50)
    print("✅ Examples completed successfully!")
    print("\nTo use with real data:")
    print("1. Start the upload API server: python SCLib_UploadAPI.py")
    print("2. Use the client methods with real file paths and parameters")
    print("3. Monitor job progress using the status endpoints")

if __name__ == '__main__':
    main()
