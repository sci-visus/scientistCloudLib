#!/usr/bin/env python3
"""
Update Dataset Sizes Script
Computes the size of upload and convert directories for each dataset
and updates the data_size field in the visstoredatas MongoDB collection.

IMPORTANT: The size is stored as a NUMERIC VALUE (float) in GB, NOT as a string.
Example: 1.234567 (not "1.23 GB")
This makes it easy to parse and convert to other units (KB, MB, TB) in the UI.

Usage:
    python update_dataset_sizes.py [--dry-run] [--uuid UUID] [--log-level LEVEL]

Environment Variables:
    MONGO_URL: MongoDB connection string (required)
    DB_NAME: Database name (required)
    UPLOAD_BASE_DIR: Base directory for uploads (default: /mnt/visus_datasets/upload)
    CONVERT_BASE_DIR: Base directory for converted data (default: /mnt/visus_datasets/converted)

This script is designed to be run as a cron job.
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
except ImportError:
    print("ERROR: pymongo is not installed. Install it with: pip install pymongo")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('update_dataset_sizes.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Default directory paths
DEFAULT_UPLOAD_DIR = "/mnt/visus_datasets/upload"
DEFAULT_CONVERT_DIR = "/mnt/visus_datasets/converted"

# Bytes to GB conversion factor
BYTES_TO_GB = 1 / (1024 ** 3)


def get_dir_size(directory: str) -> int:
    """
    Calculate the total size of a directory in bytes.
    Skips symlinks to avoid following them.
    
    Args:
        directory: Path to the directory
        
    Returns:
        Total size in bytes (0 if directory doesn't exist or is empty)
    """
    total_size = 0
    
    if not os.path.exists(directory):
        return 0
    
    if not os.path.isdir(directory):
        logger.warning(f"Path exists but is not a directory: {directory}")
        return 0
    
    try:
        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    # Skip symlinks
                    if os.path.islink(filepath):
                        continue
                    
                    # Get file size
                    size = os.path.getsize(filepath)
                    total_size += size
                except (OSError, FileNotFoundError) as e:
                    # Log but continue - file might have been deleted
                    logger.debug(f"Could not get size for {filepath}: {e}")
                    continue
    except Exception as e:
        logger.error(f"Error calculating size for {directory}: {e}")
        return 0
    
    return total_size


def calculate_dataset_size(uuid: str, upload_base_dir: str, convert_base_dir: str) -> float:
    """
    Calculate total size of a dataset by summing upload and convert directories.
    
    Args:
        uuid: Dataset UUID
        upload_base_dir: Base directory for uploads
        convert_base_dir: Base directory for converted data
        
    Returns:
        Total size in GB as a float (numeric value only, no unit suffix)
        Example: 1.234567 (not "1.23 GB")
    """
    upload_dir = os.path.join(upload_base_dir, uuid)
    convert_dir = os.path.join(convert_base_dir, uuid)
    
    upload_size = get_dir_size(upload_dir)
    convert_size = get_dir_size(convert_dir)
    
    total_bytes = upload_size + convert_size
    total_gb = total_bytes * BYTES_TO_GB
    
    logger.debug(f"Dataset {uuid}: upload={upload_size} bytes, convert={convert_size} bytes, total={total_gb:.6f} GB")
    
    return total_gb


def connect_to_mongodb(mongo_url: str, db_name: str) -> Optional[MongoClient]:
    """
    Connect to MongoDB.
    
    Args:
        mongo_url: MongoDB connection string
        db_name: Database name
        
    Returns:
        MongoDB client or None if connection fails
    """
    try:
        client = MongoClient(
            mongo_url,
            serverSelectionTimeoutMS=10000,
            connectTimeoutMS=15000,
            socketTimeoutMS=30000
        )
        
        # Test connection
        client.admin.command('ping')
        logger.info(f"Connected to MongoDB: {db_name}")
        return client
        
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error connecting to MongoDB: {e}")
        return None


def update_dataset_sizes(
    client: MongoClient,
    db_name: str,
    upload_base_dir: str,
    convert_base_dir: str,
    dry_run: bool = False,
    uuid_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Update data_size field for all datasets in visstoredatas collection.
    
    Args:
        client: MongoDB client
        db_name: Database name
        upload_base_dir: Base directory for uploads
        convert_base_dir: Base directory for converted data
        dry_run: If True, don't update database, just report what would be updated
        uuid_filter: If provided, only update this specific UUID
        
    Returns:
        Dictionary with statistics about the update operation
    """
    db = client[db_name]
    collection = db['visstoredatas']
    
    stats = {
        'total_datasets': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0,
        'total_size_gb': 0.0
    }
    
    # Build query
    query = {}
    if uuid_filter:
        query['uuid'] = uuid_filter
        logger.info(f"Filtering to UUID: {uuid_filter}")
    
    # Get all datasets
    try:
        datasets = list(collection.find(query))
        stats['total_datasets'] = len(datasets)
        logger.info(f"Found {len(datasets)} dataset(s) to process")
    except Exception as e:
        logger.error(f"Error querying datasets: {e}")
        stats['errors'] = 1
        return stats
    
    # Process each dataset
    for dataset in datasets:
        uuid = dataset.get('uuid')
        if not uuid:
            logger.warning("Dataset missing UUID, skipping")
            stats['skipped'] += 1
            continue
        
        try:
            # Calculate size
            size_gb = calculate_dataset_size(uuid, upload_base_dir, convert_base_dir)
            stats['total_size_gb'] += size_gb
            
            # Get current data_size for comparison
            current_size = dataset.get('data_size')
            
            # Update database
            # Note: data_size is stored as a float (numeric value in GB), NOT as a string
            # Example: 1.234567 (not "1.23 GB") - this makes it easy to parse and convert to other units
            if not dry_run:
                result = collection.update_one(
                    {'uuid': uuid},
                    {'$set': {
                        'data_size': size_gb,  # Float value in GB (e.g., 1.234567)
                        'data_size_updated_at': datetime.utcnow()
                    }}
                )
                
                if result.modified_count > 0:
                    logger.info(f"Updated {uuid}: {current_size} -> {size_gb:.6f} GB")
                    stats['updated'] += 1
                else:
                    logger.debug(f"No change for {uuid}: {size_gb:.6f} GB (already set)")
                    stats['skipped'] += 1
            else:
                logger.info(f"[DRY RUN] Would update {uuid}: {current_size} -> {size_gb:.6f} GB")
                stats['updated'] += 1
                
        except Exception as e:
            logger.error(f"Error processing dataset {uuid}: {e}")
            stats['errors'] += 1
            continue
    
    return stats


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description='Update dataset sizes in MongoDB visstoredatas collection',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update all datasets
  python update_dataset_sizes.py
  
  # Dry run (don't update database)
  python update_dataset_sizes.py --dry-run
  
  # Update specific dataset
  python update_dataset_sizes.py --uuid abc-123-def
  
  # Custom directories
  UPLOAD_BASE_DIR=/custom/upload CONVERT_BASE_DIR=/custom/convert python update_dataset_sizes.py
        """
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Do not update database, just report what would be updated'
    )
    
    parser.add_argument(
        '--uuid',
        type=str,
        help='Update only this specific UUID'
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
    
    # Get environment variables
    mongo_url = os.getenv('MONGO_URL')
    db_name = os.getenv('DB_NAME')
    upload_base_dir = os.getenv('UPLOAD_BASE_DIR', DEFAULT_UPLOAD_DIR)
    convert_base_dir = os.getenv('CONVERT_BASE_DIR', DEFAULT_CONVERT_DIR)
    
    # Validate required environment variables
    if not mongo_url:
        logger.error("MONGO_URL environment variable is not set")
        sys.exit(1)
    
    if not db_name:
        logger.error("DB_NAME environment variable is not set")
        sys.exit(1)
    
    # Validate directories exist
    if not os.path.isdir(upload_base_dir):
        logger.warning(f"Upload base directory does not exist: {upload_base_dir}")
    
    if not os.path.isdir(convert_base_dir):
        logger.warning(f"Convert base directory does not exist: {convert_base_dir}")
    
    logger.info("=" * 60)
    logger.info("Dataset Size Update Script")
    logger.info("=" * 60)
    logger.info(f"MongoDB: {db_name}")
    logger.info(f"Upload directory: {upload_base_dir}")
    logger.info(f"Convert directory: {convert_base_dir}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"UUID filter: {args.uuid or 'None (all datasets)'}")
    logger.info("=" * 60)
    
    # Connect to MongoDB
    client = connect_to_mongodb(mongo_url, db_name)
    if not client:
        sys.exit(1)
    
    try:
        # Update dataset sizes
        stats = update_dataset_sizes(
            client,
            db_name,
            upload_base_dir,
            convert_base_dir,
            dry_run=args.dry_run,
            uuid_filter=args.uuid
        )
        
        # Print summary
        logger.info("=" * 60)
        logger.info("Summary")
        logger.info("=" * 60)
        logger.info(f"Total datasets processed: {stats['total_datasets']}")
        logger.info(f"Updated: {stats['updated']}")
        logger.info(f"Skipped: {stats['skipped']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info(f"Total size: {stats['total_size_gb']:.2f} GB")
        logger.info("=" * 60)
        
        if args.dry_run:
            logger.info("DRY RUN - No changes were made to the database")
        
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        client.close()
        logger.info("MongoDB connection closed")


if __name__ == '__main__':
    main()

