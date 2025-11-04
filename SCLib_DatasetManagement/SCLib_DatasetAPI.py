#!/usr/bin/env python3
"""
SCLib Dataset Management API
Enhanced dataset management with user-friendly identifiers and comprehensive operations.
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Any, List
import uuid
import os
import logging
from datetime import datetime
from pathlib import Path
import re

try:
    from ..SCLib_JobProcessing.SCLib_Config import get_config, get_database_name, get_collection_name
    from ..SCLib_JobProcessing.SCLib_MongoConnection import mongo_collection_by_type_context
    from ..SCLib_JobProcessing.SCLib_UploadProcessor import get_upload_processor
except ImportError:
    import sys
    from pathlib import Path
    import os
    
    # Try multiple paths for SCLib_JobProcessing
    # In Docker, JobProcessing might be at /app (copied by Dockerfile) or /app/scientistCloudLib/SCLib_JobProcessing (mounted)
    possible_paths = [
        Path(__file__).parent.parent / 'SCLib_JobProcessing',  # Relative to scientistCloudLib
        Path('/app/SCLib_JobProcessing'),  # Docker copy location
        Path('/app/scientistCloudLib/SCLib_JobProcessing'),  # Docker mount location
    ]
    
    # Also check SCLIB_CODE_HOME environment variable
    if os.getenv('SCLIB_CODE_HOME'):
        possible_paths.insert(0, Path(os.getenv('SCLIB_CODE_HOME')) / 'SCLib_JobProcessing')
    
    imported = False
    for job_path in possible_paths:
        if job_path.exists():
            job_parent = str(job_path.parent)
            if job_parent not in sys.path:
                sys.path.insert(0, job_parent)
            try:
                from SCLib_JobProcessing.SCLib_Config import get_config, get_database_name, get_collection_name
                from SCLib_JobProcessing.SCLib_MongoConnection import mongo_collection_by_type_context
                from SCLib_JobProcessing.SCLib_UploadProcessor import get_upload_processor
                # Logger will be defined later, but log here for debugging
                print(f"✅ SCLib_JobProcessing found at: {job_path}")
                imported = True
                break
            except ImportError:
                continue
    
    if not imported:
        raise ImportError(f"Could not find SCLib_JobProcessing module. Tried paths: {[str(p) for p in possible_paths]}")

# Get logger
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="SCLib Dataset Management API",
    description="Enhanced dataset management with user-friendly identifiers",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Models
class DatasetCreateRequest(BaseModel):
    """Request model for creating a dataset."""
    name: str = Field(..., min_length=1, max_length=255, description="Dataset name")
    slug: Optional[str] = Field(None, max_length=255, description="Human-readable unique identifier (auto-generated if not provided)")
    sensor: str = Field(..., description="Sensor type")
    description: Optional[str] = Field(None, max_length=1000, description="Dataset description")
    tags: Optional[str] = Field(None, max_length=500, description="Comma-separated tags")
    folder_uuid: Optional[str] = Field(None, description="Folder UUID")
    team_uuid: Optional[str] = Field(None, description="Team UUID")
    is_public: bool = Field(False, description="Whether dataset is public")
    data_conversion_needed: bool = Field(True, description="Whether data conversion is needed")
    preferred_dashboard: Optional[str] = Field(None, description="Preferred dashboard type")
    dimensions: Optional[str] = Field(None, description="Dataset dimensions")

class DatasetUpdateRequest(BaseModel):
    """Request model for updating a dataset."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    tags: Optional[str] = Field(None, max_length=500)
    folder_uuid: Optional[str] = None
    team_uuid: Optional[str] = None
    sensor: Optional[str] = None
    dimensions: Optional[str] = None
    preferred_dashboard: Optional[str] = None
    is_public: Optional[bool] = None
    data_conversion_needed: Optional[bool] = None

class SettingsUpdateRequest(BaseModel):
    """Request model for updating dataset settings."""
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    folder_uuid: Optional[str] = None
    team_uuid: Optional[str] = None
    sensor: Optional[str] = None
    dimensions: Optional[str] = None
    preferred_dashboard: Optional[str] = None
    is_public: Optional[bool] = None
    data_conversion_needed: Optional[bool] = None

class FileAddRequest(BaseModel):
    """Request model for adding files to dataset."""
    replace_existing: bool = Field(False, description="Whether to replace all existing files")
    merge_strategy: str = Field("append", description="Merge strategy: append, replace, merge")

