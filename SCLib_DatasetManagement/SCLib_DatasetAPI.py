#!/usr/bin/env python3
"""
SCLib Dataset Management API
Enhanced dataset management with user-friendly identifiers and comprehensive operations.
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, status
from fastapi.responses import JSONResponse, FileResponse
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
    # In Docker, the Dockerfile copies SCLib_JobProcessing directly to /app (not /app/SCLib_JobProcessing)
    # So the files are at /app/SCLib_Config.py, not /app/SCLib_JobProcessing/SCLib_Config.py
    imported = False
    
    # First, try importing directly from /app (where Dockerfile copies the files)
    if Path('/app/SCLib_Config.py').exists() or Path('/app/start_fastapi_server.py').exists():
        # Files are at /app root, import directly
        if '/app' not in sys.path:
            sys.path.insert(0, '/app')
        try:
            from SCLib_Config import get_config, get_database_name, get_collection_name
            from SCLib_MongoConnection import mongo_collection_by_type_context
            from SCLib_UploadProcessor import get_upload_processor
            print(f"✅ SCLib_JobProcessing found at: /app (direct)")
            imported = True
        except ImportError:
            pass
    
    # If that didn't work, try as a package from various locations
    if not imported:
        possible_paths = [
            Path(__file__).parent.parent / 'SCLib_JobProcessing',  # Relative to scientistCloudLib
            Path('/app/scientistCloudLib/SCLib_JobProcessing'),  # Docker mount location
        ]
        
        # Also check SCLIB_CODE_HOME environment variable
        if os.getenv('SCLIB_CODE_HOME'):
            possible_paths.insert(0, Path(os.getenv('SCLIB_CODE_HOME')) / 'SCLib_JobProcessing')
        
        for job_path in possible_paths:
            if job_path and job_path.exists():
                job_parent = str(job_path.parent)
                if job_parent not in sys.path:
                    sys.path.insert(0, job_parent)
                try:
                    from SCLib_JobProcessing.SCLib_Config import get_config, get_database_name, get_collection_name
                    from SCLib_JobProcessing.SCLib_MongoConnection import mongo_collection_by_type_context
                    from SCLib_JobProcessing.SCLib_UploadProcessor import get_upload_processor
                    print(f"✅ SCLib_JobProcessing found at: {job_path}")
                    imported = True
                    break
                except ImportError:
                    continue
    
    if not imported:
        # Build a list of all paths we tried for better error message
        all_paths = ['/app (direct)'] + [str(p) for p in possible_paths]
        raise ImportError(f"Could not find SCLib_JobProcessing module. Tried paths: {all_paths}")

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

def _check_dataset_access(dataset: Dict[str, Any], user_email: str, require_download: bool = False) -> bool:
    """Check if user has access to dataset.
    
    Args:
        dataset: Dataset document
        user_email: User email to check
        require_download: If True, also check if download is allowed (for public datasets)
    
    Returns:
        True if user has access, False otherwise
    """
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
        # If download is required, also check is_public_downloadable
        if require_download:
            return dataset.get('is_public_downloadable', False)
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
    team: Optional[str] = None,  # Filter by team name (matches team_uuid)
    folder: Optional[str] = None,  # Filter by folder name (matches folder_uuid in metadata)
    public_only: Optional[bool] = None,
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
            elif team:
                # Filter by team name - team name is stored as team_uuid
                query['team_uuid'] = team
            if folder:
                # Filter by folder name - folder name is stored as folder_uuid in metadata
                # Check both metadata.folder_uuid and direct folder_uuid field
                query['$or'] = [
                    {'metadata.folder_uuid': folder},
                    {'folder_uuid': folder}
                ]
            if public_only:
                # Filter for public datasets
                query['is_public'] = True
            
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
            # Query teams where user is in emails array OR is the owner
            teams = list(teams_collection.find({
                '$or': [
                    {'emails': user_email},
                    {'owner': user_email}
                ]
            }))
            team_uuids = [team.get('uuid') for team in teams if team.get('uuid')]
            # Also get team names (some datasets use team name in team_uuid field)
            team_names = [team.get('team_name') for team in teams if team.get('team_name')]
        
        logger.debug(f"Found {len(teams)} team(s) for user {user_email}: UUIDs={team_uuids}, Names={team_names}")
        
        if team_uuids or team_names:
            team_dataset_uuids = set()
            
            # Method 1: Get datasets from shared_team collection
            if team_uuids or team_names:
                with mongo_collection_by_type_context('shared_team') as shared_team_collection:
                    # Build match conditions - check both team_uuid (UUID) and team (team name) fields
                    match_conditions = []
                    if team_uuids:
                        match_conditions.append({'team_uuid': {'$in': team_uuids}})
                    if team_names:
                        match_conditions.append({'team': {'$in': team_names}})
                    
                    if match_conditions:
                        team_pipeline = [
                            {'$match': {'$or': match_conditions}},
                            {'$lookup': {
                                'from': 'visstoredatas',
                                'localField': 'uuid',
                                'foreignField': 'uuid',
                                'as': 'sharing_data'
                            }}
                        ]
                        team_cursor = shared_team_collection.aggregate(team_pipeline)
                        for doc in team_cursor:
                            if doc.get('uuid'):
                                team_dataset_uuids.add(doc['uuid'])
            
            # Method 2: Get datasets that have team_uuid matching team UUIDs or team names
            # (datasets uploaded with team_uuid are stored directly in visstoredatas)
            with mongo_collection_by_type_context('visstoredatas') as collection:
                team_query = {}
                if team_uuids or team_names:
                    team_query_conditions = []
                    if team_uuids:
                        team_query_conditions.append({'team_uuid': {'$in': team_uuids}})
                    if team_names:
                        team_query_conditions.append({'team_uuid': {'$in': team_names}})
                    if team_query_conditions:
                        team_query = {'$or': team_query_conditions}
                        direct_team_datasets = list(collection.find(team_query))
                        for dataset in direct_team_datasets:
                            if dataset.get('uuid'):
                                team_dataset_uuids.add(dataset['uuid'])
            
            # Get all unique team datasets
            if team_dataset_uuids:
                with mongo_collection_by_type_context('visstoredatas') as collection:
                    team_datasets = list(collection.find({'uuid': {'$in': list(team_dataset_uuids)}}))
                    logger.debug(f"Found {len(team_datasets)} team dataset(s) for user {user_email}")
            else:
                logger.debug(f"No team datasets found for user {user_email} (team_uuids={team_uuids}, team_names={team_names})")
        
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
        # Set status to "conversion queued" so the background service picks it up
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": dataset_uuid},
                {
                    "$set": {
                        "status": "conversion queued",
                        "data_conversion_needed": True,
                        "updated_at": datetime.utcnow()
                    },
                    "$unset": {
                        "error_message": ""
                    }
                }
            )
        
        logger.info(f"Triggered conversion for dataset: {identifier} ({dataset_uuid})")
        
        return {
            "success": True,
            "message": "Dataset conversion triggered successfully",
            "status": "conversion queued",
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

def _should_exclude_file(filename: str, excluded_patterns: List[str] = None) -> bool:
    """Check if a file should be excluded based on patterns."""
    if excluded_patterns is None:
        excluded_patterns = ['.bin']  # Default excluded patterns
    
    import fnmatch
    filename_lower = filename.lower()
    
    for pattern in excluded_patterns:
        pattern_lower = pattern.lower()
        # Handle wildcard patterns
        if '*' in pattern_lower:
            if fnmatch.fnmatch(filename_lower, pattern_lower):
                return True
        else:
            # Handle extension patterns
            normalized_pattern = pattern_lower if pattern_lower.startswith('.') else f'.{pattern_lower}'
            if filename_lower.endswith(normalized_pattern):
                return True
    
    return False

def _scan_directory_tree(directory: Path, base_path: str = '', excluded_patterns: List[str] = None) -> List[Dict]:
    """Recursively scan directory and return hierarchical file structure.
    
    Directories are always included (even if they only contain excluded files),
    but excluded files (like .bin) are hidden from the listing.
    """
    result = []
    
    if not directory.exists() or not directory.is_dir():
        return result
    
    try:
        items = sorted(directory.iterdir(), key=lambda x: (x.is_file(), x.name))
    except PermissionError:
        logger.warning(f"Permission denied accessing directory: {directory}")
        return result
    
    # Track if directory has excluded files (for UI indication)
    excluded_file_count = 0
    visible_file_count = 0
    
    for item in items:
        if item.name.startswith('.'):
            continue
        
        relative_path = f"{base_path}/{item.name}" if base_path else item.name
        
        if item.is_dir():
            # Recursively scan subdirectory
            children = _scan_directory_tree(item, relative_path, excluded_patterns)
            
            # Count excluded files in this directory (only direct files, not in subdirectories)
            dir_excluded_count = 0
            try:
                for child_item in item.iterdir():
                    if child_item.is_file() and not child_item.name.startswith('.'):
                        if _should_exclude_file(child_item.name, excluded_patterns):
                            dir_excluded_count += 1
            except (OSError, PermissionError):
                pass  # Ignore permission errors when counting
            
            # Always include directory, even if it only has excluded files
            # This ensures users can see directories that contain .bin files
            dir_info = {
                'name': item.name,
                'type': 'directory',
                'path': relative_path,
                'children': children
            }
            
            # Add metadata if directory has excluded files
            if dir_excluded_count > 0:
                dir_info['has_excluded_files'] = True
                dir_info['excluded_file_count'] = dir_excluded_count
            
            result.append(dir_info)
        elif item.is_file():
            # Check if file should be excluded
            if _should_exclude_file(item.name, excluded_patterns):
                excluded_file_count += 1
                continue
            
            visible_file_count += 1
            try:
                stat = item.stat()
                result.append({
                    'name': item.name,
                    'type': 'file',
                    'path': relative_path,
                    'size': stat.st_size,
                    'modified': stat.st_mtime
                })
            except (OSError, PermissionError) as e:
                logger.warning(f"Error accessing file {item}: {e}")
                continue
    
    # If this directory has excluded files but no visible children, add metadata
    # This helps indicate to users that the directory contains hidden files
    if excluded_file_count > 0 and visible_file_count == 0 and len(result) == 0:
        # This case is handled by parent directory adding has_excluded_files
        pass
    
    # Sort: directories first, then files, both alphabetically
    result.sort(key=lambda x: (x['type'] != 'directory', x['name'].lower()))
    
    return result

@app.get("/api/v1/datasets/{identifier}/files")
async def list_dataset_files(
    identifier: str,
    user_email: Optional[str] = None,
    processor: Any = Depends(get_processor)
):
    """List files in a dataset with hierarchical structure.
    
    Returns files from both upload and converted directories in a tree structure.
    """
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
        
        # Get directory paths from config
        config = get_config()
        upload_dir = config.job_processing.in_data_dir if hasattr(config, 'job_processing') else f"{config.server.visus_datasets}/upload"
        converted_dir = config.job_processing.out_data_dir if hasattr(config, 'job_processing') else f"{config.server.visus_datasets}/converted"
        
        upload_path = Path(upload_dir) / dataset_uuid
        converted_path = Path(converted_dir) / dataset_uuid
        
        # Excluded file patterns (default to .bin files)
        excluded_patterns = getattr(config, 'excluded_file_patterns', ['.bin']) if hasattr(config, 'excluded_file_patterns') else ['.bin']
        
        # Scan both directories (base_path is empty string so paths are relative to dataset directory)
        upload_files = _scan_directory_tree(upload_path, '', excluded_patterns)
        converted_files = _scan_directory_tree(converted_path, '', excluded_patterns)
        
        return {
            "success": True,
            "dataset_uuid": dataset_uuid,
            "directories": {
                "upload": {
                    "path": str(upload_path),
                    "exists": upload_path.exists(),
                    "readable": upload_path.exists() and os.access(upload_path, os.R_OK),
                    "files": upload_files,
                    "file_count": len(upload_files)
                },
                "converted": {
                    "path": str(converted_path),
                    "exists": converted_path.exists(),
                    "readable": converted_path.exists() and os.access(converted_path, os.R_OK),
                    "files": converted_files,
                    "file_count": len(converted_files)
                }
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/datasets/{identifier}/file-content")
async def get_file_content(
    identifier: str,
    file_path: str,
    directory: str,  # 'upload' or 'converted'
    user_email: Optional[EmailStr] = None,
    processor: Any = Depends(get_processor)
):
    """Get file content for text files or image URL for image files.
    
    Returns:
    - For text files: {"content": "...", "type": "text", "mime_type": "..."}
    - For image files: {"url": "...", "type": "image", "mime_type": "..."}
    """
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
        
        # Validate directory
        if directory not in ['upload', 'converted']:
            raise HTTPException(status_code=400, detail="Directory must be 'upload' or 'converted'")
        
        # Get directory paths from config
        config = get_config()
        base_dir = config.job_processing.in_data_dir if directory == 'upload' else config.job_processing.out_data_dir
        if not base_dir:
            base_dir = f"{config.server.visus_datasets}/{directory}"
        
        # Build full file path
        full_path = Path(base_dir) / dataset_uuid / file_path
        
        # Security: Ensure file is within the dataset directory (prevent path traversal)
        dataset_dir = Path(base_dir) / dataset_uuid
        try:
            full_path.resolve().relative_to(dataset_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Invalid file path")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if not full_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")
        
        # Determine file type
        file_ext = full_path.suffix.lower()
        
        # Text file extensions
        text_extensions = {'.txt', '.json', '.idx', '.log', '.xml', '.csv', '.md', '.yaml', '.yml', '.ini', '.conf', '.cfg'}
        # Image file extensions
        image_extensions = {'.tiff', '.tif', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'}
        
        # Get MIME type
        if file_ext in text_extensions:
            mime_type = {
                '.txt': 'text/plain',
                '.json': 'application/json',
                '.idx': 'text/plain',
                '.log': 'text/plain',
                '.xml': 'application/xml',
                '.csv': 'text/csv',
                '.md': 'text/markdown',
                '.yaml': 'text/yaml',
                '.yml': 'text/yaml',
                '.ini': 'text/plain',
                '.conf': 'text/plain',
                '.cfg': 'text/plain'
            }.get(file_ext, 'text/plain')
            
            # Read text file content
            try:
                with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                
                return {
                    "success": True,
                    "type": "text",
                    "mime_type": mime_type,
                    "content": content,
                    "file_path": file_path,
                    "file_name": full_path.name
                }
            except Exception as e:
                logger.error(f"Failed to read text file: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")
        
        elif file_ext in image_extensions:
            mime_type = {
                '.tiff': 'image/tiff',
                '.tif': 'image/tiff',
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.bmp': 'image/bmp',
                '.webp': 'image/webp',
                '.svg': 'image/svg+xml'
            }.get(file_ext, 'image/jpeg')
            
            # For images, return a URL that can be used to serve the file
            # In production, you might want to use a proper file serving endpoint
            # For now, we'll return a path that the PHP proxy can serve
            file_url = f"/api/dataset-file-serve.php?dataset_uuid={dataset_uuid}&file_path={file_path}&directory={directory}"
            
            return {
                "success": True,
                "type": "image",
                "mime_type": mime_type,
                "url": file_url,
                "file_path": file_path,
                "file_name": full_path.name
            }
        
        else:
            raise HTTPException(status_code=400, detail=f"File type not supported: {file_ext}")
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/datasets/{identifier}/file-serve")
async def serve_file(
    identifier: str,
    file_path: str,
    directory: str,  # 'upload' or 'converted'
    user_email: Optional[EmailStr] = None,
    processor: Any = Depends(get_processor)
):
    """Serve image files directly."""
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
        
        # Validate directory
        if directory not in ['upload', 'converted']:
            raise HTTPException(status_code=400, detail="Directory must be 'upload' or 'converted'")
        
        # Get directory paths from config
        config = get_config()
        base_dir = config.job_processing.in_data_dir if directory == 'upload' else config.job_processing.out_data_dir
        if not base_dir:
            base_dir = f"{config.server.visus_datasets}/{directory}"
        
        # Build full file path
        full_path = Path(base_dir) / dataset_uuid / file_path
        
        # Security: Ensure file is within the dataset directory
        dataset_dir = Path(base_dir) / dataset_uuid
        try:
            full_path.resolve().relative_to(dataset_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=403, detail="Invalid file path")
        
        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Determine MIME type
        file_ext = full_path.suffix.lower()
        mime_types = {
            '.tiff': 'image/tiff',
            '.tif': 'image/tiff',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml'
        }
        media_type = mime_types.get(file_ext, 'application/octet-stream')
        
        return FileResponse(
            path=str(full_path),
            media_type=media_type,
            filename=full_path.name
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Import zip service after other imports are resolved
try:
    from SCLib_DatasetManagement.SCLib_ZipService import get_zip_service
except ImportError:
    try:
        from .SCLib_ZipService import get_zip_service
    except ImportError:
        # Fallback: try direct import
        import sys
        from pathlib import Path
        zip_service_path = Path(__file__).parent / 'SCLib_ZipService.py'
        if zip_service_path.exists():
            import importlib.util
            spec = importlib.util.spec_from_file_location("SCLib_ZipService", zip_service_path)
            zip_service_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(zip_service_module)
            get_zip_service = zip_service_module.get_zip_service
        else:
            raise ImportError("Could not import SCLib_ZipService")

@app.get("/api/v1/datasets/{identifier}/download-zip")
async def download_dataset_zip(
    identifier: str,
    directory: str,  # 'upload' or 'converted'
    user_email: Optional[EmailStr] = None,
    force_recreate: bool = False,
    processor: Any = Depends(get_processor)
):
    """Download a dataset directory as a zip file.
    
    Args:
        identifier: Dataset identifier (UUID, name, slug, or ID)
        directory: 'upload' or 'converted'
        user_email: User email for access control
        force_recreate: If True, recreate zip even if cached
        
    Returns:
        Zip file download
    """
    try:
        # Resolve identifier to UUID
        dataset_uuid = _resolve_dataset_identifier(identifier)
        
        # Get dataset
        dataset = _get_dataset_by_uuid(dataset_uuid)
        
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {identifier}")
        
        # Validate directory
        if directory not in ['upload', 'converted']:
            raise HTTPException(status_code=400, detail="Directory must be 'upload' or 'converted'")
        
        # Check access - allow public users if dataset is public and downloadable
        if user_email:
            if not _check_dataset_access(dataset, user_email):
                # Check if public and downloadable
                if not dataset.get('is_public', False):
                    raise HTTPException(status_code=403, detail="Access denied")
                if not dataset.get('is_public_downloadable', False):
                    raise HTTPException(status_code=403, detail="Dataset is public but not downloadable")
        else:
            # No user email - check if public and downloadable
            if not dataset.get('is_public', False) or not dataset.get('is_public_downloadable', False):
                raise HTTPException(status_code=403, detail="Access denied")
        
        # Get zip service
        zip_service = get_zip_service()
        
        # Create or get cached zip
        zip_path = zip_service.create_or_get_zip(dataset_uuid, directory, force_recreate=force_recreate)
        
        if not os.path.exists(zip_path):
            raise HTTPException(status_code=500, detail="Failed to create zip file")
        
        # Generate filename
        dataset_name = dataset.get('name', dataset_uuid)
        safe_name = re.sub(r'[^\w\s-]', '', dataset_name).strip()
        safe_name = re.sub(r'[-\s]+', '-', safe_name)
        zip_filename = f"{safe_name}_{directory}.zip"
        
        return FileResponse(
            path=zip_path,
            media_type='application/zip',
            filename=zip_filename,
            headers={
                'Content-Disposition': f'attachment; filename="{zip_filename}"'
            }
        )
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Dataset directory not found: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create zip file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create zip file: {str(e)}")

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
            'sensor', 'dimensions', 'preferred_dashboard', 'is_public', 'data_conversion_needed',
            'status'  # Allow status updates for retry operations
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

