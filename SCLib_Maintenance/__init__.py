"""
ScientistCloud Maintenance Library (SCLib_Maintenance)

This library provides maintenance and monitoring tools for the ScientistCloud platform,
including job queue monitoring, cleanup utilities, and system health checks.

Main Components:
- monitor_jobs.py: Python script for job queue monitoring and management
- maintenance.sh: Shell script for comprehensive system maintenance
- setup_host_env.sh: Environment setup for running scripts on host system

Usage:
    # From Docker container
    docker exec scientistcloud_fastapi python /app/monitor_jobs.py stats
    
    # From host system (with environment setup)
    cd SCLib_Maintenance
    ./setup_host_env.sh stats
    
    # Direct maintenance script
    ./maintenance.sh stats
"""

__version__ = "1.0.0"
__author__ = "ScientistCloud Team"
