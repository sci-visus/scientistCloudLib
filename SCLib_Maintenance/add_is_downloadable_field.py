#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration Script: Add is_downloadable Field to Existing Datasets
Adds the is_downloadable field to all datasets in the visstoredatas collection
that don't already have it, setting it to "only owner" as the default.

Usage:
    python add_is_downloadable_field.py [--dry-run] [--uuid UUID] [--log-level LEVEL]

Environment Variables:
    MONGO_URL: MongoDB connection string (required)
    DB_NAME: Database name (required)

This script is safe to run multiple times - it only updates datasets that don't have the field.
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from typing import Optional

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
except ImportError:
    print("ERROR: pymongo is not installed. Install it with: pip install pymongo")
    sys.exit(1)

# Configure logging
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(SCRIPT_DIR, 'add_is_downloadable_field.log')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Default value for is_downloadable
DEFAULT_IS_DOWNLOADABLE = "only owner"


def get_mongo_client():
    """Get MongoDB client from environment variables."""
    mongo_url = os.getenv('MONGO_URL')
    if not mongo_url:
        logger.error("MONGO_URL environment variable is not set")
        sys.exit(1)
    
    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
        # Test connection
        client.admin.command('ping')
        logger.info("✅ Successfully connected to MongoDB")
        return client
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"❌ Failed to connect to MongoDB: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error connecting to MongoDB: {e}")
        sys.exit(1)


def get_database_name():
    """Get database name from environment variables."""
    db_name = os.getenv('DB_NAME')
    if not db_name:
        logger.error("DB_NAME environment variable is not set")
        sys.exit(1)
    return db_name


def update_datasets(client, db_name: str, uuid_filter: Optional[str] = None, dry_run: bool = False):
    """
    Update datasets that don't have the is_downloadable field.
    
    Args:
        client: MongoDB client
        db_name: Database name
        uuid_filter: Optional UUID to update only a specific dataset
        dry_run: If True, don't actually update the database
    """
    db = client[db_name]
    collection = db['visstoredatas']
    
    # Build query - find datasets without is_downloadable field
    query = {
        '$or': [
            {'is_downloadable': {'$exists': False}},
            {'is_downloadable': None}
        ]
    }
    
    # Add UUID filter if provided
    if uuid_filter:
        query['uuid'] = uuid_filter
        logger.info(f"Filtering by UUID: {uuid_filter}")
    
    # Count datasets that need updating
    count = collection.count_documents(query)
    logger.info(f"Found {count} dataset(s) that need the is_downloadable field")
    
    if count == 0:
        logger.info("✅ All datasets already have the is_downloadable field")
        return {
            'total': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
    
    if dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made")
        # Show sample of what would be updated
        sample = list(collection.find(query).limit(5))
        logger.info(f"Sample datasets that would be updated:")
        for dataset in sample:
            logger.info(f"  - UUID: {dataset.get('uuid', 'N/A')}, Name: {dataset.get('name', 'N/A')}")
        
        return {
            'total': count,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
    
    # Update all matching datasets
    update_result = collection.update_many(
        query,
        {
            '$set': {
                'is_downloadable': DEFAULT_IS_DOWNLOADABLE,
                'date_updated': datetime.utcnow()
            }
        }
    )
    
    logger.info(f"✅ Updated {update_result.modified_count} dataset(s)")
    
    return {
        'total': count,
        'updated': update_result.modified_count,
        'skipped': count - update_result.modified_count,
        'errors': 0
    }


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Add is_downloadable field to existing datasets'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run in dry-run mode (no database changes)'
    )
    parser.add_argument(
        '--uuid',
        type=str,
        help='Update only a specific dataset by UUID'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Set logging level (default: INFO)'
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logger.setLevel(getattr(logging, args.log_level))
    
    logger.info("=" * 60)
    logger.info("Migration: Add is_downloadable Field to Datasets")
    logger.info("=" * 60)
    logger.info(f"Default value: {DEFAULT_IS_DOWNLOADABLE}")
    logger.info(f"Dry run: {args.dry_run}")
    if args.uuid:
        logger.info(f"UUID filter: {args.uuid}")
    logger.info("")
    
    # Get MongoDB connection
    client = get_mongo_client()
    db_name = get_database_name()
    
    try:
        # Update datasets
        result = update_datasets(
            client,
            db_name,
            uuid_filter=args.uuid,
            dry_run=args.dry_run
        )
        
        # Print summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("Summary")
        logger.info("=" * 60)
        logger.info(f"Total datasets found: {result['total']}")
        if not args.dry_run:
            logger.info(f"Updated: {result['updated']}")
            logger.info(f"Skipped: {result['skipped']}")
            logger.info(f"Errors: {result['errors']}")
        logger.info("")
        
        if args.dry_run:
            logger.info("🔍 This was a dry run. Run without --dry-run to apply changes.")
        else:
            logger.info("✅ Migration completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        client.close()
        logger.info("Closed MongoDB connection")


if __name__ == '__main__':
    main()

