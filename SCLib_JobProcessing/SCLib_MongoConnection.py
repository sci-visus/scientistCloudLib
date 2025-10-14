#!/usr/bin/env python3
"""
ScientistCloud MongoDB Connection Manager
Enhanced connection pooling and management for the SC_JobProcessing system.
"""

import os
import logging
import threading
import time
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from pymongo import MongoClient
from pymongo.errors import (
    ConnectionFailure, ServerSelectionTimeoutError, 
    PyMongoError, OperationFailure, NetworkTimeout
)
from pymongo.database import Database
from pymongo.collection import Collection

# Import configuration
from SCLib_Config import get_config, get_database_name, get_collection_name

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SC_MongoConnectionManager:
    """
    Enhanced MongoDB connection manager for ScientistCloud Job Processing.
    Provides connection pooling, health monitoring, and automatic reconnection.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SC_MongoConnectionManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.client: Optional[MongoClient] = None
            self.connection_stats = {
                'connections_created': 0,
                'connections_failed': 0,
                'last_health_check': None,
                'health_status': 'unknown'
            }
            self.initialized = True
            self._health_check_lock = threading.Lock()
    
    def get_client(self) -> MongoClient:
        """Get MongoDB client with enhanced connection pooling and health monitoring."""
        if self.client is None or not self._is_connection_healthy():
            self._create_connection()
        
        return self.client
    
    def _create_connection(self):
        """Create a new MongoDB connection with optimized settings."""
        try:
            # Get configuration
            config = get_config()
            
            # Close existing connection if any
            if self.client is not None:
                try:
                    self.client.close()
                except Exception as e:
                    logger.warning(f"Error closing existing connection: {e}")
            
            # Enhanced connection pooling configuration for job processing
            self.client = MongoClient(
                config.get_mongo_url(),
                # Connection Pool Settings
                maxPoolSize=config.database.max_pool_size,
                minPoolSize=config.database.min_pool_size,
                maxIdleTimeMS=config.database.max_idle_time_ms,
                waitQueueTimeoutMS=config.database.wait_queue_timeout_ms,
                
                # Timeout Settings
                serverSelectionTimeoutMS=config.database.server_selection_timeout_ms,
                connectTimeoutMS=config.database.connect_timeout_ms,
                socketTimeoutMS=config.database.socket_timeout_ms,
                
                # Retry Settings
                retryWrites=config.database.retry_writes,
                retryReads=config.database.retry_reads,
                
                # Heartbeat Settings
                heartbeatFrequencyMS=10000,       # Check server health every 10s
                
                # Compression
                compressors='zstd,zlib,snappy',   # Enable compression
                
                # Read Preferences
                readPreference='secondaryPreferred',  # Prefer secondary for reads
                
                # Write Concerns
                w=config.database.write_concern,
                journal=config.database.journal,
                
                # Application Name
                appName='SC_JobProcessing'        # Identify our application
            )
            
            # Test the connection with a more comprehensive health check
            self._perform_health_check()
            
            self.connection_stats['connections_created'] += 1
            self.connection_stats['health_status'] = 'healthy'
            self.connection_stats['last_health_check'] = time.time()
            
            logger.info("MongoDB connection established successfully with enhanced pooling")
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            self.connection_stats['connections_failed'] += 1
            self.connection_stats['health_status'] = 'failed'
            logger.error(f"MongoDB connection failed: {e}")
            raise e
    
    def _is_connection_healthy(self) -> bool:
        """Check if the current connection is healthy."""
        if self.client is None:
            return False
        
        # Check if enough time has passed since last health check
        last_check = self.connection_stats.get('last_health_check')
        if last_check is not None and time.time() - last_check < 30:  # Check every 30 seconds max
            return self.connection_stats.get('health_status') == 'healthy'
        
        # Perform health check
        with self._health_check_lock:
            try:
                # Quick ping to check connectivity
                self.client.admin.command('ping')
                self.connection_stats['health_status'] = 'healthy'
                self.connection_stats['last_health_check'] = time.time()
                return True
            except Exception as e:
                logger.warning(f"Health check failed: {e}")
                self.connection_stats['health_status'] = 'unhealthy'
                return False
    
    def _perform_health_check(self):
        """Perform comprehensive health check on MongoDB connection."""
        try:
            # Basic ping
            self.client.admin.command('ping')
            
            # Check server status
            server_status = self.client.admin.command('serverStatus')
            
            # Check if we can read and write
            test_db = self.client['_health_check']
            test_collection = test_db['test']
            
            # Test write
            test_doc = {'test': True, 'timestamp': time.time()}
            result = test_collection.insert_one(test_doc)
            
            # Test read
            found_doc = test_collection.find_one({'_id': result.inserted_id})
            
            # Clean up test document
            test_collection.delete_one({'_id': result.inserted_id})
            
            if found_doc is None:
                raise Exception("Health check read test failed")
            
            logger.debug("MongoDB health check passed successfully")
            
        except Exception as e:
            logger.error(f"MongoDB health check failed: {e}")
            raise
    
    def get_database(self, database_name: str) -> Database:
        """Get a database instance with connection pooling."""
        client = self.get_client()
        return client[database_name]
    
    def get_collection(self, database_name: str, collection_name: str) -> Collection:
        """Get a collection instance with connection pooling."""
        db = self.get_database(database_name)
        return db[collection_name]
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics and health information."""
        stats = self.connection_stats.copy()
        
        if self.client is not None:
            try:
                # Get MongoDB server status
                server_status = self.client.admin.command('serverStatus')
                stats['server_info'] = {
                    'version': server_status.get('version', 'unknown'),
                    'uptime': server_status.get('uptime', 0),
                    'connections': server_status.get('connections', {}),
                    'mem': server_status.get('mem', {}),
                    'opcounters': server_status.get('opcounters', {})
                }
                
                # Get connection pool info
                pool_stats = self.client._pool.get_stats()
                stats['pool_info'] = {
                    'size': pool_stats.get('size', 0),
                    'available': pool_stats.get('available', 0),
                    'checked_out': pool_stats.get('checked_out', 0)
                }
                
            except Exception as e:
                logger.warning(f"Could not get server stats: {e}")
                stats['server_info'] = {'error': str(e)}
                stats['pool_info'] = {'error': str(e)}
        
        return stats
    
    def close_connection(self):
        """Close MongoDB connection gracefully."""
        if self.client is not None:
            try:
                self.client.close()
                self.client = None
                self.connection_stats['health_status'] = 'closed'
                logger.info("MongoDB connection closed gracefully")
            except Exception as e:
                logger.error(f"Error closing MongoDB connection: {e}")
    
    def __del__(self):
        """Destructor to ensure connection is closed."""
        self.close_connection()


