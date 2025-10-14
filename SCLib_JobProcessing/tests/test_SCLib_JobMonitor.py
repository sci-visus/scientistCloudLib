"""
Test cases for SC_JobMonitor
Tests monitoring, statistics, and administrative functions.
"""

import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from SCLib_JobMonitor import SCLib_JobMonitor
from SCLib_JobQueueManager import SCLib_JobQueueManager


class TestSCLib_JobMonitor(unittest.TestCase):
    """Test cases for SC_JobMonitor."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_mongo_client = Mock()
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
        
        with patch('SCLib_JobMonitor.SCLib_JobQueueManager') as mock_job_queue_class:
            mock_job_queue_class.return_value = self.mock_job_queue
            
            self.monitor = SCLib_JobMonitor(self.mock_mongo_client, 'test_db')
            self.monitor.jobs = self.mock_jobs
            self.monitor.datasets = self.mock_datasets
    
    def test_get_queue_overview_success(self):
        """Test successful queue overview retrieval."""
        # Mock queue stats
        mock_stats = {
            'total_jobs': 100,
            'pending_jobs': 10,
            'running_jobs': 5,
            'completed_jobs': 80,
            'failed_jobs': 5
        }
        self.mock_job_queue.get_queue_stats.return_value = mock_stats
        
        # Mock health status
        with patch.object(self.monitor, '_get_health_status') as mock_health:
            mock_health.return_value = {'overall': 'healthy'}
            
            # Mock recent activity
            with patch.object(self.monitor, '_get_recent_activity') as mock_activity:
                mock_activity.return_value = {'completed': 5, 'failed': 1}
                
                # Mock performance metrics
                with patch.object(self.monitor, '_get_performance_metrics') as mock_perf:
                    mock_perf.return_value = {'avg_duration_by_type': {'dataset_conversion': 1200}}
                    
                    # Mock error summary
                    with patch.object(self.monitor, '_get_error_summary') as mock_errors:
                        mock_errors.return_value = {'total_failures': 1}
                        
                        result = self.monitor.get_queue_overview()
                        
                        # Verify structure
                        self.assertIn('timestamp', result)
                        self.assertIn('queue_stats', result)
                        self.assertIn('health_status', result)
                        self.assertIn('recent_activity', result)
                        self.assertIn('performance_metrics', result)
                        self.assertIn('error_summary', result)
                        
                        # Verify values
                        self.assertEqual(result['queue_stats'], mock_stats)
                        self.assertEqual(result['health_status']['overall'], 'healthy')
                        self.assertEqual(result['recent_activity']['completed'], 5)
    
    def test_get_queue_overview_error(self):
        """Test queue overview with error."""
        # Mock error in queue stats
        self.mock_job_queue.get_queue_stats.side_effect = Exception("Database error")
        
        result = self.monitor.get_queue_overview()
        
        # Verify error handling
        self.assertIn('error', result)
        self.assertIn('timestamp', result)
        self.assertIn('Failed to get queue overview', result['error'])
    
    def test_get_job_details_success(self):
        """Test successful job details retrieval."""
        # Mock job
        mock_job = {
            'job_id': 'job-123',
            'status': 'running',
            'dataset_uuid': 'dataset-123',
            'started_at': datetime.utcnow() - timedelta(minutes=5),
            'completed_at': None
        }
        
        self.mock_job_queue.get_job_status.return_value = mock_job
        
        # Mock dataset info
        with patch.object(self.monitor, '_get_dataset_info') as mock_dataset_info:
            mock_dataset_info.return_value = {
                'name': 'Test Dataset',
                'user': 'test@example.com',
                'status': 'processing'
            }
            
            # Mock execution time calculation
            with patch.object(self.monitor, '_calculate_execution_time') as mock_exec_time:
                mock_exec_time.return_value = 300.0
                
                # Mock completion estimation
                with patch.object(self.monitor, '_estimate_completion') as mock_estimate:
                    mock_estimate.return_value = '2024-01-15T12:00:00Z'
                    
                    result = self.monitor.get_job_details('job-123')
                    
                    # Verify structure
                    self.assertIn('job_id', result)
                    self.assertIn('status', result)
                    self.assertIn('dataset_info', result)
                    self.assertIn('execution_time', result)
                    self.assertIn('estimated_completion', result)
                    
                    # Verify values
                    self.assertEqual(result['job_id'], 'job-123')
                    self.assertEqual(result['status'], 'running')
                    self.assertEqual(result['execution_time'], 300.0)
                    self.assertEqual(result['estimated_completion'], '2024-01-15T12:00:00Z')
    
    def test_get_job_details_not_found(self):
        """Test job details retrieval when job not found."""
        self.mock_job_queue.get_job_status.return_value = None
        
        result = self.monitor.get_job_details('job-123')
        
        self.assertIsNone(result)
    
    def test_get_dataset_jobs(self):
        """Test retrieving jobs for a dataset."""
        # Mock jobs
        mock_jobs = [
            {
                'job_id': 'job-1',
                'dataset_uuid': 'dataset-123',
                'status': 'completed',
                'started_at': datetime.utcnow() - timedelta(minutes=10),
                'completed_at': datetime.utcnow() - timedelta(minutes=5)
            },
            {
                'job_id': 'job-2',
                'dataset_uuid': 'dataset-123',
                'status': 'running',
                'started_at': datetime.utcnow() - timedelta(minutes=2)
            }
        ]
        
        self.mock_job_queue.get_jobs_by_dataset.return_value = mock_jobs
        
        # Mock execution time calculation
        with patch.object(self.monitor, '_calculate_execution_time') as mock_exec_time:
            mock_exec_time.side_effect = [300.0, 120.0]  # 5 min, 2 min
            
            result = self.monitor.get_dataset_jobs('dataset-123')
            
            # Verify jobs were returned
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]['job_id'], 'job-1')
            self.assertEqual(result[1]['job_id'], 'job-2')
            
            # Verify execution times were added
            self.assertEqual(result[0]['execution_time'], 300.0)
            self.assertEqual(result[1]['execution_time'], 120.0)
    
    def test_get_active_workers(self):
        """Test getting active workers."""
        # Mock aggregation result
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
        with patch.object(self.monitor, '_calculate_worker_uptime') as mock_uptime:
            mock_uptime.return_value = 3600.0  # 1 hour
            
            result = self.monitor.get_active_workers()
            
            # Verify worker information
            self.assertEqual(len(result), 1)
            worker = result[0]
            self.assertEqual(worker['worker_id'], 'worker-1')
            self.assertEqual(worker['job_count'], 2)
            self.assertEqual(worker['uptime'], 3600.0)
            self.assertEqual(worker['status'], 'active')
            self.assertIn('dataset_conversion', worker['job_types'])
    
    def test_get_failed_jobs(self):
        """Test getting failed jobs."""
        # Mock failed jobs
        mock_failed_jobs = [
            {
                'job_id': 'job-1',
                'dataset_uuid': 'dataset-123',
                'status': 'failed',
                'attempts': 2,
                'max_attempts': 3,
                'error': 'Conversion failed',
                'updated_at': datetime.utcnow() - timedelta(hours=2)
            }
        ]
        
        self.mock_jobs.find.return_value.sort.return_value = mock_failed_jobs
        
        # Mock dataset info
        with patch.object(self.monitor, '_get_dataset_info') as mock_dataset_info:
            mock_dataset_info.return_value = {
                'name': 'Failed Dataset',
                'user': 'user@example.com'
            }
            
            result = self.monitor.get_failed_jobs(hours=24)
            
            # Verify failed jobs
            self.assertEqual(len(result), 1)
            job = result[0]
            self.assertEqual(job['job_id'], 'job-1')
            self.assertEqual(job['attempts'], 2)
            self.assertEqual(job['max_attempts'], 3)
            self.assertTrue(job['retry_available'])
            self.assertIn('dataset_info', job)
    
    def test_retry_failed_job_success(self):
        """Test successful job retry."""
        self.mock_job_queue.retry_job.return_value = True
        
        result = self.monitor.retry_failed_job('job-123')
        
        self.assertTrue(result)
        self.mock_job_queue.retry_job.assert_called_once_with('job-123')
    
    def test_retry_failed_job_failure(self):
        """Test job retry failure."""
        self.mock_job_queue.retry_job.return_value = False
        
        result = self.monitor.retry_failed_job('job-123')
        
        self.assertFalse(result)
    
    def test_cancel_job_success(self):
        """Test successful job cancellation."""
        # Mock job
        mock_job = {
            'job_id': 'job-123',
            'status': 'running',
            'pid': 12345
        }
        
        self.mock_job_queue.get_job_status.return_value = mock_job
        self.mock_job_queue.update_job_status.return_value = True
        
        # Mock process killing
        with patch.object(self.monitor, '_kill_process') as mock_kill:
            mock_kill.return_value = True
            
            result = self.monitor.cancel_job('job-123')
            
            # Verify job was cancelled
            self.assertTrue(result)
            self.mock_job_queue.update_job_status.assert_called_once_with(
                'job-123', 'cancelled', log_message="Job cancelled by user"
            )
            mock_kill.assert_called_once_with(12345)
    
    def test_cancel_job_not_found(self):
        """Test job cancellation when job not found."""
        self.mock_job_queue.get_job_status.return_value = None
        
        result = self.monitor.cancel_job('job-123')
        
        self.assertFalse(result)
    
    def test_cancel_job_invalid_status(self):
        """Test job cancellation with invalid status."""
        mock_job = {
            'job_id': 'job-123',
            'status': 'completed'  # Cannot cancel completed job
        }
        
        self.mock_job_queue.get_job_status.return_value = mock_job
        
        result = self.monitor.cancel_job('job-123')
        
        self.assertFalse(result)
        self.mock_job_queue.update_job_status.assert_not_called()
    
    def test_get_performance_report(self):
        """Test performance report generation."""
        # Mock aggregation result
        mock_performance_data = [
            {
                '_id': 'dataset_conversion',
                'count': 50,
                'avg_duration': 1800.0,  # 30 minutes
                'min_duration': 600.0,   # 10 minutes
                'max_duration': 3600.0   # 60 minutes
            }
        ]
        
        self.mock_jobs.aggregate.return_value = mock_performance_data
        
        # Mock success rate calculation
        with patch.object(self.monitor, '_calculate_success_rate') as mock_success_rate:
            mock_success_rate.return_value = 0.95  # 95%
            
            # Mock recommendations
            with patch.object(self.monitor, '_generate_recommendations') as mock_recommendations:
                mock_recommendations.return_value = ['Consider optimizing dataset_conversion jobs']
                
                result = self.monitor.get_performance_report(days=7)
                
                # Verify report structure
                self.assertIn('report_period', result)
                self.assertIn('summary', result)
                self.assertIn('by_job_type', result)
                self.assertIn('recommendations', result)
                
                # Verify summary
                self.assertEqual(result['summary']['total_jobs'], 50)
                self.assertEqual(result['summary']['success_rate'], 0.95)
                self.assertEqual(result['summary']['job_types'], 1)
                
                # Verify job type data
                self.assertEqual(len(result['by_job_type']), 1)
                job_type_data = result['by_job_type'][0]
                self.assertEqual(job_type_data['_id'], 'dataset_conversion')
                self.assertEqual(job_type_data['count'], 50)
                self.assertEqual(job_type_data['avg_duration'], 1800.0)
    
    def test_cleanup_old_data(self):
        """Test cleanup of old data."""
        # Mock delete operations
        self.mock_jobs.delete_many.side_effect = [
            Mock(deleted_count=10),  # completed jobs
            Mock(deleted_count=5),   # failed jobs
            Mock(deleted_count=2)    # cancelled jobs
        ]
        
        result = self.monitor.cleanup_old_data(days=30)
        
        # Verify cleanup statistics
        self.assertEqual(result['completed_jobs_deleted'], 10)
        self.assertEqual(result['failed_jobs_deleted'], 5)
        self.assertEqual(result['cancelled_jobs_deleted'], 2)
        
        # Verify delete operations were called
        self.assertEqual(self.mock_jobs.delete_many.call_count, 3)
    
    def test_get_health_status_healthy(self):
        """Test health status when system is healthy."""
        # Mock no stale jobs
        self.mock_job_queue.get_stale_jobs.return_value = []
        
        # Mock no recent failures
        with patch.object(self.monitor, 'get_failed_jobs') as mock_failed:
            mock_failed.return_value = []
            
            # Mock recent completed jobs
            self.mock_jobs.find.return_value = [
                {'status': 'completed', 'completed_at': datetime.utcnow() - timedelta(minutes=30)}
            ]
            
            # Mock active workers
            with patch.object(self.monitor, 'get_active_workers') as mock_workers:
                mock_workers.return_value = [{'worker_id': 'worker-1'}]
                
                result = self.monitor._get_health_status()
                
                # Verify healthy status
                self.assertEqual(result['overall'], 'healthy')
                self.assertEqual(result['stale_jobs'], 0)
                self.assertEqual(result['failure_rate'], 0.0)
                self.assertEqual(result['active_workers'], 1)
                self.assertEqual(len(result['issues']), 0)
    
    def test_get_health_status_warning(self):
        """Test health status when system has warnings."""
        # Mock stale jobs
        self.mock_job_queue.get_stale_jobs.return_value = [
            {'job_id': 'job-1'}, {'job_id': 'job-2'}, {'job_id': 'job-3'},
            {'job_id': 'job-4'}, {'job_id': 'job-5'}, {'job_id': 'job-6'}  # 6 stale jobs
        ]
        
        # Mock no recent failures
        with patch.object(self.monitor, 'get_failed_jobs') as mock_failed:
            mock_failed.return_value = []
            
            # Mock recent completed jobs
            self.mock_jobs.find.return_value = [
                {'status': 'completed', 'completed_at': datetime.utcnow() - timedelta(minutes=30)}
            ]
            
            # Mock active workers
            with patch.object(self.monitor, 'get_active_workers') as mock_workers:
                mock_workers.return_value = [{'worker_id': 'worker-1'}]
                
                result = self.monitor._get_health_status()
                
                # Verify warning status
                self.assertEqual(result['overall'], 'warning')
                self.assertEqual(result['stale_jobs'], 6)
                self.assertIn('6 stale jobs detected', result['issues'])
    
    def test_get_health_status_critical(self):
        """Test health status when system is critical."""
        # Mock no stale jobs
        self.mock_job_queue.get_stale_jobs.return_value = []
        
        # Mock high failure rate
        with patch.object(self.monitor, 'get_failed_jobs') as mock_failed:
            mock_failed.return_value = [
                {'job_id': 'job-1'}, {'job_id': 'job-2'}, {'job_id': 'job-3'}  # 3 failures
            ]
            
            # Mock few completed jobs
            self.mock_jobs.find.return_value = [
                {'status': 'completed', 'completed_at': datetime.utcnow() - timedelta(minutes=30)},
                {'status': 'completed', 'completed_at': datetime.utcnow() - timedelta(minutes=20)}
            ]  # 2 completed
            
            # Mock active workers
            with patch.object(self.monitor, 'get_active_workers') as mock_workers:
                mock_workers.return_value = [{'worker_id': 'worker-1'}]
                
                result = self.monitor._get_health_status()
                
                # Verify critical status (3 failures out of 5 total = 60% failure rate)
                self.assertEqual(result['overall'], 'critical')
                self.assertGreater(result['failure_rate'], 0.2)  # > 20%
                self.assertIn('High failure rate', result['issues'][0])
    
    def test_calculate_execution_time(self):
        """Test execution time calculation."""
        # Test with completed job
        job = {
            'started_at': datetime.utcnow() - timedelta(minutes=5),
            'completed_at': datetime.utcnow() - timedelta(minutes=2)
        }
        
        result = self.monitor._calculate_execution_time(job)
        
        # Should be approximately 3 minutes (180 seconds)
        self.assertAlmostEqual(result, 180.0, delta=10.0)
    
    def test_calculate_execution_time_running(self):
        """Test execution time calculation for running job."""
        job = {
            'started_at': datetime.utcnow() - timedelta(minutes=3),
            'completed_at': None
        }
        
        result = self.monitor._calculate_execution_time(job)
        
        # Should be approximately 3 minutes (180 seconds)
        self.assertAlmostEqual(result, 180.0, delta=10.0)
    
    def test_calculate_execution_time_no_times(self):
        """Test execution time calculation with no times."""
        job = {}
        
        result = self.monitor._calculate_execution_time(job)
        
        self.assertIsNone(result)
    
    def test_estimate_completion(self):
        """Test completion time estimation."""
        job = {
            'status': 'running',
            'started_at': datetime.utcnow() - timedelta(minutes=5),
            'job_type': 'dataset_conversion'
        }
        
        result = self.monitor._estimate_completion(job)
        
        # Should return a future timestamp
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)
    
    def test_estimate_completion_not_running(self):
        """Test completion estimation for non-running job."""
        job = {
            'status': 'completed',
            'started_at': datetime.utcnow() - timedelta(minutes=5)
        }
        
        result = self.monitor._estimate_completion(job)
        
        self.assertIsNone(result)
    
    def test_calculate_worker_uptime(self):
        """Test worker uptime calculation."""
        oldest_job_time = datetime.utcnow() - timedelta(hours=2)
        
        result = self.monitor._calculate_worker_uptime(oldest_job_time)
        
        # Should be approximately 2 hours (7200 seconds)
        self.assertAlmostEqual(result, 7200.0, delta=60.0)
    
    def test_calculate_success_rate(self):
        """Test success rate calculation."""
        # Mock total jobs
        self.mock_jobs.count_documents.side_effect = [10, 8]  # 10 total, 8 completed
        
        result = self.monitor._calculate_success_rate(datetime.utcnow() - timedelta(hours=1))
        
        # Should be 8/10 = 0.8
        self.assertEqual(result, 0.8)
    
    def test_calculate_success_rate_no_jobs(self):
        """Test success rate calculation with no jobs."""
        # Mock no jobs
        self.mock_jobs.count_documents.return_value = 0
        
        result = self.monitor._calculate_success_rate(datetime.utcnow() - timedelta(hours=1))
        
        # Should be 1.0 (100%) when no jobs
        self.assertEqual(result, 1.0)
    
    def test_generate_recommendations(self):
        """Test recommendation generation."""
        performance_data = [
            {
                '_id': 'dataset_conversion',
                'count': 150,  # High volume
                'avg_duration_seconds': 7200.0  # 2 hours (long duration)
            }
        ]
        
        result = self.monitor._generate_recommendations(performance_data)
        
        # Should generate recommendations for high volume and long duration
        self.assertGreater(len(result), 0)
        self.assertTrue(any('high volume' in rec.lower() for rec in result))
        self.assertTrue(any('optimizing' in rec.lower() for rec in result))
    
    def test_generate_recommendations_normal(self):
        """Test recommendation generation for normal performance."""
        performance_data = [
            {
                '_id': 'dataset_conversion',
                'count': 10,  # Low volume
                'avg_duration': 600.0  # 10 minutes (normal duration)
            }
        ]
        
        result = self.monitor._generate_recommendations(performance_data)
        
        # Should generate normal recommendation
        self.assertEqual(len(result), 1)
        self.assertIn('normal parameters', result[0].lower())
    
    def test_kill_process_success(self):
        """Test successful process killing."""
        with patch('os.kill') as mock_kill:
            result = self.monitor._kill_process(12345)
            
            self.assertTrue(result)
            mock_kill.assert_called_once_with(12345, 15)  # SIGTERM
    
    def test_kill_process_failure(self):
        """Test process killing failure."""
        with patch('os.kill', side_effect=OSError("Process not found")):
            result = self.monitor._kill_process(12345)
            
            self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
