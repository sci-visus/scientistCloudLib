#!/usr/bin/env python3
"""
Google OAuth Token Management for ScientistCloud
Handles retrieval and management of Google OAuth tokens from MongoDB
Based on syncGoogleUser.py functionality
"""

import os
import base64
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
from Crypto.Cipher import AES
import logging

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import google.auth.exceptions
except ImportError:
    raise ImportError("google-auth and google-api-python-client are required for Google OAuth functionality")

try:
    from .SCLib_MongoConnection import mongo_collection_by_type_context
    from .SCLib_Config import get_config
except ImportError:
    from SCLib_MongoConnection import mongo_collection_by_type_context
    from SCLib_Config import get_config

logger = logging.getLogger(__name__)

# === AES Decryption (matching PHP encryption) ===

def get_key_iv(secret_key: str, secret_iv: str):
    """Generate AES key and IV from secrets (matching PHP encryption)."""
    key = hashlib.sha256(secret_key.encode()).digest()  # 32 bytes for AES-256
    iv = hashlib.sha256(secret_iv.encode()).digest()[:16]  # 16 bytes for AES block size
    return key, iv

def unpad(s: bytes) -> bytes:
    """Remove PKCS7 padding."""
    pad_len = s[-1]
    if pad_len < 1 or pad_len > 16 or s[-pad_len:] != bytes([pad_len]) * pad_len:
        raise ValueError("Invalid padding")
    return s[:-pad_len]

def decrypt_string(encrypted_b64: str, secret_key: str, secret_iv: str) -> str:
    """Decrypt AES-encrypted string."""
    encrypted = base64.b64decode(encrypted_b64)
    key, iv = get_key_iv(secret_key, secret_iv)
    return unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(encrypted)).decode('utf-8')

def decrypt_token(encrypted_token: str) -> str:
    """Decrypt Google token using environment variables."""
    secret_key = os.environ.get('SECRET_KEY')
    secret_iv = os.environ.get('SECRET_IV')
    
    if not secret_key or not secret_iv:
        raise ValueError("SECRET_KEY or SECRET_IV not set in environment")
    
    return decrypt_string(encrypted_token, secret_key, secret_iv)

# === Token Management ===

def get_user_google_credentials(user_email: str) -> Credentials:
    """
    Get Google OAuth credentials for a user from MongoDB.
    
    Args:
        user_email: User's email address
        
    Returns:
        google.oauth2.credentials.Credentials object
        
    Raises:
        ValueError: If tokens are not found or invalid
        Exception: If token decryption fails
    """
    logger.info(f"Retrieving Google credentials for {user_email}")
    
    config = get_config()
    db_name = config.database.db_name
    
    with mongo_collection_by_type_context('user_profile') as collection:
        user_doc = collection.find_one({"email": user_email})
        
        if not user_doc:
            raise ValueError(f"No user profile found for {user_email}")
        
        enc_access = user_doc.get("google_access_token")
        enc_refresh = user_doc.get("google_refresh_token")
        expires_at = user_doc.get("google_token_expires_at")
        is_invalid = user_doc.get("google_refresh_token_invalid", False)
        
        if is_invalid:
            raise ValueError(f"Google refresh token marked as invalid for {user_email}. User must re-authenticate.")
        
        if not enc_access or not enc_refresh:
            raise ValueError(f"No Google tokens found for {user_email}. User must authenticate with Google.")
        
        try:
            access_token = decrypt_token(enc_access)
            refresh_token = decrypt_token(enc_refresh)
        except Exception as e:
            logger.error(f"Failed to decrypt tokens for {user_email}: {e}")
            raise ValueError(f"Failed to decrypt Google tokens: {e}")
        
        if not access_token or not refresh_token:
            raise ValueError("Decrypted tokens are empty")
        
        # Verify these are real Google OAuth tokens (not Auth0 JWT tokens)
        if not (access_token.startswith('ya29.') and refresh_token.startswith('1//')):
            logger.warning(f"Tokens don't appear to be real Google OAuth tokens for {user_email}")
            # Still try to use them, but log the warning
        
        google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
        google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
        
        if not google_client_id or not google_client_secret:
            raise ValueError("GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET not set in environment")
        
        # Get scopes from database if stored
        # If not stored, don't specify scopes - let Google use the scopes from the original token grant
        # This prevents "invalid_scope" errors when refreshing tokens
        stored_scopes = user_doc.get("google_token_scopes")
        
        # Create credentials object
        # Note: When refreshing, Google validates that scopes match the original grant
        # If we don't know the original scopes, it's safer to not specify them
        # The refresh token contains the scope information, so Google will use those
        creds_kwargs = {
            "token": access_token,
            "refresh_token": refresh_token,
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": google_client_id,
            "client_secret": google_client_secret,
        }
        
        # Only add scopes if we have them stored, otherwise omit to avoid scope mismatch
        if stored_scopes:
            scopes = stored_scopes if isinstance(stored_scopes, list) else [stored_scopes]
            creds_kwargs["scopes"] = scopes
        # If scopes not stored, don't specify them - the refresh token will provide the correct scopes
        
        if expires_at:
            creds_kwargs["expiry"] = datetime.utcfromtimestamp(expires_at)
        
        return Credentials(**creds_kwargs)

def get_google_drive_service(user_email: str):
    """
    Get Google Drive API service for a user.
    
    Args:
        user_email: User's email address
        
    Returns:
        Google Drive API service object
    """
    creds = get_user_google_credentials(user_email)
    return build("drive", "v3", credentials=creds)

def validate_google_token(user_email: str) -> bool:
    """
    Validate that a user's Google token is still valid.
    
    Args:
        user_email: User's email address
        
    Returns:
        True if token is valid, False otherwise
    """
    try:
        service = get_google_drive_service(user_email)
        about = service.about().get(fields="user").execute()
        logger.info(f"Token validated for {user_email} (Google account: {about.get('user', {}).get('emailAddress')})")
        return True
    except google.auth.exceptions.RefreshError as e:
        error_str = str(e)
        if 'invalid_grant' in error_str or 'invalid_scope' in error_str:
            error_msg = f"Google OAuth token error: {error_str}"
            logger.error(f"Google refresh token error for {user_email}: {e}")
            # Mark token as invalid in database
            _mark_token_invalid(user_email, error_msg)
        return False
    except Exception as e:
        logger.error(f"Error validating token for {user_email}: {e}")
        return False

def _mark_token_invalid(user_email: str, error_msg: str):
    """Mark a user's Google refresh token as invalid in the database."""
    config = get_config()
    db_name = config.database.db_name
    
    with mongo_collection_by_type_context('user_profile') as collection:
        collection.update_one(
            {"email": user_email},
            {"$set": {
                "google_refresh_token_invalid": True,
                "google_token_error": error_msg,
                "google_token_error_timestamp": datetime.utcnow()
            }}
        )
        logger.warning(f"Marked refresh token invalid for {user_email}: {error_msg}")

