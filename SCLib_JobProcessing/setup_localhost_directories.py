#!/usr/bin/env python3
"""
Localhost Directory Setup for ScientistCloud Job Processing
Creates and configures local directories for testing on localhost.
"""

import os
import sys
from pathlib import Path

def create_localhost_directories():
    """Create localhost directories for testing."""
    
    # Base directory from your env.local
    base_dir = Path("/Users/amygooch/GIT/VisStoreDataTemp")
    
    # Job processing subdirectories
    directories = {
        "upload": base_dir / "upload",
        "converted": base_dir / "converted", 
        "sync": base_dir / "sync",
        "auth": base_dir / "auth",
        "tmp": base_dir / "tmp"
    }
    
    print("🏗️  Setting up localhost directories for ScientistCloud Job Processing")
    print(f"Base directory: {base_dir}")
    print()
    
    # Create directories
    for name, path in directories.items():
        try:
            path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created: {path}")
        except PermissionError:
            print(f"❌ Permission denied: {path}")
            print(f"   Try: sudo mkdir -p {path}")
        except Exception as e:
            print(f"❌ Error creating {path}: {e}")
    
    print()
    
    # Set permissions
    print("🔐 Setting directory permissions...")
    for name, path in directories.items():
        try:
            # Set permissions to 755 (read/write/execute for owner, read/execute for others)
            os.chmod(path, 0o755)
            print(f"✅ Set permissions: {path}")
        except PermissionError:
            print(f"❌ Permission denied setting permissions: {path}")
            print(f"   Try: sudo chmod 755 {path}")
        except Exception as e:
            print(f"❌ Error setting permissions for {path}: {e}")
    
    print()
    
    # Create environment configuration
    print("📝 Creating localhost environment configuration...")
    
    env_config = f"""# Localhost Configuration for ScientistCloud Job Processing
# Add these to your env.local file

# Job Processing Directories (localhost)
IN_DATA_DIR={directories['upload']}
OUT_DATA_DIR={directories['converted']}
SYNC_DATA_DIR={directories['sync']}
AUTH_DIR={directories['auth']}
TEMP_DIR={directories['tmp']}
LARGE_UPLOADS_DIR={directories['large_uploads']}

# FastAPI Configuration
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=5000
FASTAPI_RELOAD=true

# Upload Configuration
LARGE_FILE_THRESHOLD_MB=100
CHUNK_SIZE_MB=100
MAX_FILE_SIZE_TB=10

# MongoDB Configuration (from your existing env.local)
MONGO_URL="mongodb+srv://visstore:your_db_password@cluster0.pxjz2qe.mongodb.net/SCLib_Test?retryWrites=true&w=majority&maxPoolSize=5&minPoolSize=1&maxIdleTimeMS=10000&waitQueueTimeoutMS=2000&serverSelectionTimeoutMS=10000&connectTimeoutMS=10000&socketTimeoutMS=30000&heartbeatFrequencyMS=10000&tlsAllowInvalidCertificates=true&tlsAllowInvalidHostnames=true"
DB_NAME=SCLib_Test
DB_PASS=your_db_password
DB_HOST=Cluster0.wimj3q4.mongodb.net

# Auth0 Configuration (from your existing env.local)
AUTH0_DOMAIN=dev-ep26akpb.auth0.com
AUTH0_CLIENT_ID=your_auth0_client_id_here
AUTH0_CLIENT_SECRET=your_auth0_client_secret_here

# Google OAuth (from your existing env.local)
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here

# Server Configuration (from your existing env.local)
DEPLOY_SERVER=http://localhost
DOMAIN_NAME=localhost
HOME_DIR=/Users/amygooch/GIT/VisusDataPortalPrivate
VISUS_CODE=/Users/amygooch/GIT/VisusDataPortalPrivate
VISUS_DOCKER=/Users/amygooch/GIT/VisusDataPortalPrivate/Docker
VISUS_SERVER={base_dir}
VISUS_DB={base_dir}/db
VISUS_DATASETS={base_dir}
VISUS_TEMP={directories['tmp']}
"""
    
    # Write to file
    config_file = Path("localhost_env_config.txt")
    with open(config_file, 'w') as f:
        f.write(env_config)
    
    print(f"✅ Created configuration file: {config_file}")
    print()
    
    # Display summary
    print("📋 Summary:")
    print(f"   Base directory: {base_dir}")
    print(f"   Upload directory: {directories['upload']}")
    print(f"   Converted directory: {directories['converted']}")
    print(f"   Sync directory: {directories['sync']}")
    print(f"   Auth directory: {directories['auth']}")
    print(f"   Temp directory: {directories['tmp']}")
    print(f"   Large uploads directory: {directories['large_uploads']}")
    print()
    
    print("🔧 Next steps:")
    print("1. Add the configuration from localhost_env_config.txt to your env.local file")
    print("2. Start the FastAPI server: python start_fastapi_server.py")
    print("3. Test with: python example_unified_upload.py")
    print()
    
    # Test directory access
    print("🧪 Testing directory access...")
    for name, path in directories.items():
        if path.exists() and os.access(path, os.R_OK | os.W_OK):
            print(f"✅ {name}: {path} (readable/writable)")
        else:
            print(f"❌ {name}: {path} (not accessible)")

def update_config_for_localhost():
    """Update the SCLib_Config.py to use localhost paths."""
    
    config_file = Path("SCLib_Config.py")
    if not config_file.exists():
        print("❌ SCLib_Config.py not found in current directory")
        return
    
    print("🔧 Updating SCLib_Config.py for localhost...")
    
    # Read current config
    with open(config_file, 'r') as f:
        content = f.read()
    
    # Replace the default path with localhost path
    old_path = "/home/amy/dockerStartDir/VisStoreDataTemp/"
    new_path = "/Users/amygooch/GIT/VisStoreDataTemp/"
    
    if old_path in content:
        content = content.replace(old_path, new_path)
        
        # Write updated config
        with open(config_file, 'w') as f:
            f.write(content)
        
        print(f"✅ Updated SCLib_Config.py: {old_path} → {new_path}")
    else:
        print("ℹ️  SCLib_Config.py already uses localhost paths or path not found")

if __name__ == "__main__":
    print("🚀 ScientistCloud Localhost Setup")
    print("=" * 50)
    
    # Create directories
    create_localhost_directories()
    
    print()
    print("=" * 50)
    
    # Update config
    update_config_for_localhost()
    
    print()
    print("🎉 Localhost setup complete!")
    print()
    print("📝 To use these directories:")
    print("1. Copy the configuration from localhost_env_config.txt to your env.local")
    print("2. Set environment variables: source env.local")
    print("3. Start the server: python start_fastapi_server.py")
    print("4. Test uploads: python example_unified_upload.py")
