"""
SCLib Portal API
Provides HTTP API endpoints for the ScientistCloud Data Portal
Delegates all database operations to SCLib instead of requiring PHP MongoDB extension
"""

import json
import logging
import time
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from os import getenv

from SCLib_Config import get_config
from SCLib_MongoConnection import get_mongo_connection, execute_collection_query, execute_job_query
from SCLib_JobTypes import SCLib_DatasetStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests

# Global MongoDB connection
mongo_connection = None

def get_database():
    """Get MongoDB database connection."""
    global mongo_connection
    if mongo_connection is None:
        mongo_connection = get_mongo_connection()
    return mongo_connection

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        db = get_database()
        # Test connection
        db.command('ping')
        return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

@app.route('/api/datasets', methods=['GET'])
def get_user_datasets():
    """Get user's datasets."""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': 'user_id parameter required'}), 400
        
        # Get user's own datasets
        user_datasets = execute_collection_query(
            collection_type='visstoredatas',
            query={'user_id': user_id}
        )
        
        # Get shared datasets
        shared_datasets = execute_collection_query(
            collection_type='visstoredatas',
            query={'shared_with': user_id}
        )
        
        # Get team datasets (if user has team_id)
        user_profile = execute_collection_query(
            collection_type='user_profile',
            query={'user_id': user_id}
        )
        
        team_datasets = []
        if user_profile and user_profile[0].get('team_id'):
            team_datasets = execute_collection_query(
                collection_type='visstoredatas',
                query={'team_id': user_profile[0]['team_id']}
            )
        
        # Combine and deduplicate datasets
        all_datasets = user_datasets + shared_datasets + team_datasets
        unique_datasets = {}
        for dataset in all_datasets:
            dataset_id = str(dataset['_id'])
            if dataset_id not in unique_datasets:
                unique_datasets[dataset_id] = format_dataset_for_portal(dataset)
        
        return jsonify({
            'success': True,
            'datasets': list(unique_datasets.values())
        })
        
    except Exception as e:
        logger.error(f"Failed to get user datasets: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dataset/<dataset_id>', methods=['GET'])
def get_dataset_details(dataset_id):
    """Get detailed information about a specific dataset."""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': 'user_id parameter required'}), 400
        
        # Get dataset
        datasets = execute_collection_query(
            collection_type='visstoredatas',
            query={'_id': dataset_id}
        )
        
        if not datasets:
            return jsonify({'error': 'Dataset not found'}), 404
        
        dataset = datasets[0]
        
        # Check access permissions
        if not has_dataset_access(dataset, user_id):
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify({
            'success': True,
            'dataset': format_dataset_for_portal(dataset)
        })
        
    except Exception as e:
        logger.error(f"Failed to get dataset details: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dataset/<dataset_id>/status', methods=['GET'])
def get_dataset_status(dataset_id):
    """Get the current status of a dataset."""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': 'user_id parameter required'}), 400
        
        # Get dataset
        datasets = execute_collection_query(
            collection_type='visstoredatas',
            query={'_id': dataset_id}
        )
        
        if not datasets:
            return jsonify({'error': 'Dataset not found'}), 404
        
        dataset = datasets[0]
        
        # Check access permissions
        if not has_dataset_access(dataset, user_id):
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify({
            'success': True,
            'status': dataset.get('status', 'unknown'),
            'progress': dataset.get('progress', 0),
            'message': dataset.get('status_message', '')
        })
        
    except Exception as e:
        logger.error(f"Failed to get dataset status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dataset/<dataset_id>', methods=['DELETE'])
def delete_dataset(dataset_id):
    """Delete a dataset."""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': 'user_id parameter required'}), 400
        
        # Get dataset
        datasets = execute_collection_query(
            collection_type='visstoredatas',
            query={'_id': dataset_id}
        )
        
        if not datasets:
            return jsonify({'error': 'Dataset not found'}), 404
        
        dataset = datasets[0]
        
        # Check ownership
        if dataset.get('user_id') != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # TODO: Implement actual deletion logic
        # This would involve:
        # 1. Deleting files from storage
        # 2. Removing database records
        # 3. Cleaning up any associated jobs
        
        return jsonify({
            'success': True,
            'message': 'Dataset deletion initiated'
        })
        
    except Exception as e:
        logger.error(f"Failed to delete dataset: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/dataset/<dataset_id>/share', methods=['POST'])
def share_dataset(dataset_id):
    """Share a dataset with other users."""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': 'user_id parameter required'}), 400
        
        data = request.get_json()
        if not data or 'shared_with' not in data:
            return jsonify({'error': 'shared_with parameter required'}), 400
        
        # Get dataset
        datasets = execute_collection_query(
            collection_type='visstoredatas',
            query={'_id': dataset_id}
        )
        
        if not datasets:
            return jsonify({'error': 'Dataset not found'}), 404
        
        dataset = datasets[0]
        
        # Check ownership
        if dataset.get('user_id') != user_id:
            return jsonify({'error': 'Access denied'}), 403
        
        # TODO: Implement sharing logic
        # This would involve updating the dataset's shared_with field
        
        return jsonify({
            'success': True,
            'message': 'Dataset sharing updated'
        })
        
    except Exception as e:
        logger.error(f"Failed to share dataset: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Authentication endpoints - delegate to SCLib_Auth
@app.route('/api/auth/user', methods=['GET'])
def get_user_profile():
    """Get user profile information - delegates to SCLib_Auth."""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({'error': 'user_id parameter required'}), 400
        
        # Forward request to SCLib_Auth service
        import requests
        auth_service_url = getenv('SCLIB_AUTH_URL', 'http://localhost:8001')
        
        response = requests.get(f"{auth_service_url}/api/auth/me", 
                              headers={'Authorization': f'Bearer {user_id}'})
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'error': 'User not found'}), 404
        
    except Exception as e:
        logger.error(f"Failed to get user profile: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/validate', methods=['POST'])
def validate_auth_token():
    """Validate authentication token - delegates to SCLib_Auth."""
    try:
        data = request.get_json()
        if not data or 'token' not in data:
            return jsonify({'error': 'token parameter required'}), 400
        
        token = data['token']
        
        # Forward request to SCLib_Auth service
        import requests
        auth_service_url = getenv('SCLIB_AUTH_URL', 'http://localhost:8001')
        
        response = requests.get(f"{auth_service_url}/api/auth/status",
                              headers={'Authorization': f'Bearer {token}'})
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'success': False, 'valid': False, 'error': 'Invalid token'})
        
    except Exception as e:
        logger.error(f"Failed to validate auth token: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def authenticate_user():
    """Authenticate user login - delegates to SCLib_Auth."""
    try:
        data = request.get_json()
        if not data or 'email' not in data:
            return jsonify({'error': 'email required'}), 400
        
        # Forward request to SCLib_Auth service
        import requests
        auth_service_url = getenv('SCLIB_AUTH_URL', 'http://localhost:8001')
        
        # SCLib_Auth expects authorization_code, not email/password
        # This is a simplified version - in practice, you'd need to handle Auth0 flow
        response = requests.post(f"{auth_service_url}/api/auth/login", json=data)
        
        if response.status_code == 200:
            return jsonify(response.json())
        else:
            return jsonify({'success': False, 'error': 'Authentication failed'})
        
    except Exception as e:
        logger.error(f"Failed to authenticate user: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def has_dataset_access(dataset: Dict[str, Any], user_id: str) -> bool:
    """Check if user has access to a dataset."""
    # Owner has access
    if dataset.get('user_id') == user_id:
        return True
    
    # Check if user is in shared_with list
    shared_with = dataset.get('shared_with', [])
    if user_id in shared_with:
        return True
    
    # Check team access
    # TODO: Implement team access logic
    
    return False

def format_dataset_for_portal(dataset: Dict[str, Any]) -> Dict[str, Any]:
    """Format dataset data for portal consumption."""
    return {
        'id': str(dataset['_id']),
        'name': dataset.get('name', 'Unknown'),
        'description': dataset.get('description', ''),
        'status': dataset.get('status', 'unknown'),
        'progress': dataset.get('progress', 0),
        'created_at': dataset.get('created_at', ''),
        'updated_at': dataset.get('updated_at', ''),
        'file_size': dataset.get('file_size', 0),
        'file_type': dataset.get('file_type', ''),
        'user_id': dataset.get('user_id', ''),
        'shared_with': dataset.get('shared_with', []),
        'team_id': dataset.get('team_id', ''),
        'metadata': dataset.get('metadata', {}),
        'viewer_url': dataset.get('viewer_url', ''),
        'download_url': dataset.get('download_url', '')
    }

def format_user_for_portal(user: Dict[str, Any]) -> Dict[str, Any]:
    """Format user data for portal consumption."""
    return {
        'id': user.get('user_id', ''),
        'email': user.get('email', ''),
        'name': user.get('name', ''),
        'team_id': user.get('team_id', ''),
        'is_active': user.get('is_active', True),
        'created_at': user.get('created_at', ''),
        'last_activity': user.get('last_activity', ''),
        'profile': user.get('profile', {}),
        'preferences': user.get('preferences', {})
    }

if __name__ == '__main__':
    # Get configuration
    config = get_config()
    
    # Start the API server
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=True
    )
