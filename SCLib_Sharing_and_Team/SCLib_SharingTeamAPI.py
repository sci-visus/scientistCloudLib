#!/usr/bin/env python3
"""
SCLib Sharing and Team Management API
Handles team creation and dataset sharing with users and teams.
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, Dict, Any, List
import uuid
import os
import logging
from datetime import datetime
from pathlib import Path

try:
    from ..SCLib_JobProcessing.SCLib_Config import get_config, get_database_name, get_collection_name
    from ..SCLib_JobProcessing.SCLib_MongoConnection import mongo_collection_by_type_context
except ImportError:
    import sys
    from pathlib import Path
    import os
    
    # Try multiple paths for SCLib_JobProcessing
    imported = False
    
    # First, try importing directly from /app (where Dockerfile copies the files)
    if Path('/app/SCLib_Config.py').exists() or Path('/app/start_fastapi_server.py').exists():
        if '/app' not in sys.path:
            sys.path.insert(0, '/app')
        try:
            from SCLib_Config import get_config, get_database_name, get_collection_name
            from SCLib_MongoConnection import mongo_collection_by_type_context
            print(f"✅ SCLib_JobProcessing found at: /app (direct)")
            imported = True
        except ImportError:
            pass
    
    # If that didn't work, try as a package from various locations
    if not imported:
        possible_paths = [
            Path(__file__).parent.parent / 'SCLib_JobProcessing',
            Path('/app/scientistCloudLib/SCLib_JobProcessing'),
        ]
        
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
                    print(f"✅ SCLib_JobProcessing found at: {job_path}")
                    imported = True
                    break
                except ImportError:
                    continue
    
    if not imported:
        all_paths = ['/app (direct)'] + [str(p) for p in possible_paths]
        raise ImportError(f"Could not find SCLib_JobProcessing module. Tried paths: {all_paths}")

# Get logger
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="SCLib Sharing and Team Management API",
    description="Team creation and dataset sharing with users and teams",
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
class TeamCreateRequest(BaseModel):
    """Request model for creating a team."""
    team_name: str = Field(..., min_length=1, max_length=255, description="Team name")
    emails: List[EmailStr] = Field(..., min_items=1, description="List of member email addresses")
    parents: Optional[List[str]] = Field(None, description="List of parent team UUIDs")
    owner: Optional[EmailStr] = Field(None, description="Team owner email (defaults to creator)")

class TeamUpdateRequest(BaseModel):
    """Request model for updating a team."""
    team_name: Optional[str] = Field(None, min_length=1, max_length=255)
    emails: Optional[List[EmailStr]] = None
    parents: Optional[List[str]] = None

class ShareDatasetWithUserRequest(BaseModel):
    """Request model for sharing a dataset with a user."""
    dataset_uuid: str = Field(..., description="Dataset UUID")
    user_email: EmailStr = Field(..., description="Email of user to share with")
    google_drive_link: Optional[str] = Field(None, description="Google Drive link if dataset is stored externally")

class ShareDatasetWithTeamRequest(BaseModel):
    """Request model for sharing a dataset with a team."""
    dataset_uuid: str = Field(..., description="Dataset UUID")
    team_name: str = Field(..., description="Team name (string, not UUID)")
    team_uuid: Optional[str] = Field(None, description="Team UUID (optional, will be looked up if not provided)")
    google_drive_link: Optional[str] = Field(None, description="Google Drive link if dataset is stored externally")

class UnshareDatasetRequest(BaseModel):
    """Request model for unsharing a dataset."""
    dataset_uuid: str = Field(..., description="Dataset UUID")
    user_email: Optional[EmailStr] = Field(None, description="User email to unshare from (for user sharing)")
    team_name: Optional[str] = Field(None, description="Team name to unshare from (for team sharing)")

# Helper Functions
def _get_team_by_uuid(team_uuid: str) -> Optional[Dict[str, Any]]:
    """Get team by UUID."""
    with mongo_collection_by_type_context('teams') as collection:
        team = collection.find_one({"uuid": team_uuid})
        if team and '_id' in team:
            team['_id'] = str(team['_id'])
        return team

def _get_team_by_name(team_name: str) -> Optional[Dict[str, Any]]:
    """Get team by name."""
    with mongo_collection_by_type_context('teams') as collection:
        team = collection.find_one({"team_name": team_name})
        if team and '_id' in team:
            team['_id'] = str(team['_id'])
        return team

def _get_dataset_by_uuid(dataset_uuid: str) -> Optional[Dict[str, Any]]:
    """Get dataset by UUID."""
    with mongo_collection_by_type_context('visstoredatas') as collection:
        dataset = collection.find_one({"uuid": dataset_uuid})
        if dataset and '_id' in dataset:
            dataset['_id'] = str(dataset['_id'])
        return dataset

def _check_team_ownership(team: Dict[str, Any], user_email: str) -> bool:
    """Check if user owns the team."""
    return team.get('owner') == user_email

def _check_team_membership(team: Dict[str, Any], user_email: str) -> bool:
    """Check if user is a member of the team."""
    emails = team.get('emails', [])
    return user_email in emails

# API Endpoints

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "SCLib Sharing and Team Management API",
        "version": "1.0.0",
        "endpoints": {
            "create_team": "POST /api/v1/teams",
            "get_team": "GET /api/v1/teams/{team_uuid}",
            "update_team": "PUT /api/v1/teams/{team_uuid}",
            "list_user_teams": "GET /api/v1/teams/by-user?user_email={email}",
            "share_with_user": "POST /api/v1/share/user",
            "share_with_team": "POST /api/v1/share/team",
            "unshare_dataset": "POST /api/v1/share/unshare",
            "list_shared_datasets": "GET /api/v1/share/user/{user_email}",
            "list_team_datasets": "GET /api/v1/share/team/{team_name}"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "SCLib_SharingTeam"}

# Team Management Endpoints

@app.post("/api/v1/teams")
async def create_team(
    request: TeamCreateRequest,
    owner_email: EmailStr
):
    """Create a new team."""
    try:
        # Generate team UUID
        team_uuid = str(uuid.uuid4())
        
        # Ensure owner is in emails list
        emails = list(set(request.emails))  # Remove duplicates
        if owner_email not in emails:
            emails.insert(0, owner_email)  # Add owner at the beginning
        
        # Create team document
        team_doc = {
            "uuid": team_uuid,
            "team_name": request.team_name,
            "parents": request.parents or [],
            "owner": owner_email,
            "emails": emails,
            "created_at": datetime.utcnow()
        }
        
        # Check if team name already exists
        existing_team = _get_team_by_name(request.team_name)
        if existing_team:
            raise HTTPException(
                status_code=400,
                detail=f"Team with name '{request.team_name}' already exists"
            )
        
        # Insert into database
        with mongo_collection_by_type_context('teams') as collection:
            collection.insert_one(team_doc)
        
        logger.info(f"Created team: {request.team_name} ({team_uuid}) by {owner_email}")
        
        return {
            "success": True,
            "message": "Team created successfully",
            "team": {
                "uuid": team_uuid,
                "team_name": request.team_name,
                "owner": owner_email,
                "emails": emails,
                "created_at": team_doc["created_at"].isoformat() if isinstance(team_doc["created_at"], datetime) else str(team_doc["created_at"])
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create team: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/teams/{team_uuid}")
async def get_team(
    team_uuid: str,
    user_email: Optional[EmailStr] = None
):
    """Get team information."""
    try:
        team = _get_team_by_uuid(team_uuid)
        
        if not team:
            raise HTTPException(status_code=404, detail=f"Team not found: {team_uuid}")
        
        # Check access if user_email provided
        if user_email:
            if not _check_team_membership(team, user_email) and not _check_team_ownership(team, user_email):
                raise HTTPException(status_code=403, detail="Access denied")
        
        # Format response
        return {
            "success": True,
            "team": {
                "uuid": team.get("uuid"),
                "team_name": team.get("team_name"),
                "owner": team.get("owner"),
                "emails": team.get("emails", []),
                "parents": team.get("parents", []),
                "created_at": team.get("created_at")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get team: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/teams/{team_uuid}")
async def update_team(
    team_uuid: str,
    request: TeamUpdateRequest,
    user_email: EmailStr
):
    """Update team information (only owner can update)."""
    try:
        team = _get_team_by_uuid(team_uuid)
        
        if not team:
            raise HTTPException(status_code=404, detail=f"Team not found: {team_uuid}")
        
        # Check ownership
        if not _check_team_ownership(team, user_email):
            raise HTTPException(status_code=403, detail="Only team owner can update team")
        
        # Prepare update data
        update_data = {}
        
        if request.team_name:
            # Check if new name already exists
            existing_team = _get_team_by_name(request.team_name)
            if existing_team and existing_team.get('uuid') != team_uuid:
                raise HTTPException(
                    status_code=400,
                    detail=f"Team with name '{request.team_name}' already exists"
                )
            update_data["team_name"] = request.team_name
        
        if request.emails is not None:
            # Ensure owner is in emails list
            emails = list(set(request.emails))
            if user_email not in emails:
                emails.insert(0, user_email)
            update_data["emails"] = emails
        
        if request.parents is not None:
            update_data["parents"] = request.parents
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Update in database
        with mongo_collection_by_type_context('teams') as collection:
            collection.update_one(
                {"uuid": team_uuid},
                {"$set": update_data}
            )
        
        # Get updated team
        updated_team = _get_team_by_uuid(team_uuid)
        
        logger.info(f"Updated team: {team_uuid} by {user_email}")
        
        return {
            "success": True,
            "message": "Team updated successfully",
            "team": {
                "uuid": updated_team.get("uuid"),
                "team_name": updated_team.get("team_name"),
                "owner": updated_team.get("owner"),
                "emails": updated_team.get("emails", []),
                "parents": updated_team.get("parents", [])
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update team: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/teams/by-user")
async def list_user_teams(
    user_email: EmailStr
):
    """Get all teams for a user (owned or member of)."""
    try:
        # Normalize email to lowercase for consistent matching
        user_email_lower = user_email.lower().strip()
        
        with mongo_collection_by_type_context('teams') as collection:
            # Get all teams and filter in Python for case-insensitive matching
            # This ensures we catch all teams regardless of email case variations
            all_teams = list(collection.find({}))
            
            matched_teams = []
            for team in all_teams:
                # Normalize owner email for comparison
                owner = team.get("owner", "")
                if isinstance(owner, str):
                    owner_lower = owner.lower().strip()
                else:
                    owner_lower = str(owner).lower().strip()
                
                # Normalize emails array for comparison
                emails = team.get("emails", [])
                emails_lower = []
                for email in emails:
                    if isinstance(email, str):
                        emails_lower.append(email.lower().strip())
                    else:
                        emails_lower.append(str(email).lower().strip())
                
                # Check if user is owner or in emails array (case-insensitive)
                if owner_lower == user_email_lower or user_email_lower in emails_lower:
                    matched_teams.append(team)
        
        # Format teams
        formatted_teams = []
        for team in matched_teams:
            if '_id' in team:
                team['_id'] = str(team['_id'])
            
            # Determine if user is owner (case-insensitive)
            owner = team.get("owner", "")
            owner_lower = owner.lower().strip() if isinstance(owner, str) else str(owner).lower().strip()
            is_owner = owner_lower == user_email_lower
            
            formatted_teams.append({
                "uuid": team.get("uuid"),
                "team_name": team.get("team_name"),
                "owner": team.get("owner"),
                "emails": team.get("emails", []),
                "parents": team.get("parents", []),
                "created_at": team.get("created_at"),
                "is_owner": is_owner
            })
        
        logger.info(f"Found {len(formatted_teams)} team(s) for user {user_email_lower} (normalized from {user_email})")
        
        return {
            "success": True,
            "teams": formatted_teams,
            "count": len(formatted_teams)
        }
        
    except Exception as e:
        logger.error(f"Failed to list user teams: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Sharing Endpoints

@app.post("/api/v1/share/user")
async def share_dataset_with_user(
    request: ShareDatasetWithUserRequest,
    owner_email: EmailStr
):
    """Share a dataset with a user by email."""
    try:
        # Verify dataset exists
        dataset = _get_dataset_by_uuid(request.dataset_uuid)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {request.dataset_uuid}")
        
        # Check if owner has permission (must be dataset owner)
        if dataset.get('user') != owner_email and dataset.get('user_email') != owner_email:
            raise HTTPException(status_code=403, detail="Only dataset owner can share the dataset")
        
        # Check if already shared
        with mongo_collection_by_type_context('shared_user') as collection:
            existing = collection.find_one({
                "uuid": request.dataset_uuid,
                "user": request.user_email
            })
            
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Dataset already shared with {request.user_email}"
                )
            
            # Create sharing document
            share_doc = {
                "uuid": request.dataset_uuid,
                "user": request.user_email,
                "user_uuid": str(uuid.uuid4()),  # Generate user_uuid
                "google_drive_link": request.google_drive_link or dataset.get('google_drive_link', '')
            }
            
            collection.insert_one(share_doc)
        
        logger.info(f"Shared dataset {request.dataset_uuid} with user {request.user_email} by {owner_email}")
        
        return {
            "success": True,
            "message": f"Dataset shared with {request.user_email}",
            "share": {
                "dataset_uuid": request.dataset_uuid,
                "user_email": request.user_email,
                "google_drive_link": share_doc["google_drive_link"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to share dataset with user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/share/team")
async def share_dataset_with_team(
    request: ShareDatasetWithTeamRequest,
    owner_email: EmailStr
):
    """Share a dataset with a team."""
    try:
        # Verify dataset exists
        dataset = _get_dataset_by_uuid(request.dataset_uuid)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {request.dataset_uuid}")
        
        # Check if owner has permission (must be dataset owner)
        if dataset.get('user') != owner_email and dataset.get('user_email') != owner_email:
            raise HTTPException(status_code=403, detail="Only dataset owner can share the dataset")
        
        # Get team (by UUID if provided, otherwise by name)
        team = None
        if request.team_uuid:
            team = _get_team_by_uuid(request.team_uuid)
        else:
            team = _get_team_by_name(request.team_name)
        
        if not team:
            raise HTTPException(
                status_code=404,
                detail=f"Team not found: {request.team_name or request.team_uuid}"
            )
        
        # Verify team_name matches
        if team.get('team_name') != request.team_name:
            raise HTTPException(
                status_code=400,
                detail=f"Team name mismatch: expected {team.get('team_name')}, got {request.team_name}"
            )
        
        # Check if already shared
        with mongo_collection_by_type_context('shared_team') as collection:
            existing = collection.find_one({
                "uuid": request.dataset_uuid,
                "team": request.team_name
            })
            
            if existing:
                raise HTTPException(
                    status_code=400,
                    detail=f"Dataset already shared with team {request.team_name}"
                )
            
            # Create sharing document
            share_doc = {
                "uuid": request.dataset_uuid,
                "team": request.team_name,  # Store team name (string)
                "team_uuid": team.get("uuid"),  # Store team UUID
                "google_drive_link": request.google_drive_link or dataset.get('google_drive_link', '')
            }
            
            collection.insert_one(share_doc)
        
        # Also update dataset's team_uuid field (this stores the team name, not UUID)
        with mongo_collection_by_type_context('visstoredatas') as collection:
            collection.update_one(
                {"uuid": request.dataset_uuid},
                {"$set": {"team_uuid": request.team_name}}
            )
        
        logger.info(f"Shared dataset {request.dataset_uuid} with team {request.team_name} by {owner_email}")
        
        return {
            "success": True,
            "message": f"Dataset shared with team {request.team_name}",
            "share": {
                "dataset_uuid": request.dataset_uuid,
                "team_name": request.team_name,
                "team_uuid": team.get("uuid"),
                "google_drive_link": share_doc["google_drive_link"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to share dataset with team: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/share/unshare")
async def unshare_dataset(
    request: UnshareDatasetRequest,
    owner_email: EmailStr
):
    """Unshare a dataset from a user or team."""
    try:
        # Verify dataset exists
        dataset = _get_dataset_by_uuid(request.dataset_uuid)
        if not dataset:
            raise HTTPException(status_code=404, detail=f"Dataset not found: {request.dataset_uuid}")
        
        # Check if owner has permission
        if dataset.get('user') != owner_email and dataset.get('user_email') != owner_email:
            raise HTTPException(status_code=403, detail="Only dataset owner can unshare the dataset")
        
        if request.user_email:
            # Unshare from user
            with mongo_collection_by_type_context('shared_user') as collection:
                result = collection.delete_one({
                    "uuid": request.dataset_uuid,
                    "user": request.user_email
                })
                
                if result.deleted_count == 0:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Dataset not shared with {request.user_email}"
                    )
            
            logger.info(f"Unshared dataset {request.dataset_uuid} from user {request.user_email} by {owner_email}")
            
            return {
                "success": True,
                "message": f"Dataset unshared from {request.user_email}"
            }
        
        elif request.team_name:
            # Unshare from team
            with mongo_collection_by_type_context('shared_team') as collection:
                result = collection.delete_one({
                    "uuid": request.dataset_uuid,
                    "team": request.team_name
                })
                
                if result.deleted_count == 0:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Dataset not shared with team {request.team_name}"
                    )
            
            logger.info(f"Unshared dataset {request.dataset_uuid} from team {request.team_name} by {owner_email}")
            
            return {
                "success": True,
                "message": f"Dataset unshared from team {request.team_name}"
            }
        
        else:
            raise HTTPException(
                status_code=400,
                detail="Either user_email or team_name must be provided"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unshare dataset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/share/user/{user_email}")
async def list_shared_datasets_for_user(
    user_email: EmailStr
):
    """Get all datasets shared with a user."""
    try:
        with mongo_collection_by_type_context('shared_user') as collection:
            shared_docs = list(collection.find({"user": user_email}))
        
        dataset_uuids = [doc.get("uuid") for doc in shared_docs if doc.get("uuid")]
        
        datasets = []
        if dataset_uuids:
            with mongo_collection_by_type_context('visstoredatas') as collection:
                datasets = list(collection.find({"uuid": {"$in": dataset_uuids}}))
        
        # Format datasets
        formatted_datasets = []
        for dataset in datasets:
            if '_id' in dataset:
                dataset['_id'] = str(dataset['_id'])
            
            formatted_datasets.append({
                "uuid": dataset.get("uuid"),
                "name": dataset.get("name"),
                "sensor": dataset.get("sensor"),
                "status": dataset.get("status"),
                "data_size": dataset.get("data_size"),
                "created_at": dataset.get("date_imported") or dataset.get("time")
            })
        
        return {
            "success": True,
            "user_email": user_email,
            "datasets": formatted_datasets,
            "count": len(formatted_datasets)
        }
        
    except Exception as e:
        logger.error(f"Failed to list shared datasets for user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/share/team/{team_name}")
async def list_team_datasets(
    team_name: str
):
    """Get all datasets shared with a team."""
    try:
        with mongo_collection_by_type_context('shared_team') as collection:
            shared_docs = list(collection.find({"team": team_name}))
        
        dataset_uuids = [doc.get("uuid") for doc in shared_docs if doc.get("uuid")]
        
        datasets = []
        if dataset_uuids:
            with mongo_collection_by_type_context('visstoredatas') as collection:
                datasets = list(collection.find({"uuid": {"$in": dataset_uuids}}))
        
        # Format datasets
        formatted_datasets = []
        for dataset in datasets:
            if '_id' in dataset:
                dataset['_id'] = str(dataset['_id'])
            
            formatted_datasets.append({
                "uuid": dataset.get("uuid"),
                "name": dataset.get("name"),
                "sensor": dataset.get("sensor"),
                "status": dataset.get("status"),
                "data_size": dataset.get("data_size"),
                "created_at": dataset.get("date_imported") or dataset.get("time")
            })
        
        return {
            "success": True,
            "team_name": team_name,
            "datasets": formatted_datasets,
            "count": len(formatted_datasets)
        }
        
    except Exception as e:
        logger.error(f"Failed to list team datasets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5003)

