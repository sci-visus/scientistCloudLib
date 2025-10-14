"""
Integration tests for SC_JobProcessing system
Tests end-to-end workflows and component interactions.
"""

import unittest
import tempfile
import os
import shutil
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from SC_JobQueueManager import SC_JobQueueManager
from SC_BackgroundService import SC_BackgroundService
from SC_JobMonitor import SC_JobMonitor
from SC_JobMigration import SC_JobMigration
from SC_JobTypes import SC_JobType, SC_DatasetStatus


class TestSC_JobProcessingIntegration(unittest.TestCase):
    """Integration tests for the SC_JobProcessing system."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directories
        self.temp_dirs = []
        self.settings = {
            'db_name': 'test_db',
            'in_data_dir': tempfile.mkdtemp(),
            'out_data_dir': tempfile.mkdtemp(),
            'sync_data_dir': tempfile.mkdtemp(),
            'auth_dir': tempfile.mkdtemp()
        }
        self.temp_dirs.extend(self.settings.values())
        
        # Mock MongoDB connection
        self.mock_mongo_client = Mock()
        self.mock_db = Mock()
        self.mock_jobs = Mock()
        self.mock_datasets = Mock()
        
        # Setup mock database structure
        self.mock_mongo_client.__getitem__ = Mock(return_value=self.mock_db)
        self.mock_db.__getitem__ = Mock(side_effect=lambda name: {
            'jobs': self.mock_jobs,
            'visstoredatas': self.mock_datasets
        }[name])
    
    def tearDown(self):
        """Clean up test fixtures."""
        for temp_dir in self.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    
    def test_end_to_end_job_processing(self):
        """Test complete job processing workflow."""
        # Initialize components
        job_queue = SC_JobQueueManager(self.mock_mongo_client, 'test_db')
        job_queue.jobs = self.mock_jobs
        job_queue.datasets = self.mock_datasets
        
        # Mock job creation
        self.mock_jobs.insert_one.return_value = Mock()
        
        # Create a dataset conversion job
        job_id = job_queue.create_job(
            dataset_uuid='dataset-123',
            job_type='dataset_conversion',
            parameters={
                'input_path': '/test/input',
                'output_path': '/test/output',
                'sensor_type': '4D_Probe'
            },
            priority=1
        )
        
        # Verify job was created
        self.mock_jobs.insert_one.assert_called_once()
        call_args = self.mock_jobs.insert_one.call_args[0][0]
        self.assertEqual(call_args['dataset_uuid'], 'dataset-123')
        self.assertEqual(call_args['job_type'], 'dataset_conversion')
        self.assertEqual(call_args['status'], 'pending')
        self.assertEqual(call_args['priority'], 1)
    
    def test_job_queue_and_background_service_integration(self):
        """Test integration between job queue and background service."""
        # Mock job retrieval
        mock_job = {
            'job_id': 'job-123',
            'dataset_uuid': 'dataset-123',
            'job_type': 'dataset_conversion',
            'parameters': {
                'input_path': '/test/input',
                'output_path': '/test/output',
                'sensor_type': '4D_Probe'
            }
        }
        
        self.mock_jobs.find_one_and_update.return_value = mock_job
        
        # Initialize job queue
        job_queue = SC_JobQueueManager(self.mock_mongo_client, 'test_db')
        job_queue.jobs = self.mock_jobs
        job_queue.datasets = self.mock_datasets
        
        # Get next job
        result = job_queue.get_next_job('worker-123')
        
        # Verify job was retrieved and updated
        self.assertEqual(result, mock_job)
        self.mock_jobs.find_one_and_update.assert_called_once()
        
        # Verify update data
        call_args = self.mock_jobs.find_one_and_update.call_args
        update_data = call_args[0][1]['$set']
        self.assertEqual(update_data['status'], 'running')
        self.assertEqual(update_data['worker_id'], 'worker-123')
    
    def test_monitoring_and_statistics_integration(self):
        """Test integration between job queue and monitoring."""
        # Mock queue statistics
        mock_stats = {
            'total_jobs': 100,
            'pending_jobs': 10,
            'running_jobs': 5,
            'completed_jobs': 80,
            'failed_jobs': 5
        }
        
        # Initialize components
        job_queue = SC_JobQueueManager(self.mock_mongo_client, 'test_db')
        job_queue.jobs = self.mock_jobs
        job_queue.datasets = self.mock_datasets
        
        monitor = SC_JobMonitor(self.mock_mongo_client, 'test_db')
        monitor.jobs = self.mock_jobs
        monitor.datasets = self.mock_datasets
        monitor.job_queue = job_queue
        
        # Mock job queue stats
        job_queue.get_queue_stats = Mock(return_value=mock_stats)
        
        # Mock other monitor methods
        monitor._get_health_status = Mock(return_value={'overall': 'healthy'})
        monitor._get_recent_activity = Mock(return_value={'completed': 5})
        monitor._get_performance_metrics = Mock(return_value={'avg_duration_by_type': {}})
        monitor._get_error_summary = Mock(return_value={'total_failures': 0})
        
        # Get queue overview
        overview = monitor.get_queue_overview()
        
        # Verify integration
        self.assertEqual(overview['queue_stats'], mock_stats)
        self.assertEqual(overview['health_status']['overall'], 'healthy')
    
    def test_migration_workflow(self):
        """Test complete migration workflow."""
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
        
        # Initialize migration
        migration = SC_JobMigration(self.mock_mongo_client, 'test_db')
        migration.jobs = self.mock_jobs
        migration.datasets = self.mock_datasets
        
        # Mock job queue
        mock_job_queue = Mock()
        migration.job_queue = mock_job_queue
        
        # Mock dataset finding
        self.mock_datasets.find.return_value = mock_datasets
        
        # Mock existing jobs (none)
        self.mock_jobs.find.return_value = []
        
        # Mock job creation
        mock_job_queue.create_job.return_value = 'job-123'
        
        # Perform migration
        result = migration.migrate_all_datasets(dry_run=False)
        
        # Verify migration results
        self.assertEqual(result['statistics']['datasets_processed'], 2)
        self.assertEqual(result['statistics']['jobs_created'], 2)  # Should create 2 jobs for 2 datasets
        self.assertEqual(result['statistics']['errors'], 0)
    
    def test_error_handling_and_recovery(self):
        """Test error handling and recovery mechanisms."""
        # Initialize job queue
        job_queue = SC_JobQueueManager(self.mock_mongo_client, 'test_db')
        job_queue.jobs = self.mock_jobs
        job_queue.datasets = self.mock_datasets
        
        # Mock failed job
        mock_failed_job = {
            'job_id': 'job-123',
            'dataset_uuid': 'dataset-123',
            'attempts': 2,
            'max_attempts': 3,
            'status': 'failed'
        }
        
        self.mock_jobs.find_one.return_value = mock_failed_job
        self.mock_jobs.update_one.return_value = Mock(modified_count=1)
        
        # Test job retry
        result = job_queue.retry_job('job-123')
        
        # Verify retry was successful
        self.assertTrue(result)
        self.mock_jobs.update_one.assert_called_once()
        
        # Verify update data
        call_args = self.mock_jobs.update_one.call_args
        update_data = call_args[0][1]['$set']
        self.assertEqual(update_data['status'], 'pending')
        self.assertEqual(update_data['attempts'], 3)  # Incremented
    
    def test_job_type_configuration_integration(self):
        """Test job type configuration integration."""
        from SC_JobTypes import SC_JOB_TYPE_CONFIGS, SC_JobType
        
        # Test dataset conversion configuration
        config = SC_JOB_TYPE_CONFIGS[SC_JobType.DATASET_CONVERSION]
        
        # Verify configuration values
        self.assertEqual(config['timeout_minutes'], 120)
        self.assertEqual(config['max_attempts'], 2)
        self.assertFalse(config['requires_internet'])
        self.assertEqual(config['priority'], 1)
        self.assertEqual(config['description'], 'Convert dataset to streamable format')
        
        # Test Google sync configuration
        config = SC_JOB_TYPE_CONFIGS[SC_JobType.GOOGLE_SYNC]
        
        # Verify configuration values
        self.assertEqual(config['timeout_minutes'], 60)
        self.assertEqual(config['max_attempts'], 3)
        self.assertTrue(config['requires_internet'])
        self.assertEqual(config['priority'], 2)
        self.assertEqual(config['description'], 'Synchronize data from Google Drive')
    
    def test_dataset_status_transitions(self):
        """Test dataset status transition logic."""
        from SC_JobTypes import (
            SC_DATASET_STATUS_TRANSITIONS, SC_DatasetStatus,
            is_valid_transition, get_next_possible_states
        )
        
        # Test valid transitions
        self.assertTrue(is_valid_transition(
            SC_DatasetStatus.SUBMITTED, SC_DatasetStatus.SYNC_QUEUED
        ))
        self.assertTrue(is_valid_transition(
            SC_DatasetStatus.SYNC_QUEUED, SC_DatasetStatus.SYNCING
        ))
        self.assertTrue(is_valid_transition(
            SC_DatasetStatus.SYNCING, SC_DatasetStatus.CONVERSION_QUEUED
        ))
        self.assertTrue(is_valid_transition(
            SC_DatasetStatus.CONVERSION_QUEUED, SC_DatasetStatus.CONVERTING
        ))
        self.assertTrue(is_valid_transition(
            SC_DatasetStatus.CONVERTING, SC_DatasetStatus.DONE
        ))
        
        # Test invalid transitions
        self.assertFalse(is_valid_transition(
            SC_DatasetStatus.SUBMITTED, SC_DatasetStatus.DONE
        ))
        self.assertFalse(is_valid_transition(
            SC_DatasetStatus.DONE, SC_DatasetStatus.SUBMITTED
        ))
        
        # Test next possible states
        next_states = get_next_possible_states(SC_DatasetStatus.SUBMITTED)
        self.assertIn(SC_DatasetStatus.SYNC_QUEUED, next_states)
        self.assertIn(SC_DatasetStatus.CONVERSION_QUEUED, next_states)
        self.assertIn(SC_DatasetStatus.UPLOAD_QUEUED, next_states)
    
    def test_legacy_status_compatibility(self):
        """Test legacy status compatibility."""
        from SC_JobTypes import (
            LEGACY_STATUS_MAPPING, convert_legacy_status, convert_to_legacy_status
        )
        
        # Test all legacy statuses are mapped
        expected_legacy_statuses = [
            'submitted', 'sync queued', 'syncing', 'conversion queued',
            'converting', 'upload queued', 'uploading', 'unzipping',
            'zipping', 'done', 'sync error', 'conversion error',
            'upload error', 'unzip error', 'compression error',
            'failed', 'retrying'
        ]
        
        for status in expected_legacy_statuses:
            self.assertIn(status, LEGACY_STATUS_MAPPING)
        
        # Test conversion functions
        self.assertEqual(
            convert_legacy_status('sync queued'),
            SC_DatasetStatus.SYNC_QUEUED
        )
        self.assertEqual(
            convert_to_legacy_status(SC_DatasetStatus.SYNC_QUEUED),
            'sync queued'
        )
    
    def test_performance_monitoring_integration(self):
        """Test performance monitoring integration."""
        # Initialize monitor
        monitor = SC_JobMonitor(self.mock_mongo_client, 'test_db')
        monitor.jobs = self.mock_jobs
        monitor.datasets = self.mock_datasets
        
        # Mock performance data
        mock_performance_data = [
            {
                '_id': 'dataset_conversion',
                'count': 50,
                'avg_duration': 1800.0,
                'min_duration': 600.0,
                'max_duration': 3600.0
            }
        ]
        
        self.mock_jobs.aggregate.return_value = mock_performance_data
        
        # Mock success rate calculation
        monitor._calculate_success_rate = Mock(return_value=0.95)
        
        # Mock recommendations
        monitor._generate_recommendations = Mock(return_value=[
            'Consider optimizing dataset_conversion jobs'
        ])
        
        # Get performance report
        report = monitor.get_performance_report(days=7)
        
        # Verify report structure
        self.assertIn('report_period', report)
        self.assertIn('summary', report)
        self.assertIn('by_job_type', report)
        self.assertIn('recommendations', report)
        
        # Verify summary
        self.assertEqual(report['summary']['total_jobs'], 50)
        self.assertEqual(report['summary']['success_rate'], 0.95)
        self.assertEqual(report['summary']['job_types'], 1)
    
    def test_cleanup_and_maintenance_integration(self):
        """Test cleanup and maintenance operations."""
        # Initialize monitor
        monitor = SC_JobMonitor(self.mock_mongo_client, 'test_db')
        monitor.jobs = self.mock_jobs
        monitor.datasets = self.mock_datasets
        
        # Mock cleanup operations
        self.mock_jobs.delete_many.side_effect = [
            Mock(deleted_count=10),  # completed jobs
            Mock(deleted_count=5),   # failed jobs
            Mock(deleted_count=2)    # cancelled jobs
        ]
        
        # Perform cleanup
        result = monitor.cleanup_old_data(days=30)
        
        # Verify cleanup statistics
        self.assertEqual(result['completed_jobs_deleted'], 10)
        self.assertEqual(result['failed_jobs_deleted'], 5)
        self.assertEqual(result['cancelled_jobs_deleted'], 2)
        
        # Verify delete operations were called
        self.assertEqual(self.mock_jobs.delete_many.call_count, 3)
    
    def test_worker_management_integration(self):
        """Test worker management and monitoring."""
        # Initialize monitor
        monitor = SC_JobMonitor(self.mock_mongo_client, 'test_db')
        monitor.jobs = self.mock_jobs
        monitor.datasets = self.mock_datasets
        
        # Mock worker data
        mock_workers = [
            {
                '_id': 'worker-1',
                'job_count': 2,
                'oldest_job': datetime.utcnow() - timedelta(hours=1),
                'newest_job': datetime.utcnow() - timedelta(minutes=30),
                'job_types': ['dataset_conversion', 'google_sync']
            }
        ]
        
        self.mock_jobs.aggregate.return_value = mock_workers
        
        # Mock uptime calculation
        monitor._calculate_worker_uptime = Mock(return_value=3600.0)
        
        # Get active workers
        workers = monitor.get_active_workers()
        
        # Verify worker information
        self.assertEqual(len(workers), 1)
        worker = workers[0]
        self.assertEqual(worker['worker_id'], 'worker-1')
        self.assertEqual(worker['job_count'], 2)
        self.assertEqual(worker['uptime'], 3600.0)
        self.assertEqual(worker['status'], 'active')
        self.assertIn('dataset_conversion', worker['job_types'])
    
    def test_health_monitoring_integration(self):
        """Test health monitoring integration."""
        # Initialize monitor
        monitor = SC_JobMonitor(self.mock_mongo_client, 'test_db')
        monitor.jobs = self.mock_jobs
        monitor.datasets = self.mock_datasets
        
        # Mock health data
        monitor.job_queue = Mock()
        monitor.job_queue.get_stale_jobs = Mock(return_value=[])
        monitor.get_failed_jobs = Mock(return_value=[])
        monitor.get_active_workers = Mock(return_value=[{'worker_id': 'worker-1'}])
        
        # Mock recent completed jobs
        self.mock_jobs.find.return_value = [
            {'status': 'completed', 'completed_at': datetime.utcnow() - timedelta(minutes=30)}
        ]
        
        # Get health status
        health = monitor._get_health_status()
        
        # Verify health status
        self.assertEqual(health['overall'], 'healthy')
        self.assertEqual(health['stale_jobs'], 0)
        self.assertEqual(health['failure_rate'], 0.0)
        self.assertEqual(health['active_workers'], 1)
        self.assertEqual(len(health['issues']), 0)
    
    def test_job_cancellation_integration(self):
        """Test job cancellation workflow."""
        # Initialize monitor
        monitor = SC_JobMonitor(self.mock_mongo_client, 'test_db')
        monitor.jobs = self.mock_jobs
        monitor.datasets = self.mock_datasets
        
        # Mock job
        mock_job = {
            'job_id': 'job-123',
            'status': 'running',
            'pid': 12345
        }
        
        monitor.job_queue = Mock()
        monitor.job_queue.get_job_status = Mock(return_value=mock_job)
        monitor.job_queue.update_job_status = Mock(return_value=True)
        
        # Mock process killing
        monitor._kill_process = Mock(return_value=True)
        
        # Cancel job
        result = monitor.cancel_job('job-123')
        
        # Verify cancellation
        self.assertTrue(result)
        monitor.job_queue.update_job_status.assert_called_once_with(
            'job-123', 'cancelled', log_message="Job cancelled by user"
        )
        monitor._kill_process.assert_called_once_with(12345)
    
    def test_error_recovery_integration(self):
        """Test error recovery mechanisms."""
        # Initialize monitor
        monitor = SC_JobMonitor(self.mock_mongo_client, 'test_db')
        monitor.jobs = self.mock_jobs
        monitor.datasets = self.mock_datasets
        
        # Mock failed jobs
        mock_failed_jobs = [
            {
                'job_id': 'job-1',
                'dataset_uuid': 'dataset-1',
                'status': 'failed',
                'attempts': 2,
                'max_attempts': 3,
                'error': 'Conversion failed',
                'updated_at': datetime.utcnow() - timedelta(hours=2)
            }
        ]
        
        self.mock_jobs.find.return_value.sort.return_value = mock_failed_jobs
        
        # Mock dataset info
        monitor._get_dataset_info = Mock(return_value={
            'name': 'Failed Dataset',
            'user': 'user@example.com'
        })
        
        # Get failed jobs
        failed_jobs = monitor.get_failed_jobs(hours=24)
        
        # Verify failed jobs
        self.assertEqual(len(failed_jobs), 1)
        job = failed_jobs[0]
        self.assertEqual(job['job_id'], 'job-1')
        self.assertEqual(job['attempts'], 2)
        self.assertEqual(job['max_attempts'], 3)
        self.assertTrue(job['retry_available'])
        
        # Test retry
        monitor.job_queue = Mock()
        monitor.job_queue.retry_job = Mock(return_value=True)
        
        result = monitor.retry_failed_job('job-1')
        
        # Verify retry
        self.assertTrue(result)
        monitor.job_queue.retry_job.assert_called_once_with('job-1')


if __name__ == '__main__':
    unittest.main()
