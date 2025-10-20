# SCLib Authentication Integration Guide

This guide explains how to use the integrated SCLib authentication system for token-based authorization in curl commands and web portal integration.

## Overview

The SCLib authentication system provides:
- **JWT Token Management**: Create, validate, and manage authentication tokens
- **User Profile Storage**: MongoDB-based user profiles with token tracking
- **FastAPI Integration**: Middleware and dependencies for authenticated endpoints
- **Curl Command Support**: Token-based authorization for command-line usage
- **Web Portal Integration**: Cookie and header-based authentication

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Auth Server   │    │  Upload Server   │    │   Web Portal    │
│   (Port 8001)   │    │   (Port 5001)    │    │   (Port 3000)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SCLib Authentication System                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ JWT Manager │  │User Manager │  │    Auth Middleware      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────┐
                    │   MongoDB Database  │
                    │  (User Profiles)    │
                    └─────────────────────┘
```

## Quick Start

### 1. Start the Authentication Server

```bash
cd /path/to/SCLib_Auth
python start_auth_server.py --port 8001
```

### 2. Start the Upload Server (with Authentication)

```bash
cd /path/to/SCLib_JobProcessing
python SCLib_UploadAPI_Authenticated.py
```

### 3. Login and Get Token

```bash
curl -X POST "http://localhost:8001/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com"}'
```

Response:
```json
{
  "success": true,
  "message": "Login successful for user@example.com",
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "expires_in": 86400,
    "token_type": "Bearer",
    "user": {
      "user_id": "user_abc123",
      "email": "user@example.com",
      "name": "user",
      "email_verified": true
    }
  }
}
```

### 4. Upload File with Authentication

```bash
curl -X POST "http://localhost:5001/api/upload/upload" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE" \
     -F "file=@/path/to/your/file.tiff" \
     -F "dataset_name=Test Dataset" \
     -F "sensor=TIFF" \
     -F "convert=true" \
     -F "is_public=false"
```

## Authentication Methods

### 1. Token-Based Authentication (Recommended)

Use JWT tokens in the `Authorization` header:

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" \
     -X POST "http://localhost:5001/api/upload/upload" \
     -F "file=@file.tiff" \
     -F "dataset_name=My Dataset"
```

### 2. Cookie-Based Authentication (Web Portal)

For web portal integration, tokens can be stored in cookies:

```javascript
// Set cookie in browser
document.cookie = "auth_token=YOUR_JWT_TOKEN; path=/";

// The middleware will automatically detect and use the cookie
```

### 3. Backward Compatibility

For backward compatibility, you can still use the `user_email` parameter:

```bash
curl -X POST "http://localhost:5001/api/upload/upload" \
     -F "file=@file.tiff" \
     -F "user_email=user@example.com" \
     -F "dataset_name=My Dataset"
```

## API Endpoints

### Authentication Server (Port 8001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Login and get JWT token |
| `/api/auth/refresh` | POST | Refresh access token |
| `/api/auth/logout` | POST | Logout and revoke tokens |
| `/api/auth/me` | GET | Get current user info |
| `/api/auth/status` | GET | Check authentication status |

### Upload Server (Port 5001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload/upload` | POST | Upload file (authenticated) |
| `/api/upload/initiate` | POST | Initiate cloud upload (authenticated) |
| `/api/upload/status/{job_id}` | GET | Get job status |
| `/api/upload/jobs` | GET | List user's jobs |
| `/api/auth/status` | GET | Check auth status on upload server |

## Python Client Usage

```python
from SCLib_Auth.example_authenticated_upload import AuthenticatedUploadClient

# Initialize client
client = AuthenticatedUploadClient(
    auth_server_url="http://localhost:8001",
    upload_server_url="http://localhost:5001"
)

# Login
login_result = client.login("user@example.com")
if login_result.get('success'):
    # Upload file
    upload_result = client.upload_file(
        file_path="/path/to/file.tiff",
        dataset_name="Test Dataset",
        sensor="TIFF"
    )
    
    # Check job status
    job_id = upload_result.get('job_id')
    status = client.get_job_status(job_id)
    
    # List jobs
    jobs = client.list_jobs(limit=10)
```

## FastAPI Integration

### Using Authentication Dependencies

```python
from fastapi import FastAPI, Depends
from SCLib_Auth import require_auth, optional_auth, get_current_user

app = FastAPI()

@app.post("/api/upload/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user)  # Requires authentication
):
    # current_user is a UserProfile object
    user_email = current_user.email
    # ... upload logic

@app.get("/api/public/status")
async def public_status(
    auth_result = Depends(optional_auth)  # Optional authentication
):
    if auth_result.is_authenticated:
        return {"status": "authenticated", "user": auth_result.user_email}
    else:
        return {"status": "public"}
```

