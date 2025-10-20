#!/usr/bin/env python3
"""
SCLib Authentication Middleware
FastAPI middleware and dependencies for token-based authorization.
Integrates SCLib_Auth with job processing and other SCLib components.
"""

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any, List
import logging
import os
from datetime import datetime

# Import SCLib_Auth components
try:
    from .SCLib_JWTManager import SCLib_JWTManager, get_jwt_manager
    from .SCLib_UserManager import SCLib_UserManager, get_user_manager, UserProfile
except ImportError:
    # Fallback for standalone usage
    import sys
    from pathlib import Path
    # Add current directory to path for relative imports
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    from SCLib_JWTManager import SCLib_JWTManager, get_jwt_manager
    from SCLib_UserManager import SCLib_UserManager, get_user_manager, UserProfile

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)

class AuthResult:
    """Result of authentication check."""
    def __init__(self, is_authenticated: bool, user_email: Optional[str] = None, 
                 user_id: Optional[str] = None, user_profile: Optional[UserProfile] = None,
                 access_type: str = 'none', error: Optional[str] = None):
        self.is_authenticated = is_authenticated
        self.user_email = user_email
        self.user_id = user_id
        self.user_profile = user_profile
        self.access_type = access_type
        self.error = error

class SCLib_AuthMiddleware:
    """
    Authentication middleware for SCLib components.
    Provides token validation and user authentication for FastAPI endpoints.
    """
    
    def __init__(self, jwt_manager: Optional[SCLib_JWTManager] = None, 
                 user_manager: Optional[SCLib_UserManager] = None):
        """
        Initialize the authentication middleware.
        
        Args:
            jwt_manager: JWT manager instance (if None, will get global instance)
            user_manager: User manager instance (if None, will get global instance)
        """
        self.jwt_manager = jwt_manager or get_jwt_manager()
        self.user_manager = user_manager or get_user_manager()
        
        logger.info("SCLib_AuthMiddleware initialized")
    
    def extract_token_from_request(self, request: Request) -> Optional[str]:
        """
        Extract JWT token from request headers or cookies.
        
        Args:
            request: FastAPI request object
            
        Returns:
            JWT token string or None if not found
        """
        # Try Authorization header first
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header[7:]  # Remove "Bearer " prefix
        
        # Try cookies as fallback (for web portal integration)
        cookies = request.cookies
        possible_cookies = [
            'auth_token',
            'auth0_session_0',
            'auth0_session',
            'auth0.is.authenticated',
            'auth0_session_1',
            'auth0_session_2'
        ]
        
        for cookie_name in possible_cookies:
            if cookie_name in cookies:
                token = cookies[cookie_name]
                logger.debug(f"Found token in cookie: {cookie_name}")
                return token
        
        return None
    
    async def authenticate_request(self, request: Request) -> AuthResult:
        """
        Authenticate a request and return authentication result.
        
        Args:
            request: FastAPI request object
            
        Returns:
            AuthResult with authentication status and user information
        """
        try:
            # Extract token
            token = self.extract_token_from_request(request)
            
            if not token:
                return AuthResult(
                    is_authenticated=False,
                    access_type='none',
                    error='No authentication token found'
                )
            
            # Validate JWT token
            try:
                payload = self.jwt_manager.validate_token(token)
                user_id = payload.get('user_id')
                user_email = payload.get('email')
                
                if not user_id or not user_email:
                    return AuthResult(
                        is_authenticated=False,
                        access_type='error',
                        error='Invalid token payload - missing user information'
                    )
                
                # Get user profile from database using email (primary identifier)
                user_profile = await self.user_manager.get_user_by_email(user_email)
                
                if not user_profile:
                    return AuthResult(
                        is_authenticated=False,
                        access_type='error',
                        error='User profile not found'
                    )
                
                # Update user activity
                await self.user_manager.update_user_activity(user_email)
                
                return AuthResult(
                    is_authenticated=True,
                    user_email=user_email,
                    user_id=user_id,
                    user_profile=user_profile,
                    access_type='direct'
                )
                
            except Exception as e:
                logger.warning(f"Token validation failed: {e}")
                return AuthResult(
                    is_authenticated=False,
                    access_type='error',
                    error=f'Token validation failed: {str(e)}'
                )
                
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return AuthResult(
                is_authenticated=False,
                access_type='error',
                error=f'Authentication error: {str(e)}'
            )
    
    def require_authentication(self, request: Request) -> AuthResult:
        """
        Synchronous version of authenticate_request for use in dependencies.
        
        Args:
            request: FastAPI request object
            
        Returns:
            AuthResult with authentication status
        """
        import asyncio
        
        # Run async method in sync context
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.authenticate_request(request))

# Global middleware instance
_auth_middleware: Optional[SCLib_AuthMiddleware] = None

