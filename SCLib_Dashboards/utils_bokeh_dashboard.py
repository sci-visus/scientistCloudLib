"""
Main dashboard utilities combining auth, MongoDB, and parameter parsing
"""
import os
from pathlib import Path

def initialize_dashboard(request=None, status_callback=None):
    """
    Initialize dashboard with authentication, MongoDB connection, and parameter parsing
    
    Args:
        request: Bokeh request object (optional)
        status_callback: Function to call with status messages (optional)
    
    Returns:
        dict: {
            'success': bool,
            'auth_result': dict,
            'mongodb': dict,
            'params': dict,
            'dataset_path': str or None,
            'error': str or None
        }
    """
    def add_status(message):
        if status_callback:
            status_callback(message)
        print(message)
    
    try:
        # Check if running with URL arguments - if no args, we're in local mode
        has_args = request and request.arguments and len(request.arguments) > 0
        
        if not has_args:
            # Local development - skip all the complex setup
            add_status("🏠 Running in local mode - skipping auth and MongoDB")
            
            # Set up local parameters directly
            local_base_dir = os.getenv('LOCAL_BASE_DIR', '/Users/amygooch/GIT/SCI/DATA/CHESS/mi_PIL11')
            params = {
                'uuid': 'local',
                'server': 'false',
                'name': '4D_probe_IDX_dashboard LOCAL TEST',
                'base_dir': local_base_dir,
                'save_dir': local_base_dir,
                'has_args': False
            }
            
            # Set up local auth result
            auth_result = {
                'is_authorized': True,
                'user_email': None,
                'access_type': 'local',
                'error': None
            }
            
            add_status(f"base_dir: {params['base_dir']}")
            add_status(f"save_dir: {params['save_dir']}")
            add_status("✅ Local dashboard initialization successful")
            
            return {
                'success': True,
                'auth_result': auth_result,
                'mongodb': None,  # No MongoDB needed for local
                'params': params,
                'dataset_path': None,
                'error': None
            }
        
        else:
            from utils_bokeh_auth import authenticate_user
            from utils_bokeh_mongodb import connect_to_mongodb, cleanup_mongodb
            from utils_bokeh_param import parse_url_parameters, setup_directory_paths, validate_required_params

            # Production mode - do full initialization
            add_status("🌐 Running in production mode - full initialization")
            
            # Parse URL parameters
            add_status("📝 Parsing URL parameters...")
            params = parse_url_parameters(request, status_callback)
            
            # Validate required parameters
            is_valid, missing_fields = validate_required_params(params, ['uuid'])
            if not is_valid:
                error_msg = f"Missing required parameters: {', '.join(missing_fields)}"
                add_status(f"❌ {error_msg}")
                return {
                    'success': False,
                    'auth_result': None,
                    'mongodb': None,
                    'params': params,
                    'dataset_path': None,
                    'error': error_msg
                }
            
            # Connect to MongoDB
            add_status("🔗 Connecting to MongoDB...")
            client, mymongodb, collection, collection1, team_collection, shared_team_collection = connect_to_mongodb()
            if not client:
                error_msg = "Failed to connect to MongoDB"
                add_status(f"❌ {error_msg}")
                return {
                    'success': False,
                    'auth_result': None,
                    'mongodb': None,
                    'params': params,
                    'dataset_path': None,
                    'error': error_msg
                }
            
            # Authenticate user
            add_status("🔐 Authenticating user...")
            auth_result = authenticate_user(params['uuid'], request, status_callback)
            
            if not auth_result['is_authorized']:
                error_msg = auth_result.get('error', 'User not authorized')
                add_status(f"❌ {error_msg}")
                return {
                    'success': False,
                    'auth_result': auth_result,
                    'mongodb': {
                        'client': client,
                        'mymongodb': mymongodb,
                        'collection': collection,
                        'collection1': collection1,
                        'team_collection': team_collection
                    },
                    'params': params,
                    'dataset_path': None,
                    'error': error_msg
                }
            
            # Set up directory paths based on local vs production mode
            params = setup_directory_paths(params, params['has_args'], status_callback)
            
            add_status("✅ Production dashboard initialization successful 1")
            return {
                'success': True,
                'auth_result': auth_result,
                'mongodb': {
                    'client': client,
                    'mymongodb': mymongodb,
                    'collection': collection,
                    'collection1': collection1,
                    'team_collection': team_collection
                },
                'params': params,
                'dataset_path': None,
                'error': None
            }
        
    except Exception as e:
        error_msg = f"Dashboard initialization failed: {e}"
        add_status(f"❌ {error_msg}")
        return {
            'success': False,
            'auth_result': None,
            'mongodb': None,
            'params': params if 'params' in locals() else {},
            'dataset_path': None,
            'error': error_msg
        }


def find_visus_idx_file(uuid):
    """
    Recursively search for visus.idx file given a UUID in either:
    - /mnt/visus_datasets/converted/{uuid}/visus.idx
    - /mnt/visus_datasets/upload/{uuid}/visus.idx
    
    Args:
        uuid: UUID string to search for
        
    Returns:
        str or None: Full path to visus.idx file if found, None otherwise
    """
    if not uuid:
        return None
    
    # Define the two base directories to search
    base_dirs = [
        f"/mnt/visus_datasets/converted/{uuid}",
        f"/mnt/visus_datasets/upload/{uuid}"
    ]
    
    # First, check the direct paths (non-recursive)
    for base_dir in base_dirs:
        direct_path = os.path.join(base_dir, "visus.idx")
        if os.path.isfile(direct_path):
            return direct_path
    
    # If not found directly, search recursively in both directories
    for base_dir in base_dirs:
        if not os.path.isdir(base_dir):
            continue
        
        # Use pathlib for recursive search
        base_path = Path(base_dir)
        for idx_file in base_path.rglob("visus.idx"):
            if idx_file.is_file():
                # Resolve to absolute path to ensure we return full path
                return str(idx_file.resolve())
    
    # File not found in either location
    return None
