#!/usr/bin/env python3
"""
ScientistCloud Upload Job Types
Defines upload job types and configurations for asynchronous upload handling.
"""

import os
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


class UploadSourceType(Enum):
    """Types of upload sources."""
    LOCAL = "local"
    GOOGLE_DRIVE = "google_drive"
    S3 = "s3"
    URL = "url"
    DROPBOX = "dropbox"
    ONEDRIVE = "onedrive"


class UploadStatus(Enum):
    """Upload job statuses."""
    QUEUED = "queued"
    INITIALIZING = "initializing"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class SensorType(Enum):
    """Supported sensor types for datasets."""
    IDX = "IDX"
    TIFF = "TIFF"
    TIFF_RGB = "TIFF RGB"
    NETCDF = "NETCDF"
    HDF5 = "HDF5"
    NEXUS_4D = "4D_NEXUS"
    RGB = "RGB"
    MAPIR = "MAPIR"
    OTHER = "OTHER"


@dataclass
class UploadJobConfig:
    """Configuration for upload jobs."""
    # Source configuration
    source_type: UploadSourceType
    source_path: str  # Current working path (may be temp file)
    destination_path: str
    dataset_uuid: str
    original_source_path: Optional[str] = None  # Original file path for retries
    source_config: Dict[str, Any] = field(default_factory=dict)
    
    # Upload settings
    chunk_size_mb: int = 64
    max_retries: int = 3
    retry_delay_seconds: int = 30
    timeout_minutes: int = 120
    
    # Processing settings
    auto_convert: bool = True
    auto_extract: bool = True
    verify_checksum: bool = True
    
    # Required ScientistCloud parameters
    user_email: str = ""  # User email
    dataset_name: str = ""  # Name of dataset
    sensor: SensorType = SensorType.OTHER  # Sensor type
    convert: bool = True  # Whether to convert the data
    is_public: bool = False  # Whether dataset is public
    is_downloadable: str = "only owner"  # Download permission: "only owner", "only team", "public"
    
    # Optional parameters
    folder: Optional[str] = None  # Optional folder
    team_uuid: Optional[str] = None  # Optional team UUID
    
    # Legacy metadata (for backward compatibility)
    user_id: str = ""
    team_id: Optional[str] = None
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    # Progress tracking
    total_size_bytes: int = 0
    uploaded_bytes: int = 0
    progress_percentage: float = 0.0
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Error handling
    error_message: str = ""
    retry_count: int = 0
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LocalUploadConfig:
    """Configuration for local file uploads."""
    file_path: str
    temp_upload_dir: str = "/tmp/sc_uploads"
    preserve_structure: bool = True
    delete_after_upload: bool = False


@dataclass
class GoogleDriveUploadConfig:
    """Configuration for Google Drive uploads."""
    file_id: str
    service_account_file: str
    shared_drive_id: Optional[str] = None
    download_format: str = "original"  # original, pdf, etc.
    convert_to_visus: bool = True


@dataclass
class S3UploadConfig:
    """Configuration for S3 uploads."""
    bucket_name: str
    object_key: str
    access_key_id: str
    secret_access_key: str
    region: str = "us-east-1"
    storage_class: str = "STANDARD"
    server_side_encryption: Optional[str] = None


@dataclass
class URLUploadConfig:
    """Configuration for URL-based uploads."""
    url: str
    download_method: str = "wget"  # wget, curl, requests
    auth_required: bool = False
    auth_config: Dict[str, Any] = field(default_factory=dict)
    verify_ssl: bool = True
    follow_redirects: bool = True
    max_redirects: int = 5


@dataclass
class UploadProgress:
    """Upload progress tracking."""
    job_id: str
    status: UploadStatus
    progress_percentage: float
    bytes_uploaded: int
    bytes_total: int
    speed_mbps: float
    eta_seconds: int
    current_file: str = ""
    error_message: str = ""
    last_updated: datetime = field(default_factory=datetime.utcnow)


