#!/usr/bin/env python3
"""
Example usage of SC_Config and SC_MongoConnection
Demonstrates how to use the configuration system and MongoDB connection manager.
"""

import os
import sys
from datetime import datetime

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from SC_Config import get_config, get_collection_name, get_database_name, get_mongo_url
from SC_MongoConnection import (
    get_mongo_connection, get_collection_by_type, 
    mongo_collection_by_type_context, execute_collection_query,
    check_mongo_health, monitor_mongo_performance
)


def main():
    """Main example function."""
    print("ScientistCloud Configuration and MongoDB Connection Example")
    print("=" * 70)
    
    try:
        # 1. Configuration Examples
        print("\n1. Configuration Examples")
        print("-" * 30)
        
        # Get configuration
        config = get_config()
        
        # Print configuration
        config.print_config()
        
        # Get specific values
        print(f"\nDatabase Name: {get_database_name()}")
        print(f"MongoDB URL: {get_mongo_url()[:50]}...")
        
        # Get collection names
        print(f"\nCollection Names:")
        collections = ['admins', 'teams', 'user_profile', 'visstoredatas', 'jobs']
        for collection_type in collections:
            try:
                collection_name = get_collection_name(collection_type)
                print(f"  - {collection_type}: {collection_name}")
            except ValueError as e:
                print(f"  - {collection_type}: Error - {e}")
        
        # 2. MongoDB Connection Examples
        print("\n\n2. MongoDB Connection Examples")
        print("-" * 40)
        
        # Test connection
        client = get_mongo_connection()
        print("✅ MongoDB connection established successfully")
        
        # Test health check
        health = check_mongo_health()
        print(f"✅ Health check: {health['status']}")
        if health.get('issues'):
            print(f"   Issues: {health['issues']}")
        
        # Test performance monitoring
        performance = monitor_mongo_performance()
        print(f"✅ Performance monitoring: {len(performance)} metrics collected")
        
        # 3. Collection Access Examples
        print("\n\n3. Collection Access Examples")
        print("-" * 40)
        
        # Get collections by type
        try:
            # Get datasets collection
            datasets_collection = get_collection_by_type('visstoredatas')
            print(f"✅ Got datasets collection: {datasets_collection.name}")
            
            # Get jobs collection
            jobs_collection = get_collection_by_type('jobs')
            print(f"✅ Got jobs collection: {jobs_collection.name}")
            
            # Get teams collection
            teams_collection = get_collection_by_type('teams')
            print(f"✅ Got teams collection: {teams_collection.name}")
            
        except Exception as e:
            print(f"❌ Error accessing collections: {e}")
        
        # 4. Query Examples
        print("\n\n4. Query Examples")
        print("-" * 20)
        
        try:
            # Query datasets (limit to 5 for example)
            print("Querying datasets...")
            datasets = execute_collection_query(
                'visstoredatas',
                query={},  # Empty query to get all
                projection={'uuid': 1, 'name': 1, 'status': 1, '_id': 0},  # Only specific fields
                limit=5
            )
            print(f"✅ Found {len(datasets)} datasets")
            for dataset in datasets:
                print(f"   - {dataset.get('name', 'Unknown')} ({dataset.get('uuid', 'No UUID')[:8]}...) - {dataset.get('status', 'Unknown')}")
            
            # Query jobs (if any exist)
            print("\nQuerying jobs...")
            jobs = execute_collection_query(
                'jobs',
                query={},
                projection={'job_id': 1, 'job_type': 1, 'status': 1, '_id': 0},
                limit=5
            )
            print(f"✅ Found {len(jobs)} jobs")
            for job in jobs:
                print(f"   - {job.get('job_id', 'Unknown')} - {job.get('job_type', 'Unknown')} - {job.get('status', 'Unknown')}")
            
        except Exception as e:
            print(f"❌ Error querying collections: {e}")
        
        # 5. Context Manager Examples
        print("\n\n5. Context Manager Examples")
        print("-" * 35)
        
        try:
            # Using context manager for safe operations
            with mongo_collection_by_type_context('visstoredatas') as collection:
                # Count documents
                count = collection.count_documents({})
                print(f"✅ Total datasets in collection: {count}")
                
                # Get collection stats
                stats = collection.database.command('collStats', collection.name)
                print(f"✅ Collection size: {stats.get('size', 0)} bytes")
                print(f"✅ Average document size: {stats.get('avgObjSize', 0)} bytes")
        
        except Exception as e:
            print(f"❌ Error with context manager: {e}")
        
        # 6. Configuration Validation
        print("\n\n6. Configuration Validation")
        print("-" * 35)
        
        issues = config.validate_config()
        if issues:
            print("❌ Configuration Issues:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            print("✅ Configuration is valid")
        
        # 7. Environment Variables
        print("\n\n7. Environment Variables")
        print("-" * 30)
        
        env_vars = [
            'MONGO_URL', 'DB_NAME', 'DB_HOST', 'DB_PASS',
            'DEPLOY_SERVER', 'DOMAIN_NAME', 'AUTH0_DOMAIN'
        ]
        
        for var in env_vars:
            value = os.getenv(var, 'Not set')
            if 'PASS' in var or 'SECRET' in var or 'TOKEN' in var:
                value = '***' if value != 'Not set' else value
            print(f"   {var}: {value}")
        
        print("\n" + "=" * 70)
        print("✅ Example completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up connections
        try:
            from SC_MongoConnection import close_all_connections
            close_all_connections()
            print("✅ Connections closed")
        except:
            pass


if __name__ == '__main__':
    main()
