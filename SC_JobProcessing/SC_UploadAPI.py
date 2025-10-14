#!/usr/bin/env python3
"""
ScientistCloud Upload API
RESTful API endpoints for asynchronous upload handling.
"""

from flask import Flask, request, jsonify, Response
from typing import Dict, Any, Optional
import uuid
import os
import tempfile
from datetime import datetime
import threading

from SC_Config import get_config
from SC_UploadProcessor import get_upload_processor
from SC_UploadJobTypes import (
    UploadJobConfig, UploadSourceType, create_local_upload_job,
    create_google_drive_upload_job, create_s3_upload_job, create_url_upload_job
)

# Configure Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 * 1024  # 16GB max file size

# Global upload processor
upload_processor = get_upload_processor()


@app.route('/api/upload/initiate', methods=['POST'])
def initiate_upload():
    """
    Initiate an asynchronous upload job.
    
    Request body:
    {
        "source_type": "local|google_drive|s3|url",
        "source_config": {...},
        "dataset_metadata": {
            "name": "My Dataset",
            "description": "Dataset description",
            "tags": ["tag1", "tag2"]
        },
        "user_id": "user_123",
        "team_id": "team_456"  // optional
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['source_type', 'source_config', 'dataset_metadata', 'user_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Generate dataset UUID
        dataset_uuid = str(uuid.uuid4())
        
        # Create upload job based on source type
        source_type = UploadSourceType(data['source_type'])
        source_config = data['source_config']
        dataset_metadata = data['dataset_metadata']
        user_id = data['user_id']
        team_id = data.get('team_id')
        
        if source_type == UploadSourceType.LOCAL:
            # For local uploads, we need to handle file upload first
            return _handle_local_upload_initiation(data, dataset_uuid)
        
        elif source_type == UploadSourceType.GOOGLE_DRIVE:
            job_config = create_google_drive_upload_job(
                file_id=source_config['file_id'],
                dataset_uuid=dataset_uuid,
                user_id=user_id,
                service_account_file=source_config.get('service_account_file', ''),
                dataset_name=dataset_metadata.get('name', ''),
                description=dataset_metadata.get('description', ''),
                tags=dataset_metadata.get('tags', []),
                team_id=team_id
            )
        
        elif source_type == UploadSourceType.S3:
            job_config = create_s3_upload_job(
                bucket_name=source_config['bucket_name'],
                object_key=source_config['object_key'],
                dataset_uuid=dataset_uuid,
                user_id=user_id,
                access_key_id=source_config['access_key_id'],
                secret_access_key=source_config['secret_access_key'],
                dataset_name=dataset_metadata.get('name', ''),
                description=dataset_metadata.get('description', ''),
                tags=dataset_metadata.get('tags', []),
                team_id=team_id
            )
        
        elif source_type == UploadSourceType.URL:
            job_config = create_url_upload_job(
                url=source_config['url'],
                dataset_uuid=dataset_uuid,
                user_id=user_id,
                dataset_name=dataset_metadata.get('name', ''),
                description=dataset_metadata.get('description', ''),
                tags=dataset_metadata.get('tags', []),
                team_id=team_id
            )
        
        else:
            return jsonify({'error': f'Unsupported source type: {source_type}'}), 400
        
        # Submit job
        job_id = upload_processor.submit_upload_job(job_config)
        
        # Return immediate response
        return jsonify({
            'job_id': job_id,
            'dataset_uuid': dataset_uuid,
            'status': 'queued',
            'message': 'Upload job initiated successfully',
            'estimated_time': _estimate_upload_time(source_type, source_config),
            'progress_url': f'/api/upload/status/{job_id}',
            'cancel_url': f'/api/upload/cancel/{job_id}'
        }), 202  # Accepted
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload/local/upload', methods=['POST'])
def upload_local_file():
    """
    Upload a local file and initiate processing.
    This endpoint handles the actual file upload for local files.
    """
    try:
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get metadata from form data
        dataset_name = request.form.get('dataset_name', file.filename)
        description = request.form.get('description', '')
        tags = request.form.get('tags', '').split(',') if request.form.get('tags') else []
        user_id = request.form.get('user_id')
        team_id = request.form.get('team_id')
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        # Generate dataset UUID
        dataset_uuid = str(uuid.uuid4())
        
        # Create temporary file
        temp_dir = tempfile.mkdtemp(prefix='sc_upload_')
        temp_file_path = os.path.join(temp_dir, file.filename)
        
        # Save uploaded file
        file.save(temp_file_path)
        
        # Create upload job
        job_config = create_local_upload_job(
            file_path=temp_file_path,
            dataset_uuid=dataset_uuid,
            user_id=user_id,
            dataset_name=dataset_name,
            description=description,
            tags=tags,
            team_id=team_id,
            delete_after_upload=True  # Clean up temp file after upload
        )
        
        # Submit job
        job_id = upload_processor.submit_upload_job(job_config)
        
        return jsonify({
            'job_id': job_id,
            'dataset_uuid': dataset_uuid,
            'status': 'queued',
            'message': 'File uploaded and processing initiated',
            'progress_url': f'/api/upload/status/{job_id}',
            'cancel_url': f'/api/upload/cancel/{job_id}'
        }), 202
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload/status/<job_id>', methods=['GET'])
def get_upload_status(job_id: str):
    """Get the status of an upload job."""
    try:
        progress = upload_processor.get_job_status(job_id)
        
        if not progress:
            return jsonify({'error': 'Job not found'}), 404
        
        return jsonify({
            'job_id': job_id,
            'status': progress.status.value,
            'progress_percentage': progress.progress_percentage,
            'bytes_uploaded': progress.bytes_uploaded,
            'bytes_total': progress.bytes_total,
            'speed_mbps': progress.speed_mbps,
            'eta_seconds': progress.eta_seconds,
            'current_file': progress.current_file,
            'error_message': progress.error_message,
            'last_updated': progress.last_updated.isoformat()
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload/cancel/<job_id>', methods=['POST'])
def cancel_upload(job_id: str):
    """Cancel an upload job."""
    try:
        success = upload_processor.cancel_job(job_id)
        
        if success:
            return jsonify({
                'job_id': job_id,
                'status': 'cancelled',
                'message': 'Upload job cancelled successfully'
            })
        else:
            return jsonify({'error': 'Job not found or already completed'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload/jobs', methods=['GET'])
def list_upload_jobs():
    """List upload jobs for a user."""
    try:
        user_id = request.args.get('user_id')
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        
        # Query jobs from database
        from SC_MongoConnection import execute_collection_query
        
        query = {'user_id': user_id, 'job_type': 'upload'}
        if status:
            query['status'] = status
        
        jobs = execute_collection_query(
            'jobs',
            query=query,
            sort=[('created_at', -1)],
            limit=limit
        )
        
        # Format response
        job_list = []
        for job in jobs:
            job_list.append({
                'job_id': job['job_id'],
                'dataset_uuid': job['dataset_uuid'],
                'source_type': job['source_type'],
                'status': job['status'],
                'created_at': job['created_at'].isoformat() if isinstance(job['created_at'], datetime) else str(job['created_at']),
                'progress_url': f'/api/upload/status/{job["job_id"]}',
                'cancel_url': f'/api/upload/cancel/{job["job_id"]}'
            })
        
        return jsonify({
            'jobs': job_list,
            'total': len(job_list),
            'limit': limit,
            'offset': offset
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload/estimate', methods=['POST'])
def estimate_upload_time():
    """Estimate upload time for a given source."""
    try:
        data = request.get_json()
        source_type = data.get('source_type')
        source_config = data.get('source_config', {})
        
        if not source_type:
            return jsonify({'error': 'source_type is required'}), 400
        
        estimated_time = _estimate_upload_time(UploadSourceType(source_type), source_config)
        
        return jsonify({
            'source_type': source_type,
            'estimated_time_minutes': estimated_time,
            'estimated_time_human': _format_time_human(estimated_time)
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload/supported-sources', methods=['GET'])
def get_supported_sources():
    """Get list of supported upload sources and their requirements."""
    return jsonify({
        'sources': [
            {
                'type': 'local',
                'name': 'Local File Upload',
                'description': 'Upload files from your local computer',
                'requirements': ['file'],
                'max_size': '16GB',
                'supported_formats': ['zip', 'tar', 'gz', 'bz2', '7z', 'rar']
            },
            {
                'type': 'google_drive',
                'name': 'Google Drive',
                'description': 'Import files from Google Drive',
                'requirements': ['file_id', 'service_account_file'],
                'max_size': '5TB',
                'supported_formats': ['any']
            },
            {
                'type': 's3',
                'name': 'Amazon S3',
                'description': 'Import files from Amazon S3',
                'requirements': ['bucket_name', 'object_key', 'access_key_id', 'secret_access_key'],
                'max_size': '5TB',
                'supported_formats': ['any']
            },
            {
                'type': 'url',
                'name': 'URL Download',
                'description': 'Download files from a URL',
                'requirements': ['url'],
                'max_size': 'Unlimited',
                'supported_formats': ['any']
            }
        ]
    })


@app.route('/api/upload/health', methods=['GET'])
def upload_health_check():
    """Health check for upload service."""
    try:
        # Check if upload processor is running
        processor_status = 'running' if upload_processor.running else 'stopped'
        
        # Check available tools
        available_tools = _check_available_tools()
        
        return jsonify({
            'status': 'healthy',
            'processor_status': processor_status,
            'available_tools': available_tools,
            'timestamp': datetime.utcnow().isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500


def _handle_local_upload_initiation(data: Dict[str, Any], dataset_uuid: str) -> Response:
    """Handle local upload initiation (redirect to file upload endpoint)."""
    return jsonify({
        'message': 'For local uploads, use the /api/upload/local/upload endpoint',
        'upload_url': '/api/upload/local/upload',
        'dataset_uuid': dataset_uuid,
        'instructions': 'POST a file with metadata to the upload_url'
    }), 200


def _estimate_upload_time(source_type: UploadSourceType, source_config: Dict[str, Any]) -> int:
    """Estimate upload time in minutes."""
    # This is a simplified estimation
    # Real implementation would consider file size, network speed, etc.
    
    base_times = {
        UploadSourceType.LOCAL: 5,
        UploadSourceType.GOOGLE_DRIVE: 10,
        UploadSourceType.S3: 8,
        UploadSourceType.URL: 15
    }
    
    return base_times.get(source_type, 10)


def _format_time_human(minutes: int) -> str:
    """Format time in human-readable format."""
    if minutes < 60:
        return f"{minutes} minutes"
    elif minutes < 1440:  # 24 hours
        hours = minutes // 60
        remaining_minutes = minutes % 60
        if remaining_minutes == 0:
            return f"{hours} hours"
        else:
            return f"{hours} hours {remaining_minutes} minutes"
    else:
        days = minutes // 1440
        remaining_hours = (minutes % 1440) // 60
        if remaining_hours == 0:
            return f"{days} days"
        else:
            return f"{days} days {remaining_hours} hours"


def _check_available_tools() -> Dict[str, bool]:
    """Check which upload tools are available."""
    tools = ['rclone', 'rsync', 'aws', 'wget', 'curl']
    available = {}
    
    for tool in tools:
        try:
            result = os.system(f"which {tool} > /dev/null 2>&1")
            available[tool] = result == 0
        except:
            available[tool] = False
    
    return available


# Error handlers
@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large'}), 413


@app.errorhandler(400)
def bad_request(e):
    return jsonify({'error': 'Bad request'}), 400


@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    # Start upload processor
    upload_processor.start()
    
    # Run Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)
