#!/usr/bin/env python3
"""
Test script for run_conversion.py
Allows you to test conversions with a JSON configuration file.
"""

import os
import sys
import json
import argparse
import shutil
from pathlib import Path

# Add SCLib to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir.parent))

def create_test_config_template(output_path: str):
    """Create a template JSON config file."""
    template = {
        "input_file": "/path/to/your/test/file.tif",
        "input_dir": None,  # If set, will use this directory instead of copying input_file
        "output_dir": "/tmp/test_conversion_output",
        "sensor_type": "TIFF",  # Options: IDX, TIFF, TIFF_RGB, 4D_NEXUS, RGB DRONE, MAPIR DRONE
        "conversion_params": {},  # Optional: for 4D_NEXUS conversions
        "upload_to_aws": False,
        "cleanup_output": True  # Delete output directory after test
    }
    
    with open(output_path, 'w') as f:
        json.dump(template, f, indent=2)
    
    print(f"✅ Created template config file: {output_path}")
    print("\nEdit this file with your test parameters:")
    print(f"  - input_file: Path to your test file")
    print(f"  - output_dir: Where to write converted files")
    print(f"  - sensor_type: Type of sensor/data format")
    print(f"  - conversion_params: Optional parameters (for 4D_NEXUS)")

def check_dependencies(sensor_type: str):
    """Check if required dependencies are installed."""
    missing = []
    
    # Map sensor type variations (same as run_conversion.py)
    sensor_type_mapping = {
        'RGB': 'RGB DRONE',
        'MAPIR': 'MAPIR DRONE',
        'TIFF RGB': 'TIFF_RGB',
        'TIFFRGB': 'TIFF_RGB',
    }
    normalized_type = sensor_type.upper().strip()
    if normalized_type in sensor_type_mapping:
        normalized_type = sensor_type_mapping[normalized_type]
    
    # Core dependencies
    core_deps = {
        'pymongo': 'pymongo',
        'psutil': 'psutil'
    }
    
    # Sensor-specific dependencies
    sensor_deps = {
        'TIFF_RGB': ['matplotlib', 'rasterio', 'tifffile'],
        'TIFF': ['OpenVisus'],  # This is the native module, not pip installable
        '4D_NEXUS': ['h5py', 'netCDF4'],
        'NEXUS': ['h5py', 'netCDF4'],
        'RGB DRONE': ['slampy'],  # From VisoarAgExplorer
        'MAPIR DRONE': ['slampy'],  # From VisoarAgExplorer
    }
    
    # Check core dependencies
    for module, package in core_deps.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    # Check sensor-specific dependencies
    if normalized_type in sensor_deps:
        for module in sensor_deps[normalized_type]:
            try:
                if module == 'OpenVisus':
                    try:
                        __import__('OpenVisus')
                        # Also check for VisusKernelPy
                        try:
                            import importlib
                            importlib.import_module('OpenVisus.VisusKernelPy')
                        except ImportError:
                            missing.append('OpenVisus.VisusKernelPy (native extension)')
                    except ImportError:
                        missing.append('OpenVisus')
                elif module == 'slampy':
                    # Check if VisoarAgExplorer is in PYTHONPATH
                    import sys
                    found = False
                    for path in sys.path:
                        if 'VisoarAgExplorer' in path:
                            try:
                                __import__('slampy')
                                found = True
                                break
                            except ImportError:
                                pass
                    if not found:
                        missing.append('slampy (from VisoarAgExplorer)')
                else:
                    __import__(module)
            except ImportError:
                missing.append(module)
    
    if missing:
        print("\n⚠️  Missing dependencies detected:")
        for dep in missing:
            print(f"   - {dep}")
        print("\n💡 To install dependencies:")
        print(f"   pip3 install -r {script_dir}/requirements_conversion.txt")
        print("\n   Or install specific packages:")
        for dep in missing:
            if dep not in ['OpenVisus.VisusKernelPy (native extension)', 'slampy (from VisoarAgExplorer)']:
                print(f"   pip3 install {dep}")
        
        if 'OpenVisus.VisusKernelPy (native extension)' in missing:
            print("\n   Note: OpenVisus.VisusKernelPy requires building from source.")
            print("   Consider using Docker for testing, or install OpenVisus==2.2.135")
        
        if 'slampy (from VisoarAgExplorer)' in missing:
            print("\n   Note: slampy is part of VisoarAgExplorer.")
            print("   Clone VisoarAgExplorer and add to PYTHONPATH:")
            print("   export PYTHONPATH=$PYTHONPATH:/path/to/VisoarAgExplorer")
        
        response = input("\n❓ Continue anyway? (y/N): ").strip().lower()
        if response != 'y':
            print("Exiting. Install dependencies and try again.")
            sys.exit(1)
        print("⚠️  Continuing with missing dependencies - conversion may fail.\n")
    
    return len(missing) == 0

