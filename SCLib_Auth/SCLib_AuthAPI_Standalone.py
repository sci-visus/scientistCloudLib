#!/usr/bin/env python3
"""
SCLib Authentication API - Standalone Version
FastAPI endpoints for authentication using Auth0 and JWT tokens.
Completely independent of Bokeh authorization and other SCLib components.
"""

from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
import logging
import secrets
import hashlib
from datetime import datetime, timedelta
import os
import jwt
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# Configure logging (only if not already configured)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="SCLib Authentication API",
    description="Standalone authentication and authorization endpoints for ScientistCloud",
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

# Security scheme
security = HTTPBearer()

# Pydantic models
class LoginRequest(BaseModel):
    """Login request model."""
    email: EmailStr
    password: Optional[str] = None
    redirect_uri: Optional[str] = None

class Auth0CallbackRequest(BaseModel):
    """Auth0 callback request model."""
    code: str
    state: Optional[str] = None
    redirect_uri: str = "http://localhost:8001/api/auth/callback"

class RefreshRequest(BaseModel):
    """Refresh token request model."""
    refresh_token: str

class LogoutRequest(BaseModel):
    """Logout request model."""
    token: Optional[str] = None

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

class AuthStatusResponse(BaseModel):
    """Authentication status response model."""
    is_authenticated: bool
    user_email: Optional[str] = None
    access_type: str
    error: Optional[str] = None

# MongoDB connection and configuration
class AuthConfig:
    """Authentication configuration."""
    def __init__(self):
        self.mongo_url = os.getenv('MONGO_URL', 'mongodb://localhost:27017')
        self.db_name = os.getenv('DB_NAME', 'SCLib_Test')
        self.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
        self.auth0_domain = os.getenv('AUTH0_DOMAIN', '')
        self.auth0_client_id = os.getenv('AUTHO_CLIENT_ID', '')  # Note: AUTHO not AUTH0
        self.auth0_client_secret = os.getenv('AUTHO_CLIENT_SECRET', '')
        self.auth0_audience = os.getenv('AUTH0_AUDIENCE', '')
        self.jwt_expiry_hours = int(os.getenv('JWT_EXPIRY_HOURS', '24'))
        self.refresh_token_expiry_days = int(os.getenv('REFRESH_TOKEN_EXPIRY_DAYS', '30'))
        
        # Collection names
        self.collections = type('Collections', (), {
            'user_profile': 'user_profile'
        })()

# Global configuration
config = AuthConfig()

# MongoDB connection
def get_mongo_client() -> MongoClient:
    """Get MongoDB client."""
    return MongoClient(config.mongo_url)

def get_user_collection():
    """Get user profiles collection."""
    client = get_mongo_client()
    db = client[config.db_name]
    return db[config.collections.user_profile]