# Global connection manager instance
_connection_manager: Optional[SC_MongoConnectionManager] = None


def get_mongo_connection() -> MongoClient:
    """
    Get MongoDB client with enhanced connection pooling.
    This is the main function to use for getting MongoDB connections.
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = SC_MongoConnectionManager()
    return _connection_manager.get_client()


def get_mongo_database(database_name: Optional[str] = None) -> Database:
    """Get a database instance with connection pooling."""
    if database_name is None:
        database_name = get_database_name()
    
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = SC_MongoConnectionManager()
    return _connection_manager.get_database(database_name)


def get_mongo_collection(database_name: Optional[str] = None, collection_name: Optional[str] = None) -> Collection:
    """Get a collection instance with connection pooling."""
    if database_name is None:
        database_name = get_database_name()
    
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = SC_MongoConnectionManager()
    return _connection_manager.get_collection(database_name, collection_name)


def get_collection_by_type(collection_type: str, database_name: Optional[str] = None) -> Collection:
    """
    Get a collection by type using configuration.
    
    Args:
        collection_type: Type of collection (admins, teams, visstoredatas, etc.)
        database_name: Optional database name (uses default if not provided)
    
    Returns:
        Collection instance
    """
    if database_name is None:
        database_name = get_database_name()
    
    collection_name = get_collection_name(collection_type)
    return get_mongo_collection(database_name, collection_name)


@contextmanager
def mongo_connection_context():
    """
    Context manager for MongoDB connections with automatic error handling.
    Usage:
        with mongo_connection_context() as client:
            db = client['mydb']
            collection = db['mycollection']
            # Perform operations
    """
    client = get_mongo_connection()
    try:
        yield client
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        logger.error(f"MongoDB connection error: {e}")
        # Reset connection manager to force reconnection
        global _connection_manager
        if _connection_manager is not None:
            _connection_manager.close_connection()
            _connection_manager = None
        raise
    except Exception as e:
        logger.error(f"MongoDB operation failed: {e}")
        raise


@contextmanager
def mongo_database_context(database_name: Optional[str] = None):
    """
    Context manager for MongoDB database operations.
    Usage:
        with mongo_database_context() as db:  # Uses default database
            collection = db['mycollection']
            # Perform operations
    """
    if database_name is None:
        database_name = get_database_name()
    
    with mongo_connection_context() as client:
        yield client[database_name]


@contextmanager
def mongo_collection_context(database_name: Optional[str] = None, collection_name: Optional[str] = None):
    """
    Context manager for MongoDB collection operations.
    Usage:
        with mongo_collection_context() as collection:  # Uses default database and collection
            # Perform operations
    """
    if database_name is None:
        database_name = get_database_name()
    
    with mongo_database_context(database_name) as db:
        yield db[collection_name]


@contextmanager
def mongo_collection_by_type_context(collection_type: str, database_name: Optional[str] = None):
    """
    Context manager for MongoDB collection operations using collection type.
    Usage:
        with mongo_collection_by_type_context('visstoredatas') as collection:
            # Perform operations
    """
    if database_name is None:
        database_name = get_database_name()
    
    collection_name = get_collection_name(collection_type)
    with mongo_database_context(database_name) as db:
        yield db[collection_name]


def get_connection_stats() -> Dict[str, Any]:
    """Get connection statistics and health information."""
    global _connection_manager
    if _connection_manager is None:
        return {'status': 'not_initialized'}
    return _connection_manager.get_connection_stats()


def close_all_connections():
    """Close all MongoDB connections."""
    global _connection_manager
    if _connection_manager is not None:
        _connection_manager.close_connection()
        _connection_manager = None


# Enhanced utility functions for the SC_JobProcessing system

def execute_job_query(database_name: Optional[str] = None, collection_name: Optional[str] = None, 
                     query: Dict[str, Any] = None, projection: Optional[Dict[str, Any]] = None, 
                     sort: Optional[List[tuple]] = None, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Execute a MongoDB query optimized for job processing.
    
    Args:
        database_name: Name of the database (uses default if not provided)
        collection_name: Name of the collection (uses default if not provided)
        query: MongoDB query document
        projection: Fields to include/exclude
        sort: Sort specification
        limit: Maximum number of documents to return
    
    Returns:
        List of matching documents
    """
    if database_name is None:
        database_name = get_database_name()
    if collection_name is None:
        collection_name = get_collection_name('jobs')
    if query is None:
        query = {}
    
    with mongo_collection_context(database_name, collection_name) as collection:
        try:
            cursor = collection.find(query, projection)
            
            if sort:
                cursor = cursor.sort(sort)
            
            if limit:
                cursor = cursor.limit(limit)
            
            return list(cursor)
            
        except Exception as e:
            logger.error(f"Job query execution failed: {e}")
            raise