def get_auth_middleware() -> SCLib_AuthMiddleware:
    """Get the global authentication middleware instance."""
    global _auth_middleware
    if _auth_middleware is None:
        _auth_middleware = SCLib_AuthMiddleware()
    return _auth_middleware

# FastAPI Dependencies

def require_auth(request: Request) -> AuthResult:
    """
    FastAPI dependency that requires authentication.
    
    Args:
        request: FastAPI request object
        
    Returns:
        AuthResult with user information
        
    Raises:
        HTTPException: If authentication fails
    """
    auth_middleware = get_auth_middleware()
    auth_result = auth_middleware.require_authentication(request)
    
    if not auth_result.is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=auth_result.error or "Authentication required"
        )
    
    return auth_result

def optional_auth(request: Request) -> AuthResult:
    """
    FastAPI dependency that optionally authenticates.
    
    Args:
        request: FastAPI request object
        
    Returns:
        AuthResult (may be unauthenticated)
    """
    auth_middleware = get_auth_middleware()
    return auth_middleware.require_authentication(request)

def get_current_user(auth_result: AuthResult = Depends(require_auth)) -> UserProfile:
    """
    FastAPI dependency that returns the current authenticated user.
    
    Args:
        auth_result: Authentication result from require_auth dependency
        
    Returns:
        UserProfile of the authenticated user
    """
    return auth_result.user_profile

def get_current_user_email(auth_result: AuthResult = Depends(require_auth)) -> str:
    """
    FastAPI dependency that returns the current user's email.
    
    Args:
        auth_result: Authentication result from require_auth dependency
        
    Returns:
        Email address of the authenticated user
    """
    return auth_result.user_email

def get_current_user_id(auth_result: AuthResult = Depends(require_auth)) -> str:
    """
    FastAPI dependency that returns the current user's ID.
    
    Args:
        auth_result: Authentication result from require_auth dependency
        
    Returns:
        User ID of the authenticated user
    """
    return auth_result.user_id

# Authorization Helper Functions

def check_user_permission(user_email: str, resource: str, action: str) -> bool:
    """
    Check if a user has permission to perform an action on a resource.
    
    Args:
        user_email: User's email address
        resource: Resource identifier (e.g., dataset UUID, team UUID)
        action: Action to perform (e.g., 'read', 'write', 'delete')
        
    Returns:
        True if user has permission, False otherwise
    """
    # For now, all authenticated users have full permissions
    # In the future, this could be extended with role-based access control
    return True

def validate_user_access(user_email: str, dataset_uuid: Optional[str] = None, 
                        team_uuid: Optional[str] = None) -> bool:
    """
    Validate that a user has access to a dataset or team.
    
    Args:
        user_email: User's email address
        dataset_uuid: Optional dataset UUID to check access for
        team_uuid: Optional team UUID to check access for
        
    Returns:
        True if user has access, False otherwise
    """
    # For now, all authenticated users have access to all resources
    # In the future, this could be extended with dataset/team access control
    return True

# Middleware Setup Function

def setup_auth_middleware(app: FastAPI, require_auth_for_all: bool = False):
    """
    Setup authentication middleware for a FastAPI app.
    
    Args:
        app: FastAPI application instance
        require_auth_for_all: If True, all endpoints require authentication by default
    """
    auth_middleware = get_auth_middleware()
    
    @app.middleware("http")
    async def auth_middleware_func(request: Request, call_next):
        """HTTP middleware for authentication."""
        # Skip authentication for health checks and docs
        if request.url.path in ["/health", "/docs", "/redoc", "/openapi.json", "/"]:
            return await call_next(request)
        
        # For now, we don't require auth for all endpoints by default
        # Individual endpoints can use the require_auth dependency
        response = await call_next(request)
        return response
    
    logger.info("Authentication middleware setup complete")

# Utility Functions for Integration

def create_authenticated_upload_request(user_email: str, user_id: str, 
                                      dataset_name: str, sensor: str, **kwargs) -> Dict[str, Any]:
    """
    Create an authenticated upload request with user information.
    
    Args:
        user_email: User's email address
        user_id: User's ID
        dataset_name: Name of the dataset
        sensor: Sensor type
        **kwargs: Additional parameters
        
    Returns:
        Dictionary with upload request parameters
    """
    return {
        'user_email': user_email,
        'user_id': user_id,
        'dataset_name': dataset_name,
        'sensor': sensor,
        'created_at': datetime.utcnow().isoformat(),
        **kwargs
    }

def log_authenticated_action(user_email: str, action: str, resource: str, **kwargs):
    """
    Log an authenticated user action.
    
    Args:
        user_email: User's email address
        action: Action performed
        resource: Resource affected
        **kwargs: Additional logging parameters
    """
    logger.info(f"Authenticated action: {user_email} performed {action} on {resource}", 
                extra={'user_email': user_email, 'action': action, 'resource': resource, **kwargs})
