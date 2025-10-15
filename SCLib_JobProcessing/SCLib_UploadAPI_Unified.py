#!/usr/bin/env python3
"""
ScientistCloud Upload API - Unified Version
Automatically handles both regular and TB-scale uploads based on file size.
No need for users to choose between API versions!
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Dict, Any, Optional, List, BinaryIO
import uuid
import os
import tempfile
import hashlib
import shutil
from datetime import datetime
import asyncio
import logging
import aiofiles
from pathlib import Path
import math

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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration constants
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB - use chunked upload for files larger than this
CHUNK_SIZE = 100 * 1024 * 1024  # 100MB chunks
MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024 * 1024  # 10TB max
TEMP_DIR = "/tmp/scientistcloud_uploads"
RESUMABLE_UPLOAD_TIMEOUT = 7 * 24 * 3600  # 7 days

# Ensure temp directory exists
os.makedirs(TEMP_DIR, exist_ok=True)

# Create FastAPI app
app = FastAPI(
    title="ScientistCloud Upload API - Unified",
    description="Unified API that automatically handles both regular and TB-scale uploads",
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

# In-memory storage for upload sessions (use Redis in production)
upload_sessions: Dict[str, Dict[str, Any]] = {}

# Pydantic Models
class UploadRequest(BaseModel):
    """Request for upload initiation."""
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

class ChunkUploadRequest(BaseModel):
    """Request for chunked upload initiation."""
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., gt=0, le=MAX_FILE_SIZE, description="Total file size in bytes")
    file_hash: str = Field(..., description="SHA-256 hash of the complete file")
    user_email: EmailStr = Field(..., description="User email address")
    dataset_name: str = Field(..., min_length=1, max_length=255, description="Name of the dataset")
    sensor: SensorType = Field(..., description="Sensor type")
    convert: bool = Field(True, description="Whether to convert the data")
    is_public: bool = Field(False, description="Whether dataset is public")
    folder: Optional[str] = Field(None, max_length=255, description="Optional folder name")
    team_uuid: Optional[str] = Field(None, description="Optional team UUID")

class UploadResponse(BaseModel):
    """Response for upload operations."""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Initial job status")
    message: str = Field(..., description="Status message")
    estimated_duration: Optional[int] = Field(None, description="Estimated duration in seconds")
    upload_type: str = Field(..., description="Type of upload (standard or chunked)")

class ChunkUploadResponse(BaseModel):
    """Response for chunked upload initiation."""
    upload_id: str = Field(..., description="Unique upload session ID")
    chunk_size: int = Field(..., description="Chunk size in bytes")
    total_chunks: int = Field(..., description="Total number of chunks")
    message: str = Field(..., description="Status message")

class JobStatusResponse(BaseModel):
    """Response for job status."""
    job_id: str = Field(..., description="Job identifier")
    status: UploadStatus = Field(..., description="Current job status")
    progress_percentage: float = Field(0.0, ge=0.0, le=100.0, description="Progress percentage")
    bytes_uploaded: Optional[int] = Field(None, description="Bytes uploaded so far")
    bytes_total: Optional[int] = Field(None, description="Total bytes to upload")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(..., description="Job creation time")
    updated_at: datetime = Field(..., description="Last update time")

class SupportedSourcesResponse(BaseModel):
    """Response for supported sources."""
    source_types: List[str] = Field(..., description="Supported source types")
    sensor_types: List[str] = Field(..., description="Supported sensor types")
    required_parameters: Dict[str, List[str]] = Field(..., description="Required parameters by source type")
    optional_parameters: Dict[str, List[str]] = Field(..., description="Optional parameters by source type")
    large_file_threshold_mb: int = Field(..., description="File size threshold for chunked uploads (MB)")

# Helper functions
def get_upload_session(upload_id: str) -> Dict[str, Any]:
    """Get upload session data."""
    if upload_id not in upload_sessions:
        raise HTTPException(status_code=404, detail="Upload session not found")
    return upload_sessions[upload_id]

def create_upload_session(upload_id: str, data: Dict[str, Any]) -> None:
    """Create new upload session."""
    upload_sessions[upload_id] = {
        **data,
        'created_at': datetime.now(),
        'uploaded_chunks': set(),
        'chunk_hashes': {}
    }

def update_upload_session(upload_id: str, chunk_index: int, chunk_hash: str) -> None:
    """Update upload session with new chunk."""
    if upload_id in upload_sessions:
        upload_sessions[upload_id]['uploaded_chunks'].add(chunk_index)
        upload_sessions[upload_id]['chunk_hashes'][chunk_index] = chunk_hash

def determine_upload_type(file_size: int) -> str:
    """Determine if file should use standard or chunked upload."""
    return "chunked" if file_size > LARGE_FILE_THRESHOLD else "standard"

# Dependency to get upload processor
def get_processor():
    return upload_processor

# API Endpoints

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "ScientistCloud Upload API - Unified",
        "version": "2.0.0",
        "description": "Automatically handles both regular and TB-scale uploads",
        "docs": "/docs",
        "redoc": "/redoc",
        "large_file_threshold_mb": str(LARGE_FILE_THRESHOLD // (1024 * 1024))
    }

@app.get("/health", response_model=Dict[str, str])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "upload_type": "unified",
        "large_file_threshold_mb": str(LARGE_FILE_THRESHOLD // (1024 * 1024)),
        "max_file_size_tb": str(MAX_FILE_SIZE // (1024**4))
    }

@app.post("/api/upload/initiate", response_model=UploadResponse)
async def initiate_upload(
    request: UploadRequest,
    background_tasks: BackgroundTasks,
    processor: Any = Depends(get_processor)
):
    """
    Initiate an upload job.
    
    Automatically determines whether to use standard or chunked upload based on file size.
    For cloud sources, this creates a standard job. For local files, use the /upload endpoint.
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
            upload_type = "standard"
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
            upload_type = "standard"
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
            upload_type = "standard"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported source type: {request.source_type}")
        
        # Submit job to processor
        background_tasks.add_task(processor.submit_upload_job, job_config)
        
        # Estimate duration based on source type
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
            upload_type=upload_type
        )
        
    except Exception as e:
        logger.error(f"Error initiating upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/upload", response_model=UploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="File to upload"),
    user_email: EmailStr = Form(..., description="User email address"),
    dataset_name: str = Form(..., min_length=1, max_length=255, description="Name of the dataset"),
    sensor: SensorType = Form(..., description="Sensor type"),
    convert: bool = Form(True, description="Whether to convert the data"),
    is_public: bool = Form(False, description="Whether dataset is public"),
    folder: Optional[str] = Form(None, max_length=255, description="Optional folder name"),
    team_uuid: Optional[str] = Form(None, description="Optional team UUID"),
    dataset_uuid: Optional[str] = Form(None, description="Optional dataset UUID for directory uploads"),
    processor: Any = Depends(get_processor)
):
    """
    Upload a file with automatic handling of standard vs chunked uploads.
    
    Files larger than 100MB are automatically handled with chunked uploads.
    Smaller files use standard upload for better performance.
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file selected")
        
        # Read file content to determine size
        content = await file.read()
        file_size = len(content)
        
        # Determine upload type based on file size
        upload_type = determine_upload_type(file_size)
        
        if upload_type == "chunked":
            # Use chunked upload for large files
            return await _handle_chunked_upload(
                content, file.filename, file_size, user_email, dataset_name,
                sensor, convert, is_public, folder, team_uuid, dataset_uuid, background_tasks, processor
            )
        else:
            # Use standard upload for smaller files
            return await _handle_standard_upload(
                content, file.filename, user_email, dataset_name,
                sensor, convert, is_public, folder, team_uuid, dataset_uuid, background_tasks, processor
            )
        
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def _handle_standard_upload(
    content: bytes, filename: str, user_email: str, dataset_name: str,
    sensor: SensorType, convert: bool, is_public: bool, folder: Optional[str],
    team_uuid: Optional[str], dataset_uuid: Optional[str], background_tasks: BackgroundTasks, processor: Any
) -> UploadResponse:
    """Handle standard upload for smaller files."""
    # Generate unique job ID
    job_id = f"upload_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
    
    # Save uploaded file to temporary location
    temp_dir = tempfile.mkdtemp()
    temp_file_path = os.path.join(temp_dir, filename)
    
    with open(temp_file_path, "wb") as buffer:
        buffer.write(content)
    
    # Create local upload job
    # Use provided UUID for directory uploads, or generate new one for single files
    upload_uuid = dataset_uuid if dataset_uuid else str(uuid.uuid4())
    job_config = create_local_upload_job(
        file_path=temp_file_path,
        dataset_uuid=upload_uuid,
        user_email=user_email,
        dataset_name=dataset_name or filename,
        sensor=sensor,
        convert=convert,
        is_public=is_public,
        folder=folder,  # Use folder parameter for directory structure
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
        message=f"Standard upload initiated: {filename}",
        estimated_duration=estimated_duration,
        upload_type="standard"
    )

async def _handle_chunked_upload(
    content: bytes, filename: str, file_size: int, user_email: str, dataset_name: str,
    sensor: SensorType, convert: bool, is_public: bool, folder: Optional[str],
    team_uuid: Optional[str], dataset_uuid: Optional[str], background_tasks: BackgroundTasks, processor: Any
) -> UploadResponse:
    """Handle chunked upload for large files."""
    # Generate unique upload ID
    upload_id = f"chunked_upload_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
    
    # Calculate file hash
    file_hash = hashlib.sha256(content).hexdigest()
    
    # Calculate chunk information
    total_chunks = math.ceil(file_size / CHUNK_SIZE)
    
    # Create upload session
    session_data = {
        'filename': filename,
        'file_size': file_size,
        'file_hash': file_hash,
        'user_email': user_email,
        'dataset_name': dataset_name,
        'sensor': sensor,
        'convert': convert,
        'is_public': is_public,
        'folder': folder,
        'team_uuid': team_uuid,
        'dataset_uuid': dataset_uuid,  # Include dataset UUID for directory uploads
        'total_chunks': total_chunks,
        'chunk_size': CHUNK_SIZE,
        'content': content  # Store content for processing
    }
    
    create_upload_session(upload_id, session_data)
    
    # Create upload directory
    upload_dir = os.path.join(TEMP_DIR, upload_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    # Process chunks immediately (for this unified API, we'll process all chunks at once)
    await _process_chunks(upload_id, content, background_tasks, processor)
    
    logger.info(f"Initiated chunked upload: {upload_id}, {total_chunks} chunks, {file_size} bytes")
    
    return UploadResponse(
        job_id=upload_id,
        status="queued",
        message=f"Chunked upload initiated: {filename}",
        estimated_duration=max(300, int(file_size / (1024 * 1024) * 2)),  # 2 seconds per MB
        upload_type="chunked"
    )

async def _process_chunks(upload_id: str, content: bytes, background_tasks: BackgroundTasks, processor: Any):
    """Process all chunks for a chunked upload."""
    try:
        session = get_upload_session(upload_id)
        
        # Save complete file
        upload_dir = os.path.join(TEMP_DIR, upload_id)
        final_file_path = os.path.join(upload_dir, session['filename'])
        
        with open(final_file_path, 'wb') as f:
            f.write(content)
        
        # Create upload job
        # Use provided UUID for directory uploads, or generate new one for single files
        upload_uuid = session.get('dataset_uuid') if session.get('dataset_uuid') else str(uuid.uuid4())
        job_config = create_local_upload_job(
            file_path=final_file_path,
            dataset_uuid=upload_uuid,
            user_email=session['user_email'],
            dataset_name=session['dataset_name'],
            sensor=session['sensor'],
            convert=session['convert'],
            is_public=session['is_public'],
            folder=session.get('folder'),  # Use folder parameter for directory structure
            team_uuid=session['team_uuid']
        )
        
        # Submit job to processor
        background_tasks.add_task(processor.submit_upload_job, job_config)
        
        # Mark as complete
        session['uploaded_chunks'] = set(range(session['total_chunks']))
        session['is_complete'] = True
        
        logger.info(f"Chunked upload completed: {upload_id}")
        
    except Exception as e:
        logger.error(f"Error processing chunks for {upload_id}: {e}")
        raise

@app.get("/api/upload/status/{job_id}", response_model=JobStatusResponse)
async def get_upload_status(job_id: str, processor: Any = Depends(get_processor)):
    """Get the status of an upload job."""
    try:
        # Check if it's a chunked upload session
        if job_id in upload_sessions:
            session = upload_sessions[job_id]
            uploaded_chunks = len(session['uploaded_chunks'])
            total_chunks = session['total_chunks']
            progress = (uploaded_chunks / total_chunks) * 100 if total_chunks > 0 else 0
            
            return JobStatusResponse(
                job_id=job_id,
                status=UploadStatus.UPLOADING if not session.get('is_complete', False) else UploadStatus.COMPLETED,
                progress_percentage=progress,
                bytes_uploaded=int(session['file_size'] * progress / 100) if progress > 0 else 0,
                bytes_total=session['file_size'],
                message=f"Chunked upload: {uploaded_chunks}/{total_chunks} chunks",
                created_at=session['created_at'],
                updated_at=datetime.now()
            )
        else:
            # Standard job status
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
        # Check if it's a chunked upload session
        if job_id in upload_sessions:
            # Clean up files
            upload_dir = os.path.join(TEMP_DIR, job_id)
            if os.path.exists(upload_dir):
                shutil.rmtree(upload_dir)
            
            # Remove session
            del upload_sessions[job_id]
            
            return {"message": f"Chunked upload {job_id} cancelled and cleaned up"}
        else:
            # Standard job cancellation
            success = processor.cancel_job(job_id)
            if not success:
                raise HTTPException(status_code=404, detail="Job not found or already completed")
            
            return {"message": f"Job {job_id} cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling job: {e}")
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
        },
        large_file_threshold_mb=LARGE_FILE_THRESHOLD // (1024 * 1024)
    )

@app.get("/api/upload/limits")
async def get_upload_limits():
    """Get current upload limits and configuration."""
    return {
        "max_file_size_bytes": MAX_FILE_SIZE,
        "max_file_size_tb": MAX_FILE_SIZE / (1024**4),
        "large_file_threshold_bytes": LARGE_FILE_THRESHOLD,
        "large_file_threshold_mb": LARGE_FILE_THRESHOLD / (1024**2),
        "chunk_size_bytes": CHUNK_SIZE,
        "chunk_size_mb": CHUNK_SIZE / (1024**2),
        "resumable_upload_timeout_days": RESUMABLE_UPLOAD_TIMEOUT / (24 * 3600),
        "supported_source_types": [source.value for source in UploadSourceType],
        "temp_directory": TEMP_DIR
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