### Setting Up Authentication Middleware

```python
from fastapi import FastAPI
from SCLib_Auth import setup_auth_middleware

app = FastAPI()

# Setup authentication middleware
setup_auth_middleware(app)

# Your endpoints will now support authentication
```

## Configuration

### Environment Variables

```bash
# JWT Configuration
SECRET_KEY=your-secret-key-change-in-production
JWT_EXPIRY_HOURS=24
REFRESH_TOKEN_EXPIRY_DAYS=30

# MongoDB Configuration
MONGO_URL=mongodb://localhost:27017
DB_NAME=SCLib_Test

# Auth0 Configuration (optional)
AUTH0_DOMAIN=your-domain.auth0.com
AUTHO_CLIENT_ID=your-client-id
AUTHO_CLIENT_SECRET=your-client-secret
AUTH0_AUDIENCE=your-api-audience
```

### Database Collections

The system uses the following MongoDB collections:
- `user_profile`: User information and token storage
- `upload_jobs`: Upload job tracking (existing)
- `datasets`: Dataset metadata (existing)

## Security Considerations

### 1. Token Security
- JWT tokens are signed with a secret key
- Tokens have expiration times (default: 24 hours)
- Refresh tokens have longer expiration (default: 30 days)
- Tokens are stored hashed in the database

### 2. Access Control
- Authenticated users can only access their own jobs
- Public datasets are accessible to everyone
- Private datasets require authentication
- Team access control can be extended

### 3. Production Deployment
- Use HTTPS in production
- Set strong SECRET_KEY
- Configure CORS appropriately
- Use environment variables for configuration
- Monitor authentication logs

## Troubleshooting

### Common Issues

1. **"No authentication token found"**
   - Check if the Authorization header is set correctly
   - Verify the token format: `Bearer YOUR_TOKEN`
   - Ensure the token hasn't expired

2. **"Token validation failed"**
   - Check if SECRET_KEY is configured correctly
   - Verify the token is valid and not corrupted
   - Check token expiration

3. **"User profile not found"**
   - User may not exist in the database
   - Check MongoDB connection
   - Verify user was created during login

4. **"Access denied to this job"**
   - User is trying to access another user's job
   - Check if the job belongs to the authenticated user

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Health Checks

Check server status:

```bash
# Authentication server
curl http://localhost:8001/health

# Upload server
curl http://localhost:5001/health

# Check auth status
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:5001/api/auth/status
```

## Migration from Existing System

### From VisusDataPortalPrivate

The new system is compatible with the existing VisusDataPortalPrivate authorization:

1. **Cookie Support**: The middleware supports the same cookie names
2. **JWT Validation**: Uses the same SECRET_KEY for token validation
3. **User Profiles**: Extends the existing user profile structure

### Migration Steps

1. **Backup existing data**
2. **Update environment variables**
3. **Deploy new authentication server**
4. **Update client applications**
5. **Test authentication flow**
6. **Monitor for issues**

## Examples

### Complete Curl Workflow

```bash
# 1. Login
TOKEN=$(curl -s -X POST "http://localhost:8001/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com"}' | \
     jq -r '.data.access_token')

# 2. Upload file
curl -X POST "http://localhost:5001/api/upload/upload" \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@/path/to/file.tiff" \
     -F "dataset_name=Test Dataset" \
     -F "sensor=TIFF"

# 3. Check status
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:5001/api/upload/status/JOB_ID"

# 4. List jobs
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:5001/api/upload/jobs?limit=10"
```

### Web Portal Integration

```javascript
// Login and store token
async function login(email) {
    const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({email: email})
    });
    
    const data = await response.json();
    if (data.success) {
        // Store token in cookie
        document.cookie = `auth_token=${data.data.access_token}; path=/`;
        return data.data.access_token;
    }
}

// Upload with authentication
async function uploadFile(file, datasetName) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('dataset_name', datasetName);
    formData.append('sensor', 'TIFF');
    
    const response = await fetch('/api/upload/upload', {
        method: 'POST',
        body: formData
        // Cookie will be sent automatically
    });
    
    return response.json();
}
```

## Support

For issues and questions:
1. Check the logs for error messages
2. Verify configuration and environment variables
3. Test with the provided examples
4. Check MongoDB connectivity
5. Verify token validity and expiration

The authentication system is designed to be robust and backward-compatible while providing modern token-based security for your ScientistCloud platform.
