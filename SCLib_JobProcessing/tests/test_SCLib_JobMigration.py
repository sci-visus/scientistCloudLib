"""
Test cases for SC_JobMigration
Tests migration functionality, validation, and rollback operations.
"""

import unittest
import tempfile
import os
import shutil
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from SCLib_JobMigration import SCLib_JobMigration
from SCLib_JobQueueManager import SCLib_JobQueueManager


class TestSCLib_JobMigration(unittest.TestCase):
    """Test cases for SC_JobMigration."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_mongo_client = Mock(spec=MongoClient)
        self.mock_job_queue = Mock(spec=SCLib_JobQueueManager)
        self.mock_db = Mock()
        self.mock_jobs = Mock()
        self.mock_datasets = Mock()
        
        # Setup mock database structure
        self.mock_mongo_client.__getitem__ = Mock(return_value=self.mock_db)
        self.mock_db.__getitem__ = Mock(side_effect=lambda name: {
            'jobs': self.mock_jobs,
            'visstoredatas': self.mock_datasets
        }[name])
        
        with patch('SCLib_JobMigration.SCLib_JobQueueManager') as mock_job_queue_class:
            mock_job_queue_class.return_value = self.mock_job_queue
            
            self.migration = SCLib_JobMigration(self.mock_mongo_client, 'test_db')
            self.migration.jobs = self.mock_jobs
            self.migration.datasets = self.mock_datasets
    
    def test_initialization(self):
        """Test migration utility initialization."""
        self.assertEqual(self.migration.job_queue, self.mock_job_queue)
        self.assertEqual(self.migration.db, self.mock_db)
        self.assertEqual(self.migration.datasets, self.mock_datasets)
        self.assertEqual(self.migration.jobs, self.mock_jobs)
        
        # Verify initial stats
        self.assertEqual(self.migration.stats['datasets_processed'], 0)
        self.assertEqual(self.migration.stats['jobs_created'], 0)
        self.assertEqual(self.migration.stats['errors'], 0)
        self.assertEqual(self.migration.stats['skipped'], 0)
    
    def test_find_datasets_to_migrate(self):
        """Test finding datasets that need migration."""
        # Mock datasets with migration statuses
        mock_datasets = [
            {
                'uuid': 'dataset-1',
                'status': 'sync queued',
                'name': 'Dataset 1'
            },
            {
                'uuid': 'dataset-2',
                'status': 'conversion queued',
                'name': 'Dataset 2'
            },
            {
                'uuid': 'dataset-3',
                'status': 'done',  # Should not be migrated (not in migration statuses)
                'name': 'Dataset 3'
            }
        ]
        
        # Mock existing jobs (dataset-1 has no jobs, dataset-2 has jobs)
        def mock_jobs_find(query):
            if query.get('dataset_uuid') == 'dataset-1':
                return []  # No existing jobs
            elif query.get('dataset_uuid') == 'dataset-2':
                return [{'job_id': 'existing-job'}]  # Has existing jobs
            return []
        
        # Patch the methods directly
        with patch.object(self.migration, 'datasets') as mock_datasets_obj:
            # Mock the find method to respect the query filter
            def mock_datasets_find(query):
                if 'status' in query and '$in' in query['status']:
                    # Filter datasets by status
                    migration_statuses = query['status']['$in']
                    filtered_datasets = [d for d in mock_datasets if d['status'] in migration_statuses]
                    return filtered_datasets
                return mock_datasets
            
            mock_datasets_obj.find.side_effect = mock_datasets_find
            
            with patch.object(self.migration, 'jobs') as mock_jobs_obj:
                mock_jobs_obj.find.side_effect = mock_jobs_find
                
                result = self.migration._find_datasets_to_migrate()
                
                # Should return dataset-1 and dataset-3 (dataset-2 has existing jobs)
                # dataset-1: no existing jobs, dataset-3: no existing jobs
                self.assertEqual(len(result), 2)
                result_uuids = [r['uuid'] for r in result]
                self.assertIn('dataset-1', result_uuids)
                self.assertIn('dataset-3', result_uuids)
    
    def test_find_datasets_to_migrate_database_error(self):
        """Test finding datasets with database error."""
        self.mock_datasets.find.side_effect = PyMongoError("Database error")
        
        result = self.migration._find_datasets_to_migrate()
        
        self.assertEqual(result, [])
    
    def test_migrate_dataset_sync_queued(self):
        """Test migrating dataset with sync queued status."""
        mock_dataset = {
            'uuid': 'dataset-123',
            'status': 'sync queued',
            'user': 'test@example.com',
            'google_drive_link': 'https://drive.google.com/file/123'
        }
        
        # Mock job creation
        self.mock_job_queue.create_job.return_value = 'job-123'
        
        result = self.migration._migrate_dataset(mock_dataset, dry_run=False)
        
        # Verify job was created
        self.mock_job_queue.create_job.assert_called_once()
        call_kwargs = self.mock_job_queue.create_job.call_args[1]
        
        self.assertEqual(call_kwargs['dataset_uuid'], 'dataset-123')
        self.assertEqual(call_kwargs['job_type'], 'google_sync')
        self.assertEqual(call_kwargs['parameters']['user_email'], 'test@example.com')
        self.assertEqual(call_kwargs['parameters']['data_url'], 'https://drive.google.com/file/123')
        self.assertEqual(call_kwargs['priority'], 2)
        
        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['dataset_uuid'], 'dataset-123')
        self.assertEqual(result['created_jobs'], ['job-123'])
        self.assertFalse(result['dry_run'])
    
    def test_migrate_dataset_conversion_queued(self):
        """Test migrating dataset with conversion queued status."""
        mock_dataset = {
            'uuid': 'dataset-123',
            'status': 'conversion queued',
            'sensor': '4D_Probe',
            'conversion_parameters': {
                'Xs_dataset': 'path/to/Xs',
                'Ys_dataset': 'path/to/Ys'
            }
        }
        
        # Mock job creation
        self.mock_job_queue.create_job.return_value = 'job-123'
        
        result = self.migration._migrate_dataset(mock_dataset, dry_run=False)
        
        # Verify job was created
        self.mock_job_queue.create_job.assert_called_once()
        call_kwargs = self.mock_job_queue.create_job.call_args[1]
        
        self.assertEqual(call_kwargs['dataset_uuid'], 'dataset-123')
        self.assertEqual(call_kwargs['job_type'], 'dataset_conversion')
        self.assertEqual(call_kwargs['parameters']['sensor_type'], '4D_Probe')
        self.assertEqual(call_kwargs['parameters']['conversion_params']['Xs_dataset'], 'path/to/Xs')
        self.assertEqual(call_kwargs['priority'], 1)
    
    def test_migrate_dataset_upload_queued(self):
        """Test migrating dataset with upload queued status."""
        mock_dataset = {
            'uuid': 'dataset-123',
            'status': 'upload queued'
        }
        
        # Mock job creation
        self.mock_job_queue.create_job.return_value = 'job-123'
        
        # Mock file listing
        with patch.object(self.migration, '_get_upload_files') as mock_get_files:
            mock_get_files.return_value = ['/test/file1.txt', '/test/file2.txt']
            
            result = self.migration._migrate_dataset(mock_dataset, dry_run=False)
            
            # Verify job was created
            self.mock_job_queue.create_job.assert_called_once()
            call_kwargs = self.mock_job_queue.create_job.call_args[1]
            
            self.assertEqual(call_kwargs['dataset_uuid'], 'dataset-123')
            self.assertEqual(call_kwargs['job_type'], 'file_upload')
            self.assertEqual(call_kwargs['parameters']['files'], ['/test/file1.txt', '/test/file2.txt'])
    
    def test_migrate_dataset_unzipping(self):
        """Test migrating dataset with unzipping status."""
        mock_dataset = {
            'uuid': 'dataset-123',
            'status': 'unzipping'
        }
        
        # Mock job creation
        self.mock_job_queue.create_job.return_value = 'job-123'
        
        # Mock zip file finding
        with patch.object(self.migration, '_find_zip_file') as mock_find_zip:
            mock_find_zip.return_value = '/test/archive.zip'
            
            result = self.migration._migrate_dataset(mock_dataset, dry_run=False)
            
            # Verify job was created
            self.mock_job_queue.create_job.assert_called_once()
            call_kwargs = self.mock_job_queue.create_job.call_args[1]
            
            self.assertEqual(call_kwargs['dataset_uuid'], 'dataset-123')
            self.assertEqual(call_kwargs['job_type'], 'file_extraction')
            self.assertEqual(call_kwargs['parameters']['zip_file'], '/test/archive.zip')
    
    def test_migrate_dataset_zipping(self):
        """Test migrating dataset with zipping status."""
        mock_dataset = {
            'uuid': 'dataset-123',
            'status': 'zipping'
        }
        
        # Mock job creation
        self.mock_job_queue.create_job.return_value = 'job-123'
        
        result = self.migration._migrate_dataset(mock_dataset, dry_run=False)
        
        # Verify job was created
        self.mock_job_queue.create_job.assert_called_once()
        call_kwargs = self.mock_job_queue.create_job.call_args[1]
        
        self.assertEqual(call_kwargs['dataset_uuid'], 'dataset-123')
        self.assertEqual(call_kwargs['job_type'], 'data_compression')
        self.assertEqual(call_kwargs['parameters']['compression_type'], 'lz4')
    
    def test_migrate_dataset_dry_run(self):
        """Test migrating dataset in dry run mode."""
        mock_dataset = {
            'uuid': 'dataset-123',
            'status': 'sync queued',
            'user': 'test@example.com',
            'google_drive_link': 'https://drive.google.com/file/123'
        }
        
        result = self.migration._migrate_dataset(mock_dataset, dry_run=True)
        
        # Verify no job was created
        self.mock_job_queue.create_job.assert_not_called()
        
        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['dataset_uuid'], 'dataset-123')
        self.assertEqual(result['created_jobs'], ['dry_run_google_sync'])
        self.assertTrue(result['dry_run'])
    
    def test_migrate_dataset_no_jobs_needed(self):
        """Test migrating dataset that needs no jobs."""
        mock_dataset = {
            'uuid': 'dataset-123',
            'status': 'done'  # Terminal status
        }
        
        result = self.migration._migrate_dataset(mock_dataset, dry_run=False)
        
        # Verify no job was created
        self.mock_job_queue.create_job.assert_not_called()
        
        # Verify result
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['reason'], 'No jobs needed')
    
    def test_determine_conversion_input_file_url(self):
        """Test determining conversion input for file URL."""
        mock_dataset = {
            'uuid': 'dataset-123',
            'google_drive_link': 'file:///path/to/data'
        }
        
        result = self.migration._determine_conversion_input(
            mock_dataset, 'file:///path/to/data', '/test/input'
        )
        
        self.assertEqual(result, '/path/to/data')
    
    def test_determine_conversion_input_rclone(self):
        """Test determining conversion input for rclone URL."""
        mock_dataset = {
            'uuid': 'dataset-123',
            'google_drive_link': 'rclone:remote:path'
        }
        
        result = self.migration._determine_conversion_input(
            mock_dataset, 'rclone:remote:path', '/test/input'
        )
        
        self.assertEqual(result, 'rclone:remote:path')
    
    def test_determine_conversion_input_modvisus(self):
        """Test determining conversion input for mod_visus URL."""
        mock_dataset = {
            'uuid': 'dataset-123',
            'google_drive_link': 'http://example.com/mod_visus/data'
        }
        
        result = self.migration._determine_conversion_input(
            mock_dataset, 'http://example.com/mod_visus/data', '/test/input'
        )
        
        self.assertEqual(result, 'http://example.com/mod_visus/data')
    
    def test_determine_conversion_input_default(self):
        """Test determining conversion input with default fallback."""
        mock_dataset = {
            'uuid': 'dataset-123',
            'google_drive_link': 'https://example.com/data'
        }
        
        result = self.migration._determine_conversion_input(
            mock_dataset, 'https://example.com/data', '/test/input'
        )
        
        self.assertEqual(result, '/test/input')
    
    def test_get_upload_files(self):
        """Test getting upload files from directory."""
        # Create temporary directory with test files
        temp_dir = tempfile.mkdtemp()
        try:
            # Create test files
            os.makedirs(os.path.join(temp_dir, 'subdir'))
            with open(os.path.join(temp_dir, 'file1.txt'), 'w') as f:
                f.write('test')
            with open(os.path.join(temp_dir, 'subdir', 'file2.txt'), 'w') as f:
                f.write('test')
            
            result = self.migration._get_upload_files(temp_dir)
            
            # Verify files were found
            self.assertEqual(len(result), 2)
            self.assertTrue(any('file1.txt' in path for path in result))
            self.assertTrue(any('file2.txt' in path for path in result))
            
        finally:
            shutil.rmtree(temp_dir)
    
    def test_get_upload_files_nonexistent(self):
        """Test getting upload files from nonexistent directory."""
        result = self.migration._get_upload_files('/nonexistent/directory')
        
        self.assertEqual(result, [])
    
    def test_find_zip_file(self):
        """Test finding zip file in directory."""
        # Create temporary directory with zip file
        temp_dir = tempfile.mkdtemp()
        try:
            # Create test zip file
            with open(os.path.join(temp_dir, 'archive.zip'), 'w') as f:
                f.write('test zip content')
            
            result = self.migration._find_zip_file(temp_dir)
            
            # Verify zip file was found
            self.assertIsNotNone(result)
            self.assertIn('archive.zip', result)
            
        finally:
            shutil.rmtree(temp_dir)
    
    def test_find_zip_file_nonexistent(self):
        """Test finding zip file when none exists."""
        # Create temporary directory without zip file
        temp_dir = tempfile.mkdtemp()
        try:
            result = self.migration._find_zip_file(temp_dir)
            
            # Verify no zip file was found
            self.assertIsNone(result)
            
        finally:
            shutil.rmtree(temp_dir)
    
    def test_generate_migration_report(self):
        """Test migration report generation."""
        # Set some stats
        self.migration.stats['datasets_processed'] = 10
        self.migration.stats['jobs_created'] = 15
        self.migration.stats['errors'] = 2
        self.migration.stats['skipped'] = 3
        
        result = self.migration._generate_migration_report()
        
        # Verify report structure
        self.assertIn('timestamp', result)
        self.assertIn('statistics', result)
        self.assertIn('summary', result)
        
        # Verify statistics
        self.assertEqual(result['statistics']['datasets_processed'], 10)
        self.assertEqual(result['statistics']['jobs_created'], 15)
        self.assertEqual(result['statistics']['errors'], 2)
        self.assertEqual(result['statistics']['skipped'], 3)
        
        # Verify summary
        self.assertEqual(result['summary']['total_datasets_processed'], 10)
        self.assertEqual(result['summary']['total_jobs_created'], 15)
        self.assertEqual(result['summary']['total_errors'], 2)
        self.assertEqual(result['summary']['total_skipped'], 3)
    
    def test_validate_migration_success(self):
        """Test successful migration validation."""
        # Mock datasets with active statuses
        active_datasets = [
            {
                'uuid': 'dataset-1',
                'status': 'syncing',
                'name': 'Dataset 1'
            },
            {
                'uuid': 'dataset-2',
                'status': 'converting',
                'name': 'Dataset 2'
            }
        ]
        
        # Mock existing jobs for all datasets
        def mock_jobs_find(query):
            if 'status' in query:  # Orphaned jobs query
                return []  # No orphaned jobs
            return [{'job_id': f"job-{query['dataset_uuid']}"}]
        
        with patch.object(self.migration, 'datasets') as mock_datasets_obj:
            mock_datasets_obj.find.return_value = active_datasets
            
            with patch.object(self.migration, 'jobs') as mock_jobs_obj:
                mock_jobs_obj.find.side_effect = mock_jobs_find
                
                result = self.migration.validate_migration()
        
        # Verify validation passed
        self.assertTrue(result['validation_passed'])
        self.assertEqual(len(result['datasets_without_jobs']), 0)
        self.assertEqual(len(result['orphaned_jobs']), 0)
        self.assertEqual(len(result['status_mismatches']), 0)
    
    def test_validate_migration_failures(self):
        """Test migration validation with failures."""
        # Mock datasets with active statuses
        active_datasets = [
            {
                'uuid': 'dataset-1',
                'status': 'syncing',
                'name': 'Dataset 1'
            },
            {
                'uuid': 'dataset-2',
                'status': 'converting',
                'name': 'Dataset 2'
            }
        ]
        
        # Mock missing jobs for dataset-1
        def mock_jobs_find(query):
            if query.get('dataset_uuid') == 'dataset-1':
                return []  # No jobs
            elif query.get('dataset_uuid') == 'dataset-2':
                return [{'job_id': 'job-dataset-2'}]
            return []
        
        # Mock orphaned jobs
        orphaned_jobs = [
            {
                'job_id': 'orphaned-job',
                'dataset_uuid': 'nonexistent-dataset',
                'job_type': 'dataset_conversion'
            }
        ]
        
        def mock_jobs_find_orphaned(query):
            if 'status' in query:  # Active jobs query
                return orphaned_jobs
            elif query.get('dataset_uuid') == 'dataset-1':
                return []  # No jobs for dataset-1
            elif query.get('dataset_uuid') == 'dataset-2':
                return [{'job_id': 'job-dataset-2'}]  # Has jobs for dataset-2
            return []  # Dataset lookup returns empty
        
        with patch.object(self.migration, 'datasets') as mock_datasets_obj:
            mock_datasets_obj.find.return_value = active_datasets
            mock_datasets_obj.find_one.return_value = None  # Dataset not found
            
            with patch.object(self.migration, 'jobs') as mock_jobs_obj:
                # Use the orphaned jobs mock for the validation
                mock_jobs_obj.find.side_effect = mock_jobs_find_orphaned
                
                result = self.migration.validate_migration()
        
        # Verify validation failed
        self.assertFalse(result['validation_passed'])
        self.assertEqual(len(result['datasets_without_jobs']), 1)
        self.assertEqual(result['datasets_without_jobs'][0]['uuid'], 'dataset-1')
        self.assertEqual(len(result['orphaned_jobs']), 1)
        self.assertEqual(result['orphaned_jobs'][0]['job_id'], 'orphaned-job')
    
    def test_rollback_migration_specific_dataset(self):
        """Test rolling back migration for specific dataset."""
        # Mock job deletion
        self.mock_jobs.delete_many.return_value = Mock(deleted_count=2)
        
        # Mock dataset status update
        self.mock_datasets.update_one.return_value = Mock(modified_count=1)
        
        result = self.migration.rollback_migration('dataset-123')
        
        # Verify jobs were deleted
        self.mock_jobs.delete_many.assert_called_once_with({'dataset_uuid': 'dataset-123'})
        
        # Verify dataset status was reset
        self.mock_datasets.update_one.assert_called_once_with(
            {'uuid': 'dataset-123'},
            {'$set': {'status': 'submitted'}}
        )
        
        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['statistics']['jobs_deleted'], 2)
        self.assertEqual(result['statistics']['datasets_reset'], 1)
    
    def test_rollback_migration_all_datasets(self):
        """Test rolling back migration for all datasets."""
        # Mock migration jobs
        migration_jobs = [
            {'dataset_uuid': 'dataset-1'},
            {'dataset_uuid': 'dataset-2'},
            {'dataset_uuid': 'dataset-3'}
        ]
        
        self.mock_jobs.find.return_value = migration_jobs
        
        # Mock dataset status updates
        self.mock_datasets.update_one.return_value = Mock(modified_count=1)
        
        # Mock job deletion
        self.mock_jobs.delete_many.return_value = Mock(deleted_count=5)
        
        result = self.migration.rollback_migration()
        
        # Verify dataset statuses were reset
        self.assertEqual(self.mock_datasets.update_one.call_count, 3)
        
        # Verify jobs were deleted
        self.mock_jobs.delete_many.assert_called_once_with({})
        
        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['statistics']['jobs_deleted'], 5)
        self.assertEqual(result['statistics']['datasets_reset'], 3)
    
    def test_rollback_migration_error(self):
        """Test rollback migration with error."""
        # Mock error
        self.mock_jobs.delete_many.side_effect = PyMongoError("Database error")
        
        result = self.migration.rollback_migration('dataset-123')
        
        # Verify error handling
        self.assertEqual(result['status'], 'error')
        self.assertIn('error', result)
        self.assertIn('Database error', result['error'])
    
    def test_migrate_all_datasets_success(self):
        """Test migrating all datasets successfully."""
        # Mock datasets to migrate
        mock_datasets = [
            {
                'uuid': 'dataset-1',
                'status': 'sync queued',
                'user': 'test@example.com',
                'google_drive_link': 'https://drive.google.com/file/1'
            },
            {
                'uuid': 'dataset-2',
                'status': 'conversion queued',
                'sensor': '4D_Probe'
            }
        ]
        
        with patch.object(self.migration, '_find_datasets_to_migrate') as mock_find:
            mock_find.return_value = mock_datasets
            
            # Mock successful migration
            with patch.object(self.migration, '_migrate_dataset') as mock_migrate:
                mock_migrate.return_value = {'status': 'success', 'created_jobs': ['job-1']}
                
                result = self.migration.migrate_all_datasets(dry_run=False)
                
                # Verify migration was called for each dataset
                self.assertEqual(mock_migrate.call_count, 2)
                
                # Verify result
                self.assertEqual(result['statistics']['datasets_processed'], 2)
                self.assertEqual(result['statistics']['jobs_created'], 0)  # Not tracked in this test
                self.assertEqual(result['statistics']['errors'], 0)
    
    def test_migrate_all_datasets_with_errors(self):
        """Test migrating all datasets with some errors."""
        # Mock datasets to migrate
        mock_datasets = [
            {
                'uuid': 'dataset-1',
                'status': 'sync queued'
            },
            {
                'uuid': 'dataset-2',
                'status': 'conversion queued'
            }
        ]
        
        with patch.object(self.migration, '_find_datasets_to_migrate') as mock_find:
            mock_find.return_value = mock_datasets
            
            # Mock migration with one error
            def mock_migrate(dataset, dry_run):
                if dataset['uuid'] == 'dataset-1':
                    return {'status': 'success', 'created_jobs': ['job-1']}
                else:
                    raise Exception("Migration failed")
            
            with patch.object(self.migration, '_migrate_dataset', side_effect=mock_migrate):
                result = self.migration.migrate_all_datasets(dry_run=False)
                
                # Verify result
                self.assertEqual(result['statistics']['datasets_processed'], 2)
                self.assertEqual(result['statistics']['errors'], 1)
    
    def test_migrate_specific_dataset_success(self):
        """Test migrating specific dataset successfully."""
        # Mock dataset
        mock_dataset = {
            'uuid': 'dataset-123',
            'status': 'sync queued',
            'user': 'test@example.com',
            'google_drive_link': 'https://drive.google.com/file/123'
        }
        
        self.mock_datasets.find_one.return_value = mock_dataset
        
        # Mock successful migration
        with patch.object(self.migration, '_migrate_dataset') as mock_migrate:
            mock_migrate.return_value = {'status': 'success', 'created_jobs': ['job-123']}
            
            result = self.migration.migrate_specific_dataset('dataset-123', dry_run=False)
            
            # Verify result
            self.assertEqual(result['status'], 'success')
            self.assertEqual(result['created_jobs'], ['job-123'])
    
    def test_migrate_specific_dataset_not_found(self):
        """Test migrating specific dataset that doesn't exist."""
        self.mock_datasets.find_one.return_value = None
        
        result = self.migration.migrate_specific_dataset('nonexistent-dataset', dry_run=False)
        
        # Verify error
        self.assertIn('error', result)
        self.assertIn('not found', result['error'])
    
    def test_migrate_specific_dataset_error(self):
        """Test migrating specific dataset with error."""
        # Mock dataset
        mock_dataset = {
            'uuid': 'dataset-123',
            'status': 'sync queued'
        }
        
        self.mock_datasets.find_one.return_value = mock_dataset
        
        # Mock migration error
        with patch.object(self.migration, '_migrate_dataset') as mock_migrate:
            mock_migrate.side_effect = Exception("Migration failed")
            
            result = self.migration.migrate_specific_dataset('dataset-123', dry_run=False)
            
            # Verify error
            self.assertIn('error', result)
            self.assertIn('Migration failed', result['error'])


if __name__ == '__main__':
    unittest.main()
