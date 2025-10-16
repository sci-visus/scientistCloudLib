# ScientistCloud Library (SCLib) 2.0

The ScientistCloud Library is a comprehensive system for scientific data processing, visualization, and collaboration. This version 2.0 includes enhanced authentication, modern APIs, and improved scalability.

## 🚀 **Quick Start**

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- MongoDB (cloud or local)

### Start Services

```bash
# Navigate to Docker directory
cd /Users/amygooch/GIT/ScientistCloud_2.0/scientistCloudLib/Docker

# Start all services (auth + upload + database)
./start.sh up

# Verify services are running
curl http://localhost:8001/health  # Authentication service
curl http://localhost:5001/health  # Upload service
```

### Quick Upload Example

```bash
# 1. Login to get JWT token
TOKEN=$(curl -s -X POST "http://localhost:8001/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com"}' | \
     jq -r '.data.access_token')

# 2. Upload file with authentication
curl -X POST "http://localhost:5001/api/upload/upload" \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@/path/to/your/file.tiff" \
     -F "dataset_name=My Dataset" \
     -F "sensor=TIFF"

# 3. Check upload status
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:5001/api/upload/status/JOB_ID"
```

## 📁 **Library Structure**

```
scientistCloudLib/
├── SCLib_Auth/              # 🔐 Authentication & Authorization
│   ├── SCLib_AuthManager.py     # Core authentication logic
│   ├── SCLib_JWTManager.py      # JWT token management
│   ├── SCLib_UserManager.py     # User profile management
│   ├── SCLib_AuthMiddleware.py  # FastAPI authentication middleware
│   └── SCLib_AuthAPI.py         # Authentication API endpoints
│
├── SCLib_JobProcessing/      # 📤 Upload & Processing
│   ├── SCLib_UploadAPI_Authenticated.py  # Authenticated upload API
│   ├── SCLib_UploadClient_Unified.py     # Unified upload client
│   ├── README.md                         # Job processing documentation
│   └── README_CURL.md                    # Curl command examples
│
├── Docker/                   # 🐳 Container Orchestration
│   ├── docker-compose.yml        # Service definitions
│   ├── Dockerfile.auth           # Authentication service
│   ├── Dockerfile.fastapi        # Upload service
│   ├── start.sh                  # Service management
│   └── README_AUTHENTICATION.md  # Docker authentication guide
│
└── SCLib_TryTest/           # 🧪 Examples & Testing
    ├── test_authenticated_upload.py      # Python authentication examples
    ├── test_curl_authentication.sh       # Curl authentication examples
    ├── README_AUTHENTICATION_EXAMPLES.md # Comprehensive examples guide
    └── env.local                         # Environment configuration
```

## 🔐 **Authentication System**

### JWT Token-Based Authentication

The SCLib 2.0 uses JWT (JSON Web Token) authentication for secure access to all operations:

- **Authentication Service**: `http://localhost:8001` (Port 8001)
- **Upload Service**: `http://localhost:5001` (Port 5001)
- **Token Management**: Automatic refresh and validation
- **Secure Operations**: All uploads require valid JWT tokens

### Authentication Flow

1. **Login** → Get JWT access and refresh tokens
2. **Upload** → Use access token for authenticated operations
3. **Refresh** → Automatically refresh expired tokens
4. **Logout** → Revoke tokens and clean up session

### Python Authentication Example

```python
from SCLib_Auth import AuthenticatedUploadClient, AuthenticatedScientistCloudClient

# Initialize clients
auth_client = AuthenticatedUploadClient("http://localhost:8001", "http://localhost:5001")
upload_client = AuthenticatedScientistCloudClient(auth_client)

# Login and upload
if auth_client.login("user@example.com"):
    result = upload_client.upload_file_authenticated(
        file_path="/path/to/file.tiff",
        dataset_name="My Dataset",
        sensor="TIFF"
    )
    
    if result:
        print(f"Upload successful! Job ID: {result.job_id}")
    
    # Logout
    auth_client.logout()
```

## 📤 **Upload System**

### Unified Upload API

The SCLib 2.0 provides a unified upload API that automatically handles:

- **Small Files** (< 1GB): Direct upload
- **Large Files** (1GB - 10TB): Chunked upload with resumable transfers
- **Multiple Sources**: Local files, URLs, Google Drive, S3
- **Authentication**: JWT token-based security
- **Progress Tracking**: Real-time upload status

### Supported Upload Sources

| Source | Description | Status |
|--------|-------------|--------|
| **Local Files** | Direct file system uploads | ✅ Ready |
| **Local Directories** | Batch directory uploads | ✅ Ready |
| **URLs** | Direct links (no downloading) | ✅ Ready |
| **Google Drive** | Service account authentication | ⚠️ Requires setup |
| **S3** | AWS S3 compatible storage | ⚠️ Requires setup |

### Upload Examples

#### Python Client

```python
from SCLib_JobProcessing import ScientistCloudUploadClient

# Initialize client
client = ScientistCloudUploadClient("http://localhost:5001")

# Upload single file
result = client.upload_file(
    file_path="/path/to/file.tiff",
    user_email="user@example.com",
    dataset_name="My Dataset",
    sensor="TIFF"
)

# Upload directory
results = client.upload_directory(
    directory_path="/path/to/directory",
    user_email="user@example.com",
    dataset_name="My Dataset",
    sensor="IDX"
)
```

#### Curl Commands

