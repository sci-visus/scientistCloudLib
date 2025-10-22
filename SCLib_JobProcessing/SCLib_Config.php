<?php
/**
 * SCLib Configuration - PHP Wrapper
 * This file provides PHP access to the Python SCLib configuration
 */

// Set error reporting
error_reporting(E_ALL);
ini_set('display_errors', 1);

// Define the path to the Python config
$python_config_path = __DIR__ . '/SCLib_Config.py';

// Check if Python config exists
if (!file_exists($python_config_path)) {
    throw new Exception("SCLib_Config.py not found at: $python_config_path");
}

// Function to get configuration by calling Python
function get_config() {
    global $python_config_path;
    
    // Try to execute Python script to get configuration
    $command = "cd " . dirname($python_config_path) . " && python3 -c \"
import sys
sys.path.append('.')

try:
    from SCLib_Config import get_config
    config = get_config()
    
    # Convert config to JSON-serializable format
    config_dict = {
        'database_name': config.get_database_name(),
        'mongo_url': config.get_mongo_url(),
        'server': {
            'deploy_server': config.server.deploy_server,
            'domain_name': config.server.domain_name
        },
        'auth': {
            'auth0_domain': config.auth.auth0_domain,
            'auth0_client_id': config.auth.auth0_client_id,
            'auth0_client_secret': config.auth.auth0_client_secret,
            'secret_key': config.auth.secret_key,
            'secret_iv': config.auth.secret_iv
        },
        'job_processing': config.get_job_processing_settings()
    }
    
    import json
    print(json.dumps(config_dict))
except Exception as e:
    print(json.dumps({'error': str(e)}))
\"";
    
    $output = shell_exec($command);
    if ($output) {
        $config_data = json_decode($output, true);
        
        if (isset($config_data['error'])) {
            throw new Exception("Python configuration error: " . $config_data['error']);
        }
        
        return $config_data;
    }
    
    // Fallback to environment variables if Python execution fails
    throw new Exception("Python configuration not available, using environment variables");
}

// Function to get MongoDB connection
function get_mongo_connection() {
    $config = get_config();
    
    // Create MongoDB connection
    $mongo_url = $config['mongo_url'];
    $database_name = $config['database_name'];
    
    try {
        // Try native MongoDB extension first
        if (class_exists('MongoDB\Client')) {
            $client = new MongoDB\Client($mongo_url);
            $database = $client->selectDatabase($database_name);
            return $database;
        }
        
        // Fallback to Composer MongoDB library
        if (file_exists('/var/www/html/vendor/autoload.php')) {
            require_once('/var/www/html/vendor/autoload.php');
            $client = new MongoDB\Client($mongo_url);
            $database = $client->selectDatabase($database_name);
            return $database;
        }
        
        throw new Exception("MongoDB extension not available and Composer library not found");
        
    } catch (Exception $e) {
        throw new Exception("MongoDB connection error: " . $e->getMessage());
    }
}

// Function to get collection name
function get_collection_name($type) {
    $config = get_config();
    $database_name = $config['database_name'];
    
    // Map collection types to names
    $collection_map = [
        'visstoredatas' => 'visstoredatas',
        'user_profile' => 'user_profile', 
        'teams' => 'teams',
        'shared_user' => 'shared_user'
    ];
    
    if (isset($collection_map[$type])) {
        return $collection_map[$type];
    }
    
    throw new Exception("Unknown collection type: $type");
}

// Initialize configuration
try {
    $config = get_config();
} catch (Exception $e) {
    error_log("SCLib configuration error: " . $e->getMessage());
    // Fallback to environment variables if Python config fails
    $config = [
        'database_name' => getenv('DB_NAME') ?: 'visstore',
        'mongo_url' => getenv('MONGO_URL') ?: 'mongodb://localhost:27017',
        'server' => [
            'deploy_server' => getenv('DEPLOY_SERVER') ?: 'https://scientistcloud.com',
            'domain_name' => getenv('DOMAIN_NAME') ?: 'scientistcloud.com'
        ],
        'auth' => [
            'auth0_domain' => getenv('AUTH0_DOMAIN') ?: '',
            'auth0_client_id' => getenv('AUTH0_CLIENT_ID') ?: '',
            'auth0_client_secret' => getenv('AUTH0_CLIENT_SECRET') ?: '',
            'secret_key' => getenv('SECRET_KEY') ?: '',
            'secret_iv' => getenv('SECRET_IV') ?: ''
        ],
        'job_processing' => [
            'in_data_dir' => getenv('JOB_IN_DATA_DIR') ?: '/mnt/visus_datasets/in_data',
            'out_data_dir' => getenv('JOB_OUT_DATA_DIR') ?: '/mnt/visus_datasets/out_data',
            'sync_data_dir' => getenv('JOB_SYNC_DATA_DIR') ?: '/mnt/visus_datasets/sync_data',
            'auth_dir' => getenv('JOB_AUTH_DATA_DIR') ?: '/mnt/visus_datasets/auth_data'
        ]
    ];
}
?>