class UploadJobManager:
    """Manages upload job configurations and progress tracking."""
    
    def __init__(self):
        self.upload_configs: Dict[str, UploadJobConfig] = {}
        self.progress_tracking: Dict[str, UploadProgress] = {}
    
    def create_upload_job(self, job_id: str, config: UploadJobConfig) -> str:
        """Create a new upload job."""
        self.upload_configs[job_id] = config
        self.progress_tracking[job_id] = UploadProgress(
            job_id=job_id,
            status=UploadStatus.QUEUED,
            progress_percentage=0.0,
            bytes_uploaded=0,
            bytes_total=config.total_size_bytes,
            speed_mbps=0.0,
            eta_seconds=0
        )
        return job_id
    
    def update_progress(self, job_id: str, progress: UploadProgress):
        """Update upload progress."""
        if job_id in self.progress_tracking:
            self.progress_tracking[job_id] = progress
    
    def get_progress(self, job_id: str) -> Optional[UploadProgress]:
        """Get current upload progress."""
        return self.progress_tracking.get(job_id)
    
    def get_job_config(self, job_id: str) -> Optional[UploadJobConfig]:
        """Get upload job configuration."""
        return self.upload_configs.get(job_id)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel an upload job."""
        if job_id in self.progress_tracking:
            self.progress_tracking[job_id].status = UploadStatus.CANCELLED
            return True
        return False
    
    def pause_job(self, job_id: str) -> bool:
        """Pause an upload job."""
        if job_id in self.progress_tracking:
            self.progress_tracking[job_id].status = UploadStatus.PAUSED
            return True
        return False
    
    def resume_job(self, job_id: str) -> bool:
        """Resume a paused upload job."""
        if job_id in self.progress_tracking:
            if self.progress_tracking[job_id].status == UploadStatus.PAUSED:
                self.progress_tracking[job_id].status = UploadStatus.UPLOADING
                return True
        return False


# Tool-specific configurations
TOOL_CONFIGS = {
    UploadSourceType.LOCAL: {
        "primary_tool": "rclone",
        "fallback_tool": "rsync",
        "chunk_size_mb": 64,
        "max_retries": 3,
        "resume_support": True
    },
    UploadSourceType.GOOGLE_DRIVE: {
        "primary_tool": "rclone",
        "fallback_tool": "gdrive",
        "chunk_size_mb": 32,
        "max_retries": 5,
        "resume_support": True
    },
    UploadSourceType.S3: {
        "primary_tool": "aws_cli",
        "fallback_tool": "rclone",
        "chunk_size_mb": 128,
        "max_retries": 3,
        "resume_support": True
    },
    UploadSourceType.URL: {
        "primary_tool": "wget",
        "fallback_tool": "curl",
        "chunk_size_mb": 16,
        "max_retries": 5,
        "resume_support": True
    }
}


def get_tool_config(source_type: UploadSourceType) -> Dict[str, Any]:
    """Get tool configuration for a source type."""
    return TOOL_CONFIGS.get(source_type, {})


def create_upload_job_config(
    source_type: UploadSourceType,
    source_path: str,
    destination_path: str,
    dataset_uuid: str,
    user_email: str,
    dataset_name: str,
    sensor: SensorType,
    original_source_path: Optional[str] = None,
    convert: bool = True,
    is_public: bool = False,
    is_downloadable: str = "only owner",
    folder: Optional[str] = None,
    team_uuid: Optional[str] = None,
    **kwargs
) -> UploadJobConfig:
    """Create an upload job configuration with ScientistCloud parameters."""
    return UploadJobConfig(
        source_type=source_type,
        source_path=source_path,
        destination_path=destination_path,
        dataset_uuid=dataset_uuid,
        original_source_path=original_source_path,
        user_email=user_email,
        dataset_name=dataset_name,
        sensor=sensor,
        convert=convert,
        is_public=is_public,
        is_downloadable=is_downloadable,
        folder=folder,
        team_uuid=team_uuid,
        **kwargs
    )


# Example usage functions
def create_local_upload_job(
    file_path: str,
    dataset_uuid: str,
    user_email: str,
    dataset_name: str,
    sensor: SensorType,
    original_source_path: Optional[str] = None,
    convert: bool = True,
    is_public: bool = False,
    is_downloadable: str = "only owner",
    folder: Optional[str] = None,
    team_uuid: Optional[str] = None,
    **kwargs
) -> UploadJobConfig:
    """Create a local file upload job.
    
    Note: The 'folder' parameter is for UI organization only (metadata).
    It does NOT affect file system paths - all files go directly into the UUID directory.
    For directory uploads, use the relative_path parameter to preserve directory structure.
    """
    # Always use UUID directory - folder is metadata only, not for file system structure
    destination_path = f"{os.getenv('JOB_IN_DATA_DIR', '/mnt/visus_datasets/upload')}/{dataset_uuid}"
    
    return create_upload_job_config(
        source_type=UploadSourceType.LOCAL,
        source_path=file_path,
        destination_path=destination_path,
        dataset_uuid=dataset_uuid,
        user_email=user_email,
        dataset_name=dataset_name,
        sensor=sensor,
        original_source_path=original_source_path,
        convert=convert,
        is_public=is_public,
        is_downloadable=is_downloadable,
        folder=folder,
        team_uuid=team_uuid,
        **kwargs
    )


def create_google_drive_upload_job(
    file_id: str,
    dataset_uuid: str,
    user_email: str,
    dataset_name: str,
    sensor: SensorType,
    service_account_file: Optional[str] = None,
    convert: bool = True,
    is_public: bool = False,
    is_downloadable: str = "only owner",
    folder: Optional[str] = None,
    team_uuid: Optional[str] = None,
    source_config_override: Optional[Dict[str, Any]] = None,
    **kwargs
) -> UploadJobConfig:
    """Create a Google Drive upload job.
    
    Supports both OAuth-based (user_email in source_config) and service account-based uploads.
    If source_config_override is provided, it will be used instead of building from parameters.
    """
    # Use override config if provided (for OAuth), otherwise build from parameters
    if source_config_override:
        source_config = source_config_override
    else:
        source_config = {
            "file_id": file_id
        }
        if service_account_file:
            source_config["service_account_file"] = service_account_file
    
    return create_upload_job_config(
        source_type=UploadSourceType.GOOGLE_DRIVE,
        source_path=file_id,
        destination_path=f"{os.getenv('JOB_IN_DATA_DIR', '/mnt/visus_datasets/upload')}/{dataset_uuid}",
        dataset_uuid=dataset_uuid,
        user_email=user_email,
        dataset_name=dataset_name,
        sensor=sensor,
        original_source_path=None,
        convert=convert,
        is_public=is_public,
        is_downloadable=is_downloadable,
        folder=folder,
        team_uuid=team_uuid,
        source_config=source_config,
        **kwargs
    )


def create_s3_upload_job(
    bucket_name: str,
    object_key: str,
    dataset_uuid: str,
    user_email: str,
    dataset_name: str,
    sensor: SensorType,
    access_key_id: str,
    secret_access_key: str,
    convert: bool = True,
    is_public: bool = False,
    is_downloadable: str = "only owner",
    folder: Optional[str] = None,
    team_uuid: Optional[str] = None,
    **kwargs
) -> UploadJobConfig:
    """Create an S3 upload job."""
    return create_upload_job_config(
        source_type=UploadSourceType.S3,
        source_path=f"s3://{bucket_name}/{object_key}",
        destination_path=f"{os.getenv('JOB_IN_DATA_DIR', '/mnt/visus_datasets/upload')}/{dataset_uuid}",
        dataset_uuid=dataset_uuid,
        user_email=user_email,
        dataset_name=dataset_name,
        sensor=sensor,
        original_source_path=None,
        convert=convert,
        is_public=is_public,
        is_downloadable=is_downloadable,
        folder=folder,
        team_uuid=team_uuid,
        source_config={
            "bucket_name": bucket_name,
            "object_key": object_key,
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key
        },
        **kwargs
    )


def create_url_upload_job(
    url: str,
    dataset_uuid: str,
    user_email: str,
    dataset_name: str,
    sensor: SensorType,
    convert: bool = True,
    is_public: bool = False,
    is_downloadable: str = "only owner",
    folder: Optional[str] = None,
    team_uuid: Optional[str] = None,
    **kwargs
) -> UploadJobConfig:
    """Create a URL-based upload job."""
    return create_upload_job_config(
        source_type=UploadSourceType.URL,
        source_path=url,
        destination_path=f"{os.getenv('JOB_IN_DATA_DIR', '/mnt/visus_datasets/upload')}/{dataset_uuid}",
        dataset_uuid=dataset_uuid,
        user_email=user_email,
        dataset_name=dataset_name,
        sensor=sensor,
        original_source_path=None,
        convert=convert,
        is_public=is_public,
        is_downloadable=is_downloadable,
        folder=folder,
        team_uuid=team_uuid,
        source_config={"url": url},
        **kwargs
    )


if __name__ == '__main__':
    # Example usage
    print("SC_UploadJobTypes - Upload Job Configuration Examples")
    print("=" * 60)
    
    # Create example upload jobs
    local_job = create_local_upload_job(
        file_path="/tmp/my_dataset.zip",
        dataset_uuid="dataset_123",
        user_email="user@example.com",
        dataset_name="My Local Dataset",
        sensor=SensorType.TIFF,
        original_source_path="/tmp/my_dataset.zip",
        convert=True,
        is_public=False,
        folder="research_data",
        team_uuid="team_456"
    )
    
    gdrive_job = create_google_drive_upload_job(
        file_id="1ABC123DEF456",
        dataset_uuid="dataset_789",
        user_email="user@example.com",
        dataset_name="Google Drive Dataset",
        sensor=SensorType.NETCDF,
        service_account_file="/path/to/service.json",
        convert=False,
        is_public=True
    )
    
    s3_job = create_s3_upload_job(
        bucket_name="my-bucket",
        object_key="data/dataset.zip",
        dataset_uuid="dataset_101",
        user_email="user@example.com",
        dataset_name="S3 Dataset",
        sensor=SensorType.HDF5,
        access_key_id="AKIA...",
        secret_access_key="secret...",
        convert=True,
        is_public=False,
        folder="cloud_data"
    )
    
    url_job = create_url_upload_job(
        url="https://example.com/dataset.zip",
        dataset_uuid="dataset_202",
        user_email="user@example.com",
        dataset_name="URL Dataset",
        sensor=SensorType.OTHER,
        convert=True,
        is_public=False
    )
    
    print(f"Local upload job: {local_job.source_type.value}")
    print(f"Google Drive job: {gdrive_job.source_type.value}")
    print(f"S3 upload job: {s3_job.source_type.value}")
    print(f"URL upload job: {url_job.source_type.value}")
    
    # Show tool configurations
    print(f"\nTool configurations:")
    for source_type in UploadSourceType:
        config = get_tool_config(source_type)
        print(f"  {source_type.value}: {config.get('primary_tool', 'unknown')}")
