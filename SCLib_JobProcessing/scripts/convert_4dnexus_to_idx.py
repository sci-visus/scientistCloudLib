import os, sys, time, logging, shutil, copy
import argparse
from datetime import datetime
import numpy as np

#sys.path.append("C:/projects/OpenVisus/build/RelWithDebInfo")
#sys.path.append("C:/projects/openvisuspy/src")

import OpenVisus as ov
try:
    import openvisuspy
    print("openvisuspy imported successfully")
except ImportError as e:
    print(f"Warning: openvisuspy import failed: {e}")
    print("Continuing without openvisuspy...")
    openvisuspy = None

os.environ["VISUS_DISABLE_WRITE_LOCK"]="1"
logger = logging.getLogger("OpenVisus")

# uncomment for debugging
# ov.SetupLogger(logger, stream=True)

print("OpenVisus imported")

# from nexusformat.nexus import *
# from nexusformat.nexus.tree import NX_CONFIG
#
# # alllow data to be 16000MB (i.e. 16GB)
# NX_CONFIG['memory']=16000
#
# local_nexus_filename="/mnt/data/chess/assets/3scans_HKLI.nxs"
#
# from openvisuspy.utils import DownloadObject
# DownloadObject( "s3://utah/assets/3scans_HKLI.h5",local_nexus_filename)
#
# nx=nxload(local_nexus_filename)
# print(local_nexus_filename,"loaded")
#
# from pprint import pprint
# pprint(nx.tree)

# this is very broken  not finished writing

def create_volume_directory_name(vol_dataset, index):
    """
    Create a sensible directory name for a volume dataset.
    
    Args:
        vol_dataset: The volume dataset path
        index: The index of the volume dataset (unused)
        
    Returns:
        A sensible directory name
    """
    # Extract the dataset name from the path (e.g., /waxs_azimuthal/data/I -> waxs_azimuthal)
    path_parts = vol_dataset.strip('/').split('/')
    if len(path_parts) >= 2:
        dataset_name = path_parts[0]  # e.g., waxs_azimuthal
        
        # Use just the dataset name as the directory name
        return dataset_name
    else:
        # Fallback to a generic name
        return "volume_dataset"

def convert_nexus_to_idx(streamable_filename, local_idx_filename, local_nexus_filename):
    """
    Convert a Nexus file to IDX format (legacy function).
    This is a placeholder implementation.
    """
    print("⚠️ convert_nexus_to_idx is not fully implemented")
    print(f"Would convert: {local_nexus_filename} -> {local_idx_filename}")
    print(f"Streamable: {streamable_filename}")
    # TODO: Implement proper Nexus to IDX conversion
    pass

def Convert4DNexus_simple(Xs_dataset_name, Ys_dataset_name, presample_dataset_name, postsample_dataset_name, volume_dataset_name, save_dir):
    """
    Convert 4D Nexus data to IDX format.
    Args:
        Xs_dataset_name: Name of Xs dataset(s) in Nexus file (can be a list for multiple Xs)
        Ys_dataset_name: Name of Ys dataset(s) in Nexus file (can be a list for multiple Ys)
        presample_dataset_name: Name of presample dataset(s) (can be a list for multiple)
        postsample_dataset_name: Name of postsample dataset(s) (can be a list for multiple)
        volume_dataset_name: Name of volume dataset(s) in Nexus file (can be a list for multiple volumes)
        save_dir: Directory to save the IDX file
    """
    print("Convert4DNexus called with:")
    print("Xs dataset:", Xs_dataset_name)
    print("Ys dataset:", Ys_dataset_name)
    print("presample dataset:", presample_dataset_name)
    print("postsample dataset:", postsample_dataset_name)
    print("volume dataset:", volume_dataset_name)
    
    # Handle all parameters as either strings or lists
    def ensure_list(param, param_name):
        """Ensure parameter is a list"""
        if isinstance(param, list):
            print(f"Multiple {param_name} datasets detected: {len(param)} datasets")
            for i, dataset in enumerate(param):
                print(f"  {param_name} {i+1}: {dataset}")
            return param
        else:
            print(f"Single {param_name} dataset detected")
            return [param] if param else []
    
    Xs_datasets = ensure_list(Xs_dataset_name, "Xs")
    Ys_datasets = ensure_list(Ys_dataset_name, "Ys")
    presample_datasets = ensure_list(presample_dataset_name, "presample")
    postsample_datasets = ensure_list(postsample_dataset_name, "postsample")
    volume_datasets = ensure_list(volume_dataset_name, "volume")
    
    # Find the Nexus file in the directory
    nexus_file = None
    for file in os.listdir(save_dir):
        if file.endswith('.nxs'):
            nexus_file = os.path.join(save_dir, file)
            break
    
    if not nexus_file:
        raise FileNotFoundError("No .nxs file found in directory")
    
    print(f"Loading data from: {nexus_file}")
    
    # Process each volume dataset separately
    import h5py
    with h5py.File(nexus_file, 'r') as f:
        for i, vol_dataset in enumerate(volume_datasets):
            if not vol_dataset or vol_dataset == 'None':
                print(f"Skipping empty volume dataset {i+1}")
                continue
                
            print(f"\n🔄 Processing volume dataset {i+1}/{len(volume_datasets)}: {vol_dataset}")
            
            # Create a sensible directory name for this volume dataset
            vol_dir_name = create_volume_directory_name(vol_dataset, i)
            vol_save_dir = os.path.join(save_dir, vol_dir_name)
            
            # Create the directory if it doesn't exist
            os.makedirs(vol_save_dir, exist_ok=True)
            print(f"📁 Created directory: {vol_save_dir}")
            
            # Load volume data
            try:
                volume = f.get(vol_dataset)
                if volume is None:
                    print(f"❌ Volume dataset not found: {vol_dataset}")
                    continue
                    
                print(f"📊 Volume data shape: {volume.shape}")
                volume_data = np.array(volume)
                m, M = np.min(volume_data), np.max(volume_data)
                print(f"📊 Volume data range: {m} to {M}")
                
                # Create IDX file for this volume dataset
                idx_filename = os.path.join(vol_save_dir, 'visus.idx')
                
                # Remove existing IDX file if it exists
                if os.path.exists(idx_filename):
                    os.remove(idx_filename)
                    print(f"🗑️ Removed existing IDX file: {idx_filename}")
                
                # Create the IDX file
                field = ov.Field.fromString(f"DATA {str(volume_data.dtype)} default_layout(row_major) min({m}) max({M})")
                
                db = ov.CreateIdx(
                    url=idx_filename,
                    dims=list(reversed(volume_data.shape)),
                    fields=[field],
                    compression="raw")
                
                print(f"📝 Creating IDX file: {idx_filename}")
                print(f"📐 Dimensions: {list(reversed(volume_data.shape))}")
                
                # Write the data
                t1 = time.time()
                print("⏳ Writing data...")
                db.write(volume_data)
                print(f"✅ Data written in {time.time()-t1:.2f} seconds")
                
                # Compress the dataset
                t1 = time.time()
                print("🗜️ Compressing dataset...")
                db.compressDataset(["zip"])
                print(f"✅ Dataset compressed in {time.time()-t1:.2f} seconds")
                
                print(f"✅ Successfully created IDX for volume dataset {i+1}: {vol_dataset}")
                
            except Exception as e:
                print(f"❌ Error processing volume dataset {vol_dataset}: {str(e)}")
                continue

    print(f"\n✅ Conversion completed! Created {len(volume_datasets)} volume datasets")
    print("📁 Directory structure:")
    for i, vol_dataset in enumerate(volume_datasets):
        if vol_dataset and vol_dataset != 'None':
            vol_dir_name = create_volume_directory_name(vol_dataset, i)
            print(f"   {vol_dir_name}/visus.idx")

