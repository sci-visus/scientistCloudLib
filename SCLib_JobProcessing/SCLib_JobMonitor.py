"""
ScientistCloud Job Monitor
Provides monitoring, statistics, and management capabilities for the job queue system.
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from SCLib_JobQueueManager import SC_JobQueueManager
from SCLib_JobTypes import SC_JobType, SC_JobStatus, SC_DatasetStatus, SC_JOB_PRIORITY


class SC_JobMonitor:
    """
    Monitor and manage the ScientistCloud job queue system.
    Provides statistics, health checks, and administrative functions.
    """
    
    def __init__(self, mongo_client: MongoClient, db_name: str):
        """
        Initialize the job monitor.
        
        Args:
            mongo_client: MongoDB client instance
            db_name: Database name
        """
        self.job_queue = SC_JobQueueManager(mongo_client, db_name)
        self.db = mongo_client[db_name]
        self.jobs = self.db.jobs
        self.datasets = self.db.visstoredatas
    
    def get_queue_overview(self) -> Dict[str, Any]:
        """
        Get comprehensive queue overview.
        
        Returns:
            Dictionary with queue statistics and health information
        """
        try:
            stats = self.job_queue.get_queue_stats()
            
            # Add additional metrics
            overview = {
                'timestamp': datetime.utcnow().isoformat(),
                'queue_stats': stats,
                'health_status': self._get_health_status(),
                'recent_activity': self._get_recent_activity(),
                'performance_metrics': self._get_performance_metrics(),
                'error_summary': self._get_error_summary()
            }
            
            return overview
            
        except Exception as e:
            return {
                'error': f"Failed to get queue overview: {str(e)}",
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a specific job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Job details or None if not found
        """
        try:
            job = self.job_queue.get_job_status(job_id)
            if not job:
                return None
            
            # Add additional details
            job_details = dict(job)
            job_details['dataset_info'] = self._get_dataset_info(job['dataset_uuid'])
            job_details['execution_time'] = self._calculate_execution_time(job)
            job_details['estimated_completion'] = self._estimate_completion(job)
            
            return job_details
            
        except Exception as e:
            print(f"Error getting job details: {e}")
            return None
    
    def get_dataset_jobs(self, dataset_uuid: str) -> List[Dict[str, Any]]:
        """
        Get all jobs for a specific dataset.
        
        Args:
            dataset_uuid: Dataset identifier
            
        Returns:
            List of job documents
        """
        try:
            jobs = self.job_queue.get_jobs_by_dataset(dataset_uuid)
            
            # Add execution time for each job
            for job in jobs:
                job['execution_time'] = self._calculate_execution_time(job)
            
            return jobs
            
        except Exception as e:
            print(f"Error getting dataset jobs: {e}")
            return []
    
    def get_active_workers(self) -> List[Dict[str, Any]]:
        """
        Get information about active workers.
        
        Returns:
            List of active worker information
        """
        try:
            pipeline = [
                {
                    '$match': {
                        'status': 'running',
                        'worker_id': {'$exists': True, '$ne': None}
                    }
                },
                {
                    '$group': {
                        '_id': '$worker_id',
                        'job_count': {'$sum': 1},
                        'oldest_job': {'$min': '$started_at'},
                        'newest_job': {'$max': '$started_at'},
                        'job_types': {'$addToSet': '$job_type'}
                    }
                },
                {
                    '$sort': {'oldest_job': 1}
                }
            ]
            
            workers = list(self.jobs.aggregate(pipeline))
            
            # Add additional worker information
            for worker in workers:
                worker['worker_id'] = worker['_id']
                worker['uptime'] = self._calculate_worker_uptime(worker['oldest_job'])
                worker['status'] = 'active'
            
            return workers
            
        except Exception as e:
            print(f"Error getting active workers: {e}")
            return []
    
    def get_failed_jobs(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        Get failed jobs from the last N hours.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of failed job documents
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            failed_jobs = list(self.jobs.find({
                'status': 'failed',
                'updated_at': {'$gte': cutoff_time}
            }).sort('updated_at', -1))
            
            # Add additional information
            for job in failed_jobs:
                job['dataset_info'] = self._get_dataset_info(job['dataset_uuid'])
                job['retry_available'] = job['attempts'] < job['max_attempts']
            
            return failed_jobs
            
        except Exception as e:
            print(f"Error getting failed jobs: {e}")
            return []
    
    def retry_failed_job(self, job_id: str) -> bool:
        """
        Retry a failed job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job was retried, False otherwise
        """
        try:
            return self.job_queue.retry_job(job_id)
        except Exception as e:
            print(f"Error retrying job: {e}")
            return False
    
    def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a pending or running job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job was cancelled, False otherwise
        """
        try:
            job = self.job_queue.get_job_status(job_id)
            if not job:
                return False
            
            if job['status'] not in ['pending', 'running']:
                print(f"Cannot cancel job {job_id} with status {job['status']}")
                return False
            
            # Update job status
            success = self.job_queue.update_job_status(
                job_id, 'cancelled',
                log_message="Job cancelled by user"
            )
            
            if success and job['status'] == 'running':
                # Try to kill the process
                pid = job.get('pid')
                if pid:
                    self._kill_process(pid)
            
            return success
            
        except Exception as e:
            print(f"Error cancelling job: {e}")
            return False
    
    def get_performance_report(self, days: int = 7) -> Dict[str, Any]:
        """
        Generate performance report for the last N days.
        
        Args:
            days: Number of days to include in report
            
        Returns:
            Performance report dictionary
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            
            # Get completed jobs
            pipeline = [
                {
                    '$match': {
                        'status': 'completed',
                        'completed_at': {'$gte': cutoff_time}
                    }
                },
                {
                    '$group': {
                        '_id': '$job_type',
                        'count': {'$sum': 1},
                        'avg_duration': {
                            '$avg': {
                                '$subtract': ['$completed_at', '$started_at']
                            }
                        },
                        'min_duration': {
                            '$min': {
                                '$subtract': ['$completed_at', '$started_at']
                            }
                        },
                        'max_duration': {
                            '$max': {
                                '$subtract': ['$completed_at', '$started_at']
                            }
                        }
                    }
                }
            ]
            
            performance_data = list(self.jobs.aggregate(pipeline))
            
            # Calculate additional metrics
            total_jobs = sum(item['count'] for item in performance_data)
            success_rate = self._calculate_success_rate(cutoff_time)
            
            report = {
                'report_period': {
                    'start': cutoff_time.isoformat(),
                    'end': datetime.utcnow().isoformat(),
                    'days': days
                },
                'summary': {
                    'total_jobs': total_jobs,
                    'success_rate': success_rate,
                    'job_types': len(performance_data)
                },
                'by_job_type': performance_data,
                'recommendations': self._generate_recommendations(performance_data)
            }
            
            return report
            
        except Exception as e:
            print(f"Error generating performance report: {e}")
            return {'error': str(e)}
    
    def cleanup_old_data(self, days: int = 30) -> Dict[str, int]:
        """
        Clean up old job data.
        
        Args:
            days: Number of days after which to delete data
            
        Returns:
            Dictionary with cleanup statistics
        """
        try:
            stats = {
                'completed_jobs_deleted': 0,
                'failed_jobs_deleted': 0,
                'cancelled_jobs_deleted': 0
            }
            
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            
            # Clean up completed jobs
            result = self.jobs.delete_many({
                'status': 'completed',
                'completed_at': {'$lt': cutoff_time}
            })
            stats['completed_jobs_deleted'] = result.deleted_count
            
            # Clean up old failed jobs (keep some for analysis)
            old_cutoff = datetime.utcnow() - timedelta(days=days * 2)
            result = self.jobs.delete_many({
                'status': 'failed',
                'updated_at': {'$lt': old_cutoff}
            })
            stats['failed_jobs_deleted'] = result.deleted_count
            
            # Clean up cancelled jobs
            result = self.jobs.delete_many({
                'status': 'cancelled',
                'updated_at': {'$lt': cutoff_time}
            })
            stats['cancelled_jobs_deleted'] = result.deleted_count
            
            return stats
            
        except Exception as e:
            print(f"Error cleaning up old data: {e}")
            return {'error': str(e)}
    
    def _get_health_status(self) -> Dict[str, Any]:
        """Get system health status."""
        try:
            # Check for stale jobs
            stale_jobs = self.job_queue.get_stale_jobs(timeout_hours=1)
            
            # Check for high failure rate
            recent_failures = self.get_failed_jobs(hours=1)
            recent_completed = list(self.jobs.find({
                'status': 'completed',
                'completed_at': {'$gte': datetime.utcnow() - timedelta(hours=1)}
            }))
            
            total_recent = len(recent_failures) + len(recent_completed)
            failure_rate = len(recent_failures) / total_recent if total_recent > 0 else 0
            
            health_status = {
                'overall': 'healthy',
                'stale_jobs': len(stale_jobs),
                'failure_rate': failure_rate,
                'active_workers': len(self.get_active_workers()),
                'issues': []
            }
            
            # Determine overall health
            if len(stale_jobs) > 5:
                health_status['overall'] = 'warning'
                health_status['issues'].append(f"{len(stale_jobs)} stale jobs detected")
            
            if failure_rate > 0.2:  # 20% failure rate
                health_status['overall'] = 'critical'
                health_status['issues'].append(f"High failure rate: {failure_rate:.1%}")
            
            return health_status
            
        except Exception as e:
            return {
                'overall': 'unknown',
                'error': str(e)
            }
    
    def _get_recent_activity(self) -> Dict[str, Any]:
        """Get recent activity summary."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=1)
            
            pipeline = [
                {
                    '$match': {
                        'updated_at': {'$gte': cutoff_time}
                    }
                },
                {
                    '$group': {
                        '_id': '$status',
                        'count': {'$sum': 1}
                    }
                }
            ]
            
            activity = list(self.jobs.aggregate(pipeline))
            return {item['_id']: item['count'] for item in activity}
            
        except Exception as e:
            return {'error': str(e)}
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        try:
            # Average job duration by type
            pipeline = [
                {
                    '$match': {
                        'status': 'completed',
                        'started_at': {'$exists': True},
                        'completed_at': {'$exists': True}
                    }
                },
                {
                    '$group': {
                        '_id': '$job_type',
                        'avg_duration_seconds': {
                            '$avg': {
                                '$subtract': ['$completed_at', '$started_at']
                            }
                        }
                    }
                }
            ]
            
            metrics = list(self.jobs.aggregate(pipeline))
            
            return {
                'avg_duration_by_type': {
                    item['_id']: item['avg_duration_seconds'] 
                    for item in metrics
                }
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _get_error_summary(self) -> Dict[str, Any]:
        """Get error summary."""
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=24)
            
            pipeline = [
                {
                    '$match': {
                        'status': 'failed',
                        'updated_at': {'$gte': cutoff_time}
                    }
                },
                {
                    '$group': {
                        '_id': '$job_type',
                        'count': {'$sum': 1},
                        'errors': {'$addToSet': '$error'}
                    }
                }
            ]
            
            error_summary = list(self.jobs.aggregate(pipeline))
            
            return {
                'by_job_type': error_summary,
                'total_failures': sum(item['count'] for item in error_summary)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _get_dataset_info(self, dataset_uuid: str) -> Optional[Dict[str, Any]]:
        """Get basic dataset information."""
        try:
            dataset = self.datasets.find_one({'uuid': dataset_uuid})
            if dataset:
                return {
                    'name': dataset.get('name', 'Unknown'),
                    'user': dataset.get('user', 'Unknown'),
                    'status': dataset.get('status', 'Unknown'),
                    'sensor': dataset.get('sensor', 'Unknown')
                }
            return None
        except Exception:
            return None
    
    def _calculate_execution_time(self, job: Dict[str, Any]) -> Optional[float]:
        """Calculate job execution time in seconds."""
        try:
            if job.get('started_at') and job.get('completed_at'):
                return (job['completed_at'] - job['started_at']).total_seconds()
            elif job.get('started_at'):
                return (datetime.utcnow() - job['started_at']).total_seconds()
            return None
        except Exception:
            return None
    
    def _estimate_completion(self, job: Dict[str, Any]) -> Optional[str]:
        """Estimate job completion time."""
        try:
            if job['status'] != 'running' or not job.get('started_at'):
                return None
            
            # Simple estimation based on job type
            job_type = job.get('job_type', '')
            estimated_duration = {
                'google_sync': 900,  # 15 minutes
                'dataset_conversion': 1800,  # 30 minutes
                'file_upload': 300,  # 5 minutes
                'file_extraction': 120,  # 2 minutes
                'data_compression': 600,  # 10 minutes
            }.get(job_type, 600)  # Default 10 minutes
            
            elapsed = (datetime.utcnow() - job['started_at']).total_seconds()
            remaining = max(0, estimated_duration - elapsed)
            
            return (datetime.utcnow() + timedelta(seconds=remaining)).isoformat()
            
        except Exception:
            return None
    
    def _calculate_worker_uptime(self, oldest_job_time: datetime) -> float:
        """Calculate worker uptime in seconds."""
        try:
            return (datetime.utcnow() - oldest_job_time).total_seconds()
        except Exception:
            return 0
    
    def _calculate_success_rate(self, cutoff_time: datetime) -> float:
        """Calculate success rate for jobs since cutoff time."""
        try:
            total_jobs = self.jobs.count_documents({
                'updated_at': {'$gte': cutoff_time},
                'status': {'$in': ['completed', 'failed']}
            })
            
            if total_jobs == 0:
                return 1.0
            
            completed_jobs = self.jobs.count_documents({
                'updated_at': {'$gte': cutoff_time},
                'status': 'completed'
            })
            
            return completed_jobs / total_jobs
            
        except Exception:
            return 0.0
    
    def _generate_recommendations(self, performance_data: List[Dict[str, Any]]) -> List[str]:
        """Generate performance recommendations."""
        recommendations = []
        
        try:
            for item in performance_data:
                job_type = item['_id']
                avg_duration = item.get('avg_duration_seconds', 0)
                
                if avg_duration > 3600:  # More than 1 hour
                    recommendations.append(
                        f"Consider optimizing {job_type} jobs - average duration is {avg_duration/60:.1f} minutes"
                    )
                
                if item['count'] > 100:  # High volume
                    recommendations.append(
                        f"High volume of {job_type} jobs ({item['count']}) - consider scaling workers"
                    )
            
            if not recommendations:
                recommendations.append("System performance is within normal parameters")
            
        except Exception as e:
            recommendations.append(f"Could not generate recommendations: {e}")
        
        return recommendations
    
    def _kill_process(self, pid: int) -> bool:
        """Kill a process by PID."""
        try:
            import os
            import signal
            os.kill(pid, signal.SIGTERM)
            return True
        except Exception as e:
            print(f"Could not kill process {pid}: {e}")
            return False
