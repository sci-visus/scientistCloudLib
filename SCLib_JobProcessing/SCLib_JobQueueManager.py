"""
ScientistCloud Job Queue Manager
Handles job creation, management, and status tracking for the ScientistCloud platform.
"""

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from pymongo import MongoClient
from pymongo.errors import PyMongoError


class SCLib_JobQueueManager:
    """
    Manages job queue operations for ScientistCloud.
    Handles job creation, retrieval, status updates, and retry logic.
    """
    
    def __init__(self, mongo_client: MongoClient, db_name: str):
        """
        Initialize the job queue manager.
        
        Args:
            mongo_client: MongoDB client instance
            db_name: Database name
        """
        self.db = mongo_client[db_name]
        self.jobs = self.db.jobs
        self.datasets = self.db.visstoredatas
        
        # Create indexes for better performance
        self._create_indexes()
    
    def _create_indexes(self):
        """Create database indexes for optimal performance."""
        indexes = [
            [("status", 1), ("priority", 1), ("created_at", 1)],  # Job retrieval
            [("dataset_uuid", 1)],  # Dataset lookup
            [("worker_id", 1)],  # Worker lookup
            [("status", 1), ("started_at", 1)]  # Stale job detection
        ]
        
        for index in indexes:
            try:
                self.jobs.create_index(index)
            except PyMongoError as e:
                print(f"Warning: Could not create index {index}: {e}")
    
    def create_job(self, dataset_uuid: str, job_type: str, parameters: Dict[str, Any], 
                   priority: int = 2, max_attempts: int = 3) -> str:
        """
        Create a new job for a dataset.
        
        Args:
            dataset_uuid: UUID of the dataset
            job_type: Type of job (google_sync, dataset_conversion, file_upload, etc.)
            parameters: Job-specific parameters
            priority: Job priority (1=high, 2=normal, 3=low)
            max_attempts: Maximum number of retry attempts
            
        Returns:
            job_id: Unique identifier for the created job
        """
        job = {
            'job_id': str(uuid.uuid4()),
            'dataset_uuid': dataset_uuid,
            'job_type': job_type,
            'status': 'pending',
            'priority': priority,
            'created_at': datetime.utcnow(),
            'started_at': None,
            'completed_at': None,
            'attempts': 0,
            'max_attempts': max_attempts,
            'worker_id': None,
            'pid': None,
            'lock_file': None,
            'parameters': parameters,
            'result': None,
            'error': None,
            'logs': [],
            'updated_at': datetime.utcnow()
        }
        
        try:
            self.jobs.insert_one(job)
            print(f"Created job {job['job_id']} for dataset {dataset_uuid}")
            return job['job_id']
        except PyMongoError as e:
            print(f"Error creating job: {e}")
            raise
    
    def get_next_job(self, worker_id: str, job_types: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Get the next job for a worker.
        
        Args:
            worker_id: Identifier for the worker requesting the job
            job_types: Optional list of job types to filter by
            
        Returns:
            Job document or None if no jobs available
        """
        query = {'status': 'pending'}
        if job_types:
            query['job_type'] = {'$in': job_types}
        
        try:
            job = self.jobs.find_one_and_update(
                query,
                {
                    '$set': {
                        'status': 'running',
                        'worker_id': worker_id,
                        'started_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow()
                    }
                },
                sort=[('priority', 1), ('created_at', 1)]
            )
            
            if job:
                print(f"Assigned job {job['job_id']} to worker {worker_id}")
            
            return job
        except PyMongoError as e:
            print(f"Error getting next job: {e}")
            return None
    
    def update_job_status(self, job_id: str, status: str, result: Optional[Dict[str, Any]] = None, 
                         error: Optional[str] = None, log_message: Optional[str] = None) -> bool:
        """
        Update job status and add log entry.
        
        Args:
            job_id: Job identifier
            status: New status
            result: Job result data
            error: Error message if applicable
            log_message: Log message to add
            
        Returns:
            True if update successful, False otherwise
        """
        update_data = {
            'status': status,
            'updated_at': datetime.utcnow()
        }
        
        if status == 'completed':
            update_data['completed_at'] = datetime.utcnow()
        if result:
            update_data['result'] = result
        if error:
            update_data['error'] = error
        
        # Prepare update document
        update_doc = {'$set': update_data}
        
        # Add log entry if provided
        if log_message:
            log_entry = {
                'timestamp': datetime.utcnow(),
                'message': log_message
            }
            update_doc['$push'] = {'logs': log_entry}
        
        try:
            result = self.jobs.update_one({'job_id': job_id}, update_doc)
            if result.modified_count > 0:
                print(f"Updated job {job_id} status to {status}")
                return True
            else:
                print(f"Job {job_id} not found or not updated")
                return False
        except PyMongoError as e:
            print(f"Error updating job status: {e}")
            return False
    
    def retry_job(self, job_id: str) -> bool:
        """
        Retry a failed job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job was retried, False if max attempts reached
        """
        try:
            job = self.jobs.find_one({'job_id': job_id})
            if not job:
                print(f"Job {job_id} not found")
                return False
            
            if job['attempts'] >= job['max_attempts']:
                print(f"Job {job_id} has reached max attempts ({job['max_attempts']})")
                return False
            
            # Reset job for retry
            self.jobs.update_one(
                {'job_id': job_id},
                {
                    '$set': {
                        'status': 'pending',
                        'attempts': job['attempts'] + 1,
                        'worker_id': None,
                        'pid': None,
                        'lock_file': None,
                        'error': None,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            print(f"Retrying job {job_id} (attempt {job['attempts'] + 1}/{job['max_attempts']})")
            return True
            
        except PyMongoError as e:
            print(f"Error retrying job: {e}")
            return False
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job status and details.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job document or None if not found
        """
        try:
            return self.jobs.find_one({'job_id': job_id})
        except PyMongoError as e:
            print(f"Error getting job status: {e}")
            return None
    
    def get_jobs_by_dataset(self, dataset_uuid: str) -> List[Dict[str, Any]]:
        """
        Get all jobs for a specific dataset.
        
        Args:
            dataset_uuid: Dataset identifier
            
        Returns:
            List of job documents
        """
        try:
            return list(self.jobs.find({'dataset_uuid': dataset_uuid}).sort('created_at', -1))
        except PyMongoError as e:
            print(f"Error getting jobs by dataset: {e}")
            return []
    
    def get_stale_jobs(self, timeout_hours: int = 1) -> List[Dict[str, Any]]:
        """
        Get jobs that have been running for too long.
        
        Args:
            timeout_hours: Hours after which a job is considered stale
            
        Returns:
            List of stale job documents
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=timeout_hours)
            return list(self.jobs.find({
                'status': 'running',
                'started_at': {'$lt': cutoff_time}
            }))
        except PyMongoError as e:
            print(f"Error getting stale jobs: {e}")
            return []
    
    def cleanup_completed_jobs(self, days_old: int = 30) -> int:
        """
        Clean up old completed jobs.
        
        Args:
            days_old: Number of days after which to delete completed jobs
            
        Returns:
            Number of jobs deleted
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days_old)
            result = self.jobs.delete_many({
                'status': 'completed',
                'completed_at': {'$lt': cutoff_time}
            })
            print(f"Cleaned up {result.deleted_count} old completed jobs")
            return result.deleted_count
        except PyMongoError as e:
            print(f"Error cleaning up jobs: {e}")
            return 0
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.
        
        Returns:
            Dictionary with queue statistics
        """
        try:
            stats = {
                'total_jobs': self.jobs.count_documents({}),
                'pending_jobs': self.jobs.count_documents({'status': 'pending'}),
                'running_jobs': self.jobs.count_documents({'status': 'running'}),
                'completed_jobs': self.jobs.count_documents({'status': 'completed'}),
                'failed_jobs': self.jobs.count_documents({'status': 'failed'}),
                'job_types': {}
            }
            
            # Get job type breakdown
            pipeline = [
                {'$group': {'_id': '$job_type', 'count': {'$sum': 1}}},
                {'$sort': {'count': -1}}
            ]
            job_types = list(self.jobs.aggregate(pipeline))
            stats['job_types'] = {item['_id']: item['count'] for item in job_types}
            
            return stats
        except PyMongoError as e:
            print(f"Error getting queue stats: {e}")
            return {}
    
    def update_dataset_status(self, dataset_uuid: str, status: str) -> bool:
        """
        Update dataset status in the main dataset collection.
        
        Args:
            dataset_uuid: Dataset identifier
            status: New status
            
        Returns:
            True if update successful, False otherwise
        """
        try:
            result = self.datasets.update_one(
                {'uuid': dataset_uuid},
                {'$set': {'status': status, 'updated_at': datetime.utcnow()}}
            )
            if result.modified_count > 0:
                print(f"Updated dataset {dataset_uuid} status to {status}")
                return True
            else:
                print(f"Dataset {dataset_uuid} not found or not updated")
                return False
        except PyMongoError as e:
            print(f"Error updating dataset status: {e}")
            return False