```bash
# Get authentication token
TOKEN=$(curl -s -X POST "http://localhost:8001/api/auth/login" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com"}' | \
     jq -r '.data.access_token')

# Upload file
curl -X POST "http://localhost:5001/api/upload/upload" \
     -H "Authorization: Bearer $TOKEN" \
     -F "file=@/path/to/file.tiff" \
     -F "dataset_name=My Dataset" \
     -F "sensor=TIFF"

# Check status
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:5001/api/upload/status/JOB_ID"
```

## 🐳 **Docker Services**

### Service Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    ScientistCloud Docker Stack                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │    Auth    │  │   FastAPI   │  │   MongoDB   │  │  Redis  │ │
│  │  (8001)    │  │   (5001)    │  │  (27017)    │  │ (6379)  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Service Management

```bash
# Start all services
./start.sh up

# Check service status
./start.sh status

# View logs
./start.sh logs

# Stop services
./start.sh down

# Restart services
./start.sh restart
```

### Service Endpoints

| Service | Port | Description | Documentation |
|---------|------|-------------|---------------|
| **Authentication** | 8001 | JWT token management | `http://localhost:8001/docs` |
| **Upload** | 5001 | File upload processing | `http://localhost:5001/docs` |
| **MongoDB** | 27017 | Database (cloud) | - |
| **Redis** | 6379 | Session storage | - |

## 📚 **Documentation**

### Core Documentation

- **[SCLib_JobProcessing/README.md](SCLib_JobProcessing/README.md)** - Job processing system
- **[SCLib_JobProcessing/README_CURL.md](SCLib_JobProcessing/README_CURL.md)** - Curl command examples
- **[Docker/README_AUTHENTICATION.md](Docker/README_AUTHENTICATION.md)** - Docker authentication guide

### Example Documentation

- **[SCLib_TryTest/README_AUTHENTICATION_EXAMPLES.md](SCLib_TryTest/README_AUTHENTICATION_EXAMPLES.md)** - Comprehensive examples
- **[SCLib_TryTest/test_authenticated_upload.py](SCLib_TryTest/test_authenticated_upload.py)** - Python examples
- **[SCLib_TryTest/test_curl_authentication.sh](SCLib_TryTest/test_curl_authentication.sh)** - Curl examples

### API Documentation

- **Authentication API**: `http://localhost:8001/docs`
- **Upload API**: `http://localhost:5001/docs`

## 🛠️ **Configuration**

### Environment Variables

The system uses environment variables for configuration. Key settings include:

```bash
# JWT Configuration
SECRET_KEY=your-secret-key
JWT_EXPIRY_HOURS=24
REFRESH_TOKEN_EXPIRY_DAYS=30

# Database Configuration
MONGO_URL=mongodb://admin:password@mongodb:27017/SCLib_Test
DB_NAME=SCLib_Test

# Service Configuration
AUTH_HOST=0.0.0.0
AUTH_PORT=8001
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=5001
```

### Environment Files

- **`Docker/docker.env.template`** - Template for Docker configuration
- **`SCLib_TryTest/env.local`** - Local development configuration

## 🚀 **Getting Started**

### 1. Start Services

```bash
cd /Users/amygooch/GIT/ScientistCloud_2.0/scientistCloudLib/Docker
./start.sh up
```

### 2. Test Authentication

```bash
# Test auth service
curl http://localhost:8001/health

# Test upload service
curl http://localhost:5001/health
```

### 3. Run Examples

```bash
# Python examples
cd /Users/amygooch/GIT/ScientistCloud_2.0/SCLib_TryTest
python test_authenticated_upload.py

# Curl examples
./test_curl_authentication.sh
```

### 4. View Documentation

- **Authentication API**: `http://localhost:8001/docs`
- **Upload API**: `http://localhost:5001/docs`

## 🔧 **Development**

### Adding New Features

1. **Authentication**: Add to `SCLib_Auth/`
2. **Upload Processing**: Add to `SCLib_JobProcessing/`
3. **Docker Services**: Update `Docker/docker-compose.yml`
4. **Examples**: Add to `SCLib_TryTest/`

### Testing

```bash
# Run authentication tests
python SCLib_TryTest/test_authenticated_upload.py

# Run curl tests
./SCLib_TryTest/test_curl_authentication.sh

# Check service health
curl http://localhost:8001/health
curl http://localhost:5001/health
```

## 🚨 **Troubleshooting**

### Common Issues

1. **Services not starting**
   ```bash
   # Check Docker status
   docker-compose ps
   
   # View logs
   ./start.sh logs
   ```

2. **Authentication failures**
   ```bash
   # Check auth service
   curl http://localhost:8001/health
   
   # Test login
   curl -X POST "http://localhost:8001/api/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"email": "test@example.com"}'
   ```

3. **Upload failures**
   ```bash
   # Check upload service
   curl http://localhost:5001/health
   
   # Test with authentication
   TOKEN=$(curl -s -X POST "http://localhost:8001/api/auth/login" \
        -H "Content-Type: application/json" \
        -d '{"email": "test@example.com"}' | \
        jq -r '.data.access_token')
   
   curl -H "Authorization: Bearer $TOKEN" \
        "http://localhost:5001/api/auth/status"
   ```

## 📞 **Support**

For issues and questions:

1. Check the logs: `./start.sh logs`
2. Verify configuration: `docker-compose config`
3. Test individual services: `curl http://localhost:8001/health`
4. Check database connectivity
5. Verify environment variables

## 🎯 **Next Steps**

1. **Explore Examples**: Start with `SCLib_TryTest/` examples
2. **Read Documentation**: Review the comprehensive guides
3. **Test Authentication**: Try the authentication workflow
4. **Upload Data**: Use the unified upload API
5. **Integrate**: Use the patterns in your applications

The ScientistCloud Library 2.0 is now ready for production use with comprehensive authentication, modern APIs, and scalable architecture!
