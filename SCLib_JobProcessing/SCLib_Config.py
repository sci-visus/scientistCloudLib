#!/usr/bin/env python3
"""
ScientistCloud Configuration Manager
Centralized configuration management for environment variables and collection names.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class SCLib_DatabaseConfig:
    """Database configuration settings."""
    mongo_url: str
    db_name: str
    db_host: str
    db_pass: str
    
    # Connection pool settings
    max_pool_size: int = 20
    min_pool_size: int = 5
    max_idle_time_ms: int = 60000
    wait_queue_timeout_ms: int = 10000
    server_selection_timeout_ms: int = 15000
    connect_timeout_ms: int = 20000
    socket_timeout_ms: int = 60000
    
    # SSL/TLS settings
    tls_allow_invalid_certificates: bool = True
    tls_allow_invalid_hostnames: bool = True
    
    # Write concerns
    write_concern: str = 'majority'
    journal: bool = True
    
    # Retry settings
    retry_writes: bool = True
    retry_reads: bool = True


@dataclass
class SCLib_CollectionConfig:
    """Collection names configuration."""
    # Core collections (from existing system)
    admins: str = 'admins'
    shared_team: str = 'shared_team'
    shared_user: str = 'shared_user'
    teams: str = 'teams'
    user_profile: str = 'user_profiles'
    visstoredatas: str = 'visstoredatas'
    
    # Job processing collections (new for SC_JobProcessing)
    jobs: str = 'jobs'
    job_logs: str = 'job_logs'
    job_metrics: str = 'job_metrics'
    worker_stats: str = 'worker_stats'
    
    # Legacy collections (for backward compatibility)
    collection: str = 'collection'
    collection1: str = 'collection1'
    team_collection: str = 'team_collection'


@dataclass
class SCLib_ServerConfig:
    """Server and deployment configuration."""
    deploy_server: str
    domain_name: str
    env_file: str
    
    # Directory paths
    home_dir: str
    visus_code: str
    visus_docker: str
    visus_server: str
    visus_db: str
    visus_datasets: str
    visus_temp: str
    
    # Python requirements
    python_requirements_file: str = 'ubuntu-python310-requirements.txt'


@dataclass
class SCLib_AuthConfig:
    """Authentication configuration."""
    # Auth0 settings
    auth0_domain: str
    auth0_client_id: str
    auth0_client_secret: str
    auth0_management_client_id: str
    auth0_management_client_secret: str
    
    # Google OAuth settings
    google_client_id: str
    google_client_secret: str
    auth_google_client_id: str
    auth_google_client_secret: str
    
    # Security settings
    secret_key: str
    secret_iv: str
    
    # SSL settings
    ssl_email: str


@dataclass
class SCLib_GitConfig:
    """Git configuration."""
    git_branch_visstore: str
    git_branch_js: str
    git_token: str


@dataclass
class SCLib_JobProcessingConfig:
    """Job processing specific configuration."""
    # Job processing directories
    in_data_dir: str = '/mnt/visus_datasets/upload'
    out_data_dir: str = '/mnt/visus_datasets/converted'
    sync_data_dir: str = '/mnt/visus_datasets/sync'
    auth_dir: str = '/mnt/visus_datasets/auth'
    
    # Job processing settings
    max_concurrent_jobs: int = 5
    job_timeout_minutes: int = 120
    max_retry_attempts: int = 3
    retry_delay_seconds: int = 30
    
    # Worker settings
    worker_heartbeat_interval: int = 30
    worker_cleanup_interval: int = 300
    stale_job_timeout_hours: int = 2
    
    # Monitoring settings
    health_check_interval: int = 60
    performance_report_interval: int = 3600
    cleanup_old_jobs_days: int = 30


class SCLib_Config:
    """
    Centralized configuration manager for ScientistCloud.
    Handles environment variables, collection names, and system settings.
    """
    
    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration.
        
        Args:
            env_file: Optional path to environment file to load
        """
        self.env_file = env_file
        self._load_environment()
        self._initialize_configs()
    
    def _load_environment(self):
        """Load environment variables from file or system environment."""
        if self.env_file and os.path.exists(self.env_file):
            self._load_env_file(self.env_file)
        else:
            # Try to find environment file based on common patterns
            self._auto_detect_env_file()
        
        # Override with system environment variables
        self._load_system_environment()
    
    def _load_env_file(self, env_file: str):
        """Load environment variables from a file."""
        try:
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        # Remove quotes if present
                        value = value.strip('"\'')
                        os.environ[key] = value
                        logger.debug(f"Loaded {key} from {env_file}")
        except Exception as e:
            logger.warning(f"Could not load environment file {env_file}: {e}")
    
    def _auto_detect_env_file(self):
        """Auto-detect environment file based on common patterns."""
        # Check for environment variable first
        env_file_from_env = os.getenv('SCLIB_ENV_FILE')
        if env_file_from_env and os.path.exists(env_file_from_env):
            logger.info(f"Using environment file from SCLIB_ENV_FILE: {env_file_from_env}")
            self._load_env_file(env_file_from_env)
            return
        
        # Check for SCLIB_MYTEST environment variable
        sclib_mytest = os.getenv('SCLIB_MYTEST')
        if sclib_mytest:
            env_local_path = os.path.join(sclib_mytest, 'env.local')
            if os.path.exists(env_local_path):
                logger.info(f"Using environment file from SCLIB_MYTEST: {env_local_path}")
                self._load_env_file(env_local_path)
                return
        
        # Check for SCLIB_HOME environment variable
        sclib_home = os.getenv('SCLIB_HOME')
        if sclib_home:
            # Look for env.local in SCLIB_HOME directory
            env_local_path = os.path.join(sclib_home, 'env.local')
            if os.path.exists(env_local_path):
                logger.info(f"Using environment file from SCLIB_HOME: {env_local_path}")
                self._load_env_file(env_local_path)
                return
            
            # Look for env.local in parent directory of SCLIB_HOME
            parent_env_path = os.path.join(os.path.dirname(sclib_home), 'env.local')
            if os.path.exists(parent_env_path):
                logger.info(f"Using environment file from SCLIB_HOME parent: {parent_env_path}")
                self._load_env_file(parent_env_path)
                return
        
        # Fallback to relative paths (no hardcoded absolute paths)
        possible_paths = [
            './env.local',
            '../env.local',
            './config/env.local',
            '../config/env.local',
            './SCLib_TryTest/env.local',
            '../SCLib_TryTest/env.local',
            './config/env.scientistcloud.com',
            './config/env.all',
            '../config/env.scientistcloud.com',
            '../config/env.all'
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Auto-detected environment file: {path}")
                self._load_env_file(path)
                break
        else:
            logger.info("No environment file found, using system environment variables only")
    
    def _load_system_environment(self):
        """Load system environment variables."""
        # This is already handled by os.environ, but we can add validation here
        required_vars = ['MONGO_URL', 'DB_NAME']
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            logger.warning(f"Missing required environment variables: {missing_vars}")
    
    def _initialize_configs(self):
        """Initialize all configuration objects."""
        # Database configuration
        self.database = SCLib_DatabaseConfig(
            mongo_url=os.getenv('MONGO_URL', ''),
            db_name=os.getenv('DB_NAME', 'scientistcloud'),
            db_host=os.getenv('DB_HOST', ''),
            db_pass=os.getenv('DB_PASS', ''),
            
            # Connection pool settings (can be overridden by environment)
            max_pool_size=int(os.getenv('MONGO_MAX_POOL_SIZE', '20')),
            min_pool_size=int(os.getenv('MONGO_MIN_POOL_SIZE', '5')),
            max_idle_time_ms=int(os.getenv('MONGO_MAX_IDLE_TIME_MS', '60000')),
            wait_queue_timeout_ms=int(os.getenv('MONGO_WAIT_QUEUE_TIMEOUT_MS', '10000')),
            server_selection_timeout_ms=int(os.getenv('MONGO_SERVER_SELECTION_TIMEOUT_MS', '15000')),
            connect_timeout_ms=int(os.getenv('MONGO_CONNECT_TIMEOUT_MS', '20000')),
            socket_timeout_ms=int(os.getenv('MONGO_SOCKET_TIMEOUT_MS', '60000')),
            
            # SSL settings
            tls_allow_invalid_certificates=os.getenv('MONGO_TLS_ALLOW_INVALID_CERTS', 'true').lower() == 'true',
            tls_allow_invalid_hostnames=os.getenv('MONGO_TLS_ALLOW_INVALID_HOSTNAMES', 'true').lower() == 'true',
            
            # Write concerns
            write_concern=os.getenv('MONGO_WRITE_CONCERN', 'majority'),
            journal=os.getenv('MONGO_JOURNAL', 'true').lower() == 'true',
            
            # Retry settings
            retry_writes=os.getenv('MONGO_RETRY_WRITES', 'true').lower() == 'true',
            retry_reads=os.getenv('MONGO_RETRY_READS', 'true').lower() == 'true'
        )
        
        # Collection configuration
        self.collections = SCLib_CollectionConfig(
            # Core collections (from existing system)
            admins=os.getenv('COLLECTION_ADMINS', 'admins'),
            shared_team=os.getenv('COLLECTION_SHARED_TEAM', 'shared_team'),
            shared_user=os.getenv('COLLECTION_SHARED_USER', 'shared_user'),
            teams=os.getenv('COLLECTION_TEAMS', 'teams'),
            user_profile=os.getenv('COLLECTION_USER_PROFILE', 'user_profile'),
            visstoredatas=os.getenv('COLLECTION_VISSTOREDATAS', 'visstoredatas'),
            
            # Job processing collections (new for SC_JobProcessing)
            jobs=os.getenv('COLLECTION_JOBS', 'jobs'),
            job_logs=os.getenv('COLLECTION_JOB_LOGS', 'job_logs'),
            job_metrics=os.getenv('COLLECTION_JOB_METRICS', 'job_metrics'),
            worker_stats=os.getenv('COLLECTION_WORKER_STATS', 'worker_stats'),
            
            # Legacy collections (for backward compatibility)
            collection=os.getenv('COLLECTION_LEGACY', 'collection'),
            collection1=os.getenv('COLLECTION_LEGACY1', 'collection1'),
            team_collection=os.getenv('COLLECTION_TEAM_LEGACY', 'team_collection')
        )
        
        # Server configuration
        self.server = SCLib_ServerConfig(
            deploy_server=os.getenv('DEPLOY_SERVER', 'https://scientistcloud.com'),
            domain_name=os.getenv('DOMAIN_NAME', 'scientistcloud.com'),
            env_file=os.getenv('ENV_FILE', 'env.scientistcloud.com'),
            home_dir=os.getenv('HOME_DIR', '/home/amy/VisStoreCode/visus-dataportal-private'),
            visus_code=os.getenv('VISUS_CODE', '/home/amy/VisStoreCode/visus-dataportal-private'),
            visus_docker=os.getenv('VISUS_DOCKER', '/home/amy/VisStoreCode/visus-dataportal-private/Docker/'),
            visus_server=os.getenv('VISUS_SERVER', '/home/amy/dockerStartDir/VisStoreDataTemp'),
            visus_db=os.getenv('VISUS_DB', '/home/amy/dockerStartDir/VisStoreDataTemp/db/'),
            visus_datasets=os.getenv('VISUS_DATASETS', '/home/amy/dockerStartDir/VisStoreDataTemp/'),
            visus_temp=os.getenv('VISUS_TEMP', '/home/amy/dockerStartDir/VisStoreDataTemp/tmp/'),
            python_requirements_file=os.getenv('PYTHON_REQUIREMENTS_FILE', 'ubuntu-python310-requirements.txt')
        )
        
        # Authentication configuration
        self.auth = SCLib_AuthConfig(
            auth0_domain=os.getenv('AUTH0_DOMAIN', ''),
            auth0_client_id=os.getenv('AUTH0_CLIENT_ID', ''),
            auth0_client_secret=os.getenv('AUTH0_CLIENT_SECRET', ''),
            auth0_management_client_id=os.getenv('AUTH0_MANAGEMENT_CLIENT_ID', ''),
            auth0_management_client_secret=os.getenv('AUTH0_MANAGEMENT_CLIENT_SECRET', ''),
            google_client_id=os.getenv('GOOGLE_CLIENT_ID', ''),
            google_client_secret=os.getenv('GOOGLE_CLIENT_SECRET', ''),
            auth_google_client_id=os.getenv('AUTH_GOOGLE_CLIENT_ID', ''),
            auth_google_client_secret=os.getenv('AUTH_GOOGLE_CLIENT_SECRET', ''),
            secret_key=os.getenv('SECRET_KEY', ''),
            secret_iv=os.getenv('SECRET_IV', ''),
            ssl_email=os.getenv('SSL_EMAIL', '')
        )
        
        # Git configuration
        self.git = SCLib_GitConfig(
            git_branch_visstore=os.getenv('GIT_BRANCH_VISSTORE', 'ScientistCloud_merging'),
            git_branch_js=os.getenv('GIT_BRANCH_JS', 'VisStoreOpenVisusJS_5181'),
            git_token=os.getenv('GIT_TOKEN', '')
        )
        
        # Job processing configuration
        self.job_processing = SCLib_JobProcessingConfig(
            in_data_dir=os.getenv('JOB_IN_DATA_DIR', '/mnt/visus_datasets/upload'),
            out_data_dir=os.getenv('JOB_OUT_DATA_DIR', '/mnt/visus_datasets/converted'),
            sync_data_dir=os.getenv('JOB_SYNC_DATA_DIR', '/mnt/visus_datasets/sync'),
            auth_dir=os.getenv('JOB_AUTH_DATA_DIR', '/mnt/visus_datasets/auth'),
            max_concurrent_jobs=int(os.getenv('JOB_MAX_CONCURRENT', '5')),
            job_timeout_minutes=int(os.getenv('JOB_TIMEOUT_MINUTES', '120')),
            max_retry_attempts=int(os.getenv('JOB_MAX_RETRY_ATTEMPTS', '3')),
            retry_delay_seconds=int(os.getenv('JOB_RETRY_DELAY_SECONDS', '30')),
            worker_heartbeat_interval=int(os.getenv('WORKER_HEARTBEAT_INTERVAL', '30')),
            worker_cleanup_interval=int(os.getenv('WORKER_CLEANUP_INTERVAL', '300')),
            stale_job_timeout_hours=int(os.getenv('STALE_JOB_TIMEOUT_HOURS', '2')),
            health_check_interval=int(os.getenv('HEALTH_CHECK_INTERVAL', '60')),
            performance_report_interval=int(os.getenv('PERFORMANCE_REPORT_INTERVAL', '3600')),
            cleanup_old_jobs_days=int(os.getenv('CLEANUP_OLD_JOBS_DAYS', '30'))
        )
        
        # Source directory for uploads
        self.source_dir = os.getenv('SCLIB_SOURCE_DIR', os.getcwd())
    
    def get_mongo_url(self) -> str:
        """Get the complete MongoDB URL with all connection parameters."""
        base_url = self.database.mongo_url
        
        # Remove existing parameters if any
        if '?' in base_url:
            base_url = base_url.split('?')[0]
        
        # Build parameter string
        params = [
            f"retryWrites={str(self.database.retry_writes).lower()}",
            f"w={self.database.write_concern}",
            f"maxPoolSize={self.database.max_pool_size}",
            f"minPoolSize={self.database.min_pool_size}",
            f"maxIdleTimeMS={self.database.max_idle_time_ms}",
            f"waitQueueTimeoutMS={self.database.wait_queue_timeout_ms}",
            f"serverSelectionTimeoutMS={self.database.server_selection_timeout_ms}",
            f"connectTimeoutMS={self.database.connect_timeout_ms}",
            f"socketTimeoutMS={self.database.socket_timeout_ms}",
            f"tlsAllowInvalidCertificates={str(self.database.tls_allow_invalid_certificates).lower()}",
            f"tlsAllowInvalidHostnames={str(self.database.tls_allow_invalid_hostnames).lower()}"
        ]
        
        return f"{base_url}?{'&'.join(params)}"
    
    def get_collection_name(self, collection_type: str) -> str:
        """
        Get collection name by type.
        
        Args:
            collection_type: Type of collection (datasets, jobs, users, etc.)
        
        Returns:
            Collection name
        """
        collection_map = {
            # Core collections (from existing system)
            'admins': self.collections.admins,
            'shared_team': self.collections.shared_team,
            'shared_user': self.collections.shared_user,
            'teams': self.collections.teams,
            'user_profile': self.collections.user_profile,
            'visstoredatas': self.collections.visstoredatas,
            
            # Job processing collections (new for SC_JobProcessing)
            'jobs': self.collections.jobs,
            'job_logs': self.collections.job_logs,
            'job_metrics': self.collections.job_metrics,
            'worker_stats': self.collections.worker_stats,
            
            # Legacy collections (for backward compatibility)
            'collection': self.collections.collection,
            'collection1': self.collections.collection1,
            'team_collection': self.collections.team_collection,
            
            # Aliases for backward compatibility
            'datasets': self.collections.visstoredatas,
            'users': self.collections.user_profile,
            'shared_users': self.collections.shared_user,
            'shared_teams': self.collections.shared_team
        }
        
        if collection_type not in collection_map:
            raise ValueError(f"Unknown collection type: {collection_type}")
        
        return collection_map[collection_type]
    
    def get_database_name(self) -> str:
        """Get the database name."""
        return self.database.db_name
    
    def get_job_processing_settings(self) -> Dict[str, Any]:
        """Get job processing settings as a dictionary."""
        return {
            'in_data_dir': self.job_processing.in_data_dir,
            'out_data_dir': self.job_processing.out_data_dir,
            'sync_data_dir': self.job_processing.sync_data_dir,
            'auth_dir': self.job_processing.auth_dir,
            'max_concurrent_jobs': self.job_processing.max_concurrent_jobs,
            'job_timeout_minutes': self.job_processing.job_timeout_minutes,
            'max_retry_attempts': self.job_processing.max_retry_attempts,
            'retry_delay_seconds': self.job_processing.retry_delay_seconds,
            'worker_heartbeat_interval': self.job_processing.worker_heartbeat_interval,
            'worker_cleanup_interval': self.job_processing.worker_cleanup_interval,
            'stale_job_timeout_hours': self.job_processing.stale_job_timeout_hours,
            'health_check_interval': self.job_processing.health_check_interval,
            'performance_report_interval': self.job_processing.performance_report_interval,
            'cleanup_old_jobs_days': self.job_processing.cleanup_old_jobs_days
        }
    
    def validate_config(self) -> List[str]:
        """
        Validate configuration and return list of issues.
        
        Returns:
            List of validation issues (empty if all valid)
        """
        issues = []
        
        # Check required database settings
        if not self.database.mongo_url:
            issues.append("MONGO_URL is required")
        
        if not self.database.db_name:
            issues.append("DB_NAME is required")
        
        # Check required auth settings
        if not self.auth.auth0_domain:
            issues.append("AUTH0_DOMAIN is required")
        
        if not self.auth.auth0_client_id:
            issues.append("AUTH0_CLIENT_ID is required")
        
        # Check directory paths
        required_dirs = [
            self.job_processing.in_data_dir,
            self.job_processing.out_data_dir,
            self.job_processing.sync_data_dir,
            self.job_processing.auth_dir
        ]
        
        for dir_path in required_dirs:
            if not os.path.exists(dir_path):
                issues.append(f"Directory does not exist: {dir_path}")
        
        return issues
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'database': {
                'mongo_url': self.database.mongo_url,
                'db_name': self.database.db_name,
                'db_host': self.database.db_host,
                'max_pool_size': self.database.max_pool_size,
                'min_pool_size': self.database.min_pool_size
            },
            'collections': {
                'admins': self.collections.admins,
                'shared_team': self.collections.shared_team,
                'shared_user': self.collections.shared_user,
                'teams': self.collections.teams,
                'user_profile': self.collections.user_profile,
                'visstoredatas': self.collections.visstoredatas,
                'jobs': self.collections.jobs,
                'job_logs': self.collections.job_logs,
                'job_metrics': self.collections.job_metrics,
                'worker_stats': self.collections.worker_stats
            },
            'server': {
                'deploy_server': self.server.deploy_server,
                'domain_name': self.server.domain_name,
                'home_dir': self.server.home_dir
            },
            'job_processing': self.get_job_processing_settings()
        }
    
    def print_config(self):
        """Print current configuration (excluding sensitive data)."""
        print("ScientistCloud Configuration")
        print("=" * 50)
        print(f"Database: {self.database.db_name}")
        print(f"Collections:")
        print(f"  - Admins: {self.collections.admins}")
        print(f"  - Shared Team: {self.collections.shared_team}")
        print(f"  - Shared User: {self.collections.shared_user}")
        print(f"  - Teams: {self.collections.teams}")
        print(f"  - User Profile: {self.collections.user_profile}")
        print(f"  - Visstore Datas: {self.collections.visstoredatas}")
        print(f"  - Jobs: {self.collections.jobs}")
        print(f"  - Job Logs: {self.collections.job_logs}")
        print(f"  - Job Metrics: {self.collections.job_metrics}")
        print(f"  - Worker Stats: {self.collections.worker_stats}")
        print(f"Server: {self.server.deploy_server}")
        print(f"Domain: {self.server.domain_name}")
        print(f"Job Processing:")
        print(f"  - Max Concurrent Jobs: {self.job_processing.max_concurrent_jobs}")
        print(f"  - Job Timeout: {self.job_processing.job_timeout_minutes} minutes")
        print(f"  - Max Retry Attempts: {self.job_processing.max_retry_attempts}")