def run_conversion_test(config_path: str):
    """Run conversion test with JSON config."""
    # Load config
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Get paths
    input_file = config.get('input_file')
    input_dir = config.get('input_dir')
    output_dir = config.get('output_dir')
    sensor_type = config.get('sensor_type')
    conversion_params = config.get('conversion_params', {})
    upload_to_aws = config.get('upload_to_aws', False)
    cleanup_output = config.get('cleanup_output', False)
    
    # Validate required fields
    if not input_file and not input_dir:
        print("ERROR: Either 'input_file' or 'input_dir' must be specified")
        sys.exit(1)
    
    if not output_dir:
        print("ERROR: 'output_dir' must be specified")
        sys.exit(1)
    
    if not sensor_type:
        print("ERROR: 'sensor_type' must be specified")
        sys.exit(1)
    
    # Prepare input directory
    if input_dir:
        # Use provided directory directly
        test_input_dir = Path(input_dir).resolve()
        if not test_input_dir.exists():
            print(f"ERROR: Input directory does not exist: {test_input_dir}")
            sys.exit(1)
    else:
        # Copy input file to a temporary directory
        input_file_path = Path(input_file).resolve()
        if not input_file_path.exists():
            print(f"ERROR: Input file does not exist: {input_file_path}")
            sys.exit(1)
        
        # Create a temporary input directory
        test_input_dir = Path(output_dir).parent / f"test_input_{input_file_path.stem}"
        test_input_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy file to test input directory
        dest_file = test_input_dir / input_file_path.name
        print(f"📋 Copying {input_file_path.name} to test input directory...")
        shutil.copy2(input_file_path, dest_file)
        print(f"✅ Input file copied to: {test_input_dir}")
    
    # Prepare output directory
    test_output_dir = Path(output_dir).resolve()
    if test_output_dir.exists() and cleanup_output:
        print(f"🧹 Cleaning up existing output directory: {test_output_dir}")
        shutil.rmtree(test_output_dir)
    test_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check dependencies before running
    print("🔍 Checking dependencies...")
    check_dependencies(sensor_type)
    
    # Build command
    conversion_script = script_dir / "scripts" / "run_conversion.py"
    if not conversion_script.exists():
        print(f"ERROR: Conversion script not found: {conversion_script}")
        sys.exit(1)
    
    cmd = [
        sys.executable,
        str(conversion_script),
        str(test_input_dir),
        str(test_output_dir),
        sensor_type
    ]
    
    # Add conversion params if provided
    if conversion_params:
        import json as json_module
        params_json = json_module.dumps(conversion_params)
        cmd.extend(['--params', params_json])
    
    # Add AWS upload flag if requested
    if upload_to_aws:
        cmd.append('--upload-aws')
    
    # Print configuration
    print("\n" + "=" * 60)
    print("Conversion Test Configuration")
    print("=" * 60)
    print(f"Input directory: {test_input_dir}")
    print(f"Output directory: {test_output_dir}")
    print(f"Sensor type: {sensor_type}")
    if conversion_params:
        print(f"Conversion params: {conversion_params}")
    print(f"Upload to AWS: {upload_to_aws}")
    print("=" * 60)
    print(f"\n🚀 Running conversion...\n")
    
    # Run conversion
    import subprocess
    try:
        result = subprocess.run(cmd, check=True, cwd=str(script_dir))
        print("\n✅ Conversion completed successfully!")
        print(f"📁 Output directory: {test_output_dir}")
        
        # List output files
        output_files = list(test_output_dir.rglob('*'))
        if output_files:
            print(f"\n📋 Output files ({len(output_files)}):")
            for f in sorted(output_files)[:10]:  # Show first 10
                if f.is_file():
                    size = f.stat().st_size
                    print(f"  - {f.relative_to(test_output_dir)} ({size:,} bytes)")
            if len(output_files) > 10:
                print(f"  ... and {len(output_files) - 10} more files")
        
        # Cleanup if requested
        if cleanup_output and not input_dir:
            print(f"\n🧹 Cleaning up test input directory: {test_input_dir}")
            shutil.rmtree(test_input_dir)
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Conversion failed with exit code {e.returncode}")
        return e.returncode
    except KeyboardInterrupt:
        print("\n⚠️  Conversion interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test run_conversion.py with a JSON configuration file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a template config file
  python3 test_run_conversion.py --create-template test_config.json
  
  # Run conversion test
  python3 test_run_conversion.py test_config.json
        """
    )
    parser.add_argument(
        'config',
        nargs='?',
        help='Path to JSON configuration file'
    )
    parser.add_argument(
        '--create-template',
        metavar='PATH',
        help='Create a template JSON config file at the specified path'
    )
    
    args = parser.parse_args()
    
    if args.create_template:
        create_test_config_template(args.create_template)
        return 0
    
    if not args.config:
        parser.print_help()
        print("\nERROR: Either provide a config file or use --create-template")
        sys.exit(1)
    
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)
    
    return run_conversion_test(str(config_path))


if __name__ == "__main__":
    sys.exit(main())

