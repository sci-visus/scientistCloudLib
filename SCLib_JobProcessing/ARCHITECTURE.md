# ScientistCloud Job Processing Architecture

## Core Principle: UUID-Based Job Processing

**All job processing revolves around dataset UUID, not user email.**

- **Job Processing Layer**: Works exclusively with `dataset_uuid`
- **UI/Portal Layer**: Filters by `user_email` for display purposes only
- **Background Service**: Processes all jobs regardless of user

## Architecture Layers

### 1. Job Creation (UUID-Based)

**Location**: `SCLib_JobQueueManager.create_job()`

```python
job = {
    'job_id': str(uuid.uuid4()),
    'dataset_uuid': dataset_uuid,  # ← Primary identifier
    'job_type': job_type,
    'status': 'pending',
    'parameters': {...}  # Job-specific parameters (no user_email)
}
```

**Key Points**:
- Jobs are created with `dataset_uuid` only
- No `user_email` field in job documents
- Jobs are not restricted to any user

### 2. Job Processing (UUID-Based)

**Location**: `SCLib_BackgroundService._process_jobs()`

```python
# Get next job - NO user filtering
job = self.job_queue.get_next_job(self.worker_id)
```

**Key Points**:
- `get_next_job()` queries by `status: 'pending'` only
- No user filtering in job retrieval
- Background service processes all jobs regardless of user

### 3. Dataset Management (UUID-Based)

**Location**: `SCLib_UploadProcessor._create_conversion_job()`

```python
job_id = job_queue.create_job(
    dataset_uuid=dataset_uuid,  # ← Uses UUID only
    job_type='dataset_conversion',
    parameters={
        'input_path': input_path,
        'output_path': output_path,
        'sensor_type': sensor,
        # No user_email in parameters
    }
)
```

**Key Points**:
- Conversion jobs use `dataset_uuid` to identify the dataset
- Job parameters contain paths and sensor type, not user info
- Jobs can process datasets from any user

### 4. UI/Portal Layer (User-Filtered)

**Location**: `SC_Web/api/jobs.php`

```php
// UI filters by user_email for display only
$datasets = $datasets_collection->find([
    '$or' => [
        ['user' => $userEmail],
        ['user_id' => $userEmail]
    ],
    'status' => ['$in' => ['conversion queued', 'converting']]
]);
```

**Key Points**:
- UI queries filter by `user_email` to show user's datasets
- This is for **display purposes only**
- Does not affect job processing

## Data Flow

### Upload Flow:
1. User uploads file → Creates dataset entry with `uuid` and `user` fields
2. Upload completes → Creates conversion job with `dataset_uuid` only
3. Background service → Picks up job by `dataset_uuid` (no user filtering)
4. Job processes → Updates dataset status by `uuid`

### Job Processing Flow:
1. Background service calls `get_next_job()` → Returns any pending job
2. Job contains `dataset_uuid` → Used to find dataset in `visstoredatas`
3. Dataset lookup → `collection.find_one({"uuid": dataset_uuid})`
4. Process job → Update dataset status by `uuid`

## Important Distinctions

### Jobs Collection (`jobs`)
- **Primary Key**: `dataset_uuid`
- **No user filtering** in job processing
- Jobs are processed by UUID, not user

### Datasets Collection (`visstoredatas`)
- **Primary Key**: `uuid`
- **User Field**: `user` (email) - for UI filtering only
- Status updates use `uuid`, not user email

### UI Queries
- Filter by `user_email` to show user's datasets
- This is **presentation layer only**
- Does not restrict job processing

## Verification

To verify the architecture is correct:

1. **Check job creation**:
   ```python
   # Should only have dataset_uuid, no user_email
   job = job_queue.create_job(dataset_uuid="...", ...)
   ```

2. **Check job retrieval**:
   ```python
   # Should not filter by user
   job = job_queue.get_next_job(worker_id)
   ```

3. **Check dataset updates**:
   ```python
   # Should use uuid, not user_email
   collection.update_one({"uuid": dataset_uuid}, {...})
   ```

## Summary

✅ **Job Processing**: UUID-based, no user restrictions  
✅ **Dataset Management**: UUID-based, user field for UI only  
✅ **UI Layer**: User-filtered for display, doesn't affect processing  
✅ **Background Service**: Processes all jobs regardless of user