def main():
    parser = argparse.ArgumentParser(description='Convert HDF5-based files to IDX format.')
    parser.add_argument('src_file_directory', type=str, help='directory containing HDF5-based files')
    parser.add_argument('--params', type=str, help='conversion parameters: Xs=...,Ys=...,presample=...,postsample=...,volume=...')
    args = parser.parse_args()

    input_dir = args.src_file_directory
    if not os.path.isdir(input_dir):
        print(f"The specified path {input_dir} is not a directory.")
        return

    # NEW: Parse conversion parameters
    conversion_params = {}
    if args.params:
        print(f"Parsing conversion parameters: {args.params}")
        # Parse parameters manually to handle comma-separated values correctly
        # Split by parameter boundaries (key=) rather than just commas
        import re
        
        # Find all parameter assignments using a more robust regex
        # This matches: key=value where value can contain commas
        # and stops at the next key= or end of string
        param_pattern = r'(\w+)=([^,]+(?:,[^,]+)*?)(?=,\w+=|$)'
        
        matches = re.findall(param_pattern, args.params)
        print(f"Regex matches: {matches}")
        
        for key, value in matches:
            conversion_params[key.strip()] = value.strip()
        
        print(f"Parsed parameters: {conversion_params}")
        
        # Extract the dataset names
        Xs_dataset = conversion_params.get('Xs', '')
        Ys_dataset = conversion_params.get('Ys', '')
        presample_dataset = conversion_params.get('presample', '')
        postsample_dataset = conversion_params.get('postsample', '')
        volume_dataset = conversion_params.get('volume', '')
        
        # Handle comma-separated datasets for all parameters
        def parse_comma_separated(param_value, param_name):
            """Parse comma-separated parameter values into lists"""
            if param_value and ',' in param_value:
                parsed = [v.strip() for v in param_value.split(',') if v.strip()]
                print(f"Multiple {param_name} datasets detected: {parsed}")
                return parsed
            elif param_value:
                return [param_value]  # Convert single string to list
            else:
                return []
        
        Xs_dataset = parse_comma_separated(Xs_dataset, "Xs")
        Ys_dataset = parse_comma_separated(Ys_dataset, "Ys")
        presample_dataset = parse_comma_separated(presample_dataset, "presample")
        postsample_dataset = parse_comma_separated(postsample_dataset, "postsample")
        volume_dataset = parse_comma_separated(volume_dataset, "volume")
        
        # Now you can use these to load the specific datasets
        # instead of hardcoded values
    else:
        print("No conversion parameters provided, using default behavior")
        # Fall back to your existing logic

    # Supported HDF5-based file extensions
    hdf5_extensions = ('.nxs', '.h5', '.hdf5', '.hdf')
    nexus_files = [f for f in os.listdir(input_dir) if f.endswith(hdf5_extensions)]
    
    if not nexus_files:
        print("❌ No HDF5/Nexus files found in directory")
        return
    
    print(f"Found {len(nexus_files)} HDF5/Nexus files: {nexus_files}")
    
    # Use the new conversion method if parameters are provided
    if conversion_params:
        print("🔄 Using parameter-based conversion")
        Convert4DNexus_simple(Xs_dataset, Ys_dataset, presample_dataset, postsample_dataset, volume_dataset, input_dir)
    else:
        print("⚠️ No conversion parameters provided")
        print("Please provide parameters using --params option")
        print("Example: --params 'Xs=/path/to/Xs,Ys=/path/to/Ys,volume=/path/to/volume'")
        return

if __name__ == "__main__":
    main()
    print('------Convert NETCDF to IDX DONE-------')