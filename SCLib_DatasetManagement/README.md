# SCLib Dataset Management API

Enhanced dataset management API with user-friendly identifiers and comprehensive operations.

## Features

- **User-Friendly Identifiers**: Support for UUID, name, slug, and numeric ID
- **Complete CRUD Operations**: Create, read, update, and delete datasets
- **File Management**: Add, list, remove, and replace files in datasets
- **Settings Management**: Update dataset settings individually or in bulk
- **Size & Billing**: Track dataset size and storage costs
- **Storage Overview**: User and team storage usage tracking

## API Endpoints

### Dataset CRUD

- `GET /api/v1/datasets` - List datasets with filtering
- `POST /api/v1/datasets` - Create new dataset
- `GET /api/v1/datasets/{identifier}` - Get dataset by any identifier
- `PUT /api/v1/datasets/{identifier}` - Update dataset
- `DELETE /api/v1/datasets/{identifier}` - Delete dataset

### Dataset Status & Conversion

- `GET /api/v1/datasets/{identifier}/status` - Get processing status
- `POST /api/v1/datasets/{identifier}/convert` - Trigger conversion

### File Management

- `POST /api/v1/datasets/{identifier}/files` - Add files to dataset
- `GET /api/v1/datasets/{identifier}/files` - List files in dataset
- `DELETE /api/v1/datasets/{identifier}/files/{file_id}` - Remove file
- `PUT /api/v1/datasets/{identifier}/files` - Replace all files

### Settings Management

- `PUT /api/v1/datasets/{identifier}/settings` - Update settings (bulk)
- `GET /api/v1/datasets/{identifier}/settings` - Get settings
- `PATCH /api/v1/datasets/{identifier}/settings/{setting_name}` - Update specific setting

### Size & Billing

- `GET /api/v1/datasets/{identifier}/size` - Get size and billing info
- `GET /api/v1/user/storage` - User storage overview
- `GET /api/v1/teams/{team_uuid}/storage` - Team storage overview

## Identifier Types

All endpoints support flexible identifier resolution:

- **UUID**: `550e8400-e29b-41d4-a716-446655440000`
- **Name**: `my-dataset-name` (if unique)
- **Slug**: `my-dataset-name-2024` (human-readable, unique)
- **Numeric ID**: `12345` (short numeric ID)

## Examples

### Create Dataset

```bash
curl -X POST "http://localhost:5002/api/v1/datasets?user_email=user@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My 4D Dataset",
    "sensor": "4D_Probe",
    "description": "4D probe data",
    "tags": "probe, 4d, experiment"
  }'
```

### Get Dataset by Slug

```bash
curl "http://localhost:5002/api/v1/datasets/my-4d-dataset-2024"
```

### Update Dataset Settings

```bash
curl -X PUT "http://localhost:5002/api/v1/datasets/my-4d-dataset-2024/settings?user_email=user@example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Name",
    "tags": "updated, tags"
  }'
```

### Add Files to Dataset

```bash
curl -X POST "http://localhost:5002/api/v1/datasets/my-4d-dataset-2024/files" \
  -F "files=@data.idx" \
  -F "files=@metadata.json" \
  -F "user_email=user@example.com"
```

### Get Dataset Size

```bash
curl "http://localhost:5002/api/v1/datasets/my-4d-dataset-2024/size"
```

### Get User Storage

```bash
curl "http://localhost:5002/api/v1/user/storage?user_email=user@example.com"
```

## Running the Server

```bash
python SCLib_DatasetManagement/SCLib_DatasetAPI.py
```

Or integrate into existing FastAPI server:

```python
from SCLib_DatasetManagement import dataset_api_app
app.mount("/dataset-api", dataset_api_app)
```

## Integration

This module integrates with:
- `SCLib_JobProcessing` - For dataset processing and uploads
- `SCLib_Auth` - For user authentication
- MongoDB `visstoredatas` collection - For dataset storage
- MongoDB `user_profile` collection - For user information