def execute_collection_query(collection_type: str, query: Dict[str, Any] = None, 
                           projection: Optional[Dict[str, Any]] = None, 
                           sort: Optional[List[tuple]] = None,
                           limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Execute a MongoDB query using collection type.
    
    Args:
        collection_type: Type of collection (admins, teams, visstoredatas, etc.)
        query: MongoDB query document
        projection: Fields to include/exclude
        sort: Sort specification
        limit: Maximum number of documents to return
    
    Returns:
        List of matching documents
    """
    if query is None:
        query = {}
    
    with mongo_collection_by_type_context(collection_type) as collection:
        try:
            cursor = collection.find(query, projection)
            
            if sort:
                cursor = cursor.sort(sort)
            
            if limit:
                cursor = cursor.limit(limit)
            
            return list(cursor)
            
        except Exception as e:
            logger.error(f"Collection query execution failed: {e}")
            raise


def execute_job_update(database_name: str, collection_name: str, 
                      filter_query: Dict[str, Any], 
                      update_query: Dict[str, Any],
                      upsert: bool = False) -> Dict[str, Any]:
    """
    Execute a MongoDB update operation optimized for job processing.
    
    Args:
        database_name: Name of the database
        collection_name: Name of the collection
        filter_query: Query to find documents to update
        update_query: Update operations to perform
        upsert: Whether to insert if no document matches
    
    Returns:
        Update result information
    """
    with mongo_collection_context(database_name, collection_name) as collection:
        try:
            result = collection.update_one(filter_query, update_query, upsert=upsert)
            return {
                'matched_count': result.matched_count,
                'modified_count': result.modified_count,
                'upserted_id': result.upserted_id
            }
            
        except Exception as e:
            logger.error(f"Job update execution failed: {e}")
            raise


def execute_job_insert(database_name: str, collection_name: str, 
                      document: Dict[str, Any]) -> str:
    """
    Execute a MongoDB insert operation optimized for job processing.
    
    Args:
        database_name: Name of the database
        collection_name: Name of the collection
        document: Document to insert
    
    Returns:
        Inserted document ID
    """
    with mongo_collection_context(database_name, collection_name) as collection:
        try:
            result = collection.insert_one(document)
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Job insert execution failed: {e}")
            raise


def execute_job_delete(database_name: str, collection_name: str, 
                      filter_query: Dict[str, Any]) -> int:
    """
    Execute a MongoDB delete operation optimized for job processing.
    
    Args:
        database_name: Name of the database
        collection_name: Name of the collection
        filter_query: Query to find documents to delete
    
    Returns:
        Number of documents deleted
    """
    with mongo_collection_context(database_name, collection_name) as collection:
        try:
            result = collection.delete_many(filter_query)
            return result.deleted_count
            
        except Exception as e:
            logger.error(f"Job delete execution failed: {e}")
            raise


def execute_job_aggregation(database_name: str, collection_name: str, 
                           pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Execute a MongoDB aggregation pipeline optimized for job processing.
    
    Args:
        database_name: Name of the database
        collection_name: Name of the collection
        pipeline: Aggregation pipeline stages
    
    Returns:
        List of aggregated results
    """
    with mongo_collection_context(database_name, collection_name) as collection:
        try:
            cursor = collection.aggregate(pipeline)
            return list(cursor)
            
        except Exception as e:
            logger.error(f"Job aggregation execution failed: {e}")
            raise


def create_job_indexes(database_name: str, collection_name: str, 
                      indexes: List[tuple]) -> List[str]:
    """
    Create indexes for job collections.
    
    Args:
        database_name: Name of the database
        collection_name: Name of the collection
        indexes: List of index specifications (field, direction) tuples
    
    Returns:
        List of created index names
    """
    with mongo_collection_context(database_name, collection_name) as collection:
        try:
            created_indexes = []
            for index_spec in indexes:
                if isinstance(index_spec, tuple):
                    # Simple index: (field, direction)
                    index_name = collection.create_index([index_spec])
                else:
                    # Complex index specification
                    index_name = collection.create_index(index_spec)
                created_indexes.append(index_name)
            
            logger.info(f"Created {len(created_indexes)} indexes for {collection_name}")
            return created_indexes
            
        except Exception as e:
            logger.error(f"Index creation failed: {e}")
            raise


def get_job_collection_stats(database_name: str, collection_name: str) -> Dict[str, Any]:
    """
    Get statistics for a job collection.
    
    Args:
        database_name: Name of the database
        collection_name: Name of the collection
    
    Returns:
        Collection statistics
    """
    with mongo_collection_context(database_name, collection_name) as collection:
        try:
            stats = collection.database.command('collStats', collection_name)
            return {
                'count': stats.get('count', 0),
                'size': stats.get('size', 0),
                'avgObjSize': stats.get('avgObjSize', 0),
                'storageSize': stats.get('storageSize', 0),
                'indexes': stats.get('nindexes', 0),
                'totalIndexSize': stats.get('totalIndexSize', 0)
            }
            
        except Exception as e:
            logger.error(f"Collection stats retrieval failed: {e}")
            raise


# Health monitoring functions

def check_mongo_health() -> Dict[str, Any]:
    """
    Check MongoDB health and return status information.
    
    Returns:
        Health status information
    """
    try:
        stats = get_connection_stats()
        
        health_status = {
            'status': 'healthy',
            'timestamp': time.time(),
            'connection_stats': stats,
            'issues': []
        }
        
        # Check connection health
        if stats.get('health_status') != 'healthy':
            health_status['status'] = 'unhealthy'
            health_status['issues'].append(f"Connection status: {stats.get('health_status')}")
        
        # Check connection pool
        pool_info = stats.get('pool_info', {})
        if isinstance(pool_info, dict) and 'error' not in pool_info:
            available = pool_info.get('available', 0)
            size = pool_info.get('size', 0)
            if available == 0 and size > 0:
                health_status['status'] = 'warning'
                health_status['issues'].append("No available connections in pool")
        
        # Check server status
        server_info = stats.get('server_info', {})
        if isinstance(server_info, dict) and 'error' not in server_info:
            uptime = server_info.get('uptime', 0)
            if uptime < 60:  # Server restarted recently
                health_status['status'] = 'warning'
                health_status['issues'].append("Server restarted recently")
        
        return health_status
        
    except Exception as e:
        return {
            'status': 'error',
            'timestamp': time.time(),
            'error': str(e),
            'issues': [f"Health check failed: {e}"]
        }


def monitor_mongo_performance() -> Dict[str, Any]:
    """
    Monitor MongoDB performance metrics.
    
    Returns:
        Performance metrics
    """
    try:
        stats = get_connection_stats()
        
        performance = {
            'timestamp': time.time(),
            'connection_pool': {},
            'server_metrics': {},
            'operation_counts': {}
        }
        
        # Connection pool metrics
        pool_info = stats.get('pool_info', {})
        if isinstance(pool_info, dict) and 'error' not in pool_info:
            performance['connection_pool'] = {
                'size': pool_info.get('size', 0),
                'available': pool_info.get('available', 0),
                'checked_out': pool_info.get('checked_out', 0),
                'utilization': (pool_info.get('checked_out', 0) / max(pool_info.get('size', 1), 1)) * 100
            }
        
        # Server metrics
        server_info = stats.get('server_info', {})
        if isinstance(server_info, dict) and 'error' not in server_info:
            performance['server_metrics'] = {
                'uptime': server_info.get('uptime', 0),
                'version': server_info.get('version', 'unknown'),
                'memory_usage': server_info.get('mem', {}),
                'connections': server_info.get('connections', {})
            }
            
            # Operation counts
            opcounters = server_info.get('opcounters', {})
            performance['operation_counts'] = {
                'insert': opcounters.get('insert', 0),
                'query': opcounters.get('query', 0),
                'update': opcounters.get('update', 0),
                'delete': opcounters.get('delete', 0)
            }
        
        return performance
        
    except Exception as e:
        return {
            'timestamp': time.time(),
            'error': str(e)
        }


if __name__ == '__main__':
    # Example usage and testing
    print("SC_MongoConnection - MongoDB Connection Manager for ScientistCloud")
    print("=" * 70)
    
    try:
        # Test connection
        client = get_mongo_connection()
        print("✅ MongoDB connection established successfully")
        
        # Test health check
        health = check_mongo_health()
        print(f"✅ Health check: {health['status']}")
        
        # Test performance monitoring
        performance = monitor_mongo_performance()
        print(f"✅ Performance monitoring: {len(performance)} metrics collected")
        
        # Test connection stats
        stats = get_connection_stats()
        print(f"✅ Connection stats: {stats.get('health_status', 'unknown')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        close_all_connections()
        print("✅ Connections closed")
