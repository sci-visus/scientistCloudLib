##Convert HDF5 from  https://github.com/sci-visus/OpenVisus/: Samples/jupyter/netcdf-tutorial1.ipynb#L9
import os ,sys, time, logging,shutil
import  glob
import re
import argparse
import json
from datetime import datetime
import numpy as np


def _select_netcdf_variable(ds, preferred_name: str):
    """
    Pick a 2D or 3D variable to convert. Using ds.variables.keys()[0] breaks files like
    McIDAS NetCDF where the first keys are scalars (version, sensorID, ...).
    """
    preferred_name = (preferred_name or "").strip()
    if preferred_name:
        if preferred_name not in ds.variables:
            raise ValueError(f"Requested variable {preferred_name!r} not found in NetCDF")
        var = ds.variables[preferred_name]
        rank = len(var.shape)
        if rank not in (2, 3):
            raise ValueError(
                f"Variable {preferred_name!r} has rank {rank}; only 2D or 3D arrays are supported"
            )
        return var

    keys = list(ds.variables.keys())
    # Prefer common payload names (satellite / generic grids)
    for name in ("data", "Data", "DATA", "band_data", "image"):
        if name in ds.variables:
            var = ds.variables[name]
            if len(var.shape) in (2, 3):
                print(f"Selected variable {name!r} (preferred name match), shape={var.shape}")
                return var

    # First 3D then 2D by declaration order (stable; mirrors CDL when library preserves order)
    for name in keys:
        var = ds.variables[name]
        if len(var.shape) == 3:
            print(f"Selected variable {name!r} (first 3D), shape={var.shape}")
            return var
    for name in keys:
        var = ds.variables[name]
        if len(var.shape) == 2:
            print(f"Selected variable {name!r} (first 2D), shape={var.shape}")
            return var

    raise ValueError(
        "No 2D or 3D variable found to convert. "
        f"Variables: {[(k, tuple(ds.variables[k].shape)) for k in keys]}"
    )


def convert_netcdf_to_idx(src_filename,variable, idx_filename ):
    import netCDF4 as nc
    ds = nc.Dataset(src_filename)
    print(ds)  #should put all of this into a metadata file

    #Print the NetCDF dimensions
    from pprint import pprint
    pprint(ds.dimensions)
    #data = a.entry.data.counts.nxdata

    #Print the NetCDF variables
    pprint(ds.variables)

    var = _select_netcdf_variable(ds, variable)
    print(var)

    #Read the NetCDF binary data in memory
    import time
    t1 = time.time()

    if len(var.shape) == 2:
        data = var[:, :]
        num_timesteps = 1
        H, W = data.shape[0], data.shape[1] # LTS: 6.16.2025: Shouldn't this be W, H?
        m, M = np.min(data), np.max(data)
        dims = [W, H]
    elif len(var.shape) == 3: # LTS: 6.16.2025: How can we determine if the dataset is 3D?
        data = var[:, :, :]
        # Interpret first axis as time / bands / channels (e.g. bands x lines x elems).
        num_timesteps, H, W = data.shape[0], data.shape[1], data.shape[2]
        m, M = np.min(data), np.max(data)
        dims = [W, H]
    else:
        raise ValueError(f"Dataset dimensionality not supported: rank={len(var.shape)} shape={var.shape}")

    read_sec = time.time() - t1
    print(f"NetCDF file loaded in {read_sec} seconds dtype={data.dtype} num_timesteps={num_timesteps} W={W} H={H} m={m} M={M}")

    ### Create OpenVisus File
    import OpenVisus as ov
    arco="2mb"

    db=ov.CreateIdx(
        url=idx_filename,
        dims=dims,
        fields=[ov.Field("data",str(data.dtype),"row_major")],
        compression="zip",
        time=[0,num_timesteps,"time_%04d/"],
        arco=arco)

    print(db.getDatasetBody().toString())
    print("Dataset created")


    ### Write Data to OpenVisus
    t1 = time.time()
    for timestep in range(num_timesteps):
        db.write(data[timestep,:,:],time=timestep)
    write_sec=time.time() - t1
    print(f"Wrote new timestep={timestep} done in {write_sec} seconds")

    ### Compress using zip
    t1 = time.time()
    algorithm="zip"
    db.compressDataset([algorithm])
    compress_sec=time.time()-t1
    print(f"Compressed timestep={timestep} done in {compress_sec} seconds")

def main():
    parser = argparse.ArgumentParser(description='Process NetCDF files.')
    parser.add_argument('src_file_directory',    type=str,
                        help='directory containing src files')
    parser.add_argument(
        '--variable',
        type=str,
        default='',
        help='NetCDF variable name to convert (default: auto — prefers "data", then first 3D/2D array)',
    )
    args = parser.parse_args()
    input  = args.src_file_directory
    if os.path.isdir(input):
        dir = input
    else:
        dir = os.path.dirname(input)

    print(dir)
    variable = args.variable or ''

    nc_paths = sorted(
        p for p in glob.glob(os.path.join(dir, '*.nc'))
        if os.path.isfile(p)
    )
    if not nc_paths:
        print(f"No .nc files in {dir}", file=sys.stderr)
        sys.exit(2)
    if len(nc_paths) > 1:
        print(
            "Warning: multiple NetCDF files in directory; converting the first sorted path:",
            nc_paths[0],
            file=sys.stderr,
        )
    src_filename = nc_paths[0]

    print('------src_filename-------')
    print(src_filename)
    try:
        convert_netcdf_to_idx(src_filename, variable, idx_filename=os.path.join(dir,'visus.idx'))
    except Exception as ex:
        print(f"convert_netcdf_to_idx failed: {ex}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
    print('------Convert NETCDF to IDX DONE-------')