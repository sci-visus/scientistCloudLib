#!/usr/bin/env python3
"""
ScientistCloud FastAPI Server Startup Script
Configures and starts the FastAPI server with optimal settings for large file uploads.
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def setup_logging(level: str = "INFO"):
    """Setup logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('scientistcloud_api.log')
        ]
    )

def check_environment():
    """Check if required environment variables are set."""
    required_vars = [
        'MONGO_URL',
        'DB_NAME',
        'AUTH0_DOMAIN',
        'AUTHO_CLIENT_ID',
        'AUTHO_CLIENT_SECRET'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables before starting the server.")
        return False
    
    print("✅ Environment variables check passed")
    return True

def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import fastapi
        import uvicorn
        import pydantic
        import pymongo
        print("✅ Core dependencies available")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please install requirements: pip install -r requirements_fastapi.txt")
        return False

def create_temp_directories():
    """Create necessary temporary directories."""
    # Use environment variables for paths, fallback to /tmp for localhost
    visus_datasets = os.getenv('VISUS_DATASETS', '/tmp')
    temp_dirs = [
        "/tmp/scientistcloud_uploads",
        f"{visus_datasets}/tmp"
    ]
    
    for temp_dir in temp_dirs:
        try:
            os.makedirs(temp_dir, exist_ok=True)
            print(f"✅ Created directory: {temp_dir}")
        except PermissionError:
            print(f"⚠️  Cannot create directory {temp_dir} - check permissions")

def main():
    """Main startup function."""
    parser = argparse.ArgumentParser(description="Start ScientistCloud FastAPI Server")
    parser.add_argument("--api-type", choices=["unified", "standard", "large-files"], default="unified",
                       help="Type of API to start (default: unified)")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to (default: 5000)")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers (default: 1)")
    parser.add_argument("--log-level", default="info", help="Log level (default: info)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--skip-checks", action="store_true", help="Skip environment and dependency checks")
    
    args = parser.parse_args()
    
    print("🚀 Starting ScientistCloud FastAPI Server")
    print(f"   API Type: {args.api_type}")
    print(f"   Host: {args.host}")
    print(f"   Port: {args.port}")
    print(f"   Workers: {args.workers}")
    print()
    
    # Setup logging
    setup_logging(args.log_level)
    
    # Run checks unless skipped
    if not args.skip_checks:
        print("🔍 Running startup checks...")
        
        if not check_dependencies():
            sys.exit(1)
        
        if not check_environment():
            sys.exit(1)
        
        create_temp_directories()
        print()
    
    # Import and start the appropriate API
    try:
        if args.api_type == "unified":
            from SCLib_UploadAPI_Unified import app
            print("🎯 Starting Unified API (automatic file size handling)")
        elif args.api_type == "large-files":
            from SCLib_UploadAPI_LargeFiles import app
            print("📁 Starting Large Files API (TB-scale support)")
        else:
            from SCLib_UploadAPI_FastAPI import app
            print("📄 Starting Standard API")
        
        # Configure uvicorn settings
        uvicorn_config = {
            "app": app,
            "host": args.host,
            "port": args.port,
            "log_level": args.log_level,
            "access_log": True,
            "workers": args.workers if not args.reload else 1,
            "reload": args.reload,
            "timeout_keep_alive": 300,  # 5 minutes for large uploads
            "limit_max_requests": 100,
            "limit_concurrency": 1000
        }
        
        # Remove reload-specific settings if not in reload mode
        if not args.reload:
            uvicorn_config.pop("reload")
        
        print(f"🌐 Server will be available at: http://{args.host}:{args.port}")
        print(f"📚 API Documentation: http://{args.host}:{args.port}/docs")
        print(f"📖 ReDoc Documentation: http://{args.host}:{args.port}/redoc")
        print()
        print("Press Ctrl+C to stop the server")
        print()
        
        # Start the server
        import uvicorn
        uvicorn.run(**uvicorn_config)
        
    except ImportError as e:
        print(f"❌ Error importing API module: {e}")
        print("Make sure you're running this script from the correct directory")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
