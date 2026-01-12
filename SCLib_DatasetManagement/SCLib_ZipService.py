#!/usr/bin/env python3
"""
ScientistCloud Zip Service
Creates zip archives from dataset directories for download
"""

import os
import zipfile
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ZipService:
    """Service for creating zip archives from dataset directories."""
    
    def __init__(self, upload_dir: Optional[str] = None, converted_dir: Optional[str] = None):
        """
        Initialize zip service.
        
        Args:
            upload_dir: Base directory for upload files (default: from env)
            converted_dir: Base directory for converted files (default: from env)
        """
        self.upload_dir = upload_dir or os.getenv('JOB_IN_DATA_DIR', '/mnt/visus_datasets/upload')
        self.converted_dir = converted_dir or os.getenv('JOB_OUT_DATA_DIR', '/mnt/visus_datasets/converted')
        self.cache_dir = os.getenv('ZIP_CACHE_DIR', '/tmp/sc_zip_cache')
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def get_directory_path(self, dataset_uuid: str, directory: str) -> Path:
        """
        Get the full path to a dataset directory.
        
        Args:
            dataset_uuid: Dataset UUID
            directory: 'upload' or 'converted'
            
        Returns:
            Path to the directory
        """
        if directory == 'upload':
            base_dir = self.upload_dir
        elif directory == 'converted':
            base_dir = self.converted_dir
        else:
            raise ValueError(f"Invalid directory: {directory}. Must be 'upload' or 'converted'")
        
        return Path(base_dir) / dataset_uuid
    
    def create_zip(self, dataset_uuid: str, directory: str, output_path: Optional[str] = None) -> str:
        """
        Create a zip archive from a dataset directory.
        
        Args:
            dataset_uuid: Dataset UUID
            directory: 'upload' or 'converted'
            output_path: Optional path to save zip file. If None, uses cache directory.
            
        Returns:
            Path to the created zip file
            
        Raises:
            FileNotFoundError: If the dataset directory doesn't exist
            ValueError: If directory is invalid
        """
        source_dir = self.get_directory_path(dataset_uuid, directory)
        
        if not source_dir.exists():
            raise FileNotFoundError(f"Dataset directory not found: {source_dir}")
        
        if not source_dir.is_dir():
            raise ValueError(f"Path is not a directory: {source_dir}")
        
        # Determine output path
        if output_path:
            zip_path = Path(output_path)
        else:
            # Use cache directory with dataset UUID and directory name
            zip_filename = f"{dataset_uuid}_{directory}.zip"
            zip_path = Path(self.cache_dir) / zip_filename
        
        # Create parent directory if needed
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Creating zip archive: {zip_path} from {source_dir}")
        
        # Create zip file
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
            # Walk through all files in the directory
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = Path(root) / file
                    # Calculate relative path from source_dir
                    arcname = file_path.relative_to(source_dir)
                    zipf.write(file_path, arcname)
                    logger.debug(f"Added to zip: {arcname}")
        
        logger.info(f"Zip archive created: {zip_path} ({zip_path.stat().st_size / (1024*1024):.2f} MB)")
        
        return str(zip_path)
    
    def get_cached_zip_path(self, dataset_uuid: str, directory: str) -> Optional[str]:
        """
        Get path to cached zip file if it exists.
        
        Args:
            dataset_uuid: Dataset UUID
            directory: 'upload' or 'converted'
            
        Returns:
            Path to cached zip file, or None if not found
        """
        zip_filename = f"{dataset_uuid}_{directory}.zip"
        zip_path = Path(self.cache_dir) / zip_filename
        
        if zip_path.exists():
            return str(zip_path)
        
        return None
    
    def create_or_get_zip(self, dataset_uuid: str, directory: str, force_recreate: bool = False) -> str:
        """
        Create a zip file or return cached version.
        
        Args:
            dataset_uuid: Dataset UUID
            directory: 'upload' or 'converted'
            force_recreate: If True, recreate zip even if cached version exists
            
        Returns:
            Path to zip file
        """
        # Check cache first
        if not force_recreate:
            cached_path = self.get_cached_zip_path(dataset_uuid, directory)
            if cached_path:
                logger.info(f"Using cached zip: {cached_path}")
                return cached_path
        
        # Create new zip
        return self.create_zip(dataset_uuid, directory)
    
    def cleanup_old_zips(self, max_age_hours: int = 24):
        """
        Clean up zip files older than max_age_hours.
        
        Args:
            max_age_hours: Maximum age in hours for zip files
        """
        if not os.path.exists(self.cache_dir):
            return
        
        cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
        removed_count = 0
        
        for zip_file in Path(self.cache_dir).glob('*.zip'):
            try:
                if zip_file.stat().st_mtime < cutoff_time:
                    zip_file.unlink()
                    removed_count += 1
                    logger.info(f"Removed old zip file: {zip_file}")
            except Exception as e:
                logger.warning(f"Failed to remove zip file {zip_file}: {e}")
        
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old zip files")


def get_zip_service() -> ZipService:
    """Get a ZipService instance."""
    return ZipService()

