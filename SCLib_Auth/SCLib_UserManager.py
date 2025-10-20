#!/usr/bin/env python3
"""
SCLib User Manager
Handles user data and token storage in MongoDB for SCLib authentication.
Standalone system independent of Bokeh authorization.
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from pymongo import MongoClient
from pymongo.errors import PyMongoError, DuplicateKeyError
import logging

# Import SCLib configuration and MongoDB connection
try:
    from ..SCLib_JobProcessing.SCLib_Config import get_config
    from ..SCLib_JobProcessing.SCLib_MongoConnection import get_mongo_connection
except ImportError:
    # Fallback for standalone usage
    import sys
    from pathlib import Path
    # Add SCLib_JobProcessing to path for relative imports
    job_processing_dir = Path(__file__).parent.parent / 'SCLib_JobProcessing'
    sys.path.insert(0, str(job_processing_dir))
    from SCLib_Config import get_config
    from SCLib_MongoConnection import get_mongo_connection

logger = logging.getLogger(__name__)

@dataclass
class UserProfile:
    """User profile data structure."""
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    email_verified: bool = False
    created_at: datetime = None
    last_login: datetime = None
    last_activity: datetime = None
    is_active: bool = True
    
    # Auth0 integration
    auth0_user_id: Optional[str] = None
    auth0_metadata: Optional[Dict[str, Any]] = None
    
    # Token storage
    access_tokens: List[Dict[str, Any]] = None
    refresh_tokens: List[Dict[str, Any]] = None
    
    # User preferences and settings
    preferences: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.last_login is None:
            self.last_login = datetime.utcnow()
        if self.last_activity is None:
            self.last_activity = datetime.utcnow()
        if self.access_tokens is None:
            self.access_tokens = []
        if self.refresh_tokens is None:
            self.refresh_tokens = []
        if self.preferences is None:
            self.preferences = {}

@dataclass
class TokenRecord:
    """Token storage record."""
    token_id: str
    token_type: str  # 'access' or 'refresh'
    user_id: str
    email: str
    token_hash: str  # Hashed version for security
    created_at: datetime
    expires_at: datetime
    is_revoked: bool = False
    revoked_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

class SCLib_UserManager:
    """
    User manager for SCLib authentication.
    Handles user profiles and token storage in MongoDB.
    """
    
    def __init__(self, mongo_client: Optional[MongoClient] = None, db_name: Optional[str] = None):
        """
        Initialize the user manager.
        
        Args:
            mongo_client: MongoDB client (if None, will get from SCLib config)
            db_name: Database name (if None, will get from SCLib config)
        """
        if mongo_client is None or db_name is None:
            # Get configuration
            config = get_config()
            if mongo_client is None:
                mongo_client = get_mongo_connection()
            if db_name is None:
                db_name = config.database.db_name
        
        self.db = mongo_client[db_name]
        self.user_profile = self.db[config.collections.user_profile]
        
        # Create indexes for better performance
        self._create_indexes()
        
        logger.info(f"SCLib_UserManager initialized with database: {db_name}")
    
    def _create_indexes(self):
        """Create database indexes for optimal performance."""
        indexes = [
            [("user_id", 1)],  # Primary lookup
            [("email", 1)],    # Email lookup
            [("auth0_user_id", 1)],  # Auth0 integration
            [("is_active", 1), ("last_activity", -1)],  # Active users
            [("access_tokens.token_id", 1)],  # Token lookup
            [("refresh_tokens.token_id", 1)],  # Refresh token lookup
            [("access_tokens.expires_at", 1)],  # Token expiry cleanup
            [("refresh_tokens.expires_at", 1)]  # Refresh token expiry cleanup
        ]
        
        for index in indexes:
            try:
                self.user_profile.create_index(index)
            except PyMongoError as e:
                logger.warning(f"Could not create index {index}: {e}")
    
    async def create_or_update_user(self, user_info: 'UserInfo') -> UserProfile:
        """
        Create or update a user profile.
        
        Args:
            user_info: User information from Auth0 or other source
            
        Returns:
            UserProfile object
        """
        try:
            # Check if user exists
            existing_user = self.user_profile.find_one({"user_id": user_info.user_id})
            
            if existing_user:
                # Update existing user
                update_data = {
                    "email": user_info.email,
                    "name": user_info.name,
                    "picture": user_info.picture,
                    "email_verified": user_info.email_verified,
                    "last_login": datetime.utcnow(),
                    "last_activity": datetime.utcnow(),
                    "auth0_user_id": user_info.user_id,
                    "auth0_metadata": {
                        "last_auth0_sync": datetime.utcnow().isoformat()
                    }
                }
                
                result = self.user_profile.update_one(
                    {"user_id": user_info.user_id},
                    {"$set": update_data}
                )
                
                if result.modified_count > 0:
                    logger.info(f"Updated user profile: {user_info.email}")
                
                # Return updated user
                updated_user = self.user_profile.find_one({"user_id": user_info.user_id})
                return self._dict_to_user_profile(updated_user)
            else:
                # Create new user
                user_profile = UserProfile(
                    user_id=user_info.user_id,
                    email=user_info.email,
                    name=user_info.name,
                    picture=user_info.picture,
                    email_verified=user_info.email_verified,
                    auth0_user_id=user_info.user_id,
                    auth0_metadata={
                        "created_from_auth0": True,
                        "first_sync": datetime.utcnow().isoformat()
                    }
                )
                
                self.user_profile.insert_one(asdict(user_profile))
                logger.info(f"Created new user profile: {user_info.email}")
                return user_profile
                
        except DuplicateKeyError:
            # Handle race condition
            logger.warning(f"Duplicate user creation attempt: {user_info.email}")
            return await self.create_or_update_user(user_info)
        except Exception as e:
            logger.error(f"Failed to create/update user: {e}")
            raise
    
    async def get_user_by_id(self, user_id: str) -> Optional[UserProfile]:
        """
        Get user profile by user ID.
        
        Args:
            user_id: User's unique identifier
            
        Returns:
            UserProfile object or None if not found
        """
        try:
            user_data = self.user_profile.find_one({"user_id": user_id})
            if user_data:
                return self._dict_to_user_profile(user_data)
            return None
        except Exception as e:
            logger.error(f"Failed to get user by ID: {e}")
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[UserProfile]:
        """
        Get user profile by email.
        
        Args:
            email: User's email address
            
        Returns:
            UserProfile object or None if not found
        """
        try:
            user_data = self.user_profile.find_one({"email": email})
            if user_data:
                return self._dict_to_(user_data)
            return None
        except Exception as e:
            logger.error(f"Failed to get user by email: {e}")
            return None
    
    async def store_token(self, user_id: str, token: str, token_type: str = 'access', 
                         expires_at: Optional[datetime] = None) -> bool:
        """
        Store a token for a user.
        
        Args:
            user_id: User's unique identifier
            token: Token string
            token_type: Type of token ('access' or 'refresh')
            expires_at: Token expiration time
            
        Returns:
            True if successful
        """
        try:
            import hashlib
            
            # Create token record
            token_id = str(uuid.uuid4())
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            
            if expires_at is None:
                if token_type == 'access':
                    expires_at = datetime.utcnow() + timedelta(hours=24)
                else:
                    expires_at = datetime.utcnow() + timedelta(days=30)
            
            token_record = {
                "token_id": token_id,
                "token_type": token_type,
                "token_hash": token_hash,
                "created_at": datetime.utcnow(),
                "expires_at": expires_at,
                "is_revoked": False,
                "last_used": datetime.utcnow(),
                "metadata": {
                    "stored_at": datetime.utcnow().isoformat()
                }
            }
            
            # Add to user's token list
            field_name = f"{token_type}_tokens"
            result = self.user_profile.update_one(
                {"user_id": user_id},
                {
                    "$push": {field_name: token_record},
                    "$set": {"last_activity": datetime.utcnow()}
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Stored {token_type} token for user: {user_id}")
                return True
            else:
                logger.warning(f"Failed to store token for user: {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to store token: {e}")
            return False
    
    async def revoke_token(self, user_id: str, token_id: str, token_type: str = 'access') -> bool:
        """
        Revoke a token for a user.
        
        Args:
            user_id: User's unique identifier
            token_id: Token ID to revoke
            token_type: Type of token ('access' or 'refresh')
            
        Returns:
            True if successful
        """
        try:
            field_name = f"{token_type}_tokens"
            result = self.user_profile.update_one(
                {
                    "user_id": user_id,
                    f"{field_name}.token_id": token_id
                },
                {
                    "$set": {
                        f"{field_name}.$.is_revoked": True,
                        f"{field_name}.$.revoked_at": datetime.utcnow(),
                        "last_activity": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Revoked {token_type} token for user: {user_id}")
                return True
            else:
                logger.warning(f"Token not found for revocation: {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            return False
    
    async def revoke_all_tokens(self, user_id: str) -> bool:
        """
        Revoke all tokens for a user (logout from all devices).
        
        Args:
            user_id: User's unique identifier
            
        Returns:
            True if successful
        """
        try:
            now = datetime.utcnow()
            result = self.user_profile.update_one(
                {"user_id": user_id},
                {
                    "$set": {
                        "access_tokens.$[].is_revoked": True,
                        "access_tokens.$[].revoked_at": now,
                        "refresh_tokens.$[].is_revoked": True,
                        "refresh_tokens.$[].revoked_at": now,
                        "last_activity": now
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Revoked all tokens for user: {user_id}")
                return True
            else:
                logger.warning(f"User not found for token revocation: {user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to revoke all tokens: {e}")
            return False
    
    async def cleanup_expired_tokens(self) -> int:
        """
        Clean up expired tokens from all user profiles.
        
        Returns:
            Number of tokens cleaned up
        """
        try:
            now = datetime.utcnow()
            
            # Remove expired access tokens
            access_result = self.user_profile.update_many(
                {"access_tokens.expires_at": {"$lt": now}},
                {"$pull": {"access_tokens": {"expires_at": {"$lt": now}}}}
            )
            
            # Remove expired refresh tokens
            refresh_result = self.user_profile.update_many(
                {"refresh_tokens.expires_at": {"$lt": now}},
                {"$pull": {"refresh_tokens": {"expires_at": {"$lt": now}}}}
            )
            
            total_cleaned = access_result.modified_count + refresh_result.modified_count
            logger.info(f"Cleaned up expired tokens from {total_cleaned} user profiles")
            return total_cleaned
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired tokens: {e}")
            return 0
    
    async def update_user_activity(self, email: str) -> bool:
        """
        Update user's last activity timestamp.
        
        Args:
            email: User's email address
            
        Returns:
            True if successful
        """
        try:
            result = self.user_profile.update_one(
                {"email": email},
                {"$set": {"last_activity": datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update user activity: {e}")
            return False
    
    def _dict_to_user_profile(self, user_data: Dict[str, Any]) -> UserProfile:
        """Convert MongoDB document to UserProfile object."""
        # Remove MongoDB _id field
        user_data.pop('_id', None)
        
        # Convert datetime strings back to datetime objects if needed
        for field in ['created_at', 'last_login', 'last_activity']:
            if field in user_data and isinstance(user_data[field], str):
                user_data[field] = datetime.fromisoformat(user_data[field].replace('Z', '+00:00'))
        
        return UserProfile(**user_data)

# Global instance
_user_manager: Optional[SCLib_UserManager] = None

def get_user_manager() -> SCLib_UserManager:
    """Get the global user manager instance."""
    global _user_manager
    if _user_manager is None:
        _user_manager = SCLib_UserManager()
    return _user_manager