# JWT token management
class JWTManager:
    """JWT token manager."""
    
    @staticmethod
    def create_token(user_id: str, email: str, expires_hours: int = None) -> str:
        """Create a JWT token."""
        now = int(datetime.utcnow().timestamp())
        expiry_hours = expires_hours or config.jwt_expiry_hours
        expiry = now + (expiry_hours * 3600)
        
        # Get audience from environment (should match Auth0 audience)
        audience = os.getenv('AUTH0_AUDIENCE', 'sclib-api')
        
        payload = {
            'user_id': user_id,
            'email': email,
            'iat': now,
            'exp': expiry,
            'jti': secrets.token_urlsafe(32),
            'iss': 'sclib-auth',
            'aud': audience,
            'type': 'access'
        }
        
        return jwt.encode(payload, config.secret_key, algorithm='HS256')
    
    @staticmethod
    def create_refresh_token(user_id: str, email: str) -> str:
        """Create a refresh token."""
        now = int(datetime.utcnow().timestamp())
        expiry = now + (config.refresh_token_expiry_days * 24 * 3600)
        
        # Get audience from environment (should match Auth0 audience)
        audience = os.getenv('AUTH0_AUDIENCE', 'sclib-api')
        
        payload = {
            'user_id': user_id,
            'email': email,
            'iat': now,
            'exp': expiry,
            'jti': secrets.token_urlsafe(32),
            'iss': 'sclib-auth',
            'aud': audience,
            'type': 'refresh'
        }
        
        return jwt.encode(payload, config.secret_key, algorithm='HS256')
    
    @staticmethod
    def validate_token(token: str) -> Dict[str, Any]:
        """Validate a JWT token."""
        try:
            # Get audience from environment (should match Auth0 audience)
            audience = os.getenv('AUTH0_AUDIENCE', 'sclib-api')
            
            payload = jwt.decode(
                token, 
                config.secret_key, 
                algorithms=['HS256'],
                audience=audience,
                issuer='sclib-auth'
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

# User management
class UserManager:
    """User management for MongoDB."""
    
    @staticmethod
    def create_or_update_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update user in MongoDB."""
        collection = get_user_collection()
        
        user_id = user_data.get('user_id') or user_data.get('sub')
        email = user_data.get('email')
        name = user_data.get('name', email.split('@')[0] if email else 'Unknown')
        
        if not email:
            raise ValueError("email is required")
        
        # Check if user exists by email (primary identifier)
        existing_user = collection.find_one({"email": email})
        
        user_doc = {
            "email": email,
            "name": name,
            "picture": user_data.get('picture'),
            "email_verified": user_data.get('email_verified', False),
            "last_login": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "is_active": True,
            "auth0_metadata": user_data,
            "access_tokens": [],
            "refresh_tokens": [],
            "preferences": {}
        }
        
        if existing_user:
            # Update existing user
            collection.update_one(
                {"email": email},
                {
                    "$set": {
                        "email": email,
                        "name": name,
                        "picture": user_data.get('picture'),
                        "email_verified": user_data.get('email_verified', False),
                        "last_login": datetime.utcnow(),
                        "last_activity": datetime.utcnow(),
                        "auth0_metadata": user_data
                    }
                }
            )
            logger.info(f"Updated user: {email}")
        else:
            # Create new user
            user_doc["created_at"] = datetime.utcnow()
            collection.insert_one(user_doc)
            logger.info(f"Created new user: {email}")
        
        # Return user data with user_id for JWT compatibility
        return {
            "user_id": user_id,  # Keep for JWT token compatibility
            "email": email,
            "name": name,
            "email_verified": user_data.get('email_verified', False)
        }
    
    @staticmethod
    def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID (for backward compatibility)."""
        collection = get_user_collection()
        return collection.find_one({"user_id": user_id})
    
    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Get user by email (primary lookup method)."""
        collection = get_user_collection()
        return collection.find_one({"email": email})
    
    @staticmethod
    def store_token(user_id: str, token: str, token_type: str = 'access') -> bool:
        """Store token for user."""
        collection = get_user_collection()
        
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        token_record = {
            "token_id": secrets.token_urlsafe(32),
            "token_type": token_type,
            "token_hash": token_hash,
            "created_at": datetime.utcnow(),
            "expires_at": datetime.utcnow() + timedelta(hours=24 if token_type == 'access' else 24*30),
            "is_revoked": False,
            "last_used": datetime.utcnow()
        }
        
        field_name = f"{token_type}_tokens"
        result = collection.update_one(
            {"user_id": user_id},
            {
                "$push": {field_name: token_record},
                "$set": {"last_activity": datetime.utcnow()}
            }
        )
        
        return result.modified_count > 0
    
    @staticmethod
    def revoke_all_tokens(user_id: str) -> bool:
        """Revoke all tokens for user."""
        collection = get_user_collection()
        now = datetime.utcnow()
        
        result = collection.update_one(
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
        
        return result.modified_count > 0

# Dependency to get current user
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Get current user from JWT token."""
    try:
        token = credentials.credentials
        payload = JWTManager.validate_token(token)
        user_id = payload.get('user_id')
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        user = UserManager.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")

# API Endpoints

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "SCLib Authentication API - Standalone",
        "version": "1.0.0",
        "endpoints": {
            "login": "POST /api/auth/login",
            "callback": "POST /api/auth/callback",
            "logout": "POST /api/auth/logout", 
            "refresh": "POST /api/auth/refresh",
            "me": "GET /api/auth/me",
            "status": "GET /api/auth/status",
            "authorize": "GET /api/auth/authorize"
        }
    }

@app.get("/health", response_model=Dict[str, str])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "SCLib_Auth_Standalone"}

