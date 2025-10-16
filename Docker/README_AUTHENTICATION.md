# SCLib Authentication Service - Docker Integration

This guide explains how to use the integrated SCLib authentication service within the existing Docker infrastructure.

## Overview

The authentication service is now integrated into the main ScientistCloud Docker setup, providing:

- **🔐 JWT Token Management**: Secure token creation and validation
- **👤 User Profile Storage**: MongoDB-based user profiles with token tracking
- **🌐 FastAPI Integration**: RESTful API for authentication
- **🐳 Docker Integration**: Seamless integration with existing Docker infrastructure
- **🔄 Shared Configuration**: Uses the same environment variables and database

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ScientistCloud Docker Stack                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │    Auth    │  │   FastAPI   │  │   MongoDB   │  │  Redis  │ │
│  │  (8001)    │  │   (5001)    │  │  (27017)    │  │ (6379)  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────┐
                    │   Shared MongoDB    │
                    │  (User Profiles +   │
                    │   Job Processing)   │
                    └─────────────────────┘
```

## Quick Start

### 1. Configure Environment

Copy and customize the environment template:

```bash
cd /path/to/SCLib/Docker
cp docker.env.template docker.env
```

Edit `docker.env` and set your configuration:

```bash
# JWT Configuration
SECRET_KEY=your-secret-key-change-in-production-make-it-long-and-random
JWT_EXPIRY_HOURS=24
REFRESH_TOKEN_EXPIRY_DAYS=30

# Database Configuration (shared with main app)
MONGO_URL=mongodb://admin:password@mongodb:27017/SCLib_Test?authSource=admin
DB_NAME=SCLib_Test
DB_PASS=password

# Auth0 Configuration (optional)
AUTH0_DOMAIN=your-domain.auth0.com
AUTHO_CLIENT_ID=your-client-id
AUTHO_CLIENT_SECRET=your-client-secret
AUTH0_AUDIENCE=your-api-audience
```

### 2. Start All Services

```bash
# Start all services (auth + fastapi + mongodb + redis)
./start.sh up

# Or start only specific services
./start.sh up --services auth,fastapi
```

### 3. Verify Services

```bash
# Check service status
./start.sh status

# View logs
./start.sh logs

# Test authentication service
curl http://localhost:8001/health

# Test upload service
curl http://localhost:5001/health
```

## Service Endpoints

### Authentication Service (Port 8001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/docs` | GET | API documentation |
| `/api/auth/login` | POST | Login and get JWT token |
| `/api/auth/refresh` | POST | Refresh access token |
| `/api/auth/logout` | POST | Logout and revoke tokens |
| `/api/auth/me` | GET | Get current user info |
| `/api/auth/status` | GET | Check authentication status |

### Upload Service (Port 5001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/docs` | GET | API documentation |
| `/api/upload/upload` | POST | Upload file (with auth) |
| `/api/upload/status/{job_id}` | GET | Get job status |
| `/api/upload/jobs` | GET | List user's jobs |
| `/api/auth/status` | GET | Check auth status |

## Usage Examples

### 1. Login and Get Token

```bash
# Login to get JWT token
curl -X POST "http://localhost:8001/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com"}'

# Response:
# {
#   "success": true,
#   "data": {
#     "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
#     "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
#     "expires_in": 86400,
#     "token_type": "Bearer"
#   }
# }
```

### 2. Upload File with Authentication

```bash
# Upload file with JWT token
curl -X POST "http://localhost:5001/api/upload/upload" \
     -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE" \
     -F "file=@/path/to/your/file.tiff" \
     -F "dataset_name=Test Dataset" \
     -F "sensor=TIFF" \
     -F "convert=true" \
     -F "is_public=false"
```

### 3. Check Job Status

```bash
# Check job status
curl -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE" \
     "http://localhost:5001/api/upload/status/JOB_ID"
```

### 4. List User's Jobs

```bash
# List jobs for authenticated user
curl -H "Authorization: Bearer YOUR_JWT_TOKEN_HERE" \
     "http://localhost:5001/api/upload/jobs?limit=10"
```

## Docker Commands

### Start Services

```bash
# Start all services
./start.sh up

# Start with specific environment file
./start.sh up --env-file env.production

# Start only authentication service
./start.sh up --services auth

# Start authentication and upload services
./start.sh up --services auth,fastapi
```

### Manage Services

```bash
# Stop all services
./start.sh down

# Restart services
./start.sh restart

# View logs
./start.sh logs

# Check status
./start.sh status

# Build services
./start.sh build

# Clean up (removes containers and volumes)
./start.sh clean
```

### Direct Docker Compose Commands

