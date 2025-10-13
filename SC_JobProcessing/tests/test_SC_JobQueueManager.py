"""
Test cases for SC_JobQueueManager
Tests job creation, retrieval, status updates, and retry logic.
"""

import unittest
import uuid
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from SC_JobQueueManager import SC_JobQueueManager


class TestSC_JobQueueManager(unittest.TestCase):
    """Test cases for SC_JobQueueManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_client = Mock(spec=MongoClient)
        self.mock_db = Mock()
        self.mock_jobs = Mock()
        self.mock_datasets = Mock()
        
        self.mock_client.__getitem__.return_value = self.mock_db
        self.mock_db.__getitem__.side_effect = lambda name: {
            'jobs': self.mock_jobs,
            'visstoredatas': self.mock_datasets
        }[name]
        
        self.job_queue = SC_JobQueueManager(self.mock_client, 'test_db')
        self.job_queue.jobs = self.mock_jobs
        self.job_queue.datasets = self.mock_datasets
    
    def test_create_job_success(self):
        """Test successful job creation."""
        # Mock successful insert
        self.mock_jobs.insert_one.return_value = Mock()
        
        job_id = self.job_queue.create_job(
            dataset_uuid='test-uuid-123',
            job_type='dataset_conversion',
            parameters={'input_path': '/test/input', 'output_path': '/test/output'},
            priority=1,
            max_attempts=3
        )
        
        # Verify job was created with correct data
        self.mock_jobs.insert_one.assert_called_once()
        call_args = self.mock_jobs.insert_one.call_args[0][0]
        
        self.assertEqual(call_args['dataset_uuid'], 'test-uuid-123')
        self.assertEqual(call_args['job_type'], 'dataset_conversion')
        self.assertEqual(call_args['status'], 'pending')
        self.assertEqual(call_args['priority'], 1)
        self.assertEqual(call_args['max_attempts'], 3)
        self.assertEqual(call_args['attempts'], 0)
        self.assertIsNotNone(call_args['job_id'])
        self.assertIsNotNone(call_args['created_at'])
    
    def test_create_job_database_error(self):
        """Test job creation with database error."""
        # Mock database error
        self.mock_jobs.insert_one.side_effect = PyMongoError("Database error")
        
        with self.assertRaises(PyMongoError):
            self.job_queue.create_job(
                dataset_uuid='test-uuid-123',
                job_type='dataset_conversion',
                parameters={}
            )
    
    def test_get_next_job_success(self):
        """Test successful job retrieval."""
        # Mock job document
        mock_job = {
            'job_id': 'job-123',
            'dataset_uuid': 'dataset-123',
            'job_type': 'dataset_conversion',
            'status': 'pending',
            'priority': 1,
            'created_at': datetime.utcnow()
        }
        
        self.mock_jobs.find_one_and_update.return_value = mock_job
        
        result = self.job_queue.get_next_job('worker-123')
        
        # Verify job was retrieved and updated
        self.mock_jobs.find_one_and_update.assert_called_once()
        call_args = self.mock_jobs.find_one_and_update.call_args
        
        # Check query
        self.assertEqual(call_args[0][0], {'status': 'pending'})
        
        # Check update
        update_data = call_args[0][1]['$set']
        self.assertEqual(update_data['status'], 'running')
        self.assertEqual(update_data['worker_id'], 'worker-123')
        self.assertIsNotNone(update_data['started_at'])
        
        # Check sort
        self.assertEqual(call_args[1]['sort'], [('priority', 1), ('created_at', 1)])
        
        self.assertEqual(result, mock_job)
    
    def test_get_next_job_with_job_types_filter(self):
        """Test job retrieval with job type filtering."""
        self.mock_jobs.find_one_and_update.return_value = None
        
        self.job_queue.get_next_job('worker-123', ['dataset_conversion', 'google_sync'])
        
        call_args = self.mock_jobs.find_one_and_update.call_args
        query = call_args[0][0]
        
        self.assertEqual(query['status'], 'pending')
        self.assertEqual(query['job_type'], {'$in': ['dataset_conversion', 'google_sync']})
    
    def test_get_next_job_no_jobs_available(self):
        """Test job retrieval when no jobs are available."""
        self.mock_jobs.find_one_and_update.return_value = None
        
        result = self.job_queue.get_next_job('worker-123')
        
        self.assertIsNone(result)
    
    def test_update_job_status_success(self):
        """Test successful job status update."""
        self.mock_jobs.update_one.return_value = Mock(modified_count=1)
        
        result = self.job_queue.update_job_status(
            'job-123',
            'completed',
            result={'output': 'test'},
            log_message='Job completed successfully'
        )
        
        # Verify update was called
        self.mock_jobs.update_one.assert_called_once()
        call_args = self.mock_jobs.update_one.call_args
        
        # Check query
        self.assertEqual(call_args[0][0], {'job_id': 'job-123'})
        
        # Check update data
        update_data = call_args[0][1]['$set']
        self.assertEqual(update_data['status'], 'completed')
        self.assertEqual(update_data['result'], {'output': 'test'})
        self.assertIsNotNone(update_data['updated_at'])
        self.assertIsNotNone(update_data['completed_at'])
        
        # Check log entry
        log_update = call_args[0][1]['$push']
        self.assertIn('logs', log_update)
        self.assertEqual(log_update['logs']['message'], 'Job completed successfully')
        
        self.assertTrue(result)
    
    def test_update_job_status_job_not_found(self):
        """Test job status update when job is not found."""
        self.mock_jobs.update_one.return_value = Mock(modified_count=0)
        
        result = self.job_queue.update_job_status('job-123', 'completed')
        
        self.assertFalse(result)
    
    def test_retry_job_success(self):
        """Test successful job retry."""
        # Mock existing job
        mock_job = {
            'job_id': 'job-123',
            'attempts': 1,
            'max_attempts': 3,
            'status': 'failed'
        }
        
        self.mock_jobs.find_one.return_value = mock_job
        self.mock_jobs.update_one.return_value = Mock(modified_count=1)
        
        result = self.job_queue.retry_job('job-123')
        
        # Verify job was updated for retry
        self.mock_jobs.update_one.assert_called_once()
        call_args = self.mock_jobs.update_one.call_args
        
        update_data = call_args[0][1]['$set']
        self.assertEqual(update_data['status'], 'pending')
        self.assertEqual(update_data['attempts'], 2)  # Incremented
        self.assertIsNone(update_data['worker_id'])
        self.assertIsNone(update_data['pid'])
        self.assertIsNone(update_data['lock_file'])
        self.assertIsNone(update_data['error'])
        
        self.assertTrue(result)
    
    def test_retry_job_max_attempts_reached(self):
        """Test job retry when max attempts reached."""
        mock_job = {
            'job_id': 'job-123',
            'attempts': 3,
            'max_attempts': 3
        }
        
        self.mock_jobs.find_one.return_value = mock_job
        
        result = self.job_queue.retry_job('job-123')
        
        # Should not update the job
        self.mock_jobs.update_one.assert_not_called()
        self.assertFalse(result)
    
    def test_retry_job_not_found(self):
        """Test job retry when job is not found."""
        self.mock_jobs.find_one.return_value = None
        
        result = self.job_queue.retry_job('job-123')
        
        self.assertFalse(result)
    
    def test_get_job_status_success(self):
        """Test successful job status retrieval."""
        mock_job = {
            'job_id': 'job-123',
            'status': 'running',
            'dataset_uuid': 'dataset-123'
        }
        
        self.mock_jobs.find_one.return_value = mock_job
        
        result = self.job_queue.get_job_status('job-123')
        
        self.mock_jobs.find_one.assert_called_once_with({'job_id': 'job-123'})
        self.assertEqual(result, mock_job)
    
    def test_get_job_status_not_found(self):
        """Test job status retrieval when job is not found."""
        self.mock_jobs.find_one.return_value = None
        
        result = self.job_queue.get_job_status('job-123')
        
        self.assertIsNone(result)
    
    def test_get_jobs_by_dataset(self):
        """Test retrieving jobs by dataset UUID."""
        mock_jobs = [
            {'job_id': 'job-1', 'dataset_uuid': 'dataset-123', 'status': 'completed'},
            {'job_id': 'job-2', 'dataset_uuid': 'dataset-123', 'status': 'running'}
        ]
        
        self.mock_jobs.find.return_value.sort.return_value = mock_jobs
        
        result = self.job_queue.get_jobs_by_dataset('dataset-123')
        
        self.mock_jobs.find.assert_called_once_with({'dataset_uuid': 'dataset-123'})
        self.assertEqual(result, mock_jobs)
    
    def test_get_stale_jobs(self):
        """Test retrieving stale jobs."""
        mock_stale_jobs = [
            {'job_id': 'job-1', 'status': 'running', 'started_at': datetime.utcnow() - timedelta(hours=2)},
            {'job_id': 'job-2', 'status': 'running', 'started_at': datetime.utcnow() - timedelta(hours=3)}
        ]
        
        self.mock_jobs.find.return_value = mock_stale_jobs
        
        result = self.job_queue.get_stale_jobs(timeout_hours=1)
        
        # Verify query
        call_args = self.mock_jobs.find.call_args[0][0]
        self.assertEqual(call_args['status'], 'running')
        self.assertIn('started_at', call_args)
        
        self.assertEqual(result, mock_stale_jobs)
    
    def test_cleanup_completed_jobs(self):
        """Test cleanup of old completed jobs."""
        self.mock_jobs.delete_many.return_value = Mock(deleted_count=5)
        
        result = self.job_queue.cleanup_completed_jobs(days_old=30)
        
        # Verify delete query
        call_args = self.mock_jobs.delete_many.call_args[0][0]
        self.assertEqual(call_args['status'], 'completed')
        self.assertIn('completed_at', call_args)
        
        self.assertEqual(result, 5)
    
    def test_get_queue_stats(self):
        """Test queue statistics retrieval."""
        # Mock count_documents calls
        self.mock_jobs.count_documents.side_effect = [100, 10, 5, 80, 5]
        
        # Mock aggregate for job type breakdown
        mock_aggregate_result = [
            {'_id': 'dataset_conversion', 'count': 50},
            {'_id': 'google_sync', 'count': 30}
        ]
        self.mock_jobs.aggregate.return_value = mock_aggregate_result
        
        result = self.job_queue.get_queue_stats()
        
        # Verify statistics
        self.assertEqual(result['total_jobs'], 100)
        self.assertEqual(result['pending_jobs'], 10)
        self.assertEqual(result['running_jobs'], 5)
        self.assertEqual(result['completed_jobs'], 80)
        self.assertEqual(result['failed_jobs'], 5)
        self.assertEqual(result['job_types']['dataset_conversion'], 50)
        self.assertEqual(result['job_types']['google_sync'], 30)
    
    def test_update_dataset_status_success(self):
        """Test successful dataset status update."""
        self.mock_datasets.update_one.return_value = Mock(modified_count=1)
        
        result = self.job_queue.update_dataset_status('dataset-123', 'done')
        
        # Verify update
        call_args = self.mock_datasets.update_one.call_args
        self.assertEqual(call_args[0][0], {'uuid': 'dataset-123'})
        
        update_data = call_args[0][1]['$set']
        self.assertEqual(update_data['status'], 'done')
        self.assertIsNotNone(update_data['updated_at'])
        
        self.assertTrue(result)
    
    def test_update_dataset_status_not_found(self):
        """Test dataset status update when dataset is not found."""
        self.mock_datasets.update_one.return_value = Mock(modified_count=0)
        
        result = self.job_queue.update_dataset_status('dataset-123', 'done')
        
        self.assertFalse(result)
    
    def test_create_indexes(self):
        """Test index creation."""
        # Mock successful index creation
        self.mock_jobs.create_index.return_value = 'index_name'
        
        # This should not raise an exception
        self.job_queue._create_indexes()
        
        # Verify indexes were created
        expected_calls = [
            [("status", 1), ("priority", 1), ("created_at", 1)],
            [("dataset_uuid", 1)],
            [("worker_id", 1)],
            [("status", 1), ("started_at", 1)]
        ]
        
        self.assertEqual(self.mock_jobs.create_index.call_count, len(expected_calls))
    
    def test_create_indexes_with_error(self):
        """Test index creation with error."""
        # Mock index creation error
        self.mock_jobs.create_index.side_effect = PyMongoError("Index error")
        
        # Should not raise exception, just print warning
        self.job_queue._create_indexes()
        
        # Verify indexes were attempted
        self.assertEqual(self.mock_jobs.create_index.call_count, 4)


if __name__ == '__main__':
    unittest.main()
