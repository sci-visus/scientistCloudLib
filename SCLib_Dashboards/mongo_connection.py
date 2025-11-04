#!/usr/bin/env python3
"""
MongoDB Connection Manager for Python
Implements connection pooling and proper connection lifecycle management
"""

import os
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from contextlib import contextmanager
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoConnectionManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(MongoConnectionManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.client = None
            self.initialized = True
    
    def get_client(self):
        """Get MongoDB client with connection pooling"""
        if self.client is None:
            try:
                # Get MongoDB URL from environment (required)
                mongo_url = os.getenv('MONGO_URL')
                if not mongo_url:
                    logger.error("MONGO_URL environment variable is not set")
                    raise EnvironmentError("MONGO_URL environment variable must be set")
                
                # Connection pooling configuration - let MongoDB handle SSL automatically
                self.client = MongoClient(
                    mongo_url,
                    maxPoolSize=10,           # Maximum connections in pool
                    minPoolSize=2,            # Minimum connections in pool
                    maxIdleTimeMS=30000,      # Close idle connections after 30 seconds
                    waitQueueTimeoutMS=5000,  # Wait up to 5 seconds for available connection
                    serverSelectionTimeoutMS=10000,  # Increased timeout
                    connectTimeoutMS=15000,   # Increased timeout
                    socketTimeoutMS=30000
                )
                
                # Test the connection
                self.client.admin.command('ping')
                logger.info("MongoDB connection established successfully")
                
            except (ConnectionFailure, ServerSelectionTimeoutError) as e:
                logger.error(f"MongoDB connection failed: {e}")
                raise e
        
        return self.client
    
    def close_connection(self):
        """Close MongoDB connection"""
        if self.client is not None:
            try:
                self.client.close()
                self.client = None
                logger.info("MongoDB connection closed")
            except Exception as e:
                logger.error(f"Error closing MongoDB connection: {e}")
    
    def __del__(self):
        """Destructor to ensure connection is closed"""
        self.close_connection()

# Global connection manager instance
_connection_manager = None

def get_mongo_client():
    """Get MongoDB client with connection pooling"""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = MongoConnectionManager()
    return _connection_manager.get_client()

@contextmanager
def get_mongo_connection():
    """Context manager for MongoDB connections"""
    client = get_mongo_client()
    try:
        yield client
    except Exception as e:
        logger.error(f"MongoDB operation failed: {e}")
        raise
    # Connection is managed by the pool, no need to close manually

def close_all_connections():
    """Close all MongoDB connections"""
    global _connection_manager
    if _connection_manager is not None:
        _connection_manager.close_connection()
        _connection_manager = None

# Example usage functions
def execute_query(database_name, collection_name, query, projection=None):
    """Execute a MongoDB query with proper error handling"""
    with get_mongo_connection() as client:
        try:
            db = client[database_name]
            collection = db[collection_name]
            
            if projection:
                cursor = collection.find(query, projection)
            else:
                cursor = collection.find(query)
            
            return list(cursor)
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

def execute_command(database_name, command):
    """Execute a MongoDB command with proper error handling"""
    with get_mongo_connection() as client:
        try:
            db = client[database_name]
            result = db.command(command)
            return result
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise

def insert_document(database_name, collection_name, document):
    """Insert a document with proper error handling"""
    with get_mongo_connection() as client:
        try:
            db = client[database_name]
            collection = db[collection_name]
            result = collection.insert_one(document)
            return result.inserted_id
            
        except Exception as e:
            logger.error(f"Document insertion failed: {e}")
            raise

def update_document(database_name, collection_name, filter_query, update_query):
    """Update a document with proper error handling"""
    with get_mongo_connection() as client:
        try:
            db = client[database_name]
            collection = db[collection_name]
            result = collection.update_one(filter_query, update_query)
            return result
            
        except Exception as e:
            logger.error(f"Document update failed: {e}")
            raise

def delete_document(database_name, collection_name, filter_query):
    """Delete a document with proper error handling"""
    with get_mongo_connection() as client:
        try:
            db = client[database_name]
            collection = db[collection_name]
            result = collection.delete_one(filter_query)
            return result
            
        except Exception as e:
            logger.error(f"Document deletion failed: {e}")
            raise
