#!/usr/bin/env python3
"""
ScientistCloud Job Queue Monitor
Simple script to check and manage the job queue.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add the SCLib_JobProcessing directory to the path
# Check if we're running inside Docker container or on host
if os.path.exists('/app'):
    # Running inside Docker container
    sys.path.insert(0, '/app')
else:
    # Running on host system - add the SCLib_JobProcessing directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sc_lib_dir = os.path.dirname(script_dir)
    sc_job_processing_dir = os.path.join(sc_lib_dir, 'SCLib_JobProcessing')
    sys.path.insert(0, sc_job_processing_dir)

from SCLib_Config import get_config, get_database_name
from SCLib_MongoConnection import get_mongo_connection


def get_job_stats() -> Dict[str, Any]:
    """Get job statistics from the database."""
    try:
        config = get_config()
        mongo_client = get_mongo_connection()
        db = mongo_client[get_database_name()]
        jobs = db.jobs
        
        # Get counts by status
        status_counts = {}
        for status in ['queued', 'processing', 'completed', 'failed', 'cancelled']:
            count = jobs.count_documents({'status': status})
            status_counts[status] = count
        
        # Get total count
        total_jobs = jobs.count_documents({})
        
        # Get recent jobs (last 24 hours)
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent_jobs = jobs.count_documents({
            'created_at': {'$gte': yesterday}
        })
        
        # Get old queued jobs (older than 1 hour)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        old_queued = jobs.count_documents({
            'status': 'queued',
            'created_at': {'$lt': one_hour_ago}
        })
        
        return {
            'total_jobs': total_jobs,
            'status_counts': status_counts,
            'recent_jobs': recent_jobs,
            'old_queued_jobs': old_queued
        }
    except Exception as e:
        print(f"Error getting job stats: {e}")
        return {}


def list_queued_jobs(limit: int = 10) -> List[Dict[str, Any]]:
    """List queued jobs with details."""
    try:
        config = get_config()
        mongo_client = get_mongo_connection()
        db = mongo_client[get_database_name()]
        jobs = db.jobs
        
        queued_jobs = list(jobs.find(
            {'status': 'queued'},
            {
                'job_id': 1,
                'created_at': 1,
                'dataset_uuid': 1,
                'user_email': 1,
                'job_type': 1
            }
        ).sort('created_at', -1).limit(limit))
        
        return queued_jobs
    except Exception as e:
        print(f"Error listing queued jobs: {e}")
        return []


def clean_old_queued_jobs(older_than_hours: int = 1) -> int:
    """Clean up old queued jobs that are likely stuck."""
    try:
        config = get_config()
        mongo_client = get_mongo_connection()
        db = mongo_client[get_database_name()]
        jobs = db.jobs
        
        cutoff_time = datetime.utcnow() - timedelta(hours=older_than_hours)
        
        # Find old queued jobs
        old_jobs = list(jobs.find({
            'status': 'queued',
            'created_at': {'$lt': cutoff_time}
        }, {'job_id': 1, 'created_at': 1}))
        
        if old_jobs:
            print(f"Found {len(old_jobs)} old queued jobs:")
            for job in old_jobs:
                age = datetime.utcnow() - job['created_at']
                print(f"  - {job['job_id']} (age: {age})")
            
            # Delete them
            result = jobs.delete_many({
                'status': 'queued',
                'created_at': {'$lt': cutoff_time}
            })
            
            print(f"Deleted {result.deleted_count} old queued jobs")
            return result.deleted_count
        else:
            print("No old queued jobs found")
            return 0
            
    except Exception as e:
        print(f"Error cleaning old jobs: {e}")
        return 0


def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python monitor_jobs.py <command> [options]")
        print("Commands:")
        print("  stats                    - Show job statistics")
        print("  list [limit]             - List queued jobs (default limit: 10)")
        print("  clean [hours]            - Clean old queued jobs (default: 1 hour)")
        print("  status <job_id>          - Show status of specific job")
        return
    
    command = sys.argv[1]
    
    if command == "stats":
        stats = get_job_stats()
        if stats:
            print("=== Job Queue Statistics ===")
            print(f"Total jobs: {stats['total_jobs']}")
            print(f"Recent jobs (24h): {stats['recent_jobs']}")
            print(f"Old queued jobs (>1h): {stats['old_queued_jobs']}")
            print("\nJobs by status:")
            for status, count in stats['status_counts'].items():
                print(f"  {status}: {count}")
    
    elif command == "list":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        jobs = list_queued_jobs(limit)
        if jobs:
            print(f"=== Queued Jobs (showing {len(jobs)}) ===")
            for job in jobs:
                age = datetime.utcnow() - job['created_at']
                print(f"  {job['job_id']} - {job.get('user_email', 'N/A')} - {age}")
        else:
            print("No queued jobs found")
    
    elif command == "clean":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        print(f"Cleaning queued jobs older than {hours} hour(s)...")
        deleted = clean_old_queued_jobs(hours)
        print(f"Cleaned {deleted} old jobs")
    
    elif command == "status":
        if len(sys.argv) < 3:
            print("Please provide a job ID")
            return
        
        job_id = sys.argv[2]
        try:
            config = get_config()
            mongo_client = get_mongo_connection()
            db = mongo_client[get_database_name()]
            jobs = db.jobs
            
            job = jobs.find_one({'job_id': job_id})
            if job:
                print(f"=== Job Status: {job_id} ===")
                print(f"Status: {job.get('status', 'unknown')}")
                print(f"Created: {job.get('created_at', 'unknown')}")
                print(f"User: {job.get('user_email', 'unknown')}")
                print(f"Type: {job.get('job_type', 'unknown')}")
                if 'dataset_uuid' in job:
                    print(f"Dataset UUID: {job['dataset_uuid']}")
            else:
                print(f"Job {job_id} not found")
        except Exception as e:
            print(f"Error getting job status: {e}")
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
