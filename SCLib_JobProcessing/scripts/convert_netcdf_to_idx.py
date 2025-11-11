##Convert HDF5 from  https://github.com/sci-visus/OpenVisus/: Samples/jupyter/netcdf-tutorial1.ipynb#L9
import os ,sys, time, logging,shutil
import  glob
import re
import argparse
import json
from datetime import datetime
import numpy as np

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

    if (len(variable)>0):
        #Crap, now we need to pick a variable to convert... sigh..
        var=ds.variables[variable]  #Replace this with one of them...
        print(var)
    else:
        #grab first one
        allkeys = list(ds.variables.keys())
        var = ds.variables[allkeys[0]]

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
        num_timesteps, H, W = data.shape[0], data.shape[1], data.shape[2]
        m, M = np.min(data), np.max(data)
        dims = [W, H]
    else:
        print("Dataset dimensionality is not supported.")
        return

    read_sec = time.time() - t1
    print(f"NetCDF file loaded in {read_sec} seconds dtype={data.dtype} num_timesteps={num_timesteps} W={W} H={H} m={m} M={M}")

    ### Create OpenVisus File
    import OpenVisus as ov
    arco="modvisus"

    db=ov.CreateIdx(
        url=idx_filename,
        dims=dims,
        fields=[ov.Field("data",str(data.dtype),"row_major")],
        compression="raw",
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
    # parser.add_argument('variable',   type=str,
    #                     help='variable chosen to display from netCDF file (see getVariable_netcdf.py)')
    args = parser.parse_args()
    input  = args.src_file_directory
    if os.path.isdir(input):
        dir = input
    else:
        dir = os.path.dirname(input)

    print(dir)
    variable = ''
    # if (args.variable):
    #     variable  = args.variable[0]
    # else:
    #     variable = ''
    # print('------variable-------')
    # print(variable)
    # print(variable[0])

    src_filename=''
    for file in os.listdir(dir):
        if file.endswith(".nc"):
            print(os.path.join(dir, file))
            src_filename =os.path.join(dir, file)

    print('------src_filename-------')
    print(src_filename)
    convert_netcdf_to_idx(src_filename, variable, idx_filename=os.path.join(dir,'visus.idx'))
    #convert_netcdf_to_idx(src_filename, variable, idx_filename= 'visus.idx')

if __name__ == "__main__":
    main()
    print('------Convert NETCDF to IDX DONE-------')