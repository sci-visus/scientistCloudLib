"""
ScientistCloud Job Migration Utility
Migrates existing datasets from the old background service to the new job queue system.
"""

import os
import json
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from SCLib_JobQueueManager import SCLib_JobQueueManager
from SCLib_JobTypes import (
    SCLib_JobType, SCLib_DatasetStatus, LEGACY_STATUS_MAPPING, 
    convert_legacy_status, convert_to_legacy_status
)


class SCLib_JobMigration:
    """
    Handles migration of existing datasets from the old system to the new job queue system.
    """
    
    def __init__(self, mongo_client: MongoClient, db_name: str):
        """
        Initialize the migration utility.
        
        Args:
            mongo_client: MongoDB client instance
            db_name: Database name
        """
        self.job_queue = SCLib_JobQueueManager(mongo_client, db_name)
        self.db = mongo_client[db_name]
        self.datasets = self.db.visstoredatas
        self.jobs = self.db.jobs
        
        # Migration statistics
        self.stats = {
            'datasets_processed': 0,
            'jobs_created': 0,
            'errors': 0,
            'skipped': 0
        }
    
    def migrate_all_datasets(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Migrate all datasets that need processing.
        
        Args:
            dry_run: If True, only analyze without making changes
            
        Returns:
            Migration report
        """
        print(f"Starting migration {'(DRY RUN)' if dry_run else '(LIVE)'}")
        
        # Find datasets that need migration
        datasets_to_migrate = self._find_datasets_to_migrate()
        
        print(f"Found {len(datasets_to_migrate)} datasets to migrate")
        
        for dataset in datasets_to_migrate:
            self.stats['datasets_processed'] += 1  # Count all attempts
            try:
                self._migrate_dataset(dataset, dry_run)
            except Exception as e:
                print(f"Error migrating dataset {dataset['uuid']}: {e}")
                self.stats['errors'] += 1
        
        return self._generate_migration_report()
    
    def migrate_specific_dataset(self, dataset_uuid: str, dry_run: bool = True) -> Dict[str, Any]:
        """
        Migrate a specific dataset.
        
        Args:
            dataset_uuid: UUID of the dataset to migrate
            dry_run: If True, only analyze without making changes
            
        Returns:
            Migration result
        """
        print(f"Migrating dataset {dataset_uuid} {'(DRY RUN)' if dry_run else '(LIVE)'}")
        
        try:
            dataset = self.datasets.find_one({'uuid': dataset_uuid})
            if not dataset:
                return {'error': f'Dataset {dataset_uuid} not found'}
            
            result = self._migrate_dataset(dataset, dry_run)
            return result
            
        except Exception as e:
            return {'error': f'Migration failed: {e}'}
    
    def _find_datasets_to_migrate(self) -> List[Dict[str, Any]]:
        """Find datasets that need migration to the job queue system."""
        # Find datasets with statuses that should have corresponding jobs
        migration_statuses = [
            'submitted', 'sync queued', 'syncing', 'conversion queued', 'converting',
            'upload queued', 'uploading', 'unzipping', 'zipping', 'done'
        ]
        
        try:
            datasets = list(self.datasets.find({
                'status': {'$in': migration_statuses}
            }))
            
            # Filter out datasets that already have jobs
            datasets_without_jobs = []
            for dataset in datasets:
                existing_jobs = list(self.jobs.find({'dataset_uuid': dataset['uuid']}))
                if not existing_jobs:
                    datasets_without_jobs.append(dataset)
            
            return datasets_without_jobs
            
        except PyMongoError as e:
            print(f"Error finding datasets to migrate: {e}")
            return []
    
    def _migrate_dataset(self, dataset: Dict[str, Any], dry_run: bool) -> Dict[str, Any]:
        """Migrate a single dataset to the job queue system."""
        dataset_uuid = dataset['uuid']
        current_status = dataset['status']
        
        print(f"Processing dataset {dataset_uuid} with status '{current_status}'")
        
        # Convert legacy status to enum
        dataset_status = convert_legacy_status(current_status)
        
        # Determine what job(s) need to be created
        jobs_to_create = self._determine_jobs_to_create(dataset, dataset_status)
        
        if not jobs_to_create:
            print(f"No jobs needed for dataset {dataset_uuid}")
            self.stats['skipped'] += 1
            return {'status': 'skipped', 'reason': 'No jobs needed'}
        
        created_jobs = []
        
        for job_config in jobs_to_create:
            if not dry_run:
                job_id = self.job_queue.create_job(
                    dataset_uuid=dataset_uuid,
                    job_type=job_config['job_type'],
                    parameters=job_config['parameters'],
                    priority=job_config.get('priority', 2),
                    max_attempts=job_config.get('max_attempts', 3)
                )
                created_jobs.append(job_id)
                self.stats['jobs_created'] += 1
                print(f"Created job {job_id} for dataset {dataset_uuid}")
            else:
                print(f"Would create job of type {job_config['job_type']} for dataset {dataset_uuid}")
                created_jobs.append(f"dry_run_{job_config['job_type']}")
        
        return {
            'status': 'success',
            'dataset_uuid': dataset_uuid,
            'created_jobs': created_jobs,
            'dry_run': dry_run
        }
    
    def _determine_jobs_to_create(self, dataset: Dict[str, Any], 
                                 dataset_status: SCLib_DatasetStatus) -> List[Dict[str, Any]]:
        """Determine what jobs need to be created for a dataset."""
        jobs_to_create = []
        dataset_uuid = dataset['uuid']
        
        # Get dataset parameters
        user_email = dataset.get('user', '')
        data_url = dataset.get('google_drive_link', '')
        sensor = dataset.get('sensor', '')
        
        # Define directory paths
        base_data_dir = '/mnt/visus_datasets'
        input_dir = os.path.join(base_data_dir, 'upload', dataset_uuid)
        output_dir = os.path.join(base_data_dir, 'converted', dataset_uuid)
        
        # Create jobs based on current status
        if dataset_status == SCLib_DatasetStatus.SYNC_QUEUED:
            jobs_to_create.append({
                'job_type': SCLib_JobType.GOOGLE_SYNC.value,
                'parameters': {
                    'user_email': user_email,
                    'input_dir': input_dir,
                    'data_url': data_url
                },
                'priority': 2
            })
        
        elif dataset_status == SCLib_DatasetStatus.SYNCING:
            # Job is already running, create a monitoring job
            jobs_to_create.append({
                'job_type': SCLib_JobType.GOOGLE_SYNC.value,
                'parameters': {
                    'user_email': user_email,
                    'input_dir': input_dir,
                    'data_url': data_url,
                    'monitor_existing': True
                },
                'priority': 1
            })
        
        elif dataset_status == SCLib_DatasetStatus.CONVERSION_QUEUED:
            jobs_to_create.append({
                'job_type': SCLib_JobType.DATASET_CONVERSION.value,
                'parameters': {
                    'input_path': self._determine_conversion_input(dataset, data_url, input_dir),
                    'output_path': output_dir,
                    'sensor_type': sensor,
                    'conversion_params': dataset.get('conversion_parameters', {})
                },
                'priority': 1
            })
        
        elif dataset_status == SCLib_DatasetStatus.CONVERTING:
            # Job is already running, create a monitoring job
            jobs_to_create.append({
                'job_type': SCLib_JobType.DATASET_CONVERSION.value,
                'parameters': {
                    'input_path': self._determine_conversion_input(dataset, data_url, input_dir),
                    'output_path': output_dir,
                    'sensor_type': sensor,
                    'conversion_params': dataset.get('conversion_parameters', {}),
                    'monitor_existing': True
                },
                'priority': 1
            })
        
        elif dataset_status == SCLib_DatasetStatus.UPLOAD_QUEUED:
            jobs_to_create.append({
                'job_type': SCLib_JobType.FILE_UPLOAD.value,
                'parameters': {
                    'files': self._get_upload_files(input_dir),
                    'destination': output_dir
                },
                'priority': 2
            })
        
        elif dataset_status == SCLib_DatasetStatus.UPLOADING:
            jobs_to_create.append({
                'job_type': SCLib_JobType.FILE_UPLOAD.value,
                'parameters': {
                    'files': self._get_upload_files(input_dir),
                    'destination': output_dir,
                    'monitor_existing': True
                },
                'priority': 1
            })
        
        elif dataset_status == SCLib_DatasetStatus.UNZIPPING:
            jobs_to_create.append({
                'job_type': SCLib_JobType.FILE_EXTRACTION.value,
                'parameters': {
                    'zip_file': self._find_zip_file(input_dir),
                    'extract_dir': os.path.join(input_dir, 'unzipped')
                },
                'priority': 1
            })
        
        elif dataset_status == SCLib_DatasetStatus.ZIPPING:
            jobs_to_create.append({
                'job_type': SCLib_JobType.DATA_COMPRESSION.value,
                'parameters': {
                    'source_dir': output_dir,
                    'compression_type': 'lz4'
                },
                'priority': 3
            })
        
        return jobs_to_create
    
    def _determine_conversion_input(self, dataset: Dict[str, Any], data_url: str, 
                                   input_dir: str) -> str:
        """Determine the input path for conversion based on dataset configuration."""
        # Check for different types of data sources
        if data_url and data_url.startswith('file:'):
            # Local file path
            import urllib.parse
            parsed = urllib.parse.urlparse(data_url)
            return parsed.path
        elif data_url and data_url.startswith('rclone:'):
            # RClone source
            return data_url
        elif data_url and 'mod_visus' in data_url:
            # ModVisus link
            return data_url
        else:
            # Default to input directory
            return input_dir
    
    def _get_upload_files(self, input_dir: str) -> List[str]:
        """Get list of files to upload from input directory."""
        files = []
        if os.path.exists(input_dir):
            for root, dirs, filenames in os.walk(input_dir):
                for filename in filenames:
                    files.append(os.path.join(root, filename))
        return files
    
    def _find_zip_file(self, input_dir: str) -> Optional[str]:
        """Find zip file in input directory."""
        if not os.path.exists(input_dir):
            return None
        
        for filename in os.listdir(input_dir):
            if filename.endswith('.zip'):
                return os.path.join(input_dir, filename)
        
        return None
    
    def _generate_migration_report(self) -> Dict[str, Any]:
        """Generate migration report."""
        return {
            'timestamp': datetime.utcnow().isoformat(),
            'statistics': self.stats,
            'summary': {
                'total_datasets_processed': self.stats['datasets_processed'],
                'total_jobs_created': self.stats['jobs_created'],
                'total_errors': self.stats['errors'],
                'total_skipped': self.stats['skipped']
            }
        }
    
    def validate_migration(self) -> Dict[str, Any]:
        """Validate that migration was successful."""
        print("Validating migration...")
        
        validation_results = {
            'timestamp': datetime.utcnow().isoformat(),
            'datasets_without_jobs': [],
            'orphaned_jobs': [],
            'status_mismatches': [],
            'validation_passed': True
        }
        
        try:
            # Find datasets that should have jobs but don't
            active_statuses = [
                'submitted', 'sync queued', 'syncing', 'conversion queued', 'converting',
                'upload queued', 'uploading', 'unzipping', 'zipping', 'done'
            ]
            
            for dataset in self.datasets.find({'status': {'$in': active_statuses}}):
                dataset_uuid = dataset['uuid']
                jobs = list(self.jobs.find({'dataset_uuid': dataset_uuid}))
                
                if not jobs:
                    validation_results['datasets_without_jobs'].append({
                        'uuid': dataset_uuid,
                        'status': dataset['status'],
                        'name': dataset.get('name', 'Unknown')
                    })
                    validation_results['validation_passed'] = False
            
            # Find orphaned jobs (jobs without corresponding datasets)
            for job in self.jobs.find({'status': {'$in': ['pending', 'running']}}):
                dataset = self.datasets.find_one({'uuid': job['dataset_uuid']})
                if not dataset:
                    validation_results['orphaned_jobs'].append({
                        'job_id': job['job_id'],
                        'dataset_uuid': job['dataset_uuid'],
                        'job_type': job['job_type']
                    })
                    validation_results['validation_passed'] = False
            
            print(f"Validation {'PASSED' if validation_results['validation_passed'] else 'FAILED'}")
            return validation_results
            
        except Exception as e:
            return {
                'error': f"Validation failed: {e}",
                'validation_passed': False
            }
    
    def rollback_migration(self, dataset_uuid: Optional[str] = None) -> Dict[str, Any]:
        """
        Rollback migration by removing jobs and resetting dataset statuses.
        
        Args:
            dataset_uuid: Specific dataset to rollback, or None for all
            
        Returns:
            Rollback report
        """
        print(f"Rolling back migration for {'all datasets' if not dataset_uuid else dataset_uuid}")
        
        rollback_stats = {
            'jobs_deleted': 0,
            'datasets_reset': 0,
            'errors': 0
        }
        
        try:
            if dataset_uuid:
                # Rollback specific dataset
                jobs_deleted = self.jobs.delete_many({'dataset_uuid': dataset_uuid}).deleted_count
                rollback_stats['jobs_deleted'] = jobs_deleted
                
                # Reset dataset status
                result = self.datasets.update_one(
                    {'uuid': dataset_uuid},
                    {'$set': {'status': 'submitted'}}
                )
                if result.modified_count > 0:
                    rollback_stats['datasets_reset'] = 1
            else:
                # Rollback all migrated datasets
                # Find all jobs created during migration
                migration_jobs = list(self.jobs.find({}))
                
                for job in migration_jobs:
                    # Reset dataset status
                    result = self.datasets.update_one(
                        {'uuid': job['dataset_uuid']},
                        {'$set': {'status': 'submitted'}}
                    )
                    if result.modified_count > 0:
                        rollback_stats['datasets_reset'] += 1
                
                # Delete all jobs
                jobs_deleted = self.jobs.delete_many({}).deleted_count
                rollback_stats['jobs_deleted'] = jobs_deleted
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'success',
                'statistics': rollback_stats
            }
            
        except Exception as e:
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'status': 'error',
                'error': str(e),
                'statistics': rollback_stats
            }


def main():
    """Main entry point for migration utility."""
    if len(sys.argv) < 2:
        print("Usage: SCLib_JobMigration.py <command> [options]")
        print("Commands:")
        print("  migrate [--dry-run] [--dataset-uuid=<uuid>]")
        print("  validate")
        print("  rollback [--dataset-uuid=<uuid>]")
        sys.exit(1)
    
    command = sys.argv[1]
    
    try:
        # Get MongoDB connection
        mongo_url = os.getenv('MONGO_URL')
        db_name = os.getenv('DB_NAME', 'scientistcloud')
        
        if not mongo_url:
            print("ERROR: MONGO_URL environment variable is required")
            sys.exit(1)
        
        mongo_client = MongoClient(mongo_url)
        migration = SC_JobMigration(mongo_client, db_name)
        
        if command == 'migrate':
            # Parse options
            dry_run = '--dry-run' in sys.argv
            dataset_uuid = None
            
            for arg in sys.argv[2:]:
                if arg.startswith('--dataset-uuid='):
                    dataset_uuid = arg.split('=', 1)[1]
            
            if dataset_uuid:
                result = migration.migrate_specific_dataset(dataset_uuid, dry_run)
            else:
                result = migration.migrate_all_datasets(dry_run)
            
            print(json.dumps(result, indent=2, default=str))
        
        elif command == 'validate':
            result = migration.validate_migration()
            print(json.dumps(result, indent=2, default=str))
        
        elif command == 'rollback':
            dataset_uuid = None
            for arg in sys.argv[2:]:
                if arg.startswith('--dataset-uuid='):
                    dataset_uuid = arg.split('=', 1)[1]
            
            result = migration.rollback_migration(dataset_uuid)
            print(json.dumps(result, indent=2, default=str))
        
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
