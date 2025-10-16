#!/usr/bin/env python3
"""
ScientistCloud Upload API - Authenticated Version
Enhanced upload API with token-based authentication integration.
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends, Request
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

# Import SCLib components
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

# Import authentication components
try:
    from ..SCLib_Auth.SCLib_AuthMiddleware import (
        require_auth, optional_auth, get_current_user, get_current_user_email,
        get_current_user_id, AuthResult, setup_auth_middleware,
        create_authenticated_upload_request, log_authenticated_action
    )
except ImportError:
    # Fallback for standalone usage
    import sys
    sys.path.append('/Users/amygooch/GIT/ScientistCloud_2.0/scientistCloudLib/SCLib_Auth')
    from SCLib_AuthMiddleware import (
        require_auth, optional_auth, get_current_user, get_current_user_email,
        get_current_user_id, AuthResult, setup_auth_middleware,
        create_authenticated_upload_request, log_authenticated_action
    )

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="ScientistCloud Upload API - Authenticated",
    description="Authenticated upload API for ScientistCloud datasets with token-based authorization",
    version="2.1.0",
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

# Setup authentication middleware
setup_auth_middleware(app)

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

class AuthenticatedUploadRequest(BaseModel):
    """Upload request with optional authentication override."""
    source_type: UploadSourceType = Field(..., description="Type of upload source")
    source_config: Dict[str, Any] = Field(..., description="Source-specific configuration")
    user_email: Optional[EmailStr] = Field(None, description="User email address (optional if authenticated)")
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
    user_email: str = Field(..., description="User email who initiated the upload")

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
    user_email: str = Field(..., description="User email who owns the job")

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

# Helper function to resolve user email
def resolve_user_email(auth_result: AuthResult, provided_email: Optional[str] = None) -> str:
    """
    Resolve user email from authentication or provided parameter.
    
    Args:
        auth_result: Authentication result
        provided_email: Optional email provided in request
        
    Returns:
        Resolved user email
        
    Raises:
        HTTPException: If no valid email can be resolved
    """
    if auth_result.is_authenticated and auth_result.user_email:
        # If authenticated, use authenticated email (ignore provided email for security)
        return auth_result.user_email
    elif provided_email:
        # If not authenticated but email provided, use provided email (for backward compatibility)
        return provided_email
    else:
        raise HTTPException(
            status_code=400,
            detail="User email is required. Either authenticate with a token or provide user_email parameter."
        )

# API Endpoints

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "ScientistCloud Upload API - Authenticated",
        "version": "2.1.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "authentication": "Token-based authentication supported via Authorization header or cookies"
    }

@app.get("/health", response_model=Dict[str, str])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/api/upload/initiate", response_model=UploadResponse)
async def initiate_upload(
    request: AuthenticatedUploadRequest,
    background_tasks: BackgroundTasks,
    auth_result: AuthResult = Depends(optional_auth),
    processor: Any = Depends(get_processor)
):
    """
    Initiate an asynchronous upload job with optional authentication.
    
    If authenticated via token, the authenticated user's email will be used.
    If not authenticated, the user_email parameter is required.
    
    Supports multiple source types:
    - google_drive: Import from Google Drive
    - s3: Import from S3/cloud storage
    - url: Download from URL
    """
    try:
        # Resolve user email
        user_email = resolve_user_email(auth_result, request.user_email)
        
        # Log the action
        log_authenticated_action(
            user_email=user_email,
            action="initiate_upload",
            resource=f"{request.source_type}:{request.dataset_name}",
            source_type=request.source_type,
            dataset_name=request.dataset_name
        )
        
        # Generate unique job ID
        job_id = f"upload_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        
        # Create upload job based on source type
        if request.source_type == UploadSourceType.GOOGLE_DRIVE:
            job_config = create_google_drive_upload_job(
                file_id=request.source_config['file_id'],
                service_account_file=request.source_config['service_account_file'],
                dataset_uuid=str(uuid.uuid4()),
                user_email=user_email,
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
                user_email=user_email,
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
                user_email=user_email,
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
            estimated_duration=estimated_duration,
            user_email=user_email
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/upload", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File to upload"),
    user_email: Optional[EmailStr] = Form(None, description="User email address (optional if authenticated)"),
    dataset_name: str = Form(..., min_length=1, max_length=255, description="Name of the dataset"),
    sensor: SensorType = Form(..., description="Sensor type"),
    convert: bool = Form(True, description="Whether to convert the data"),
    is_public: bool = Form(False, description="Whether dataset is public"),
    folder: Optional[str] = Form(None, max_length=255, description="Optional folder name"),
    team_uuid: Optional[str] = Form(None, description="Optional team UUID"),
    dataset_identifier: Optional[str] = Form(None, description="Dataset identifier for adding to existing dataset"),
    add_to_existing: bool = Form(False, description="Whether to add to existing dataset"),
    auth_result: AuthResult = Depends(require_auth),
    processor: Any = Depends(get_processor)
):
    """
    Upload a file with automatic handling and required authentication.
    
    This is the main upload endpoint that requires JWT token authentication.
    The authenticated user's email will be automatically extracted from the token.
    
    Files larger than 100MB are automatically handled with chunked uploads.
    Smaller files use standard upload for better performance.
    """
    try:
        # Resolve user email
        resolved_user_email = resolve_user_email(auth_result, user_email)
        
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file selected")
        
        # Log the action
        log_authenticated_action(
            user_email=resolved_user_email,
            action="upload_file",
            resource=f"file:{file.filename}",
            filename=file.filename,
            dataset_name=dataset_name
        )
        
        # Read file content to determine size
        content = await file.read()
        file_size = len(content)
        
        # Generate unique job ID
        job_id = f"upload_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        
        # Save uploaded file to temporary location
        temp_dir = tempfile.mkdtemp()
        temp_file_path = os.path.join(temp_dir, file.filename)
        
        with open(temp_file_path, "wb") as buffer:
            buffer.write(content)
        
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
        
        # Create local upload job
        job_config = create_local_upload_job(
            file_path=temp_file_path,
            dataset_uuid=upload_uuid,
            user_email=resolved_user_email,
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
        file_size_mb = file_size / (1024 * 1024)
        estimated_duration = max(60, int(file_size_mb * 2))  # 2 seconds per MB, minimum 1 minute
        
        return UploadResponse(
            job_id=job_id,
            status="queued",
            message=f"File upload initiated: {file.filename}",
            estimated_duration=estimated_duration,
            user_email=resolved_user_email
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/upload/status/{job_id}", response_model=JobStatusResponse)
async def get_upload_status(
    job_id: str, 
    auth_result: AuthResult = Depends(optional_auth),
    processor: Any = Depends(get_processor)
):
    """
    Get the status of an upload job.
    
    If authenticated, only returns jobs owned by the authenticated user.
    If not authenticated, returns any job (for backward compatibility).
    """
    try:
        status = processor.get_job_status(job_id)
        if not status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Check if user has access to this job
        if auth_result.is_authenticated:
            # For authenticated users, only show their own jobs
            if hasattr(status, 'user_email') and status.user_email != auth_result.user_email:
                raise HTTPException(status_code=403, detail="Access denied to this job")
        
        return JobStatusResponse(
            job_id=status.job_id,
            status=status.status,
            progress_percentage=status.progress_percentage,
            bytes_uploaded=status.bytes_uploaded,
            bytes_total=status.bytes_total,
            message=getattr(status, 'current_file', '') or f"Processing {status.status.value}",
            error=getattr(status, 'error_message', None),
            created_at=getattr(status, 'created_at', datetime.now()),
            updated_at=status.last_updated,
            user_email=getattr(status, 'user_email', 'unknown')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/upload/jobs", response_model=JobListResponse)
async def list_upload_jobs(
    user_email: Optional[EmailStr] = None,
    status: Optional[UploadStatus] = None,
    limit: int = 50,
    offset: int = 0,
    auth_result: AuthResult = Depends(optional_auth),
    processor: Any = Depends(get_processor)
):
    """
    List upload jobs.
    
    If authenticated, only returns jobs owned by the authenticated user.
    If not authenticated, user_email parameter is required.
    """
    try:
        # Resolve user email
        if auth_result.is_authenticated:
            # For authenticated users, use their email
            resolved_user_email = auth_result.user_email
        elif user_email:
            # For unauthenticated users, use provided email
            resolved_user_email = user_email
        else:
            raise HTTPException(
                status_code=400, 
                detail="user_email parameter is required when not authenticated"
            )
        
        jobs = processor.get_queued_jobs(resolved_user_email, status, limit, offset)
        
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

@app.get("/api/auth/status")
async def get_auth_status(auth_result: AuthResult = Depends(optional_auth)):
    """
    Get authentication status for the current request.
    
    Returns:
        Authentication status information
    """
    return {
        "is_authenticated": auth_result.is_authenticated,
        "user_email": auth_result.user_email,
        "user_id": auth_result.user_id,
        "access_type": auth_result.access_type,
        "error": auth_result.error
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
        port=5001,  # Different port to avoid conflicts
        log_level="info",
        reload=True  # Enable auto-reload for development
    )
