# Add is_downloadable Field Migration Script

**Location:** `scientistCloudLib/SCLib_Maintenance/add_is_downloadable_field.py`

This script adds the `is_downloadable` field to all existing datasets in the `visstoredatas` collection that don't already have it, setting the default value to `"only owner"`.

## Purpose

The `is_downloadable` field controls who can download a dataset:
- `"only owner"` - Only the dataset owner can download (default)
- `"only team"` - Only team members can download
- `"public"` - Anyone can download

This migration ensures all existing datasets have this field set, maintaining backward compatibility.

## Requirements

- Python 3.6+
- pymongo library: `pip install pymongo`
- MongoDB connection (via MONGO_URL environment variable)

## Environment Variables

Required:
- `MONGO_URL`: MongoDB connection string
- `DB_NAME`: Database name

## Usage

### Dry Run (Recommended First Step)

Test the migration without making changes:

```bash
export MONGO_URL="mongodb://user:pass@host:port/db"
export DB_NAME="your_database_name"

python add_is_downloadable_field.py --dry-run
```

### Run the Migration

Once you've verified the dry run looks correct:

```bash
python add_is_downloadable_field.py
```

### Update Specific Dataset

Update only a specific dataset by UUID:

```bash
python add_is_downloadable_field.py --uuid abc-123-def-456
```

### Verbose Logging

Get more detailed output:

```bash
python add_is_downloadable_field.py --log-level DEBUG
```

## What It Does

1. Connects to MongoDB using the `MONGO_URL` environment variable
2. Finds all datasets in the `visstoredatas` collection that don't have the `is_downloadable` field (or have it set to `None`)
3. Updates those datasets to set `is_downloadable` to `"only owner"`
4. Also updates the `date_updated` field to the current timestamp

## Safety Features

- **Idempotent**: Safe to run multiple times - only updates datasets that don't have the field
- **Dry Run Mode**: Test before applying changes
- **UUID Filter**: Update specific datasets for testing
- **Comprehensive Logging**: All actions are logged to both console and log file

## Log File

The script creates a log file at:
```
scientistCloudLib/SCLib_Maintenance/add_is_downloadable_field.log
```

## Example Output

```
============================================================
Migration: Add is_downloadable Field to Datasets
============================================================
Default value: only owner
Dry run: False

✅ Successfully connected to MongoDB
Found 42 dataset(s) that need the is_downloadable field
✅ Updated 42 dataset(s)

============================================================
Summary
============================================================
Total datasets found: 42
Updated: 42
Skipped: 0
Errors: 0

✅ Migration completed successfully!
```

## Backward Compatibility

The codebase has been updated to handle datasets without the `is_downloadable` field:
- When retrieving datasets, if the field is missing, it defaults to `"only owner"`
- This ensures the system works correctly even if the migration hasn't been run yet

However, it's recommended to run this migration to ensure all datasets have the field explicitly set in the database.

## Related Changes

This migration is part of adding the `is_downloadable` feature to the system. Other changes include:
- Added `is_downloadable` field to upload forms
- Added `is_downloadable` field to dataset details edit form
- Updated API endpoints to accept and save `is_downloadable`
- Updated dataset retrieval to default to `"only owner"` if field is missing