class DatasetResponse(BaseModel):
    """Response model for dataset operations."""
    success: bool
    message: Optional[str] = None
    dataset: Optional[Dict[str, Any]] = None
    identifiers: Optional[Dict[str, Any]] = None

# Dependency to get upload processor (for identifier resolution)
def get_processor():
    """Get upload processor instance."""
    return get_upload_processor()

# Helper Functions
def _generate_slug(name: str, user_email: str) -> str:
    """Generate a unique slug from dataset name."""
    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = re.sub(r'[^\w\s-]', '', name.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    
    # Add user email prefix for uniqueness
    user_prefix = user_email.split('@')[0].lower()
    timestamp = int(datetime.now().timestamp())
    
    return f"{user_prefix}-{slug}-{timestamp}"

def _generate_numeric_id() -> int:
    """Generate a short numeric ID."""
    import time
    return int(time.time() * 1000) % 100000  # 5-digit ID

def _resolve_dataset_identifier(identifier: str) -> str:
    """Resolve various identifier types to a dataset UUID."""
    processor = get_processor()
    return processor._resolve_dataset_identifier(identifier)

def _get_dataset_by_uuid(dataset_uuid: str) -> Optional[Dict[str, Any]]:
    """Get dataset by UUID."""
    with mongo_collection_by_type_context('visstoredatas') as collection:
        dataset = collection.find_one({"uuid": dataset_uuid})
        if dataset and '_id' in dataset:
            dataset['_id'] = str(dataset['_id'])
        return dataset

def _check_dataset_access(dataset: Dict[str, Any], user_email: str) -> bool:
    """Check if user has access to dataset."""
    if dataset.get('user') == user_email or dataset.get('user_email') == user_email:
        return True
    
    # Check shared access
    shared_with = dataset.get('shared_with', [])
    if user_email in shared_with:
        return True
    
    # Check team access
    if dataset.get('team_uuid'):
        # Get user's team from user_profile
        with mongo_collection_by_type_context('user_profile') as user_collection:
            user_profile = user_collection.find_one({"email": user_email})
            if user_profile and user_profile.get('team_id') == dataset.get('team_uuid'):
                return True
    
    # Check if public
    if dataset.get('is_public', False):
        return True
    
    return False

def _calculate_dataset_size(dataset_uuid: str) -> Dict[str, Any]:
    """Calculate dataset size information."""
    # Get dataset directory from config
    config = get_config()
    # Use in_data_dir from job_processing config, or fallback to visus_datasets/upload
    upload_dir = config.job_processing.in_data_dir if hasattr(config, 'job_processing') else f"{config.server.visus_datasets}/upload"
    dataset_dir = Path(upload_dir) / dataset_uuid
    
    total_size = 0
    file_count = 0
    files = []
    
    if dataset_dir.exists():
        for file_path in dataset_dir.rglob('*'):
            if file_path.is_file():
                file_size = file_path.stat().st_size
                total_size += file_size
                file_count += 1
                files.append({
                    'name': file_path.name,
                    'path': str(file_path.relative_to(dataset_dir)),
                    'size': file_size,
                    'size_human': _format_size(file_size)
                })
    
    # Find largest file
    largest_file = max(files, key=lambda x: x['size']) if files else None
    
    return {
        'raw_size': total_size,
        'raw_size_human': _format_size(total_size),
        'file_count': file_count,
        'files': files,
        'largest_file': largest_file
    }

def _format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

# API Endpoints

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "SCLib Dataset Management API",
        "version": "1.0.0",
        "endpoints": {
            "list_datasets": "GET /api/v1/datasets",
            "get_user_datasets": "GET /api/v1/datasets/by-user?user_email={email}",
            "create_dataset": "POST /api/v1/datasets",
            "get_dataset": "GET /api/v1/datasets/{identifier}",
            "update_dataset": "PUT /api/v1/datasets/{identifier}",
            "delete_dataset": "DELETE /api/v1/datasets/{identifier}",
            "get_status": "GET /api/v1/datasets/{identifier}/status",
            "trigger_conversion": "POST /api/v1/datasets/{identifier}/convert",
            "add_files": "POST /api/v1/datasets/{identifier}/files",
            "list_files": "GET /api/v1/datasets/{identifier}/files",
            "remove_file": "DELETE /api/v1/datasets/{identifier}/files/{file_id}",
            "replace_files": "PUT /api/v1/datasets/{identifier}/files",
            "update_settings": "PUT /api/v1/datasets/{identifier}/settings",
            "get_settings": "GET /api/v1/datasets/{identifier}/settings",
            "update_setting": "PATCH /api/v1/datasets/{identifier}/settings/{setting_name}",
            "get_size": "GET /api/v1/datasets/{identifier}/size",
            "user_storage": "GET /api/v1/user/storage",
            "team_storage": "GET /api/v1/teams/{team_uuid}/storage"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "SCLib_DatasetManagement"}

# Dataset CRUD Operations

@app.get("/api/v1/datasets")
async def list_datasets(
    name: Optional[str] = None,
    slug: Optional[str] = None,
    id: Optional[int] = None,
    user_email: Optional[str] = None,
    team_uuid: Optional[str] = None,
    processor: Any = Depends(get_processor)
):
    """List datasets with optional filtering."""
    try:
        with mongo_collection_by_type_context('visstoredatas') as collection:
            query = {}
            
            # Apply filters
            if name:
                query['name'] = name
            if slug:
                query['slug'] = slug
            if id:
                query['id'] = id
            if user_email:
                query['user'] = user_email
            if team_uuid:
                query['team_uuid'] = team_uuid
            
            datasets = list(collection.find(query))
            
            # Convert ObjectId to string
            for dataset in datasets:
                if '_id' in dataset:
                    dataset['_id'] = str(dataset['_id'])
            
            return {
                'success': True,
                'datasets': datasets,
                'count': len(datasets)
            }
            
    except Exception as e:
        logger.error(f"Failed to list datasets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/datasets/by-user")
async def get_user_datasets_organized(
    user_email: EmailStr,
    processor: Any = Depends(get_processor)
):
    """
    Get all datasets for a user organized by type (my, shared, team).
    Similar to old portal's getFullDatasets() function.
    """
    try:
        db_name = get_database_name()
        
        # Get my datasets
        with mongo_collection_by_type_context('visstoredatas') as collection:
            my_datasets = list(collection.find({
                '$or': [
                    {'user': user_email},
                    {'user_email': user_email}
                ]
            }).sort([('folder_uuid', 1), ('name', 1)]))
        
        # Get shared datasets via shared_user collection
        with mongo_collection_by_type_context('shared_user') as shared_collection:
            shared_pipeline = [
                {'$match': {'user': user_email}},
                {'$lookup': {
                    'from': 'visstoredatas',
                    'localField': 'uuid',
                    'foreignField': 'uuid',
                    'as': 'sharing_data'
                }},
                {'$sort': {'folder_uuid': 1, 'name': 1}}
            ]
            shared_cursor = shared_collection.aggregate(shared_pipeline)
            shared_uuids = [doc['uuid'] for doc in shared_cursor if doc.get('uuid')]
        
        shared_datasets = []
        if shared_uuids:
            with mongo_collection_by_type_context('visstoredatas') as collection:
                shared_datasets = list(collection.find({'uuid': {'$in': shared_uuids}}))
        
        # Get team datasets
        team_datasets = []
        with mongo_collection_by_type_context('teams') as teams_collection:
            teams = list(teams_collection.find({'emails': user_email}))
            team_uuids = [team.get('uuid') for team in teams if team.get('uuid')]
        
        if team_uuids:
            with mongo_collection_by_type_context('shared_team') as shared_team_collection:
                team_pipeline = [
                    {'$match': {'team_uuid': {'$in': team_uuids}}},
                    {'$lookup': {
                        'from': 'visstoredatas',
                        'localField': 'uuid',
                        'foreignField': 'uuid',
                        'as': 'sharing_data'
                    }}
                ]
                team_cursor = shared_team_collection.aggregate(team_pipeline)
                team_uuids_list = [doc['uuid'] for doc in team_cursor if doc.get('uuid')]
            
            if team_uuids_list:
                with mongo_collection_by_type_context('visstoredatas') as collection:
                    team_datasets = list(collection.find({'uuid': {'$in': team_uuids_list}}))
        
        # Format datasets
        def format_dataset(doc):
            doc_dict = dict(doc) if not isinstance(doc, dict) else doc
            if '_id' in doc_dict:
                doc_dict['_id'] = str(doc_dict['_id'])
            
            # Format similar to old portal
            link = doc_dict.get('google_drive_link', '')
            uuid = doc_dict.get('uuid', '')
            contains_http = 'http' in link
            contains_google = 'google.com' in link
            server = 'true' if (contains_http and not contains_google) else 'false'
            
            dataset_url = ''
            if server == 'true':
                dataset_url = link
            else:
                config = get_config()
                deploy_server = config.server.deploy_server
                dataset_url = f"{deploy_server}/mod_visus?dataset={uuid}&&server=false"
            
            return {
                'uuid': uuid,
                'name': doc_dict.get('name', 'Unnamed Dataset'),
                'data_size': doc_dict.get('data_size') or doc_dict.get('total_size', 0),
                'folder': doc_dict.get('folder_uuid', ''),
                'folder_uuid': doc_dict.get('folder_uuid', ''),
                'time': doc_dict.get('time') or doc_dict.get('date_imported'),
                'team': doc_dict.get('team_uuid', ''),
                'team_uuid': doc_dict.get('team_uuid', ''),
                'tags': doc_dict.get('tags', []),
                'sensor': doc_dict.get('sensor', 'Unknown'),
                'status': doc_dict.get('status', 'unknown'),
                'compression_status': doc_dict.get('compression_status', 'unknown'),
                'url': dataset_url,
                'google_drive_link': link,
                'bucket': doc_dict.get('bucket'),
                'prefix': doc_dict.get('prefix'),
                'accesskey': doc_dict.get('accesskey'),
                'secretkey': doc_dict.get('secretkey')
            }
        
        return {
            'success': True,
            'datasets': {
                'my': [format_dataset(d) for d in my_datasets],
                'shared': [format_dataset(d) for d in shared_datasets],
                'team': [format_dataset(d) for d in team_datasets]
            },
            'counts': {
                'my': len(my_datasets),
                'shared': len(shared_datasets),
                'team': len(team_datasets)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get user datasets organized: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/datasets")
async def create_dataset(
    request: DatasetCreateRequest,
    user_email: EmailStr,
    files: Optional[List[UploadFile]] = File(None),
    processor: Any = Depends(get_processor)
):
    """Create a new dataset with user-friendly identifiers."""
    try:
        # Generate identifiers
        dataset_uuid = str(uuid.uuid4())
        dataset_id = _generate_numeric_id()
        slug = request.slug or _generate_slug(request.name, user_email)
        
        # Ensure slug is unique
        with mongo_collection_by_type_context('visstoredatas') as collection:
            existing = collection.find_one({"slug": slug})
            if existing:
                # Add timestamp to make unique
                slug = f"{slug}-{int(datetime.now().timestamp())}"
        
        # Parse tags
        tags_list = [tag.strip() for tag in request.tags.split(',')] if request.tags else []
        
        # Create dataset document
        dataset_doc = {
            "uuid": dataset_uuid,
            "id": dataset_id,
            "slug": slug,
            "name": request.name,
            "user": user_email,
            "user_email": user_email,
            "description": request.description,
            "sensor": request.sensor,
            "tags": tags_list,
            "folder_uuid": request.folder_uuid,
            "team_uuid": request.team_uuid,
            "is_public": request.is_public,
            "data_conversion_needed": request.data_conversion_needed,
            "preferred_dashboard": request.preferred_dashboard or "openvisus",
            "dimensions": request.dimensions,
            "status": "submitted",
            "file_count": 0,
            "total_size": 0,
            "date_imported": datetime.utcnow(),
            "date_updated": datetime.utcnow(),
            "last_accessed": datetime.utcnow(),
            "metadata": {}
        }
        
        # Insert into database
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.insert_one(dataset_doc)
        
        logger.info(f"Created dataset: {slug} ({dataset_uuid}) for user: {user_email}")
        
        return {
            "success": True,
            "uuid": dataset_uuid,
            "id": dataset_id,
            "name": request.name,
            "slug": slug,
            "status": "submitted",
            "message": "Dataset created successfully",
            "identifiers": {
                "uuid": dataset_uuid,
                "id": dataset_id,
                "slug": slug,
                "name": request.name
            },
            "upload_url": f"/api/v1/datasets/{slug}/files",
            "processing_estimate": "5-10 minutes"
        }
        
    except Exception as e:
        logger.error(f"Failed to create dataset: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create dataset: {e}")

@app.get("/api/v1/datasets/{identifier}")
async def get_dataset(
    identifier: str,
    user_email: Optional[str] = None,
    processor: Any = Depends(get_processor)
):
    """Get dataset information using flexible identifier."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access if user_email provided
        if user_email and not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return {
            "success": True,
            "identifier": identifier,
            "resolved_uuid": dataset_uuid,
            "dataset": dataset
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/datasets/{identifier}")
async def update_dataset(
    identifier: str,
    request: DatasetUpdateRequest,
    user_email: EmailStr = None,
    processor: Any = Depends(get_processor)
):
    """Update dataset information."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access (user_email required for updates)
        if not user_email:
            raise HTTPException(status_code=400, detail="user_email is required for updates")
        
        if not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Prepare update data
        update_data = {
            "date_updated": datetime.utcnow()
        }
        
        # Update fields if provided
        if request.name:
            update_data["name"] = request.name
        if request.description is not None:
            update_data["description"] = request.description
        if request.tags is not None:
            tags_list = [tag.strip() for tag in request.tags.split(',')] if request.tags else []
            update_data["tags"] = tags_list
        if request.folder_uuid is not None:
            update_data["folder_uuid"] = request.folder_uuid
        if request.team_uuid is not None:
            update_data["team_uuid"] = request.team_uuid
        if request.sensor is not None:
            update_data["sensor"] = request.sensor
        if request.dimensions is not None:
            update_data["dimensions"] = request.dimensions
        if request.preferred_dashboard is not None:
            update_data["preferred_dashboard"] = request.preferred_dashboard
        if request.is_public is not None:
            update_data["is_public"] = request.is_public
        if request.data_conversion_needed is not None:
            update_data["data_conversion_needed"] = request.data_conversion_needed
        
        # Update in database
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": dataset_uuid},
                {"$set": update_data}
            )
        
        # Get updated dataset
        updated_dataset = _get_dataset_by_uuid(dataset_uuid)
        
        updated_fields = list(update_data.keys())
        updated_fields.remove('date_updated')
        
        logger.info(f"Updated dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": "Dataset updated successfully",
            "updated_fields": updated_fields,
            "dataset": updated_dataset
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/datasets/{identifier}")
async def delete_dataset(
    identifier: str,
    user_email: EmailStr = None,
    processor: Any = Depends(get_processor)
):
    """Delete a dataset."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access (user_email required for deletes)
        if not user_email:
            raise HTTPException(status_code=400, detail="user_email is required for deletes")
        
        # Only owner can delete
        if dataset.get('user') != user_email and dataset.get('user_email') != user_email:
            raise HTTPException(status_code=403, detail="Only the dataset owner can delete it")
        
        # Delete dataset from database
        with mongo_collection_by_type_context('visstoredatas') as collection:
            result = collection.delete_one({"uuid": dataset_uuid})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # TODO: Delete associated files from storage
        # This would involve removing files from the file system/S3/etc.
        
        logger.info(f"Deleted dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": "Dataset deleted successfully"
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/datasets/{identifier}/status")
async def get_dataset_status(
    identifier: str,
    user_email: Optional[str] = None,
    processor: Any = Depends(get_processor)
):
    """Get dataset processing status."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access if user_email provided
        if user_email and not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        return {
            "success": True,
            "status": dataset.get('status', 'unknown'),
            "progress": dataset.get('progress', 0),
            "message": dataset.get('status_message', ''),
            "dataset_uuid": dataset_uuid
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dataset status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/datasets/{identifier}/convert")
async def trigger_conversion(
    identifier: str,
    user_email: EmailStr = None,
    processor: Any = Depends(get_processor)
):
    """Trigger dataset conversion."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access (user_email required for conversions)
        if not user_email:
            raise HTTPException(status_code=400, detail="user_email is required for conversions")
        
        if not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Update dataset status to trigger conversion
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": dataset_uuid},
                {
                    "$set": {
                        "status": "processing",
                        "data_conversion_needed": True,
                        "date_updated": datetime.utcnow()
                    }
                }
            )
        
        logger.info(f"Triggered conversion for dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": "Dataset conversion triggered successfully",
            "status": "processing",
            "dataset_uuid": dataset_uuid
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger conversion: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# File Management Endpoints

@app.post("/api/v1/datasets/{identifier}/files")
async def add_files_to_dataset(
    identifier: str,
    files: List[UploadFile] = File(...),
    replace_existing: bool = Form(False),
    merge_strategy: str = Form("append"),
    user_email: EmailStr = Form(...),
    processor: Any = Depends(get_processor)
):
    """Add files to an existing dataset."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access
        if not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # TODO: Implement file upload to storage
        # This would involve:
        # 1. Saving files to the dataset directory
        # 2. Updating file list in database
        # 3. Updating dataset size
        
        files_added = len(files)
        total_files = dataset.get('file_count', 0) + files_added
        
        # Update dataset
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": dataset_uuid},
                {
                    "$set": {
                        "file_count": total_files,
                        "date_updated": datetime.utcnow(),
                        "status": "processing" if dataset.get('data_conversion_needed') else "completed"
                    }
                }
            )
        
        logger.info(f"Added {files_added} files to dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": "Files added successfully",
            "files_added": files_added,
            "total_files": total_files,
            "processing_required": dataset.get('data_conversion_needed', False)
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/datasets/{identifier}/files")
async def list_dataset_files(
    identifier: str,
    user_email: Optional[str] = None,
    processor: Any = Depends(get_processor)
):
    """List files in a dataset."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access if user_email provided
        if user_email and not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get file list from dataset directory
        config = get_config()
        upload_dir = config.job_processing.in_data_dir if hasattr(config, 'job_processing') else f"{config.server.visus_datasets}/upload"
        dataset_dir = Path(upload_dir) / dataset_uuid
        
        files = []
        if dataset_dir.exists():
            for file_path in dataset_dir.rglob('*'):
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    files.append({
                        'name': file_path.name,
                        'path': str(file_path.relative_to(dataset_dir)),
                        'size': file_size,
                        'size_human': _format_size(file_size),
                        'modified': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat()
                    })
        
        return {
            "success": True,
            "dataset_uuid": dataset_uuid,
            "files": files,
            "file_count": len(files),
            "total_size": sum(f['size'] for f in files),
            "total_size_human": _format_size(sum(f['size'] for f in files))
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/v1/datasets/{identifier}/files/{file_id}")
async def remove_file_from_dataset(
    identifier: str,
    file_id: str,
    user_email: EmailStr = None,
    processor: Any = Depends(get_processor)
):
    """Remove a file from a dataset."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access (user_email required for file operations)
        if not user_email:
            raise HTTPException(status_code=400, detail="user_email is required for file operations")
        
        if not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # TODO: Implement file removal from storage
        # This would involve:
        # 1. Finding the file by file_id (could be path, name, or UUID)
        # 2. Deleting the file from storage
        # 3. Updating dataset file count and size
        
        # Update dataset
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": dataset_uuid},
                {
                    "$inc": {"file_count": -1},
                    "$set": {"date_updated": datetime.utcnow()}
                }
            )
        
        logger.info(f"Removed file {file_id} from dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": "File removed successfully",
            "file_id": file_id
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/datasets/{identifier}/files")
async def replace_files_in_dataset(
    identifier: str,
    files: List[UploadFile] = File(...),
    user_email: EmailStr = Form(...),
    processor: Any = Depends(get_processor)
):
    """Replace all files in a dataset."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access
        if not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # TODO: Implement file replacement
        # This would involve:
        # 1. Deleting all existing files
        # 2. Uploading new files
        # 3. Updating dataset file count and size
        
        files_count = len(files)
        
        # Update dataset
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": dataset_uuid},
                {
                    "$set": {
                        "file_count": files_count,
                        "date_updated": datetime.utcnow(),
                        "status": "processing" if dataset.get('data_conversion_needed') else "completed"
                    }
                }
            )
        
        logger.info(f"Replaced files in dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": "Files replaced successfully",
            "files_count": files_count
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to replace files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Settings Management Endpoints

@app.put("/api/v1/datasets/{identifier}/settings")
async def update_dataset_settings(
    identifier: str,
    request: SettingsUpdateRequest,
    user_email: EmailStr = None,
    processor: Any = Depends(get_processor)
):
    """Update dataset settings."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access (user_email required for settings updates)
        if not user_email:
            raise HTTPException(status_code=400, detail="user_email is required for settings updates")
        
        if not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Prepare update data
        update_data = {
            "date_updated": datetime.utcnow()
        }
        
        # Update fields if provided
        if request.name:
            update_data["name"] = request.name
        if request.description is not None:
            update_data["description"] = request.description
        if request.tags is not None:
            tags_list = [tag.strip() for tag in request.tags.split(',')] if request.tags else []
            update_data["tags"] = tags_list
        if request.folder_uuid is not None:
            update_data["folder_uuid"] = request.folder_uuid
        if request.team_uuid is not None:
            update_data["team_uuid"] = request.team_uuid
        if request.sensor is not None:
            update_data["sensor"] = request.sensor
        if request.dimensions is not None:
            update_data["dimensions"] = request.dimensions
        if request.preferred_dashboard is not None:
            update_data["preferred_dashboard"] = request.preferred_dashboard
        if request.is_public is not None:
            update_data["is_public"] = request.is_public
        if request.data_conversion_needed is not None:
            update_data["data_conversion_needed"] = request.data_conversion_needed
        
        # Update in database
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": dataset_uuid},
                {"$set": update_data}
            )
        
        # Get updated dataset
        updated_dataset = _get_dataset_by_uuid(dataset_uuid)
        
        updated_fields = list(update_data.keys())
        updated_fields.remove('date_updated')
        
        logger.info(f"Updated settings for dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": "Dataset settings updated successfully",
            "updated_fields": updated_fields,
            "dataset": updated_dataset
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/datasets/{identifier}/settings")
async def get_dataset_settings(
    identifier: str,
    user_email: Optional[str] = None,
    processor: Any = Depends(get_processor)
):
    """Get dataset settings."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access if user_email provided
        if user_email and not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Extract settings from dataset
        settings = {
            "name": dataset.get('name'),
            "description": dataset.get('description'),
            "tags": ', '.join(dataset.get('tags', [])),
            "folder_uuid": dataset.get('folder_uuid'),
            "team_uuid": dataset.get('team_uuid'),
            "sensor": dataset.get('sensor'),
            "dimensions": dataset.get('dimensions'),
            "preferred_dashboard": dataset.get('preferred_dashboard'),
            "is_public": dataset.get('is_public', False),
            "data_conversion_needed": dataset.get('data_conversion_needed', True)
        }
        
        return {
            "success": True,
            "settings": settings,
            "dataset_uuid": dataset_uuid
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.patch("/api/v1/datasets/{identifier}/settings/{setting_name}")
async def update_specific_setting(
    identifier: str,
    setting_name: str,
    setting_value: str,
    user_email: EmailStr = None,
    processor: Any = Depends(get_processor)
):
    """Update a specific setting."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access (user_email required for setting updates)
        if not user_email:
            raise HTTPException(status_code=400, detail="user_email is required for setting updates")
        
        if not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Allowed settings
        allowed_settings = {
            'name', 'description', 'tags', 'folder_uuid', 'team_uuid',
            'sensor', 'dimensions', 'preferred_dashboard', 'is_public', 'data_conversion_needed'
        }
        
        if setting_name not in allowed_settings:
            raise HTTPException(status_code=400, detail=f"Invalid setting name: {setting_name}")
        
        # Prepare update
        update_data = {
            "date_updated": datetime.utcnow()
        }
        
        # Convert value based on setting type
        if setting_name == 'tags':
            update_data[setting_name] = [tag.strip() for tag in setting_value.split(',')]
        elif setting_name == 'is_public' or setting_name == 'data_conversion_needed':
            update_data[setting_name] = setting_value.lower() in ('true', '1', 'yes')
        else:
            update_data[setting_name] = setting_value
        
        # Update in database
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": dataset_uuid},
                {"$set": update_data}
            )
        
        logger.info(f"Updated setting {setting_name} for dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": f"Setting {setting_name} updated successfully",
            "setting_name": setting_name,
            "setting_value": setting_value
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update setting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Size and Billing Endpoints

@app.get("/api/v1/datasets/{identifier}/size")
async def get_dataset_size(
    identifier: str,
    user_email: Optional[str] = None,
    processor: Any = Depends(get_processor)
):
    """Get dataset size information and billing details."""
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Check access if user_email provided
        if user_email and not _check_dataset_access(dataset, user_email):
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Calculate size
        size_info = _calculate_dataset_size(dataset_uuid)
        
        # Get storage location from config
        config = get_config()
        upload_dir = config.job_processing.in_data_dir if hasattr(config, 'job_processing') else f"{config.server.visus_datasets}/upload"
        
        return {
            "success": True,
            "dataset": {
                "uuid": dataset_uuid,
                "name": dataset.get('name'),
                "size": {
                    "raw_size": size_info['raw_size'],
                    "raw_size_human": size_info['raw_size_human'],
                    "file_count": size_info['file_count'],
                    "largest_file": size_info['largest_file']
                },
                "storage": {
                    "location": f"{upload_dir}/{dataset_uuid}",
                    "region": "us-west-2",  # TODO: Get from config
                    "storage_class": "STANDARD",
                    "replication": "3x"
                },
                "billing": {
                    "storage_cost_per_month": "$0.023",  # TODO: Calculate based on size
                    "data_transfer_cost": "$0.005",
                    "processing_cost": "$0.012",
                    "total_cost_this_month": "$0.040"
                }
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get dataset size: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/user/storage")
async def get_user_storage(
    user_email: EmailStr,
    processor: Any = Depends(get_processor)
):
    """Get user's storage overview."""
    try:
        # Get all user's datasets
        with mongo_collection_by_type_context('visstoredatas') as collection:
            user_datasets = list(collection.find({
                "$or": [
                    {"user": user_email},
                    {"user_email": user_email}
                ]
            }))
        
        # Calculate total storage
        total_size = 0
        datasets_count = len(user_datasets)
        files_count = 0
        
        for dataset in user_datasets:
            dataset_uuid = dataset.get('uuid')
            if dataset_uuid:
                size_info = _calculate_dataset_size(dataset_uuid)
                total_size += size_info['raw_size']
                files_count += size_info['file_count']
        
        # TODO: Get user limits from user_profile or config
        total_available = 1024 * 1024 * 1024 * 1024  # 1TB default
        usage_percentage = (total_size / total_available) * 100 if total_available > 0 else 0
        
        return {
            "success": True,
            "user": user_email,
            "storage": {
                "total_used": _format_size(total_size),
                "total_used_bytes": total_size,
                "total_available": _format_size(total_available),
                "total_available_bytes": total_available,
                "usage_percentage": round(usage_percentage, 2),
                "datasets_count": datasets_count,
                "files_count": files_count
            },
            "breakdown": {
                "raw_data": _format_size(total_size),
                "processed_data": _format_size(0),  # TODO: Calculate processed data size
                "compressed_data": _format_size(0)   # TODO: Calculate compressed data size
            },
            "billing": {
                "current_month_cost": "$12.50",  # TODO: Calculate from actual usage
                "projected_monthly_cost": "$15.75",
                "cost_per_gb": "$0.10"
            },
            "limits": {
                "max_dataset_size": "100 GB",
                "max_files_per_dataset": 1000,
                "max_datasets": 100
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get user storage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/teams/{team_uuid}/storage")
async def get_team_storage(
    team_uuid: str,
    user_email: Optional[EmailStr] = None,
    processor: Any = Depends(get_processor)
):
    """Get team's storage overview."""
    try:
        # Verify user has access to team (if user_email provided)
        if user_email:
            with mongo_collection_by_type_context('user_profile') as user_collection:
                user_profile = user_collection.find_one({"email": user_email})
                if not user_profile or user_profile.get('team_id') != team_uuid:
                    raise HTTPException(status_code=403, detail="Access denied to team")
        
        # Get all team's datasets
        with mongo_collection_by_type_context('visstoredatas') as collection:
            team_datasets = list(collection.find({"team_uuid": team_uuid}))
        
        # Calculate total storage
        total_size = 0
        datasets_count = len(team_datasets)
        files_count = 0
        
        for dataset in team_datasets:
            dataset_uuid = dataset.get('uuid')
            if dataset_uuid:
                size_info = _calculate_dataset_size(dataset_uuid)
                total_size += size_info['raw_size']
                files_count += size_info['file_count']
        
        # TODO: Get team limits from team collection or config
        total_available = 10 * 1024 * 1024 * 1024 * 1024  # 10TB default for teams
        usage_percentage = (total_size / total_available) * 100 if total_available > 0 else 0
        
        return {
            "success": True,
            "team_uuid": team_uuid,
            "storage": {
                "total_used": _format_size(total_size),
                "total_used_bytes": total_size,
                "total_available": _format_size(total_available),
                "total_available_bytes": total_available,
                "usage_percentage": round(usage_percentage, 2),
                "datasets_count": datasets_count,
                "files_count": files_count
            },
            "breakdown": {
                "raw_data": _format_size(total_size),
                "processed_data": _format_size(0),  # TODO: Calculate
                "compressed_data": _format_size(0)   # TODO: Calculate
            },
            "billing": {
                "current_month_cost": "$125.00",  # TODO: Calculate from actual usage
                "projected_monthly_cost": "$157.50",
                "cost_per_gb": "$0.10"
            },
            "limits": {
                "max_dataset_size": "500 GB",
                "max_files_per_dataset": 5000,
                "max_datasets": 500
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get team storage: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5002)

