# SCLib Authentication System

A standalone authentication and authorization system for ScientistCloud, completely independent of Bokeh authorization and other SCLib components.

## Features

- **Standalone Operation**: No dependencies on other SCLib components
- **JWT Token Management**: Secure token creation, validation, and refresh
- **MongoDB Integration**: User profiles and token storage in MongoDB
- **Auth0 Ready**: Prepared for Auth0 integration (optional)
- **FastAPI Based**: Modern, fast, and well-documented API
- **Token Storage**: Secure token storage in user profiles
- **Multi-device Support**: Track and manage tokens across devices

## Quick Start

### 1. Environment Setup

Create an `env.local` file with the following variables:

```bash
# MongoDB Configuration
MONGO_URL="mongodb+srv://username:password@cluster.mongodb.net/database?retryWrites=true&w=majority"
DB_NAME="SCLib_Test"

# JWT Configuration
SECRET_KEY="your-super-secret-jwt-key-change-in-production"
JWT_EXPIRY_HOURS=24
REFRESH_TOKEN_EXPIRY_DAYS=30

# Auth0 Configuration (Optional)
AUTH0_DOMAIN="your-domain.auth0.com"
AUTHO_CLIENT_ID="your-client-id"
AUTHO_CLIENT_SECRET="your-client-secret"
AUTH0_AUDIENCE="your-api-audience"

# SCLib Environment Variables (Optional)
SCLIB_HOME="/path/to/parentOf/SCLib_Auth"
SCLIB_MYTEST="/path/to/SCLib_TryTest"
```

### 2. Install Dependencies

```bash
pip install fastapi uvicorn pymongo python-jose[cryptography] python-multipart
```

### 3. Start the Authentication Server

```bash
# Option 1: Auto-detect environment file
cd ${SCLIB_HOME}/SCLib_Auth
python start_auth_server.py --port 8001

# Option 2: Specify environment file
python start_auth_server.py --port 8001 --env-file /path/to/env.local

# Option 3: Development mode with auto-reload
python start_auth_server.py --port 8001 --reload
```

### 4. Access the API

- **API Documentation**: http://localhost:8001/docs
- **Health Check**: http://localhost:8001/health
- **API Root**: http://localhost:8001/

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/auth/login` | Login with email/password |
| `POST` | `/api/auth/refresh` | Refresh access token |
| `POST` | `/api/auth/logout` | Logout and revoke tokens |
| `GET` | `/api/auth/me` | Get current user info |
| `GET` | `/api/auth/status` | Check authentication status |
| `GET` | `/api/auth/authorize` | Get Auth0 authorization URL |

### Example Usage

#### Login

```bash
curl -X POST "http://localhost:8001/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "optional-password"
  }'
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

#### Get User Info

```bash
curl -X GET "http://localhost:8001/api/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

#### Refresh Token

```bash
curl -X POST "http://localhost:8001/api/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "YOUR_REFRESH_TOKEN"
  }'
```

#### Logout

```bash
curl -X POST "http://localhost:8001/api/auth/logout" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "YOUR_ACCESS_TOKEN"
  }'
```

## MongoDB Schema

### User Profiles Collection (`user_profile`)

```json
{
  "_id": ObjectId("..."),
  "user_id": "user_abc123",
  "email": "user@example.com",
  "name": "User Name",
  "picture": "https://example.com/avatar.jpg",
  "email_verified": true,
  "created_at": "2024-01-01T00:00:00Z",
  "last_login": "2024-01-01T12:00:00Z",
  "last_activity": "2024-01-01T12:30:00Z",
  "is_active": true,
  "auth0_metadata": {
    "auth0_user_id": "auth0|123456789",
    "last_sync": "2024-01-01T12:00:00Z"
  },
  "access_tokens": [
    {
      "token_id": "token_abc123",
      "token_type": "access",
      "token_hash": "sha256_hash_of_token",
      "created_at": "2024-01-01T12:00:00Z",
      "expires_at": "2024-01-02T12:00:00Z",
      "is_revoked": false,
      "last_used": "2024-01-01T12:30:00Z"
    }
  ],
  "refresh_tokens": [
    {
      "token_id": "refresh_abc123",
      "token_type": "refresh",
      "token_hash": "sha256_hash_of_token",
      "created_at": "2024-01-01T12:00:00Z",
      "expires_at": "2024-01-31T12:00:00Z",
      "is_revoked": false,
      "last_used": "2024-01-01T12:30:00Z"
    }
  ],
  "preferences": {
    "theme": "dark",
    "notifications": true
  }
}
```

## Integration with Other SCLib Components

### Using in SCLib_JobProcessing

```python
from SCLib_Auth import auth_api_app
from fastapi import FastAPI

# Create main app
app = FastAPI()

# Include authentication routes
app.include_router(auth_api_app.router, prefix="/auth")

# Your other routes...
@app.get("/api/upload")
async def upload_file(token: str = Depends(get_current_user)):
    # This endpoint now requires authentication
    pass
```

### Using in Other Services

```python
import requests

# Login to get token
login_response = requests.post("http://localhost:8001/api/auth/login", json={
    "email": "user@example.com"
})

token = login_response.json()["data"]["access_token"]

# Use token for authenticated requests
headers = {"Authorization": f"Bearer {token}"}
response = requests.get("http://localhost:8001/api/auth/me", headers=headers)
```

## Security Features

- **JWT Tokens**: Secure, stateless authentication
- **Token Hashing**: Tokens are hashed before storage in MongoDB
- **Token Expiration**: Configurable token expiry times
- **Token Revocation**: Ability to revoke individual or all tokens
- **CORS Support**: Configurable cross-origin resource sharing
- **Input Validation**: Pydantic models for request/response validation

## Development

### Running Tests

```bash
# Install test dependencies
pip install pytest httpx

# Run tests
pytest tests/
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MONGO_URL` | MongoDB connection string | Required |
| `DB_NAME` | Database name | Required |
| `SECRET_KEY` | JWT secret key | Required |
| `JWT_EXPIRY_HOURS` | Access token expiry in hours | 24 |
| `REFRESH_TOKEN_EXPIRY_DAYS` | Refresh token expiry in days | 30 |
| `AUTH0_DOMAIN` | Auth0 domain (optional) | - |
| `AUTHO_CLIENT_ID` | Auth0 client ID (optional) | - |
| `AUTHO_CLIENT_SECRET` | Auth0 client secret (optional) | - |
| `AUTH0_AUDIENCE` | Auth0 API audience (optional) | - |

## Production Deployment

### Using Gunicorn

```bash
gunicorn SCLib_AuthAPI_Standalone:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001
```

### Using Docker

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8001

CMD ["python", "start_auth_server.py", "--host", "0.0.0.0", "--port", "8001"]
```

### Environment Security

- Use strong, unique `SECRET_KEY` values
- Enable MongoDB authentication
- Use HTTPS in production
- Configure proper CORS origins
- Set up proper firewall rules
- Monitor token usage and revoke suspicious tokens

## Troubleshooting

### Common Issues

1. **MongoDB Connection Failed**
   - Check `MONGO_URL` format
   - Verify network connectivity
   - Check MongoDB authentication

2. **JWT Token Invalid**
   - Verify `SECRET_KEY` is consistent
   - Check token expiration
   - Ensure proper token format

3. **Environment Variables Not Loaded**
   - Check `env.local` file path
   - Verify file permissions
   - Use `--env-file` argument

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python start_auth_server.py --port 8001 --reload
```

## License

This authentication system is part of the ScientistCloud project.
