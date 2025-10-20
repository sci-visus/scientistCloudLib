#!/usr/bin/env python3
"""
ScientistCloud Upload API - FastAPI Version
Modern, high-performance RESTful API for asynchronous upload handling.
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Dict, Any, Optional, List
import uuid
import os
import tempfile
from datetime import datetime
import asyncio
import logging

try:
    from .SCLib_Config import get_config
    from .SCLib_UploadProcessor import get_upload_processor
    from .SCLib_UploadJobTypes import (
        UploadJobConfig, UploadSourceType, SensorType, UploadStatus,
        create_local_upload_job, create_google_drive_upload_job,
        create_s3_upload_job, create_url_upload_job
    )
except ImportError:
    from SCLib_Config import get_config
    from SCLib_UploadProcessor import get_upload_processor
    from SCLib_UploadJobTypes import (
        UploadJobConfig, UploadSourceType, SensorType, UploadStatus,
        create_local_upload_job, create_google_drive_upload_job,
        create_s3_upload_job, create_url_upload_job
    )

# Configure logging (only if not already configured)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="ScientistCloud Upload API",
    description="Asynchronous upload API for ScientistCloud datasets",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global upload processor
upload_processor = get_upload_processor()

# Pydantic Models for Request/Response
class GoogleDriveConfig(BaseModel):
    file_id: str = Field(..., description="Google Drive file ID")
    service_account_file: str = Field(..., description="Path to service account JSON file")

class S3Config(BaseModel):
    bucket_name: str = Field(..., description="S3 bucket name")
    object_key: str = Field(..., description="S3 object key")
    access_key_id: str = Field(..., description="AWS access key ID")
    secret_access_key: str = Field(..., description="AWS secret access key")

class URLConfig(BaseModel):
    url: str = Field(..., description="URL to download from")

class UploadRequest(BaseModel):
    source_type: UploadSourceType = Field(..., description="Type of upload source")
    source_config: Dict[str, Any] = Field(..., description="Source-specific configuration")
    user_email: EmailStr = Field(..., description="User email address")
    dataset_name: str = Field(..., min_length=1, max_length=255, description="Name of the dataset")
    sensor: SensorType = Field(..., description="Sensor type")
    convert: bool = Field(True, description="Whether to convert the data")
    is_public: bool = Field(False, description="Whether dataset is public")
    folder: Optional[str] = Field(None, max_length=255, description="Optional folder name")
    team_uuid: Optional[str] = Field(None, description="Optional team UUID")

    @validator('source_config')
    def validate_source_config(cls, v, values):
        source_type = values.get('source_type')
        if source_type == UploadSourceType.GOOGLE_DRIVE:
            required_fields = ['file_id', 'service_account_file']
        elif source_type == UploadSourceType.S3:
            required_fields = ['bucket_name', 'object_key', 'access_key_id', 'secret_access_key']
        elif source_type == UploadSourceType.URL:
            required_fields = ['url']
        else:
            return v
        
        for field in required_fields:
            if field not in v:
                raise ValueError(f"Missing required field '{field}' for source type '{source_type}'")
        return v

class UploadResponse(BaseModel):
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Initial job status")
    message: str = Field(..., description="Status message")
    estimated_duration: Optional[int] = Field(None, description="Estimated duration in seconds")

class JobStatusResponse(BaseModel):
    job_id: str = Field(..., description="Job identifier")
    status: UploadStatus = Field(..., description="Current job status")
    progress_percentage: float = Field(0.0, ge=0.0, le=100.0, description="Progress percentage")
    bytes_uploaded: Optional[int] = Field(None, description="Bytes uploaded so far")
    bytes_total: Optional[int] = Field(None, description="Total bytes to upload")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Job creation time")
    updated_at: datetime = Field(..., description="Last update time")

class JobListResponse(BaseModel):
    jobs: List[JobStatusResponse] = Field(..., description="List of jobs")
    total: int = Field(..., description="Total number of jobs")
    limit: int = Field(..., description="Limit applied")
    offset: int = Field(..., description="Offset applied")

class SupportedSourcesResponse(BaseModel):
    source_types: List[str] = Field(..., description="Supported source types")
    sensor_types: List[str] = Field(..., description="Supported sensor types")
    required_parameters: Dict[str, List[str]] = Field(..., description="Required parameters by source type")
    optional_parameters: Dict[str, List[str]] = Field(..., description="Optional parameters by source type")

# Dependency to get upload processor
def get_processor():
    return upload_processor

# API Endpoints
@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "ScientistCloud Upload API",
        "version": "2.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health", response_model=Dict[str, str])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/api/upload/initiate", response_model=UploadResponse)
async def initiate_upload(
    request: UploadRequest,
    background_tasks: BackgroundTasks,
    processor: Any = Depends(get_processor)
):
    """
    Initiate an asynchronous upload job.
    
    Supports multiple source types:
    - google_drive: Import from Google Drive
    - s3: Import from S3/cloud storage
    - url: Download from URL
    """
    try:
        # Generate unique job ID
        job_id = f"upload_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        
        # Create upload job based on source type
        if request.source_type == UploadSourceType.GOOGLE_DRIVE:
            job_config = create_google_drive_upload_job(
                file_id=request.source_config['file_id'],
                service_account_file=request.source_config['service_account_file'],
                dataset_uuid=str(uuid.uuid4()),
                user_email=request.user_email,
                dataset_name=request.dataset_name,
                sensor=request.sensor,
                convert=request.convert,
                is_public=request.is_public,
                folder=request.folder,
                team_uuid=request.team_uuid
            )
        elif request.source_type == UploadSourceType.S3:
            job_config = create_s3_upload_job(
                bucket_name=request.source_config['bucket_name'],
                object_key=request.source_config['object_key'],
                access_key_id=request.source_config['access_key_id'],
                secret_access_key=request.source_config['secret_access_key'],
                dataset_uuid=str(uuid.uuid4()),
                user_email=request.user_email,
                dataset_name=request.dataset_name,
                sensor=request.sensor,
                convert=request.convert,
                is_public=request.is_public,
                folder=request.folder,
                team_uuid=request.team_uuid
            )
        elif request.source_type == UploadSourceType.URL:
            job_config = create_url_upload_job(
                url=request.source_config['url'],
                dataset_uuid=str(uuid.uuid4()),
                user_email=request.user_email,
                dataset_name=request.dataset_name,
                sensor=request.sensor,
                convert=request.convert,
                is_public=request.is_public,
                folder=request.folder,
                team_uuid=request.team_uuid
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported source type: {request.source_type}")
        
        # Submit job to processor
        background_tasks.add_task(processor.submit_upload_job, job_config)
        
        # Estimate duration based on source type and size
        estimated_duration = 300  # Default 5 minutes
        if request.source_type == UploadSourceType.URL:
            estimated_duration = 180  # 3 minutes for URL downloads
        elif request.source_type == UploadSourceType.GOOGLE_DRIVE:
            estimated_duration = 600  # 10 minutes for Google Drive
        
        return UploadResponse(
            job_id=job_id,
            status="queued",
            message=f"Upload job initiated for {request.source_type}",
            estimated_duration=estimated_duration
        )
        
    except Exception as e:
        logger.error(f"Error initiating upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/local/upload", response_model=UploadResponse)
async def upload_local_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File to upload"),
    user_email: EmailStr = Form(..., description="User email address"),
    dataset_name: str = Form(..., min_length=1, max_length=255, description="Name of the dataset"),
    sensor: SensorType = Form(..., description="Sensor type"),
    convert: bool = Form(True, description="Whether to convert the data"),
    is_public: bool = Form(False, description="Whether dataset is public"),
    folder: Optional[str] = Form(None, max_length=255, description="Optional folder name"),
    team_uuid: Optional[str] = Form(None, description="Optional team UUID"),
    processor: Any = Depends(get_processor)
):
    """
    Upload a local file and initiate processing.
    This endpoint handles the actual file upload for local files.
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file selected")
        
        # Generate unique job ID
        job_id = f"upload_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        
        # Save uploaded file to temporary location
        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, file.filename)
        
        with open(temp_file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Create local upload job
        job_config = create_local_upload_job(
            file_path=temp_file_path,
            dataset_uuid=str(uuid.uuid4()),
            user_email=user_email,
            dataset_name=dataset_name or file.filename,
            sensor=sensor,
            original_source_path=file.filename,
            convert=convert,
            is_public=is_public,
            folder=folder,
            team_uuid=team_uuid
        )
        
        # Submit job to processor
        background_tasks.add_task(processor.submit_upload_job, job_config)
        
        # Estimate duration based on file size
        file_size_mb = len(content) / (1024 * 1024)
        estimated_duration = max(60, int(file_size_mb * 2))  # 2 seconds per MB, minimum 1 minute
        
        return UploadResponse(
            job_id=job_id,
            status="queued",
            message=f"Local file upload initiated: {file.filename}",
            estimated_duration=estimated_duration
        )
        
    except Exception as e:
        logger.error(f"Error uploading local file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/upload-path", response_model=UploadResponse)
async def upload_file_by_path(
    background_tasks: BackgroundTasks,
    file_path: str = Form(..., description="Path to the file to upload"),
    user_email: EmailStr = Form(..., description="User email address"),
    dataset_name: str = Form(..., min_length=1, max_length=255, description="Name of the dataset"),
    sensor: SensorType = Form(..., description="Sensor type"),
    convert: bool = Form(True, description="Whether to convert the data"),
    is_public: bool = Form(False, description="Whether dataset is public"),
    folder: Optional[str] = Form(None, max_length=255, description="Optional folder name"),
    team_uuid: Optional[str] = Form(None, description="Optional team UUID"),
    dataset_identifier: Optional[str] = Form(None, description="Dataset identifier (UUID, name, slug, or numeric ID) for directory uploads or adding to existing dataset"),
    add_to_existing: bool = Form(False, description="Whether to add to existing dataset (requires dataset_identifier)"),
    processor: Any = Depends(get_processor)
):
    """
    Upload a file by providing its path instead of uploading the file content.
    This is more efficient for large files as it avoids copying to /tmp.
    
    ⚠️  IMPORTANT: This endpoint requires the file to be accessible from the server.
    It's primarily intended for development use where files are mounted in Docker.
    For production use, prefer the /api/upload/upload endpoint which works across all environments.
    
    See README_upload_methods.md for detailed documentation.
    """
    try:
        # Validate file path exists
        if not os.path.exists(file_path):
            raise HTTPException(status_code=400, detail=f"File not found: {file_path}")
        
        if not os.path.isfile(file_path):
            raise HTTPException(status_code=400, detail=f"Path is not a file: {file_path}")
        
        # Get file info
        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        
        # Resolve dataset identifier to UUID if provided
        upload_uuid = None
        if dataset_identifier:
            try:
                upload_uuid = processor._resolve_dataset_identifier(dataset_identifier)
                logger.info(f"Resolved dataset identifier '{dataset_identifier}' to UUID: {upload_uuid}")
            except ValueError as e:
                raise HTTPException(status_code=404, detail=str(e))
        else:
            upload_uuid = str(uuid.uuid4())  # Generate new UUID for single files
        
        # For single file uploads, don't use folder for file system structure
        # The folder parameter is for UI organization only
        # Only use folder structure for directory uploads (when dataset_identifier is provided)
        file_system_folder = folder if dataset_identifier else None
        
        # Create local upload job with the original file path (no /tmp copying!)
        job_config = create_local_upload_job(
            file_path=file_path,  # Use original file path directly
            dataset_uuid=upload_uuid,
            user_email=user_email,
            dataset_name=dataset_name or filename,
            sensor=sensor,
            original_source_path=file_path,
            convert=convert,
            is_public=is_public,
            folder=file_system_folder,
            team_uuid=team_uuid
        )
        
        # Submit job to processor and get the actual job ID
        actual_job_id = processor.submit_upload_job(job_config)
        
        # Estimate duration based on file size
        file_size_mb = file_size / (1024 * 1024)
        estimated_duration = max(60, int(file_size_mb * 2))  # 2 seconds per MB, minimum 1 minute
        
        return UploadResponse(
            job_id=actual_job_id,
            status="queued",
            message=f"File path upload initiated: {filename}",
            estimated_duration=estimated_duration,
            upload_type="path"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file by path: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/upload/status/{job_id}", response_model=JobStatusResponse)
async def get_upload_status(job_id: str, processor: Any = Depends(get_processor)):
    """Get the status of an upload job."""
    try:
        status = processor.get_job_status(job_id)
        if not status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return JobStatusResponse(
            job_id=status.job_id,
            status=status.status,
            progress_percentage=status.progress_percentage,
            bytes_uploaded=status.bytes_uploaded,
            bytes_total=status.bytes_total,
            message=getattr(status, 'current_file', '') or f"Processing {status.status.value}",
            error=getattr(status, 'error_message', None),
            created_at=getattr(status, 'created_at', datetime.now()),
            updated_at=status.last_updated
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/cancel/{job_id}", response_model=Dict[str, str])
async def cancel_upload(job_id: str, processor: Any = Depends(get_processor)):
    """Cancel an upload job."""
    try:
        success = processor.cancel_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail="Job not found or already completed")
        
        return {"message": f"Job {job_id} cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/upload/jobs", response_model=JobListResponse)
async def list_upload_jobs(
    user_id: EmailStr = None,
    status: Optional[UploadStatus] = None,
    limit: int = 50,
    offset: int = 0,
    processor: Any = Depends(get_processor)
):
    """List upload jobs for a user."""
    try:
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id parameter is required")
        
        jobs = processor.get_queued_jobs(user_id, status, limit, offset)
        
        return JobListResponse(
            jobs=[JobStatusResponse(**job) for job in jobs['jobs']],
            total=jobs['total'],
            limit=limit,
            offset=offset
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/upload/supported-sources", response_model=SupportedSourcesResponse)
async def get_supported_sources():
    """Get supported upload sources and their requirements."""
    return SupportedSourcesResponse(
        source_types=[source.value for source in UploadSourceType],
        sensor_types=[sensor.value for sensor in SensorType],
        required_parameters={
            "google_drive": ["file_id", "service_account_file"],
            "s3": ["bucket_name", "object_key", "access_key_id", "secret_access_key"],
            "url": ["url"],
            "local": ["file"]
        },
        optional_parameters={
            "google_drive": ["folder", "team_uuid"],
            "s3": ["folder", "team_uuid"],
            "url": ["folder", "team_uuid"],
            "local": ["folder", "team_uuid"]
        }
    )

@app.get("/api/upload/estimate-time", response_model=Dict[str, Any])
async def estimate_upload_time(
    source_type: UploadSourceType,
    file_size_mb: Optional[float] = None
):
    """Estimate upload time based on source type and file size."""
    base_times = {
        UploadSourceType.LOCAL: 60,      # 1 minute base
        UploadSourceType.GOOGLE_DRIVE: 300,  # 5 minutes base
        UploadSourceType.S3: 180,        # 3 minutes base
        UploadSourceType.URL: 120        # 2 minutes base
    }
    
    base_time = base_times.get(source_type, 300)
    
    if file_size_mb:
        # Add time based on file size (2 seconds per MB)
        additional_time = file_size_mb * 2
        estimated_time = base_time + additional_time
    else:
        estimated_time = base_time
    
    return {
        "source_type": source_type.value,
        "estimated_seconds": int(estimated_time),
        "estimated_minutes": round(estimated_time / 60, 1),
        "file_size_mb": file_size_mb
    }

# Error handlers
@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Not found", "detail": str(exc)}
    )

@app.exception_handler(422)
async def validation_error_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"error": "Validation error", "detail": exc.errors()}
    )

@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": "An unexpected error occurred"}
    )

if __name__ == "__main__":
    import uvicorn
    
    # Start the upload processor
    upload_processor.start()
    
    # Run the FastAPI app
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000,
        log_level="info",
        reload=True  # Enable auto-reload for development
    )
