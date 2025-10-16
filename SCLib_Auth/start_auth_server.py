#!/usr/bin/env python3
"""
Start SCLib Authentication Server
Standalone authentication server for ScientistCloud.
"""

import os
import sys
import argparse
import uvicorn
from pathlib import Path

def load_env_file(env_path: str = None):
    """Load environment variables from specified env file."""
    if env_path and Path(env_path).exists():
        print(f"📁 Loading environment from: {env_path}")
        loaded_vars = []
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Remove quotes if present
                    value = value.strip('"\'')
                    os.environ[key] = value
                    loaded_vars.append(key)
        print(f"✅ Loaded {len(loaded_vars)} environment variables: {', '.join(loaded_vars[:5])}{'...' if len(loaded_vars) > 5 else ''}")
        return True
    else:
        print("ℹ️  Using system environment variables (no env file specified).")
        return False

def check_required_env_vars():
    """Check for required environment variables."""
    required_vars = [
        'MONGO_URL',
        'DB_NAME',
        'SECRET_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables in your environment or env.local file.")
        return False
    
    print("✅ All required environment variables are set.")
    return True

def main():
    """Main function to start the authentication server."""
    parser = argparse.ArgumentParser(description='Start SCLib Authentication Server')
    parser.add_argument('--port', type=int, default=8001, help='Port to run the server on (default: 8001)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--env-file', type=str, help='Path to environment file (env.local)')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')
    parser.add_argument('--workers', type=int, default=1, help='Number of worker processes')
    
    args = parser.parse_args()
    
    print("🚀 Starting SCLib Authentication Server...")
    print(f"   Host: {args.host}")
    print(f"   Port: {args.port}")
    print(f"   Workers: {args.workers}")
    print(f"   Reload: {args.reload}")
    
    # Set SCLIB_ENV_FILE environment variable if specified
    if args.env_file:
        os.environ['SCLIB_ENV_FILE'] = args.env_file
        print(f"🔧 Set SCLIB_ENV_FILE: {args.env_file}")
    
    # Load environment variables from env.local
    load_env_file(args.env_file)
    
    # Check required environment variables
    if not check_required_env_vars():
        sys.exit(1)
    
    # Import the app
    try:
        from SCLib_AuthAPI_Standalone import app
        print("✅ Authentication API loaded successfully")
    except ImportError as e:
        print(f"❌ Failed to import authentication API: {e}")
        sys.exit(1)
    
    # Start the server
    print(f"\n🌐 Starting server on http://{args.host}:{args.port}")
    print("📚 API Documentation: http://localhost:8001/docs")
    print("🔍 Health Check: http://localhost:8001/health")
    print("\nPress Ctrl+C to stop the server")
    
    try:
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            workers=args.workers if not args.reload else 1,
            reload=args.reload,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Server error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

