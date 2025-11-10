# SCLib Sharing and Team Management API

This module provides API endpoints for team creation and dataset sharing functionality.

## Features

- **Team Management**: Create, update, and list teams
- **User Sharing**: Share datasets with individual users by email
- **Team Sharing**: Share datasets with teams
- **Unsharing**: Remove sharing permissions

## API Endpoints

### Team Management

#### Create Team
```
POST /api/v1/teams?owner_email={email}
```

Request body:
```json
{
  "team_name": "My Team",
  "emails": ["user1@example.com", "user2@example.com"],
  "parents": []  // Optional: parent team UUIDs
}
```

#### Get Team
```
GET /api/v1/teams/{team_uuid}?user_email={email}
```

#### Update Team
```
PUT /api/v1/teams/{team_uuid}?user_email={email}
```

Request body (all fields optional):
```json
{
  "team_name": "Updated Team Name",
  "emails": ["user1@example.com", "user2@example.com", "user3@example.com"],
  "parents": []
}
```

#### List User Teams
```
GET /api/v1/teams/by-user?user_email={email}
```

### Dataset Sharing

#### Share with User
```
POST /api/v1/share/user?owner_email={email}
```

Request body:
```json
{
  "dataset_uuid": "dataset-uuid-here",
  "user_email": "user@example.com",
  "google_drive_link": ""  // Optional
}
```

#### Share with Team
```
POST /api/v1/share/team?owner_email={email}
```

Request body:
```json
{
  "dataset_uuid": "dataset-uuid-here",
  "team_name": "My Team",
  "team_uuid": "team-uuid-here",  // Optional, will be looked up if not provided
  "google_drive_link": ""  // Optional
}
```

#### Unshare Dataset
```
POST /api/v1/share/unshare?owner_email={email}
```

Request body:
```json
{
  "dataset_uuid": "dataset-uuid-here",
  "user_email": "user@example.com"  // For user unsharing
}
```

OR

```json
{
  "dataset_uuid": "dataset-uuid-here",
  "team_name": "My Team"  // For team unsharing
}
```

#### List Shared Datasets for User
```
GET /api/v1/share/user/{user_email}
```

#### List Team Datasets
```
GET /api/v1/share/team/{team_name}
```

## MongoDB Collections

### teams
- `uuid`: Unique team identifier
- `team_name`: Team name (string)
- `owner`: Owner email
- `emails`: Array of member email addresses
- `parents`: Array of parent team UUIDs
- `created_at`: Creation timestamp

### shared_user
- `uuid`: Dataset UUID
- `user`: User email
- `user_uuid`: Generated UUID for the share record
- `google_drive_link`: External storage link (if applicable)

### shared_team
- `uuid`: Dataset UUID
- `team`: Team name (string, not UUID)
- `team_uuid`: Team UUID
- `google_drive_link`: External storage link (if applicable)

### visstoredatas
- `team_uuid`: Stores team name (string), not UUID

## Usage Examples

### Python

```python
import requests

# Create a team
response = requests.post(
    "http://localhost:5003/api/v1/teams?owner_email=owner@example.com",
    json={
        "team_name": "My Team",
        "emails": ["user1@example.com", "user2@example.com"]
    }
)

# Share dataset with user
response = requests.post(
    "http://localhost:5003/api/v1/share/user?owner_email=owner@example.com",
    json={
        "dataset_uuid": "dataset-uuid",
        "user_email": "user@example.com"
    }
)

# Share dataset with team
response = requests.post(
    "http://localhost:5003/api/v1/share/team?owner_email=owner@example.com",
    json={
        "dataset_uuid": "dataset-uuid",
        "team_name": "My Team"
    }
)
```

### Curl

```bash
# Create team
curl -X POST "http://localhost:5003/api/v1/teams?owner_email=owner@example.com" \
     -H "Content-Type: application/json" \
     -d '{
       "team_name": "My Team",
       "emails": ["user1@example.com", "user2@example.com"]
     }'

# Share with user
curl -X POST "http://localhost:5003/api/v1/share/user?owner_email=owner@example.com" \
     -H "Content-Type: application/json" \
     -d '{
       "dataset_uuid": "dataset-uuid",
       "user_email": "user@example.com"
     }'

# Share with team
curl -X POST "http://localhost:5003/api/v1/share/team?owner_email=owner@example.com" \
     -H "Content-Type: application/json" \
     -d '{
       "dataset_uuid": "dataset-uuid",
       "team_name": "My Team"
     }'
```

## Notes

- Team names must be unique
- Only dataset owners can share/unshare datasets
- Only team owners can update teams
- The `team_uuid` field in `visstoredatas` actually stores the team name (string), not the UUID
- When sharing with a team, the dataset's `team_uuid` field is automatically updated

