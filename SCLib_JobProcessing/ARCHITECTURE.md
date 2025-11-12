# ScientistCloud Job Processing Architecture

## Core Principle: Status-Based Processing (No Jobs Collection)

**All job processing revolves around dataset status in `visstoredatas` collection.**

- **No separate jobs collection needed** - dataset status is the source of truth
- **Job Processing Layer**: Queries `visstoredatas` directly by `status` field
- **UI/Portal Layer**: Filters by `user_email` for display purposes only
- **Background Service**: Processes all datasets regardless of user

## Simplified Architecture

### 1. Dataset Status Management (UUID-Based)

**Location**: `SCLib_UploadProcessor._update_dataset_status()`

When a dataset needs conversion:
```python
# Set status to "conversion queued" - that's it!
collection.update_one(
    {'uuid': dataset_uuid},
    {'$set': {'status': 'conversion queued'}}
)
```

**Key Points**:
- No job creation needed - just update dataset status
- Status field in `visstoredatas` is the single source of truth
- Simple and direct - no intermediate job records

### 2. Job Processing (Status-Based Query)

**Location**: `SCLib_BackgroundService._process_jobs()`

```python
# Query datasets directly by status - NO jobs collection needed
datasets_to_convert = datasets_collection.find({
    'status': 'conversion queued'  # ← Direct status query
}).limit(1)

dataset = next(datasets_to_convert, None)
if dataset:
    self._process_dataset_conversion(dataset)
```

**Key Points**:
- Background service queries `visstoredatas` collection directly
- Finds datasets with `status: 'conversion queued'`
- No user filtering - processes all datasets regardless of user
- Updates dataset status directly: `conversion queued` → `converting` → `done`

### 3. Conversion Processing (Direct Dataset Processing)

**Location**: `SCLib_BackgroundService._process_dataset_conversion()`

```python
# Process dataset directly - no job wrapper
dataset_uuid = dataset['uuid']
sensor = dataset.get('sensor', 'OTHER')

# Update status to "converting"
datasets_collection.update_one(
    {'uuid': dataset_uuid},
    {'$set': {'status': 'converting'}}
)

# Run conversion
result = self._handle_dataset_conversion_direct(...)

# Update status to "done"
datasets_collection.update_one(
    {'uuid': dataset_uuid},
    {'$set': {'status': 'done'}}
)
```

**Key Points**:
- Processes dataset directly from `visstoredatas` collection
- Updates status in place: `conversion queued` → `converting` → `done`
- No intermediate job records needed

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
2. Upload completes → Sets dataset `status: 'conversion queued'` (no job creation)
3. Background service → Queries `visstoredatas` for `status: 'conversion queued'`
4. Background service → Processes dataset directly and updates status

### Conversion Processing Flow:
1. Background service queries: `datasets_collection.find({'status': 'conversion queued'})`
2. Gets dataset → Contains all needed info (uuid, sensor, paths)
3. Updates status: `conversion queued` → `converting`
4. Runs conversion script
5. Updates status: `converting` → `done` (or `conversion failed` on error)

## Important Distinctions

### No Jobs Collection Needed
- **Simplified Architecture**: Dataset status in `visstoredatas` is the source of truth
- **No intermediate records**: No need to create/update/delete job records
- **Direct processing**: Background service queries datasets directly by status

### Datasets Collection (`visstoredatas`)
- **Primary Key**: `uuid`
- **Status Field**: `status` - values: `uploading`, `conversion queued`, `converting`, `done`, `conversion failed`
- **User Field**: `user` (email) - for UI filtering only
- **Status updates**: Use `uuid`, not user email

### UI Queries
- Filter by `user_email` to show user's datasets
- Query by `status` to show conversion progress
- This is **presentation layer only**
- Does not restrict job processing

## Status Transitions

```
uploading → conversion queued → converting → done
                              ↓
                         conversion failed
```

- **uploading**: Files are being uploaded
- **conversion queued**: Upload complete, waiting for conversion
- **converting**: Conversion in progress
- **done**: Conversion complete
- **conversion failed**: Conversion failed after max retries

## Verification

To verify the architecture is correct:

1. **Check dataset status update**:
   ```python
   # Should set status directly, no job creation
   collection.update_one(
       {'uuid': dataset_uuid},
       {'$set': {'status': 'conversion queued'}}
   )
   ```

2. **Check background service query**:
   ```python
   # Should query visstoredatas directly by status
   datasets = datasets_collection.find({'status': 'conversion queued'})
   ```

3. **Check dataset updates**:
   ```python
   # Should use uuid, not user_email
   collection.update_one({"uuid": dataset_uuid}, {"$set": {"status": "done"}})
   ```

## Summary

✅ **Simplified Architecture**: No jobs collection - dataset status is source of truth  
✅ **Direct Processing**: Background service queries `visstoredatas` by status  
✅ **UUID-Based**: All processing uses `dataset_uuid`, not user email  
✅ **Status-Driven**: Status transitions: `conversion queued` → `converting` → `done`  
✅ **UI Layer**: User-filtered for display, doesn't affect processing  
✅ **Background Service**: Processes all datasets regardless of user

