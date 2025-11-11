import os,glob
import sys
import numpy as np
import re
import argparse
import json
from OpenVisus import *
import matplotlib.pyplot as plt
import rasterio
import tifffile
def tiff_tags_to_dict(tags):
    tag_dict = {}
    for tag in tags:
        if isinstance(tag.value, bytes):
            continue
        elif isinstance(tag.value, tifffile.TiffTag):
            tag_dict[tag.name] = str(tag.value)
        else:
            tag_dict[tag.name] = tag.value
    return tag_dict

def process_tif_as_time(tif_filename,each_time, output_idx_dir,num_timesteps=0):
    print('---> process_tif_as_time')
    image_stack_data=[]
    with tifffile.TiffFile(tif_filename) as tif:
        depth=len(tif.pages)
        width=tif.pages[0].tags['ImageWidth'].value
        height=tif.pages[0].tags['ImageLength'].value
        for stack in tif.pages:
            image_data=stack.asarray()
            image_stack_data.append(image_data)

    image_stack_data=np.array(image_stack_data)
    field1 = tif_filename.split('/')[-1]
    field = field1.split('_')[0]
    metadata=rasterio.open(tif_filename)
    datype = metadata.meta['dtype']
    idx_filename = f'{field}.idx'
    fields = [Field(f'{field}', f'{datype}')]

    print(f"---> idx: visus.idx")
    os.chdir(output_idx_dir)

    if depth>=2:
        if not os.path.exists('visus.idx'):
            print('creating idx file')
            db = CreateIdx(url='visus.idx', dims=[width, height,depth], fields=fields, time=[0, num_timesteps, "time%0000d/"])
        else:
            db=LoadDataset('visus.idx')
    if depth<2:
        if not os.path.exists('visus.idx'):
            print('creating idx file')
            db = CreateIdx(url='visus.idx', dims=[width, height], fields=fields, time=[0, num_timesteps, "time%0000d/"])
        else:
            db=LoadDataset('visus.idx')
    db.write(image_stack_data, time=each_time)
    print(f"---> Dataset created with dimensions: {width}x{height}x{depth}")

def process_tif_as_stack(tif_filename,depth,all_data, output_idx_dir ,num_steps=0):
    print('---> process_tif_as_stack')
    metadata = rasterio.open(tif_filename)
    data_to_write = metadata.read()
    width = metadata.meta['width']
    height = metadata.meta['height']
    field1 = tif_filename.split('/')[-1]
    field = field1.split('_')[0]
    datype = metadata.meta['dtype']
    idx_filename = f'{field}.idx'
    fields = [Field(f'{field}', f'{datype}')]

    print(f"---> idx: visus.idx")
    db=None
    os.chdir(output_idx_dir)

    if depth>=2:
        if not os.path.exists('visus.idx'):
            print('creating idx file')
            db = CreateIdx(url='visus.idx', dims=[width, height,depth], fields=fields, time=[0, num_steps, "time%0000d/"])
        else:
            db=LoadDataset('visus.idx')
    if depth<2:
        if not os.path.exists('visus.idx'):
            print('creating idx file')
            db = CreateIdx(url='visus.idx', dims=[width, height], fields=fields, time=[0, num_steps, "time%0000d/"])
        else:
            db=LoadDataset('visus.idx')
    timesteps=[int(it) for it in db.getTimesteps()]
    for t in timesteps:
        db.write(all_data, time=t)
    print(f"---> Dataset created with dimensions: {width}x{height}x{depth}")

def main():
    parser = argparse.ArgumentParser(description='Process TIFF files.')
    parser.add_argument('tif_file_directory', metavar='N', type=str, nargs='+', 
                        help='directory containing tiff files')
    # parser.add_argument('--stack_each_file', default=False, action='store_true', 
    #                     help='an optional argument to stack each file')
    
    args = parser.parse_args()
    output_idx_dir=args.tif_file_directory[0]
    print('---> output_idx_dir')
    print(output_idx_dir)
    # stack_each_file=args.stack_each_file
    tif_files = glob.glob(os.path.join(args.tif_file_directory[0], '*.tif')) + glob.glob(os.path.join(args.tif_file_directory[0], '*.tiff'))
    tif_files += glob.glob(os.path.join(args.tif_file_directory[0], '*.TIF')) + glob.glob(os.path.join(args.tif_file_directory[0], '*.TIFF'))

    sorted_tif_filenames = sorted(tif_files)
    with tifffile.TiffFile(sorted_tif_filenames[0]) as tif:
        len_stacks=len(tif.pages)
        if len_stacks<=1:
            stack_each_file=True
        else:
            stack_each_file=False

    num_files = len(sorted_tif_filenames)

    if stack_each_file==False:
        print('Running each file as a timestep')
        print(sorted_tif_filenames)
        for i in range(len(sorted_tif_filenames)):
            print(sorted_tif_filenames[i])
            process_tif_as_time(sorted_tif_filenames[i],i,output_idx_dir, num_files)
    else:
        print('Running each file as a stack')
        depth = len(sorted_tif_filenames)

        all_data=[]
        for i in range(len(sorted_tif_filenames)):
            metadata = rasterio.open(sorted_tif_filenames[i])
            data_to_write = metadata.read()
            if len(data_to_write.shape)>2:           
                all_data.append(data_to_write[0,:,:])
            else:
                all_data.append(data_to_write)
        all_data=np.array(all_data)
        if all_data.shape[0]==1:
            all_data=all_data[0,:,:]

        process_tif_as_stack(sorted_tif_filenames[0],depth,all_data,output_idx_dir)

    with tifffile.TiffFile(sorted_tif_filenames[0]) as tif:
        tags = tif.pages[0].tags.values()
        metadata_dict = tiff_tags_to_dict(tags)

    with open('metadata.json', 'w') as json_file:
        os.chdir(output_idx_dir)
        json.dump(metadata_dict, json_file, indent=4)
    print('Metadata saved locally as metadata.json')
        

if __name__ == "__main__":
    main()
    print('----> End of convert_tif_to_idx')

