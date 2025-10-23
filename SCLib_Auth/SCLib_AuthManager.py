#!/usr/bin/env python3
"""
SCLib_AuthManager - Core Authentication Manager
Handles Auth0 integration, user authentication, and token management.
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import requests
import jwt
from jwt import PyJWKClient
import json

logger = logging.getLogger(__name__)

@dataclass
class AuthConfig:
    """Authentication configuration."""
    auth0_domain: str
    auth0_client_id: str
    auth0_client_secret: str
    auth0_audience: str
    jwt_algorithm: str = "RS256"
    token_expiry_hours: int = 24
    refresh_token_expiry_days: int = 30

@dataclass
class UserInfo:
    """User information from Auth0."""
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    email_verified: bool = False
    created_at: datetime = None
    last_login: datetime = None

@dataclass
class TokenPair:
    """Access and refresh token pair."""
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "Bearer"

class SCLib_AuthManager:
    """
    Core authentication manager for ScientistCloud.
    Handles Auth0 integration, JWT validation, and user management.
    """
    
    def __init__(self, config: Optional[AuthConfig] = None):
        """
        Initialize the authentication manager.
        
        Args:
            config: Authentication configuration. If None, loads from environment.
        """
        self.config = config or self._load_config_from_env()
        self.jwks_client = PyJWKClient(f"https://{self.config.auth0_domain}/.well-known/jwks.json")
        
        # Cache for user info
        self._user_cache: Dict[str, UserInfo] = {}
        self._cache_expiry: Dict[str, datetime] = {}
        
        logger.info(f"SCLib_AuthManager initialized for domain: {self.config.auth0_domain}")
    
    def _load_config_from_env(self) -> AuthConfig:
        """Load authentication configuration from environment variables."""
        return AuthConfig(
            auth0_domain=os.getenv('AUTH0_DOMAIN', ''),
            auth0_client_id=os.getenv('AUTH0_CLIENT_ID', ''),
            auth0_client_secret=os.getenv('AUTH0_CLIENT_SECRET', ''),
            auth0_audience=os.getenv('AUTH0_AUDIENCE', ''),
            jwt_algorithm=os.getenv('JWT_ALGORITHM', 'RS256'),
            token_expiry_hours=int(os.getenv('TOKEN_EXPIRY_HOURS', '24')),
            refresh_token_expiry_days=int(os.getenv('REFRESH_TOKEN_EXPIRY_DAYS', '30'))
        )
    
    def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a JWT token and return the payload.
        
        Args:
            token: JWT token to validate
            
        Returns:
            Token payload if valid
            
        Raises:
            jwt.InvalidTokenError: If token is invalid
        """
        try:
            # Get the signing key
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)
            
            # Decode and validate the token
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[self.config.jwt_algorithm],
                audience=self.config.auth0_audience,
                issuer=f"https://{self.config.auth0_domain}/"
            )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            raise jwt.InvalidTokenError("Token has expired")
        except jwt.InvalidAudienceError:
            logger.warning("Invalid token audience")
            raise jwt.InvalidTokenError("Invalid token audience")
        except jwt.InvalidIssuerError:
            logger.warning("Invalid token issuer")
            raise jwt.InvalidTokenError("Invalid token issuer")
        except Exception as e:
            logger.error(f"Token validation failed: {e}")
            raise jwt.InvalidTokenError(f"Token validation failed: {e}")
    
    def get_user_info(self, token: str) -> UserInfo:
        """
        Get user information from Auth0 using the access token.
        
        Args:
            token: Valid access token
            
        Returns:
            UserInfo object with user details
        """
        try:
            # Validate token first
            payload = self.validate_token(token)
            user_id = payload.get('sub')
            
            # Check cache first
            if user_id in self._user_cache:
                cache_time = self._cache_expiry.get(user_id)
                if cache_time and datetime.now() < cache_time:
                    return self._user_cache[user_id]
            
            # Get user info from Auth0
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                f"https://{self.config.auth0_domain}/userinfo",
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            
            user_data = response.json()
            
            # Create UserInfo object
            user_info = UserInfo(
                user_id=user_data.get('sub', ''),
                email=user_data.get('email', ''),
                name=user_data.get('name', ''),
                picture=user_data.get('picture'),
                email_verified=user_data.get('email_verified', False),
                created_at=datetime.now(),  # Would need to get from Auth0 management API
                last_login=datetime.now()
            )
            
            # Cache the user info
            self._user_cache[user_id] = user_info
            self._cache_expiry[user_id] = datetime.now() + timedelta(minutes=15)
            
            return user_info
            
        except requests.RequestException as e:
            logger.error(f"Failed to get user info from Auth0: {e}")
            raise Exception(f"Failed to get user info: {e}")
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            raise Exception(f"Error getting user info: {e}")
    
    def exchange_code_for_tokens(self, authorization_code: str, redirect_uri: str) -> TokenPair:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            authorization_code: Authorization code from Auth0
            redirect_uri: Redirect URI used in the authorization flow
            
        Returns:
            TokenPair with access and refresh tokens
        """
        try:
            token_url = f"https://{self.config.auth0_domain}/oauth/token"
            
            payload = {
                'grant_type': 'authorization_code',
                'client_id': self.config.auth0_client_id,
                'client_secret': self.config.auth0_client_secret,
                'code': authorization_code,
                'redirect_uri': redirect_uri
            }
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.post(token_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            token_data = response.json()
            
            return TokenPair(
                access_token=token_data['access_token'],
                refresh_token=token_data.get('refresh_token', ''),
                expires_in=token_data.get('expires_in', 3600),
                token_type=token_data.get('token_type', 'Bearer')
            )
            
        except requests.RequestException as e:
            logger.error(f"Failed to exchange code for tokens: {e}")
            raise Exception(f"Failed to exchange code for tokens: {e}")
    
    def refresh_access_token(self, refresh_token: str) -> TokenPair:
        """
        Refresh an access token using a refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New TokenPair with refreshed access token
        """
        try:
            token_url = f"https://{self.config.auth0_domain}/oauth/token"
            
            payload = {
                'grant_type': 'refresh_token',
                'client_id': self.config.auth0_client_id,
                'client_secret': self.config.auth0_client_secret,
                'refresh_token': refresh_token
            }
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.post(token_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            token_data = response.json()
            
            return TokenPair(
                access_token=token_data['access_token'],
                refresh_token=token_data.get('refresh_token', refresh_token),
                expires_in=token_data.get('expires_in', 3600),
                token_type=token_data.get('token_type', 'Bearer')
            )
            
        except requests.RequestException as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise Exception(f"Failed to refresh access token: {e}")
    
    def revoke_token(self, token: str) -> bool:
        """
        Revoke a token (logout).
        
        Args:
            token: Token to revoke
            
        Returns:
            True if successful
        """
        try:
            revoke_url = f"https://{self.config.auth0_domain}/oauth/revoke"
            
            payload = {
                'token': token,
                'client_id': self.config.auth0_client_id,
                'client_secret': self.config.auth0_client_secret
            }
            
            headers = {
                'Content-Type': 'application/json'
            }
            
            response = requests.post(revoke_url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            return True
            
        except requests.RequestException as e:
            logger.error(f"Failed to revoke token: {e}")
            return False
    
    def get_authorization_url(self, redirect_uri: str, state: Optional[str] = None) -> str:
        """
        Get the Auth0 authorization URL for login.
        
        Args:
            redirect_uri: Where to redirect after authorization
            state: Optional state parameter for security
            
        Returns:
            Authorization URL
        """
        params = {
            'response_type': 'code',
            'client_id': self.config.auth0_client_id,
            'redirect_uri': redirect_uri,
            'scope': 'openid profile email',
            'audience': self.config.auth0_audience
        }
        
        if state:
            params['state'] = state
        
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"https://{self.config.auth0_domain}/authorize?{query_string}"

# Global instance
_auth_manager: Optional[SCLib_AuthManager] = None

def get_auth_manager() -> SCLib_AuthManager:
    """Get the global authentication manager instance."""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = SCLib_AuthManager()
    return _auth_manager

