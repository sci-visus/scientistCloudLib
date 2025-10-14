"""
ScientistCloud Job Processing Library (SCLib_JobProcessing)

This library provides a comprehensive job processing system for ScientistCloud 2.0,
including job queue management, background processing, monitoring, and upload handling.

Main Components:
- SCLib_JobQueueManager: Job queue management
- SCLib_BackgroundService: Background job processing
- SCLib_JobMonitor: Monitoring and statistics
- SCLib_JobMigration: Migration utilities
- SCLib_Config: Configuration management
- SCLib_MongoConnection: Database connections
- SCLib_UploadClient: Upload API client
- SCLib_UploadAPI: Upload REST API server
- SCLib_UploadProcessor: Upload processing engine

Quick Start:
    from SCLib_JobProcessing import SCLib_UploadClient
    
    # Initialize client
    client = SCLib_UploadClient("http://localhost:5000")
    
    # Upload a local file
    result = client.upload_local_file(
        file_path="/path/to/file.zip",
        user_email="user@example.com",
        dataset_name="My Dataset",
        sensor="TIFF"
    )
    
    # Monitor progress
    status = client.wait_for_completion(result['job_id'])
"""

# Core job processing classes
from .SCLib_JobQueueManager import SCLib_JobQueueManager
from .SCLib_BackgroundService import SCLib_BackgroundService
from .SCLib_JobMonitor import SCLib_JobMonitor
from .SCLib_JobMigration import SCLib_JobMigration
from .SCLib_Config import SCLib_Config, get_config
from .SCLib_MongoConnection import SCLib_MongoConnectionManager, get_mongo_connection

# Upload system classes
from .SCLib_UploadClient import ScientistCloudUploadClient
from .SCLib_UploadAPI import app as upload_api_app
from .SCLib_UploadProcessor import SCLib_UploadProcessor, get_upload_processor
from .SCLib_UploadJobTypes import (
    UploadJobConfig, UploadSourceType, SensorType, UploadStatus,
    create_local_upload_job, create_google_drive_upload_job,
    create_s3_upload_job, create_url_upload_job
)

# Job types and enums
from .SCLib_JobTypes import (
    SCLib_JobType, SCLib_JobStatus, SCLib_DatasetStatus, SC_JOB_PRIORITY,
    SC_JOB_TYPE_CONFIGS, SC_DATASET_STATUS_TRANSITIONS,
    get_job_type_config, get_dataset_status_config,
    get_next_possible_states, is_valid_transition,
    get_job_type_for_status, is_terminal_status,
    get_status_description, get_job_type_description,
    LEGACY_STATUS_MAPPING, convert_legacy_status, convert_to_legacy_status
)

# Version information
__version__ = "2.0.0"
__author__ = "ScientistCloud Team"

# Main exports for easy importing
__all__ = [
    # Core classes
    'SCLib_JobQueueManager',
    'SCLib_BackgroundService', 
    'SCLib_JobMonitor',
    'SCLib_JobMigration',
    'SCLib_Config',
    'SCLib_MongoConnectionManager',
    
    # Upload system
    'ScientistCloudUploadClient',
    'upload_api_app',
    'SCLib_UploadProcessor',
    'UploadJobConfig',
    'UploadSourceType',
    'SensorType',
    'UploadStatus',
    
    # Job types and enums
    'SCLib_JobType',
    'SCLib_JobStatus', 
    'SCLib_DatasetStatus',
    'SC_JOB_PRIORITY',
    
    # Utility functions
    'get_config',
    'get_mongo_connection',
    'get_upload_processor',
    'create_local_upload_job',
    'create_google_drive_upload_job',
    'create_s3_upload_job',
    'create_url_upload_job',
    'get_job_type_config',
    'get_dataset_status_config',
    'get_next_possible_states',
    'is_valid_transition',
    'get_job_type_for_status',
    'is_terminal_status',
    'get_status_description',
    'get_job_type_description',
    'convert_legacy_status',
    'convert_to_legacy_status',
]