```bash
# Start specific services
docker-compose up -d auth fastapi

# View logs for specific service
docker-compose logs -f auth

# Rebuild and restart authentication service
docker-compose up -d --build auth

# Scale services (if needed)
docker-compose up -d --scale auth=2
```

## Configuration

### Environment Variables

The authentication service uses the same environment variables as the main application:

```bash
# JWT Configuration
SECRET_KEY=your-secret-key-change-in-production
JWT_EXPIRY_HOURS=24
REFRESH_TOKEN_EXPIRY_DAYS=30

# Database Configuration (shared)
MONGO_URL=mongodb://admin:password@mongodb:27017/SCLib_Test?authSource=admin
DB_NAME=SCLib_Test
DB_PASS=password

# Auth0 Configuration (optional)
AUTH0_DOMAIN=your-domain.auth0.com
AUTHO_CLIENT_ID=your-client-id
AUTHO_CLIENT_SECRET=your-client-secret
AUTH0_AUDIENCE=your-api-audience

# Service Configuration
AUTH_HOST=0.0.0.0
AUTH_PORT=8001
AUTH_LOG_LEVEL=info
```

### Database Collections

The authentication service uses the following MongoDB collections:

- `user_profiles`: User information and token storage
- `upload_jobs`: Upload job tracking (shared with main app)
- `datasets`: Dataset metadata (shared with main app)

## Development

### Local Development

```bash
# Start only the services you need for development
./start.sh up --services auth,fastapi

# View logs in real-time
./start.sh logs

# Rebuild after code changes
./start.sh build
```

### Testing

```bash
# Test authentication service
curl http://localhost:8001/health

# Test upload service
curl http://localhost:5001/health

# Test with authentication
TOKEN=$(curl -s -X POST "http://localhost:8001/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com"}' | \
     jq -r '.data.access_token')

curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:5001/api/auth/status"
```

## Production Deployment

### Security Considerations

1. **Set Strong SECRET_KEY**: Use a long, random secret key
2. **Use HTTPS**: Configure SSL/TLS in production
3. **Restrict CORS**: Set appropriate CORS origins
4. **Monitor Logs**: Set up log monitoring and alerting
5. **Backup Database**: Regular MongoDB backups

### Environment Configuration

```bash
# Production environment file
SECRET_KEY=your-production-secret-key-very-long-and-random
JWT_EXPIRY_HOURS=24
REFRESH_TOKEN_EXPIRY_DAYS=30
AUTH_LOG_LEVEL=warning
FASTAPI_LOG_LEVEL=warning
```

### Scaling

```bash
# Scale authentication service
docker-compose up -d --scale auth=3

# Use load balancer for multiple auth instances
# Configure nginx or similar for load balancing
```

## Troubleshooting

### Common Issues

1. **Authentication service not starting**
   ```bash
   # Check logs
   docker-compose logs auth
   
   # Check environment variables
   docker-compose config
   ```

2. **Database connection issues**
   ```bash
   # Check MongoDB connection
   docker-compose exec auth python -c "from pymongo import MongoClient; print(MongoClient('mongodb://admin:password@mongodb:27017/SCLib_Test?authSource=admin').admin.command('ping'))"
   ```

3. **Token validation failures**
   ```bash
   # Check SECRET_KEY configuration
   echo $SECRET_KEY
   
   # Verify token format
   curl -H "Authorization: Bearer YOUR_TOKEN" \
        "http://localhost:8001/api/auth/status"
   ```

### Debug Mode

```bash
# Enable debug logging
AUTH_LOG_LEVEL=debug ./start.sh up

# View detailed logs
docker-compose logs -f auth
```

### Health Checks

```bash
# Check all services
curl http://localhost:8001/health  # Auth service
curl http://localhost:5001/health  # Upload service

# Check database
docker-compose exec mongodb mongosh --eval "db.adminCommand('ping')"

# Check Redis
docker-compose exec redis redis-cli ping
```

## Integration with Existing Systems

### Web Portal Integration

The authentication service is designed to work with existing web portals:

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
        // Store token in cookie (automatically handled by middleware)
        document.cookie = `auth_token=${data.data.access_token}; path=/`;
        return data.data.access_token;
    }
}
```

### Curl Command Integration

```bash
# Complete workflow
TOKEN=$(curl -s -X POST "http://localhost:8001/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com"}' | \
     jq -r '.data.access_token')

curl -X POST "http://localhost:5001/api/upload/upload" \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@file.tiff" \
     -F "dataset_name=My Dataset" \
     -F "sensor=TIFF"
```

## Support

For issues and questions:

1. Check the logs: `./start.sh logs`
2. Verify configuration: `docker-compose config`
3. Test individual services: `curl http://localhost:8001/health`
4. Check database connectivity
5. Verify environment variables

The authentication service is now fully integrated into your existing Docker infrastructure and ready for production use!
