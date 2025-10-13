"""
ScientistCloud Job Types and State Definitions
Defines all job types, states, and their transitions for the ScientistCloud platform.
"""

from typing import Dict, List, Any
from enum import Enum


class SC_JobType(Enum):
    """Enumeration of all supported job types."""
    GOOGLE_SYNC = "google_sync"
    DATASET_CONVERSION = "dataset_conversion"
    FILE_UPLOAD = "file_upload"
    FILE_EXTRACTION = "file_extraction"
    DATA_COMPRESSION = "data_compression"
    RSYNC_TRANSFER = "rsync_transfer"
    BACKUP_CREATION = "backup_creation"
    DATA_VALIDATION = "data_validation"


class SC_JobStatus(Enum):
    """Enumeration of all job statuses."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class SC_DatasetStatus(Enum):
    """Enumeration of all dataset statuses."""
    SUBMITTED = "submitted"
    SYNC_QUEUED = "sync queued"
    SYNCING = "syncing"
    CONVERSION_QUEUED = "conversion queued"
    CONVERTING = "converting"
    UPLOAD_QUEUED = "upload queued"
    UPLOADING = "uploading"
    UNZIPPING = "unzipping"
    ZIPPING = "zipping"
    DONE = "done"
    SYNC_ERROR = "sync error"
    CONVERSION_ERROR = "conversion error"
    UPLOAD_ERROR = "upload error"
    UNZIP_ERROR = "unzip error"
    COMPRESSION_ERROR = "compression error"
    FAILED = "failed"
    RETRYING = "retrying"


# Job type configurations
SC_JOB_TYPE_CONFIGS = {
    SC_JobType.GOOGLE_SYNC: {
        'description': 'Synchronize data from Google Drive',
        'timeout_minutes': 60,
        'max_attempts': 3,
        'requires_internet': True,
        'priority': 2,
        'estimated_duration': '5-30 minutes'
    },
    SC_JobType.DATASET_CONVERSION: {
        'description': 'Convert dataset to streamable format',
        'timeout_minutes': 120,
        'max_attempts': 2,
        'requires_internet': False,
        'priority': 1,
        'estimated_duration': '10-60 minutes'
    },
    SC_JobType.FILE_UPLOAD: {
        'description': 'Upload files to storage',
        'timeout_minutes': 30,
        'max_attempts': 5,
        'requires_internet': True,
        'priority': 2,
        'estimated_duration': '2-15 minutes'
    },
    SC_JobType.FILE_EXTRACTION: {
        'description': 'Extract files from archive',
        'timeout_minutes': 15,
        'max_attempts': 3,
        'requires_internet': False,
        'priority': 1,
        'estimated_duration': '1-5 minutes'
    },
    SC_JobType.DATA_COMPRESSION: {
        'description': 'Compress data for storage',
        'timeout_minutes': 45,
        'max_attempts': 2,
        'requires_internet': False,
        'priority': 3,
        'estimated_duration': '5-20 minutes'
    },
    SC_JobType.RSYNC_TRANSFER: {
        'description': 'Transfer data via rsync',
        'timeout_minutes': 90,
        'max_attempts': 3,
        'requires_internet': False,
        'priority': 2,
        'estimated_duration': '10-45 minutes'
    },
    SC_JobType.BACKUP_CREATION: {
        'description': 'Create data backup',
        'timeout_minutes': 60,
        'max_attempts': 2,
        'requires_internet': False,
        'priority': 3,
        'estimated_duration': '5-30 minutes'
    },
    SC_JobType.DATA_VALIDATION: {
        'description': 'Validate dataset integrity',
        'timeout_minutes': 30,
        'max_attempts': 2,
        'requires_internet': False,
        'priority': 2,
        'estimated_duration': '2-10 minutes'
    }
}


# Dataset status transitions
SC_DATASET_STATUS_TRANSITIONS = {
    SC_DatasetStatus.SUBMITTED: {
        'description': 'Dataset submitted, waiting for processing',
        'next_states': [SC_DatasetStatus.SYNC_QUEUED, SC_DatasetStatus.CONVERSION_QUEUED, SC_DatasetStatus.UPLOAD_QUEUED],
        'job_type': None,
        'is_terminal': False
    },
    SC_DatasetStatus.SYNC_QUEUED: {
        'description': 'Queued for Google Drive sync',
        'next_states': [SC_DatasetStatus.SYNCING, SC_DatasetStatus.SYNC_ERROR],
        'job_type': SC_JobType.GOOGLE_SYNC,
        'is_terminal': False
    },
    SC_DatasetStatus.SYNCING: {
        'description': 'Currently syncing from Google Drive',
        'next_states': [SC_DatasetStatus.CONVERSION_QUEUED, SC_DatasetStatus.SYNC_ERROR],
        'job_type': SC_JobType.GOOGLE_SYNC,
        'is_terminal': False
    },
    SC_DatasetStatus.CONVERSION_QUEUED: {
        'description': 'Queued for data conversion',
        'next_states': [SC_DatasetStatus.CONVERTING, SC_DatasetStatus.CONVERSION_ERROR],
        'job_type': SC_JobType.DATASET_CONVERSION,
        'is_terminal': False
    },
    SC_DatasetStatus.CONVERTING: {
        'description': 'Currently converting data',
        'next_states': [SC_DatasetStatus.DONE, SC_DatasetStatus.CONVERSION_ERROR],
        'job_type': SC_JobType.DATASET_CONVERSION,
        'is_terminal': False
    },
    SC_DatasetStatus.UPLOAD_QUEUED: {
        'description': 'Queued for file upload',
        'next_states': [SC_DatasetStatus.UPLOADING, SC_DatasetStatus.UPLOAD_ERROR],
        'job_type': SC_JobType.FILE_UPLOAD,
        'is_terminal': False
    },
    SC_DatasetStatus.UPLOADING: {
        'description': 'Currently uploading files',
        'next_states': [SC_DatasetStatus.DONE, SC_DatasetStatus.UPLOAD_ERROR],
        'job_type': SC_JobType.FILE_UPLOAD,
        'is_terminal': False
    },
    SC_DatasetStatus.UNZIPPING: {
        'description': 'Unzipping uploaded files',
        'next_states': [SC_DatasetStatus.CONVERSION_QUEUED, SC_DatasetStatus.UNZIP_ERROR],
        'job_type': SC_JobType.FILE_EXTRACTION,
        'is_terminal': False
    },
    SC_DatasetStatus.ZIPPING: {
        'description': 'Compressing data',
        'next_states': [SC_DatasetStatus.DONE, SC_DatasetStatus.COMPRESSION_ERROR],
        'job_type': SC_JobType.DATA_COMPRESSION,
        'is_terminal': False
    },
    SC_DatasetStatus.DONE: {
        'description': 'Processing completed successfully',
        'next_states': [],
        'job_type': None,
        'is_terminal': True
    },
    SC_DatasetStatus.SYNC_ERROR: {
        'description': 'Google Drive sync failed',
        'next_states': [SC_DatasetStatus.SYNC_QUEUED, SC_DatasetStatus.FAILED],
        'job_type': SC_JobType.GOOGLE_SYNC,
        'is_terminal': False
    },
    SC_DatasetStatus.CONVERSION_ERROR: {
        'description': 'Data conversion failed',
        'next_states': [SC_DatasetStatus.CONVERSION_QUEUED, SC_DatasetStatus.FAILED],
        'job_type': SC_JobType.DATASET_CONVERSION,
        'is_terminal': False
    },
    SC_DatasetStatus.UPLOAD_ERROR: {
        'description': 'File upload failed',
        'next_states': [SC_DatasetStatus.UPLOAD_QUEUED, SC_DatasetStatus.FAILED],
        'job_type': SC_JobType.FILE_UPLOAD,
        'is_terminal': False
    },
    SC_DatasetStatus.UNZIP_ERROR: {
        'description': 'File extraction failed',
        'next_states': [SC_DatasetStatus.UNZIPPING, SC_DatasetStatus.FAILED],
        'job_type': SC_JobType.FILE_EXTRACTION,
        'is_terminal': False
    },
    SC_DatasetStatus.COMPRESSION_ERROR: {
        'description': 'Data compression failed',
        'next_states': [SC_DatasetStatus.ZIPPING, SC_DatasetStatus.FAILED],
        'job_type': SC_JobType.DATA_COMPRESSION,
        'is_terminal': False
    },
    SC_DatasetStatus.FAILED: {
        'description': 'Processing failed after max retries',
        'next_states': [],
        'job_type': None,
        'is_terminal': True
    },
    SC_DatasetStatus.RETRYING: {
        'description': 'Retrying failed operation',
        'next_states': [SC_DatasetStatus.SYNC_QUEUED, SC_DatasetStatus.CONVERSION_QUEUED, SC_DatasetStatus.UPLOAD_QUEUED],
        'job_type': None,
        'is_terminal': False
    }
}


# Job priority levels
SC_JOB_PRIORITY = {
    'HIGH': 1,
    'NORMAL': 2,
    'LOW': 3
}


# Helper functions
def get_job_type_config(job_type: SC_JobType) -> Dict[str, Any]:
    """Get configuration for a specific job type."""
    return SC_JOB_TYPE_CONFIGS.get(job_type, {})


def get_dataset_status_config(status: SC_DatasetStatus) -> Dict[str, Any]:
    """Get configuration for a specific dataset status."""
    return SC_DATASET_STATUS_TRANSITIONS.get(status, {})


def get_next_possible_states(current_status: SC_DatasetStatus) -> List[SC_DatasetStatus]:
    """Get list of possible next states for a given status."""
    config = get_dataset_status_config(current_status)
    return config.get('next_states', [])


def is_valid_transition(from_status: SC_DatasetStatus, to_status: SC_DatasetStatus) -> bool:
    """Check if a status transition is valid."""
    possible_states = get_next_possible_states(from_status)
    return to_status in possible_states


def get_job_type_for_status(status: SC_DatasetStatus) -> SC_JobType:
    """Get the job type associated with a dataset status."""
    config = get_dataset_status_config(status)
    return config.get('job_type')


def is_terminal_status(status: SC_DatasetStatus) -> bool:
    """Check if a status is terminal (no further transitions possible)."""
    config = get_dataset_status_config(status)
    return config.get('is_terminal', False)


def get_status_description(status: SC_DatasetStatus) -> str:
    """Get human-readable description for a status."""
    config = get_dataset_status_config(status)
    return config.get('description', 'Unknown status')


def get_job_type_description(job_type: SC_JobType) -> str:
    """Get human-readable description for a job type."""
    config = get_job_type_config(job_type)
    return config.get('description', 'Unknown job type')


# Status mapping for backward compatibility with existing system
LEGACY_STATUS_MAPPING = {
    'submitted': SC_DatasetStatus.SUBMITTED,
    'sync queued': SC_DatasetStatus.SYNC_QUEUED,
    'syncing': SC_DatasetStatus.SYNCING,
    'conversion queued': SC_DatasetStatus.CONVERSION_QUEUED,
    'converting': SC_DatasetStatus.CONVERTING,
    'upload queued': SC_DatasetStatus.UPLOAD_QUEUED,
    'uploading': SC_DatasetStatus.UPLOADING,
    'unzipping': SC_DatasetStatus.UNZIPPING,
    'zipping': SC_DatasetStatus.ZIPPING,
    'done': SC_DatasetStatus.DONE,
    'sync error': SC_DatasetStatus.SYNC_ERROR,
    'conversion error': SC_DatasetStatus.CONVERSION_ERROR,
    'upload error': SC_DatasetStatus.UPLOAD_ERROR,
    'unzip error': SC_DatasetStatus.UNZIP_ERROR,
    'compression error': SC_DatasetStatus.COMPRESSION_ERROR,
    'failed': SC_DatasetStatus.FAILED,
    'retrying': SC_DatasetStatus.RETRYING
}


def convert_legacy_status(legacy_status: str) -> SC_DatasetStatus:
    """Convert legacy status string to enum."""
    return LEGACY_STATUS_MAPPING.get(legacy_status, SC_DatasetStatus.SUBMITTED)


def convert_to_legacy_status(status: SC_DatasetStatus) -> str:
    """Convert enum status to legacy string."""
    for legacy, enum_status in LEGACY_STATUS_MAPPING.items():
        if enum_status == status:
            return legacy
    return status.value
