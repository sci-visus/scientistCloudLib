#!/usr/bin/env python3
"""
SCLib_AuthAPI - FastAPI Authentication Endpoints
Provides REST API endpoints for authentication using Auth0 and JWT tokens.
"""

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
import logging
import secrets
from datetime import datetime

from .SCLib_AuthManager import SCLib_AuthManager, get_auth_manager, UserInfo, TokenPair
from .SCLib_JWTManager import SCLib_JWTManager, get_jwt_manager
from .SCLib_UserManager import SCLib_UserManager, get_user_manager, UserProfile

# Get logger without configuring
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="SCLib Authentication API",
    description="Authentication and authorization endpoints for ScientistCloud",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class LoginRequest(BaseModel):
    """Login request model."""
    authorization_code: str
    redirect_uri: str

class RefreshRequest(BaseModel):
    """Refresh token request model."""
    refresh_token: str

class LogoutRequest(BaseModel):
    """Logout request model."""
    token: str

class UserResponse(BaseModel):
    """User information response model."""
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    email_verified: bool = False
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None

class TokenResponse(BaseModel):
    """Token response model."""
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"

class AuthResponse(BaseModel):
    """Authentication response model."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None

class CreateUserRequest(BaseModel):
    """Create user request model."""
    email: EmailStr
    name: str
    auth0_id: Optional[str] = None
    sub: Optional[str] = None  # Auth0 user ID (sub claim)
    picture: Optional[str] = None
    email_verified: bool = False
    preferences: Optional[Dict[str, Any]] = None
    permissions: Optional[list] = None
    auth0_metadata: Optional[Dict[str, Any]] = None

# Dependency to get auth manager
def get_auth_manager_dep() -> SCLib_AuthManager:
    return get_auth_manager()

def get_jwt_manager_dep() -> SCLib_JWTManager:
    return get_jwt_manager()

def get_user_manager_dep() -> SCLib_UserManager:
    return get_user_manager()

# Helper function to extract token from request
def extract_token_from_request(request: Request) -> str:
    """Extract JWT token from Authorization header."""
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme"
            )
        return token
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format"
        )

# API Endpoints

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "SCLib Authentication API",
        "version": "1.0.0",
        "endpoints": {
            "login": "POST /api/auth/login",
            "logout": "POST /api/auth/logout", 
            "refresh": "POST /api/auth/refresh",
            "me": "GET /api/auth/me",
            "authorize": "GET /api/auth/authorize",
            "user-by-email": "GET /api/auth/user-by-email?email=...",
            "create-user": "POST /api/auth/create-user",
            "update-last-login": "POST /api/auth/user/{email}/update-last-login",
            "validate": "GET /api/auth/validate"
        }
    }

@app.get("/health", response_model=Dict[str, str])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "SCLib_Auth"}

@app.get("/api/auth/authorize")
async def get_authorization_url(
    redirect_uri: str,
    state: Optional[str] = None,
    auth_manager: SCLib_AuthManager = Depends(get_auth_manager_dep)
):
    """
    Get Auth0 authorization URL for login.
    
    Args:
        redirect_uri: Where to redirect after authorization
        state: Optional state parameter for security
        
    Returns:
        Authorization URL
    """
    try:
        # Generate state if not provided
        if not state:
            state = secrets.token_urlsafe(32)
        
        auth_url = auth_manager.get_authorization_url(redirect_uri, state)
        
        return {
            "authorization_url": auth_url,
            "state": state
        }
        
    except Exception as e:
        logger.error(f"Failed to generate authorization URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate authorization URL: {e}"
        )

@app.post("/api/auth/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    auth_manager: SCLib_AuthManager = Depends(get_auth_manager_dep),
    jwt_manager: SCLib_JWTManager = Depends(get_jwt_manager_dep),
    user_manager: SCLib_UserManager = Depends(get_user_manager_dep)
):
    """
    Exchange authorization code for tokens and create user session.
    
    Args:
        request: Login request with authorization code
        
    Returns:
        Authentication response with tokens
    """
    try:
        # Exchange code for tokens
        token_pair = auth_manager.exchange_code_for_tokens(
            request.authorization_code,
            request.redirect_uri
        )
        
        # Get user info
        user_info = auth_manager.get_user_info(token_pair.access_token)
        
        # Create or update user in database
        user = await user_manager.create_or_update_user(user_info)
        
        # Generate our own JWT token for API access - use email as primary identifier
        api_token = jwt_manager.create_token(
            email=user_info.email,
            user_id=user_info.user_id,  # Optional for backward compatibility
            expires_hours=24
        )
        
        return AuthResponse(
            success=True,
            message="Login successful",
            data={
                "access_token": api_token,
                "auth0_access_token": token_pair.access_token,
                "refresh_token": token_pair.refresh_token,
                "expires_in": token_pair.expires_in,
                "token_type": token_pair.token_type,
                "user": {
                    "user_id": user_info.user_id,
                    "email": user_info.email,
                    "name": user_info.name,
                    "picture": user_info.picture,
                    "email_verified": user_info.email_verified
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Login failed: {e}"
        )

@app.post("/api/auth/refresh", response_model=AuthResponse)
async def refresh_token(
    request: RefreshRequest,
    auth_manager: SCLib_AuthManager = Depends(get_auth_manager_dep),
    jwt_manager: SCLib_JWTManager = Depends(get_jwt_manager_dep)
):
    """
    Refresh access token using refresh token.
    
    Args:
        request: Refresh request with refresh token
        
    Returns:
        New token pair
    """
    try:
        # Refresh the Auth0 token
        token_pair = auth_manager.refresh_access_token(request.refresh_token)
        
        # Get user info
        user_info = auth_manager.get_user_info(token_pair.access_token)
        
        # Generate new API token - use email as primary identifier
        api_token = jwt_manager.create_token(
            email=user_info.email,
            user_id=user_info.user_id,  # Optional for backward compatibility
            expires_hours=24
        )
        
        return AuthResponse(
            success=True,
            message="Token refreshed successfully",
            data={
                "access_token": api_token,
                "auth0_access_token": token_pair.access_token,
                "refresh_token": token_pair.refresh_token,
                "expires_in": token_pair.expires_in,
                "token_type": token_pair.token_type
            }
        )
        
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {e}"
        )

@app.post("/api/auth/logout", response_model=AuthResponse)
async def logout(
    request: LogoutRequest,
    auth_manager: SCLib_AuthManager = Depends(get_auth_manager_dep)
):
    """
    Logout and revoke tokens.
    
    Args:
        request: Logout request with token to revoke
        
    Returns:
        Logout confirmation
    """
    try:
        # Revoke the token
        success = auth_manager.revoke_token(request.token)
        
        if success:
            return AuthResponse(
                success=True,
                message="Logout successful"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to revoke token"
            )
            
    except Exception as e:
        logger.error(f"Logout failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Logout failed: {e}"
        )

@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user(
    request: Request,
    auth_manager: SCLib_AuthManager = Depends(get_auth_manager_dep),
    jwt_manager: SCLib_JWTManager = Depends(get_jwt_manager_dep),
    user_manager: SCLib_UserManager = Depends(get_user_manager_dep)
):
    """
    Get current user information.
    
    Returns:
        Current user information
    """
    try:
        # Extract token from request
        token = extract_token_from_request(request)
        
        # Validate our JWT token
        payload = jwt_manager.validate_token(token)
        email = payload.get('email')
        
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload - missing email"
            )
        
        # Get user from database using email (primary identifier)
        user = await user_manager.get_user_by_email(email)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse(
            user_id=user.user_id or user.email,  # Use email if user_id is not set
            email=user.email,
            name=user.name,
            picture=user.picture,
            email_verified=user.email_verified,
            created_at=user.created_at,
            last_login=user.last_login
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to get user info: {e}"
        )

@app.get("/api/auth/validate")
async def validate_token(
    request: Request,
    jwt_manager: SCLib_JWTManager = Depends(get_jwt_manager_dep)
):
    """
    Validate a JWT token.
    
    Returns:
        Token validation result
    """
    try:
        # Extract token from request
        token = extract_token_from_request(request)
        
        # Validate token
        payload = jwt_manager.validate_token(token)
        
        return {
            "valid": True,
            "payload": payload
        }
        
    except Exception as e:
        logger.error(f"Token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token validation failed: {e}"
        )

@app.get("/api/auth/user-by-email")
async def get_user_by_email(
    email: EmailStr,
    user_manager: SCLib_UserManager = Depends(get_user_manager_dep)
):
    """
    Get user profile by email address.
    
    Args:
        email: User's email address
        
    Returns:
        User information or null if not found
    """
    try:
        user = await user_manager.get_user_by_email(email)
        
        if not user:
            return {
                "user": None,
                "found": False
            }
        
        return {
            "user": {
                "id": user.user_id,
                "user_id": user.user_id,
                "email": user.email,
                "name": user.name,
                "picture": user.picture,
                "email_verified": user.email_verified,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "preferences": user.preferences or {},
                "auth0_id": user.auth0_user_id
            },
            "found": True
        }
        
    except Exception as e:
        logger.error(f"Failed to get user by email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user by email: {e}"
        )

@app.post("/api/auth/create-user")
async def create_user(
    request: CreateUserRequest,
    user_manager: SCLib_UserManager = Depends(get_user_manager_dep)
):
    """
    Create or update user profile from Auth0 user info.
    
    Args:
        request: User information from Auth0 callback
        
    Returns:
        Created/updated user information
    """
    try:
        # Convert request to UserInfo object
        # Use sub (Auth0 user ID) or auth0_id as user_id
        user_id = request.sub or request.auth0_id or f"user_{request.email.replace('@', '_').replace('.', '_')}"
        
        user_info = UserInfo(
            user_id=user_id,
            email=request.email,
            name=request.name,
            picture=request.picture,
            email_verified=request.email_verified
        )
        
        # Create or update user in database
        user = await user_manager.create_or_update_user(user_info)
        
        # Update preferences if provided
        if request.preferences:
            from datetime import datetime
            user_manager.user_profile.update_one(
                {"email": user.email},
                {"$set": {"preferences": request.preferences}}
            )
        
        logger.info(f"Created/updated user: {user.email}")
        
        return {
            "success": True,
            "user_id": user.user_id,
            "user": {
                "id": user.user_id,
                "user_id": user.user_id,
                "email": user.email,
                "name": user.name,
                "picture": user.picture,
                "email_verified": user.email_verified,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None,
                "preferences": user.preferences or {},
                "auth0_id": user.auth0_user_id
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to create/update user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create/update user: {e}"
        )

@app.post("/api/auth/user/{email}/update-last-login")
async def update_user_last_login(
    email: str,
    user_manager: SCLib_UserManager = Depends(get_user_manager_dep)
):
    """
    Update user's last login timestamp.
    
    Args:
        email: User's email address (primary identifier)
        
    Returns:
        Success status
    """
    try:
        from datetime import datetime
        
        # Update last_login in user_profile collection using email
        result = user_manager.user_profile.update_one(
            {"email": email},
            {
                "$set": {
                    "last_login": datetime.utcnow(),
                    "last_activity": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found: {email}"
            )
        
        logger.info(f"Updated last login for user: {email}")
        
        return {
            "success": True,
            "email": email,
            "message": "Last login updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update last login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update last login: {e}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
