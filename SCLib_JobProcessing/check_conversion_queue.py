#!/usr/bin/env python3
"""
Quick script to check the conversion queue status.
Shows how many datasets are waiting for conversion.
"""

import os
import sys
from pymongo import MongoClient

# Add SCLib to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(script_dir, '..'))

def get_mongo_connection():
    """Get MongoDB connection."""
    mongo_url = os.getenv('MONGO_URL')
    if not mongo_url:
        print("ERROR: MONGO_URL environment variable is required")
        sys.exit(1)
    return MongoClient(mongo_url)

def check_queue():
    """Check conversion queue status."""
    db_name = os.getenv('DB_NAME', 'scientistcloud')
    
    try:
        client = get_mongo_connection()
        db = client[db_name]
        collection = db['visstoredatas']
        
        # Count datasets by status
        statuses = ['conversion queued', 'converting', 'done', 'conversion failed', 'error']
        counts = {}
        
        for status in statuses:
            count = collection.count_documents({'status': status})
            counts[status] = count
        
        # Get queued datasets
        queued = list(collection.find(
            {'status': 'conversion queued'},
            {'uuid': 1, 'name': 1, 'sensor': 1, 'user': 1, '_id': 0}
        ).limit(10))
        
        print("=" * 60)
        print("Conversion Queue Status")
        print("=" * 60)
        print(f"\nDatabase: {db_name}")
        print(f"\nStatus Counts:")
        for status, count in counts.items():
            if count > 0:
                print(f"  {status:20s}: {count:4d}")
        
        if queued:
            print(f"\n📋 Queued for conversion (showing up to 10):")
            for i, ds in enumerate(queued, 1):
                name = ds.get('name', 'Unknown')
                uuid = ds.get('uuid', 'No UUID')
                sensor = ds.get('sensor', 'Unknown')
                user = ds.get('user', ds.get('user_id', 'Unknown'))
                print(f"  {i}. {name}")
                print(f"     UUID: {uuid}")
                print(f"     Sensor: {sensor}, User: {user}")
        else:
            print("\n✅ No datasets queued for conversion")
        
        print("\n" + "=" * 60)
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    check_queue()

