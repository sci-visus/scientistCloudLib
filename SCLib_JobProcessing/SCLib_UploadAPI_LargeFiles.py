#!/usr/bin/env python3
"""
ScientistCloud Upload API - Large File Support (TB-scale)
Optimized for handling enormous datasets with chunked uploads, resumable transfers, and cloud storage integration.
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

# Large file configuration
CHUNK_SIZE = 100 * 1024 * 1024  # 100MB chunks
MAX_FILE_SIZE = 10 * 1024 * 1024 * 1024 * 1024  # 10TB max
TEMP_DIR = "/tmp/scientistcloud_uploads"  # Configure for your environment
RESUMABLE_UPLOAD_TIMEOUT = 7 * 24 * 3600  # 7 days

# Ensure temp directory exists
os.makedirs(TEMP_DIR, exist_ok=True)

# Create FastAPI app with large file support
app = FastAPI(
    title="ScientistCloud Upload API - Large Files",
    description="High-performance API for TB-scale dataset uploads with chunked and resumable transfers",
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

# Pydantic Models
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

class ChunkUploadResponse(BaseModel):
    """Response for chunked upload initiation."""
    upload_id: str = Field(..., description="Unique upload session ID")
    chunk_size: int = Field(..., description="Chunk size in bytes")
    total_chunks: int = Field(..., description="Total number of chunks")
    message: str = Field(..., description="Status message")

class ChunkStatusResponse(BaseModel):
    """Response for chunk upload status."""
    upload_id: str = Field(..., description="Upload session ID")
    uploaded_chunks: List[int] = Field(..., description="List of uploaded chunk indices")
    total_chunks: int = Field(..., description="Total number of chunks")
    is_complete: bool = Field(..., description="Whether all chunks are uploaded")
    progress_percentage: float = Field(0.0, ge=0.0, le=100.0, description="Upload progress")

class ResumeUploadResponse(BaseModel):
    """Response for resumable upload info."""
    upload_id: str = Field(..., description="Upload session ID")
    missing_chunks: List[int] = Field(..., description="List of missing chunk indices")
    total_chunks: int = Field(..., description="Total number of chunks")
    can_resume: bool = Field(..., description="Whether upload can be resumed")

class CloudUploadRequest(BaseModel):
    """Request for cloud storage upload."""
    source_type: UploadSourceType = Field(..., description="Type of cloud source")
    source_config: Dict[str, Any] = Field(..., description="Source-specific configuration")
    user_email: EmailStr = Field(..., description="User email address")
    dataset_name: str = Field(..., min_length=1, max_length=255, description="Name of the dataset")
    sensor: SensorType = Field(..., description="Sensor type")
    convert: bool = Field(True, description="Whether to convert the data")
    is_public: bool = Field(False, description="Whether dataset is public")
    folder: Optional[str] = Field(None, max_length=255, description="Optional folder name")
    team_uuid: Optional[str] = Field(None, description="Optional team UUID")

# In-memory storage for upload sessions (use Redis in production)
upload_sessions: Dict[str, Dict[str, Any]] = {}

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

# Dependency to get upload processor
def get_processor():
    return upload_processor

# API Endpoints for Large Files

@app.post("/api/upload/large/initiate", response_model=ChunkUploadResponse)
async def initiate_large_upload(
    request: ChunkUploadRequest,
    background_tasks: BackgroundTasks,
    processor: Any = Depends(get_processor)
):
    """
    Initiate a chunked upload for large files (TB-scale).
    
    This endpoint creates an upload session and returns chunk information.
    Files are uploaded in 100MB chunks to handle TB-scale data efficiently.
    """
    try:
        # Generate unique upload ID
        upload_id = f"large_upload_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        
        # Calculate chunk information
        total_chunks = math.ceil(request.file_size / CHUNK_SIZE)
        
        # Validate file size
        if request.file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413, 
                detail=f"File size {request.file_size} exceeds maximum allowed size of {MAX_FILE_SIZE} bytes"
            )
        
        # Create upload session
        session_data = {
            'filename': request.filename,
            'file_size': request.file_size,
            'file_hash': request.file_hash,
            'user_email': request.user_email,
            'dataset_name': request.dataset_name,
            'sensor': request.sensor,
            'convert': request.convert,
            'is_public': request.is_public,
            'folder': request.folder,
            'team_uuid': request.team_uuid,
            'total_chunks': total_chunks,
            'chunk_size': CHUNK_SIZE
        }
        
        create_upload_session(upload_id, session_data)
        
        # Create upload directory
        upload_dir = os.path.join(TEMP_DIR, upload_id)
        os.makedirs(upload_dir, exist_ok=True)
        
        logger.info(f"Initiated large upload: {upload_id}, {total_chunks} chunks, {request.file_size} bytes")
        
        return ChunkUploadResponse(
            upload_id=upload_id,
            chunk_size=CHUNK_SIZE,
            total_chunks=total_chunks,
            message=f"Upload session created for {request.filename}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating large upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/large/chunk/{upload_id}/{chunk_index}")
async def upload_chunk(
    upload_id: str,
    chunk_index: int,
    chunk: UploadFile = File(...),
    chunk_hash: str = Form(..., description="SHA-256 hash of the chunk"),
    processor: Any = Depends(get_processor)
):
    """
    Upload a single chunk of a large file.
    
    Chunks are validated by hash and stored temporarily until all chunks are received.
    """
    try:
        # Get upload session
        session = get_upload_session(upload_id)
        
        # Validate chunk index
        if chunk_index < 0 or chunk_index >= session['total_chunks']:
            raise HTTPException(status_code=400, detail="Invalid chunk index")
        
        # Validate chunk size (except for last chunk)
        expected_chunk_size = CHUNK_SIZE
        if chunk_index == session['total_chunks'] - 1:
            # Last chunk might be smaller
            expected_chunk_size = session['file_size'] - (chunk_index * CHUNK_SIZE)
        
        if chunk.size > expected_chunk_size:
            raise HTTPException(status_code=400, detail="Chunk size exceeds expected size")
        
        # Read and validate chunk
        chunk_data = await chunk.read()
        actual_hash = hashlib.sha256(chunk_data).hexdigest()
        
        if actual_hash != chunk_hash:
            raise HTTPException(status_code=400, detail="Chunk hash mismatch")
        
        # Save chunk to temporary file
        upload_dir = os.path.join(TEMP_DIR, upload_id)
        chunk_file = os.path.join(upload_dir, f"chunk_{chunk_index:06d}")
        
        async with aiofiles.open(chunk_file, 'wb') as f:
            await f.write(chunk_data)
        
        # Update session
        update_upload_session(upload_id, chunk_index, chunk_hash)
        
        logger.info(f"Uploaded chunk {chunk_index}/{session['total_chunks']} for {upload_id}")
        
        return {
            "message": f"Chunk {chunk_index} uploaded successfully",
            "uploaded_chunks": len(session['uploaded_chunks']),
            "total_chunks": session['total_chunks']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading chunk: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/upload/large/status/{upload_id}", response_model=ChunkStatusResponse)
async def get_chunk_upload_status(upload_id: str):
    """Get the status of a chunked upload."""
    try:
        session = get_upload_session(upload_id)
        
        uploaded_chunks = sorted(list(session['uploaded_chunks']))
        progress = (len(uploaded_chunks) / session['total_chunks']) * 100
        
        return ChunkStatusResponse(
            upload_id=upload_id,
            uploaded_chunks=uploaded_chunks,
            total_chunks=session['total_chunks'],
            is_complete=len(uploaded_chunks) == session['total_chunks'],
            progress_percentage=progress
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chunk status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/large/complete/{upload_id}")
async def complete_large_upload(
    upload_id: str,
    background_tasks: BackgroundTasks,
    processor: Any = Depends(get_processor)
):
    """
    Complete a chunked upload by assembling all chunks and starting processing.
    
    This endpoint:
    1. Verifies all chunks are uploaded
    2. Assembles the complete file
    3. Validates the file hash
    4. Starts the upload processing job
    """
    try:
        session = get_upload_session(upload_id)
        
        # Verify all chunks are uploaded
        if len(session['uploaded_chunks']) != session['total_chunks']:
            missing_chunks = set(range(session['total_chunks'])) - session['uploaded_chunks']
            raise HTTPException(
                status_code=400, 
                detail=f"Missing chunks: {sorted(missing_chunks)}"
            )
        
        # Assemble file
        upload_dir = os.path.join(TEMP_DIR, upload_id)
        final_file_path = os.path.join(upload_dir, session['filename'])
        
        logger.info(f"Assembling {session['total_chunks']} chunks for {upload_id}")
        
        with open(final_file_path, 'wb') as final_file:
            for chunk_index in range(session['total_chunks']):
                chunk_file = os.path.join(upload_dir, f"chunk_{chunk_index:06d}")
                with open(chunk_file, 'rb') as chunk_f:
                    shutil.copyfileobj(chunk_f, final_file)
        
        # Validate file hash
        logger.info(f"Validating file hash for {upload_id}")
        file_hash = hashlib.sha256()
        with open(final_file_path, 'rb') as f:
            for chunk_data in iter(lambda: f.read(8192), b""):
                file_hash.update(chunk_data)
        
        if file_hash.hexdigest() != session['file_hash']:
            raise HTTPException(status_code=400, detail="File hash validation failed")
        
        # Create upload job
        job_config = create_local_upload_job(
            file_path=final_file_path,
            dataset_uuid=str(uuid.uuid4()),
            user_id=session['user_email'],
            dataset_name=session['dataset_name'],
            sensor_type=session['sensor'],
            convert=session['convert'],
            is_public=session['is_public'],
            folder=session['folder'],
            team_uuid=session['team_uuid']
        )
        
        # Submit job to processor
        background_tasks.add_task(processor.submit_upload_job, job_config)
        
        # Clean up chunk files
        for chunk_index in range(session['total_chunks']):
            chunk_file = os.path.join(upload_dir, f"chunk_{chunk_index:06d}")
            if os.path.exists(chunk_file):
                os.remove(chunk_file)
        
        logger.info(f"Large upload completed: {upload_id}, file: {final_file_path}")
        
        return {
            "message": f"Upload completed successfully: {session['filename']}",
            "file_path": final_file_path,
            "file_size": session['file_size'],
            "job_submitted": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing large upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/upload/large/resume/{upload_id}", response_model=ResumeUploadResponse)
async def get_resume_info(upload_id: str):
    """Get information needed to resume an interrupted upload."""
    try:
        session = get_upload_session(upload_id)
        
        uploaded_chunks = session['uploaded_chunks']
        all_chunks = set(range(session['total_chunks']))
        missing_chunks = sorted(list(all_chunks - uploaded_chunks))
        
        return ResumeUploadResponse(
            upload_id=upload_id,
            missing_chunks=missing_chunks,
            total_chunks=session['total_chunks'],
            can_resume=len(missing_chunks) > 0
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting resume info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload/cloud/large", response_model=Dict[str, str])
async def initiate_cloud_large_upload(
    request: CloudUploadRequest,
    background_tasks: BackgroundTasks,
    processor: Any = Depends(get_processor)
):
    """
    Initiate a large file upload from cloud storage (S3, Google Drive, etc.).
    
    This endpoint is optimized for TB-scale files from cloud sources.
    """
    try:
        # Generate unique job ID
        job_id = f"cloud_large_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        
        # Create upload job based on source type
        if request.source_type == UploadSourceType.GOOGLE_DRIVE:
            job_config = create_google_drive_upload_job(
                file_id=request.source_config['file_id'],
                service_account_file=request.source_config['service_account_file'],
                dataset_uuid=str(uuid.uuid4()),
                user_id=request.user_email,
                dataset_name=request.dataset_name,
                sensor_type=request.sensor,
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
                user_id=request.user_email,
                dataset_name=request.dataset_name,
                sensor_type=request.sensor,
                convert=request.convert,
                is_public=request.is_public,
                folder=request.folder,
                team_uuid=request.team_uuid
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported source type for large files: {request.source_type}")
        
        # Submit job to processor
        background_tasks.add_task(processor.submit_upload_job, job_config)
        
        return {
            "job_id": job_id,
            "status": "queued",
            "message": f"Large cloud upload initiated for {request.source_type}",
            "estimated_duration": "Varies by file size and network"
        }
        
    except Exception as e:
        logger.error(f"Error initiating cloud large upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/upload/large/limits")
async def get_upload_limits():
    """Get current upload limits and configuration."""
    return {
        "max_file_size_bytes": MAX_FILE_SIZE,
        "max_file_size_tb": MAX_FILE_SIZE / (1024**4),
        "chunk_size_bytes": CHUNK_SIZE,
        "chunk_size_mb": CHUNK_SIZE / (1024**2),
        "resumable_upload_timeout_days": RESUMABLE_UPLOAD_TIMEOUT / (24 * 3600),
        "supported_source_types": [source.value for source in UploadSourceType],
        "recommended_for_files_larger_than_mb": 100,  # Use chunked upload for files > 100MB
        "temp_directory": TEMP_DIR
    }

@app.delete("/api/upload/large/cancel/{upload_id}")
async def cancel_large_upload(upload_id: str):
    """Cancel a large file upload and clean up resources."""
    try:
        if upload_id not in upload_sessions:
            raise HTTPException(status_code=404, detail="Upload session not found")
        
        # Clean up files
        upload_dir = os.path.join(TEMP_DIR, upload_id)
        if os.path.exists(upload_dir):
            shutil.rmtree(upload_dir)
        
        # Remove session
        del upload_sessions[upload_id]
        
        return {"message": f"Upload session {upload_id} cancelled and cleaned up"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling large upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check with large file info
@app.get("/health/large-files")
async def health_check_large_files():
    """Health check with large file upload information."""
    active_uploads = len(upload_sessions)
    temp_dir_size = 0
    
    if os.path.exists(TEMP_DIR):
        for root, dirs, files in os.walk(TEMP_DIR):
            for file in files:
                temp_dir_size += os.path.getsize(os.path.join(root, file))
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "active_uploads": active_uploads,
        "temp_directory_size_mb": temp_dir_size / (1024**2),
        "max_file_size_tb": MAX_FILE_SIZE / (1024**4),
        "chunk_size_mb": CHUNK_SIZE / (1024**2)
    }

if __name__ == "__main__":
    import uvicorn
    
    # Start the upload processor
    upload_processor.start()
    
    # Run the FastAPI app with optimized settings for large files
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5001,  # Different port for large file API
        log_level="info",
        reload=False,  # Disable reload for production
        workers=1,  # Single worker for large file handling
        limit_max_requests=100,  # Limit requests per worker
        timeout_keep_alive=300  # 5 minute keep-alive for large uploads
    )

