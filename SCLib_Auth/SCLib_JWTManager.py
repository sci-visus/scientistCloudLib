#!/usr/bin/env python3
"""
SCLib JWT Manager
Handles JWT token creation, validation, and management for SCLib authentication.
"""

import os
import jwt
import time
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class SCLib_JWTManager:
    """
    JWT token manager for SCLib authentication.
    Handles token creation, validation, and management.
    """
    
    def __init__(self, secret_key: Optional[str] = None):
        """
        Initialize the JWT manager.
        
        Args:
            secret_key: JWT secret key (if None, will use SECRET_KEY from environment)
        """
        self.secret_key = secret_key or os.getenv('SECRET_KEY')
        if not self.secret_key:
            raise ValueError("SECRET_KEY must be provided or set in environment variables")
        
        # Token configuration
        self.token_expiry_hours = int(os.getenv('JWT_EXPIRY_HOURS', '24'))
        self.algorithm = 'HS256'
        
        logger.info("SCLib_JWTManager initialized")
    
    def create_token(self, user_id: str, email: str, expires_hours: Optional[int] = None, 
                    additional_claims: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a JWT token for a user.
        
        Args:
            user_id: User's unique identifier
            email: User's email address
            expires_hours: Token expiry in hours (defaults to configured value)
            additional_claims: Additional claims to include in the token
            
        Returns:
            JWT token string
        """
        now = int(time.time())
        expiry_hours = expires_hours or self.token_expiry_hours
        expiry = now + (expiry_hours * 3600)
        
        # Generate unique token ID
        token_id = secrets.token_urlsafe(32)
        
        # Get audience from environment (should match Auth0 audience)
        audience = os.getenv('AUTH0_AUDIENCE', 'sclib-api')
        
        payload = {
            'user_id': user_id,
            'email': email,
            'iat': now,
            'exp': expiry,
            'jti': token_id,  # JWT ID for token tracking
            'iss': 'sclib-auth',
            'aud': audience,
            'type': 'access'
        }
        
        # Add additional claims if provided
        if additional_claims:
            payload.update(additional_claims)
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.info(f"Created JWT token for user: {email}")
        return token
    
    def create_refresh_token(self, user_id: str, email: str, expires_days: int = 30) -> str:
        """
        Create a refresh token for a user.
        
        Args:
            user_id: User's unique identifier
            email: User's email address
            expires_days: Token expiry in days
            
        Returns:
            Refresh token string
        """
        now = int(time.time())
        expiry = now + (expires_days * 24 * 3600)
        
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
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        logger.info(f"Created refresh token for user: {email}")
        return token
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a JWT token and return the payload.
        
        Args:
            token: JWT token string
            
        Returns:
            Token payload if valid
            
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            # Get audience from environment (should match Auth0 audience)
            audience = os.getenv('AUTH0_AUDIENCE', 'sclib-api')
            
            # Decode with audience validation
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm],
                audience=audience,
                issuer='sclib-auth'
            )
            
            # Validate required fields
            if 'user_id' not in payload:
                raise jwt.InvalidTokenError("Missing 'user_id' field in token")
            
            logger.debug(f"Token validated for user: {payload.get('email', 'unknown')}")
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise jwt.InvalidTokenError("Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            raise
        except Exception as e:
            logger.error(f"Token validation error: {e}")
            raise jwt.InvalidTokenError(f"Token validation failed: {e}")
    
    def extract_user_id(self, token: str) -> str:
        """
        Extract user ID from a JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            User ID
            
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        payload = self.validate_token(token)
        return payload['user_id']
    
    def extract_email(self, token: str) -> str:
        """
        Extract email from a JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Email address
            
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        payload = self.validate_token(token)
        return payload.get('email', '')
    
    def is_token_expired(self, token: str) -> bool:
        """
        Check if a token is expired without raising an exception.
        
        Args:
            token: JWT token string
            
        Returns:
            True if token is expired, False otherwise
        """
        try:
            self.validate_token(token)
            return False
        except jwt.ExpiredSignatureError:
            return True
        except:
            return True
    
    def get_token_info(self, token: str) -> Dict[str, Any]:
        """
        Get token information without validation.
        
        Args:
            token: JWT token string
            
        Returns:
            Token information dictionary
        """
        try:
            # Decode without verification to get payload
            payload = jwt.decode(token, options={"verify_signature": False})
            
            return {
                'user_id': payload.get('user_id'),
                'email': payload.get('email'),
                'issued_at': datetime.fromtimestamp(payload.get('iat', 0)).isoformat(),
                'expires_at': datetime.fromtimestamp(payload.get('exp', 0)).isoformat(),
                'token_id': payload.get('jti'),
                'type': payload.get('type', 'unknown'),
                'is_expired': self.is_token_expired(token)
            }
        except Exception as e:
            logger.error(f"Failed to get token info: {e}")
            return {
                'error': str(e),
                'is_expired': True
            }

# Global instance
_jwt_manager: Optional[SCLib_JWTManager] = None

def get_jwt_manager() -> SCLib_JWTManager:
    """Get the global JWT manager instance."""
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = SCLib_JWTManager()
    return _jwt_manager