# Global configuration instance
_config_instance: Optional[SCLib_Config] = None


def get_config(env_file: Optional[str] = None) -> SCLib_Config:
    """
    Get global configuration instance.
    
    Args:
        env_file: Optional path to environment file
    
    Returns:
        SCLib_Config instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = SCLib_Config(env_file)
    return _config_instance


def reload_config(env_file: Optional[str] = None) -> SCLib_Config:
    """
    Reload configuration from environment.
    
    Args:
        env_file: Optional path to environment file
    
    Returns:
        New SCLib_Config instance
    """
    global _config_instance
    _config_instance = SCLib_Config(env_file)
    return _config_instance


# Convenience functions for common operations

def get_database_name() -> str:
    """Get the database name."""
    return get_config().get_database_name()


def get_collection_name(collection_type: str) -> str:
    """Get collection name by type."""
    return get_config().get_collection_name(collection_type)


def get_mongo_url() -> str:
    """Get the complete MongoDB URL."""
    return get_config().get_mongo_url()


def get_job_processing_settings() -> Dict[str, Any]:
    """Get job processing settings."""
    return get_config().get_job_processing_settings()


if __name__ == '__main__':
    # Example usage and testing
    print("SCLib_Config - ScientistCloud Configuration Manager")
    print("=" * 60)
    
    try:
        # Load configuration
        config = get_config()
        
        # Print configuration
        config.print_config()
        
        # Validate configuration
        issues = config.validate_config()
        if issues:
            print(f"\nConfiguration Issues:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"\n✅ Configuration is valid")
        
        # Test collection name retrieval
        print(f"\nCollection Names:")
        print(f"  - Admins: {get_collection_name('admins')}")
        print(f"  - Shared Team: {get_collection_name('shared_team')}")
        print(f"  - Shared User: {get_collection_name('shared_user')}")
        print(f"  - Teams: {get_collection_name('teams')}")
        print(f"  - User Profile: {get_collection_name('user_profile')}")
        print(f"  - Visstore Datas: {get_collection_name('visstoredatas')}")
        print(f"  - Jobs: {get_collection_name('jobs')}")
        
        # Test aliases
        print(f"\nCollection Aliases:")
        print(f"  - Datasets (alias): {get_collection_name('datasets')}")
        print(f"  - Users (alias): {get_collection_name('users')}")
        print(f"  - Shared Users (alias): {get_collection_name('shared_users')}")
        print(f"  - Shared Teams (alias): {get_collection_name('shared_teams')}")
        
        # Test MongoDB URL
        print(f"\nMongoDB URL: {get_mongo_url()[:50]}...")
        
    except Exception as e:
        print(f"❌ Error: {e}")
