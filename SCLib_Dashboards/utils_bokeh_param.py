"""
Parameter parsing utilities for Bokeh dashboards
"""
import os
from urllib.parse import unquote
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def parse_url_parameters(request=None, status_callback=None):
    """
    Parse URL parameters from Bokeh request - matches your 4d_dashboard.py implementation
    
    Args:
        request: Bokeh request object (optional)
        status_callback: Function to call with status messages (optional)
    
    Returns:
        dict: Parsed parameters with hardcoded values
    """
    def add_status(message):
        if status_callback:
            status_callback(message)
        print(message)
    
    params = {
        'uuid': None,
        'server': None,
        'name': None,
        'base_dir': None,
        'save_dir': None,
        'has_args': False
    }
    
    try:
        if not request:
            add_status("❌ No request provided")
            return params
        
        # Get parameters from URL arguments (matches your implementation)
        args = request.arguments
        
        if not args:
            add_status("❌ No parameters provided - running in local mode")
            params['has_args'] = False
            return params
            
        # Extract the three URL parameters
        params['uuid'] = args.get('uuid', [b''])[0].decode('utf-8')
        params['server'] = args.get('server', [b''])[0].decode('utf-8')
        params['name'] = args.get('name', [b''])[0].decode('utf-8')
        
        if not params['uuid'] or not params['server'] or not params['name']:
            add_status("❌ Missing required parameters")
            return params
            
        # Decode name (matches your implementation)
        params['name'] = unquote(params['name'])
        
        # Set hardcoded values (matches your implementation)
        params['base_dir'] = f'/mnt/visus_datasets/upload/{params["uuid"]}'
        params['save_dir'] = f'/mnt/visus_datasets/converted/{params["uuid"]}'
        
        # Determine if running with URL args - if we have URL args, we're in production mode
        params['has_args'] = True
        add_status(f"✅ Parameters processed: {params['uuid']}, {params['server']}, {params['name']}")
        add_status(f"base_dir: {params['base_dir']}")
        add_status(f"save_dir: {params['save_dir']}")
        
        return params
        
    except Exception as e:
        add_status(f"❌ Parameter parsing failed: {e}")
        return params

def setup_directory_paths(params, has_args=False, status_callback=None):
    """
    Set up directory paths based on local vs production mode - matches your 4d_dashboard.py implementation
    
    Args:
        params: Parsed parameters dict
        has_args: Whether running with URL arguments (production mode)
        status_callback: Function to call with status messages (optional)
    
    Returns:
        dict: Updated params with correct directory paths
    """
    def add_status(message):
        if status_callback:
            status_callback(message)
        print(message)
    
    if not has_args:
        # Local development - use hardcoded local directory
        local_base_dir = os.getenv('LOCAL_BASE_DIR', '/Users/amygooch/GIT/SCI/DATA/CHESS/mi_PIL11')
        params['base_dir'] = local_base_dir
        params['save_dir'] = local_base_dir
        params['server'] = 'false'
        params['name'] = '4D_probe_IDX_dashboard LOCAL TEST'
        add_status(f"base_dir: {params['base_dir']}")
        add_status(f"save_dir: {params['save_dir']}")
    else:
        # Production mode - use the parsed parameters
        # base_dir and save_dir are already set in parse_url_parameters
        add_status(f"base_dir: {params['base_dir']}")
        add_status(f"save_dir: {params['save_dir']}")
    
    return params

def validate_required_params(params, required_fields=['uuid']):
    """
    Validate that required parameters are present
    
    Args:
        params: Parsed parameters dict
        required_fields: List of required field names
    
    Returns:
        tuple: (is_valid, missing_fields)
    """
    missing_fields = []
    for field in required_fields:
        if not params.get(field):
            missing_fields.append(field)
    
    return len(missing_fields) == 0, missing_fields