@app.post("/api/auth/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """
    Login endpoint - supports both direct login and Auth0 redirect.
    """
    try:
        logger.info(f"Login attempt for email: {request.email}")
        
        # For now, this is a placeholder implementation
        # In a real implementation, you would validate credentials against Auth0 or your user database
        
        if not request.email or '@' not in request.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format"
            )
        
        # Create user data (placeholder)
        user_data = {
            'user_id': f"user_{hashlib.md5(request.email.encode()).hexdigest()}",
            'email': request.email,
            'name': request.email.split('@')[0],
            'email_verified': True
        }
        
        # Create or update user
        user = UserManager.create_or_update_user(user_data)
        
        # Generate tokens
        access_token = JWTManager.create_token(user['user_id'], user['email'])
        refresh_token = JWTManager.create_refresh_token(user['user_id'], user['email'])
        
        # Note: Token storage is disabled - tokens are stateless JWT tokens
        
        return AuthResponse(
            success=True,
            message=f"Login successful for {request.email}",
            data={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": config.jwt_expiry_hours * 3600,
                "token_type": "Bearer",
                "user": {
                    "user_id": user['user_id'],
                    "email": user['email'],
                    "name": user['name'],
                    "email_verified": user['email_verified']
                }
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@app.post("/api/auth/refresh", response_model=AuthResponse)
async def refresh_token(request: RefreshRequest):
    """
    Refresh access token using refresh token.
    """
    try:
        logger.info("Token refresh attempt")
        
        # Validate refresh token
        payload = JWTManager.validate_token(request.refresh_token)
        
        if payload.get('type') != 'refresh':
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user_id = payload.get('user_id')
        email = payload.get('email')
        
        if not user_id or not email:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        # Generate new tokens
        new_access_token = JWTManager.create_token(user_id, email)
        new_refresh_token = JWTManager.create_refresh_token(user_id, email)
        
        # Note: Token storage is disabled - tokens are stateless JWT tokens
        
        return AuthResponse(
            success=True,
            message="Token refreshed successfully",
            data={
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "expires_in": config.jwt_expiry_hours * 3600,
                "token_type": "Bearer"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token refresh failed: {str(e)}"
        )

@app.post("/api/auth/logout", response_model=AuthResponse)
async def logout(request: LogoutRequest):
    """
    Logout endpoint - revoke all tokens for user.
    """
    try:
        if not request.token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token is required for logout"
            )
        
        logger.info("Logout attempt")
        
        # Validate token to get user_id
        payload = JWTManager.validate_token(request.token)
        user_id = payload.get('user_id')
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        # Note: Token revocation is disabled - tokens are stateless JWT tokens
        # In a stateless system, logout is handled client-side by discarding the token
        
        return AuthResponse(
            success=True,
            message="Logout successful - please discard your token"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Logout error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )

@app.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    """
    Get current user information.
    """
    try:
        return UserResponse(
            user_id=current_user['user_id'],
            email=current_user['email'],
            name=current_user['name'],
            picture=current_user.get('picture'),
            email_verified=current_user.get('email_verified', False),
            created_at=current_user.get('created_at'),
            last_login=current_user.get('last_login')
        )
        
    except Exception as e:
        logger.error(f"Failed to get user info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get user info: {e}"
        )

@app.get("/api/auth/status", response_model=AuthStatusResponse)
async def auth_status(request: Request):
    """
    Check authentication status from request headers or cookies.
    """
    try:
        # Try to get token from Authorization header
        auth_header = request.headers.get("Authorization")
        token = None
        
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
        
        # If no token in header, try to get from cookies
        if not token:
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
                    logger.info(f"Found token in cookie: {cookie_name}")
                    break
        
        if not token:
            return AuthStatusResponse(
                is_authenticated=False,
                access_type='none',
                error='No authentication token found'
            )
        
        # Validate token
        try:
            payload = JWTManager.validate_token(token)
            user_id = payload.get('user_id')
            email = payload.get('email')
            
            return AuthStatusResponse(
                is_authenticated=True,
                user_email=email,
                access_type='direct'
            )
        except Exception as e:
            logger.warning(f"Token validation failed: {e}")
            return AuthStatusResponse(
                is_authenticated=False,
                access_type='error',
                error=str(e)
            )
        
    except Exception as e:
        logger.error(f"Auth status check error: {e}")
        return AuthStatusResponse(
            is_authenticated=False,
            access_type='error',
            error=str(e)
        )

@app.get("/api/auth/authorize")
async def get_authorization_url(
    redirect_uri: str,
    state: Optional[str] = None
):
    """
    Get Auth0 authorization URL for login (placeholder).
    """
    try:
        if not state:
            state = secrets.token_urlsafe(32)
        
        # This would be the actual Auth0 authorization URL
        # For now, return a placeholder
        auth_url = f"https://{config.auth0_domain}/authorize?response_type=code&client_id={config.auth0_client_id}&redirect_uri={redirect_uri}&scope=openid profile email&state={state}"
        
        return {
            "authorization_url": auth_url,
            "state": state
        }
        
    except Exception as e:
        logger.error(f"Get authorization URL error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get authorization URL: {e}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

