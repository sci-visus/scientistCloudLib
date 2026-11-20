import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import numpy as np
import re
import argparse
import matplotlib.pyplot as plt
import rasterio
import tifffile
import math
import io
from PIL import Image
from PIL import Image, ImageOps
from pathlib import Path
Image.MAX_IMAGE_PIXELS = None  # allow very large images
import glob,time,shutil,sys, glob,json
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass
import large_image
import OpenVisus as ov



import psutil
import traceback
import subprocess
import urllib.parse
import uuid
os.umask(0)
from datetime import datetime
from pymongo import MongoClient


def _merge_jpeg_tables(tables, payload):
    """Build one JPEG stream from a TIFF JPEGTables blob and a strip."""
    if not payload:
        raise OSError("empty JPEG strip")
    if not tables:
        if not payload.endswith(b"\xff\xd9"):
            payload = payload + b"\xff\xd9"
        return payload
    if not isinstance(tables, (bytes, bytearray)):
        tables = bytes(tables)
    if tables.endswith(b"\xff\xd9"):
        tables = tables[:-2]
    if not tables.startswith(b"\xff\xd8"):
        tables = b"\xff\xd8" + tables
    if payload.startswith(b"\xff\xd8"):
        payload = payload[2:]
    if not payload.endswith(b"\xff\xd9"):
        payload = payload + b"\xff\xd9"
    return tables + payload


def _decode_jpeg_bytes(blob):
    with Image.open(io.BytesIO(blob)) as img:
        img.load()
        return np.array(img)


def _iter_jpeg_tiff(path):
    """Yield JPEG-in-TIFF strips that libtiff refuses to decode.

    libtiff aborts when the TIFF sampling tag (often 1,1) disagrees with the
    JPEG stream (often 2,2). Pillow's JPEG decoder reads the stream itself.
    """
    with tifffile.TiffFile(path) as tif:
        page = tif.pages[0]
        if page.compression not in (6, 7, 33007):
            raise OSError(
                f"TIFF compression {page.compression} is not JPEG"
            )
        if page.planarconfig not in (1, None):
            raise OSError("separate-plane JPEG TIFF is not supported")
        tables = page.jpegtables
        width = int(page.imagewidth)
        height = int(page.imagelength)
        if page.is_tiled:
            tw = int(page.tilewidth)
            th = int(page.tilelength)
            across = max(1, math.ceil(width / tw))
        else:
            tw = width
            th = int(page.rowsperstrip) if page.rowsperstrip else height
            across = 1
        fh = tif.filehandle
        offsets = page.dataoffsets
        counts = page.databytecounts
        total = len(offsets)
        print(
            f"Decoding {total} JPEG strips from {path} ({width}x{height})",
            flush=True,
        )
        produced = 0
        for index, (offset, count) in enumerate(zip(offsets, counts)):
            count = int(count)
            if count <= 0:
                continue
            fh.seek(int(offset))
            raw = fh.read(count)
            try:
                tile = _decode_jpeg_bytes(_merge_jpeg_tables(tables, raw))
            except OSError:
                bare = raw if raw.endswith(b"\xff\xd9") else raw + b"\xff\xd9"
                tile = _decode_jpeg_bytes(bare)
            if page.is_tiled:
                x = (index % across) * tw
                y = (index // across) * th
            else:
                x = 0
                y = index * th
            if x >= width or y >= height:
                continue
            tile_h = min(int(tile.shape[0]), th, height - y)
            tile_w = min(int(tile.shape[1]), tw, width - x)
            if tile_h <= 0 or tile_w <= 0:
                continue
            produced += 1
            if produced == 1 or produced % 64 == 0:
                print(f"  decoded strip {index + 1}/{total}", flush=True)
            yield np.ascontiguousarray(tile[:tile_h, :tile_w]), int(x), int(y)
        if produced == 0:
            raise OSError("JPEG TIFF contained no decodable strips")


def iter_image_tiles(path):
    """Yield (array, x, y) for one image file.

    A normal TIFF or JPEG is one tile at the origin. JPEG-in-TIFF files that
    libtiff rejects are decoded strip by strip.
    """
    try:
        with Image.open(path) as img:
            img.load()
            yield np.array(img), 0, 0
            return
    except OSError as exc:
        print(
            f"PIL could not decode {path} ({exc}); reading JPEG segments",
            flush=True,
        )
    yield from _iter_jpeg_tiff(path)


def load_image_array(path):
    """Load one image file into a single array."""
    pieces = []
    height = 0
    width = 0
    for tile, x, y in iter_image_tiles(path):
        pieces.append((tile, x, y))
        height = max(height, y + tile.shape[0])
        width = max(width, x + tile.shape[1])
    if not pieces:
        raise OSError(f"no image data in {path}")
    if len(pieces) == 1 and pieces[0][1] == 0 and pieces[0][2] == 0:
        return pieces[0][0]
    sample = pieces[0][0]
    if sample.ndim == 2:
        canvas = np.zeros((height, width), dtype=sample.dtype)
    else:
        canvas = np.zeros((height, width, sample.shape[2]), dtype=sample.dtype)
    for tile, x, y in pieces:
        canvas[y:y + tile.shape[0], x:x + tile.shape[1]] = tile
    return canvas


def write_flipped_tile(db, tile, x, y, image_height):
    """Write one tile in the same vertical flip the full-image path uses."""
    tile = np.ascontiguousarray(np.flipud(tile))
    h = int(tile.shape[0])
    w = int(tile.shape[1])
    y1 = int(image_height) - (int(y) + h)
    y2 = int(image_height) - int(y)
    db.write(tile, logic_box=[[int(x), y1], [int(x) + w, y2]])



# Set up argument parser
parser = argparse.ArgumentParser(description='Process TIFF files.')
parser.add_argument('tif_file_directory', metavar='N', type=str, nargs='+', 
                    help='directory containing tiff files')

args = parser.parse_args()
output_idx_dir=args.tif_file_directory[0]

print('---> output_idx_dir', output_idx_dir)  # /mnt/visus_datasets/upload/50a06184-81fc-456e-b7da-a02d26e9f4f8/

# Find TIFF files (case-insensitive by checking multiple patterns)
tif_files = glob.glob(os.path.join(output_idx_dir, '*.tif'))
tif_files += glob.glob(os.path.join(output_idx_dir, '*.tiff'))
tif_files += glob.glob(os.path.join(output_idx_dir, '*.TIF'))
tif_files += glob.glob(os.path.join(output_idx_dir, '*.TIFF'))

# ALSO find JPG/JPEG
jpg_files = glob.glob(os.path.join(output_idx_dir, '*.jpg'))
jpg_files += glob.glob(os.path.join(output_idx_dir, '*.jpeg'))
jpg_files += glob.glob(os.path.join(output_idx_dir, '*.JPG'))
jpg_files += glob.glob(os.path.join(output_idx_dir, '*.JPEG'))

# Sort filenames
sorted_tif_filenames =  sorted(set(tif_files + jpg_files))

# Count files
file_count = len(sorted_tif_filenames)
print(f"Found {file_count} files in {output_idx_dir}")

# Check first file resolution (if any files exist)
if file_count > 0:
    first_file = sorted_tif_filenames[0]
    with Image.open(first_file) as img:
        tile_width, tile_height = img.size

    print(f"Resolution X x Y: {tile_width} x {tile_height} pixels")
else:
    print("No TIFF files found.")


print(f"---> idx: visus.idx")
os.chdir(output_idx_dir)
dst = "visus.idx"

if len(sorted_tif_filenames) == 0:
    print("No TIFF files found in the specified directory.")
    sys.exit(1)
elif len(sorted_tif_filenames) == 1:
    # Single Image Case
    src = sorted_tif_filenames[0]
    ext = Path(src).suffix.lower()

    if ext in ('.tif', '.tiff'):
        ts = large_image.getTileSource(src)
        meta=ts.getMetadata() 
        sizeX=meta["sizeX"] 
        sizeY=meta["sizeY"]
        bandCount=meta["bandCount"]
        print(f"sizeX={sizeX} sizeY={sizeY} bandCount={bandCount}")

    elif ext in ('.jpg', '.jpeg'):
        # JPG/JPEG: use PIL only; force RGB uint8
        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img)   # honor EXIF rotation
            img = img.convert('RGB')             # ensure 3 channels, uint8
            sizeX, sizeY = img.size
            bandCount = 3
            print(f"sizeX={sizeX} sizeY={sizeY} bandCount={bandCount}")

    else:
        print(f"Unsupported extension for single-image case: {ext}")
        sys.exit(1)


    # Create OpenVisus idx file
    db=None
    os.environ["VISUS_DISABLE_WRITE_LOCK"]="1" # writings to OpenVisus will happen serially
    if not os.path.exists('visus.idx'):
        print('creating idx file')
        field=ov.Field("data" ,f"uint8[{bandCount}]",'row_major')
        bitmask=ov.DatasetBitmask.guess(ord('V'),ov.PointNi.fromString(f"{sizeX} {sizeY}"), True).toString()
        assert(bitmask.endswith("01") or bitmask.endswith("10"))
        db=ov.CreateIdx(url=dst, dim=2, dims=[sizeX,sizeY], fields=[field], arco="2mb", compression="zip", bitmask=bitmask)  # create ARCO + zip directly
        print(f"OpenVisus {dst} created")
        #db = CreateIdx(url='visus.idx', dims=[width, height], fields=fields, time=[0, num_steps, "time%0000d/"])
    else:
        db=ov.LoadDataset('visus.idx')

    # Conversion in Openvisus

    T1 = time.time()
    x=0
    y=0

    if os.path.exists(output_idx_dir):
        # Write strip by strip. A rejected JPEG-in-TIFF never has to sit in one array.
        for n, (img_array, tile_x, tile_y) in enumerate(iter_image_tiles(src)):
            if n == 0 or (n + 1) % 64 == 0:
                print(f"writing tile {n + 1} x={tile_x} y={tile_y} shape={img_array.shape}", flush=True)
            write_flipped_tile(db, img_array, tile_x, tile_y, sizeY)

    print("Compressing OpenVisus dataset (CAN BE SLOW!)...")
    T1 = time.time()
    db.compressDataset(["zip"])
    sec_compress=time.time()-T1
    print(f"Compression done in {sec_compress} seconds")



elif len(sorted_tif_filenames) > 1:

    # Stitched WSI with Multiple tiles Case
    # Connect to MongoDB to get metadata
    mongo_url = os.getenv('MONGO_URL')
    db_name=os.getenv('DB_NAME')
    client = MongoClient(mongo_url)
    db = client[db_name]
    collection = db['visstoredatas']

    # Get the most recently inserted document's name
    last_doc = collection.find_one({}, {"name": 1, "_id": 0}, sort=[("_id", -1)])

    client.close()

    if last_doc:
        name_str = last_doc["name"]  # "caseNum_panelNum_xAxis_yAxis"
        parts = name_str.split("_")

        # Extract separately
        panel_name = "_".join(parts[:2])  # "caseNum_panelNum"
        sizeX = int(parts[2])             # "x_axis"
        sizeY = int(parts[3])             # "y_axis"

    
    
    window = tile_width
    scale_factor =int(tile_width/2048)

    bandCount=3
    
    # Metadata of SR of Panel
    sizeX= int(sizeX * scale_factor)
    sizeY = int(sizeY * scale_factor)
    print(f"sizeX={sizeX} sizeY={sizeY} bandCount={bandCount}")


    total_cols = math.ceil(sizeX/window)
    total_rows = math.ceil(sizeY/window)
    print(f"total_cols={total_cols} total_rows {total_rows}")


    # framework of Panel in Openvisus

    db=None
    os.environ["VISUS_DISABLE_WRITE_LOCK"]="1" # writings to OpenVisus will happen serially
    if not os.path.exists('visus.idx'):
        print('creating idx file')
        field=ov.Field("data" ,f"uint8[{bandCount}]",'row_major')
        bitmask=ov.DatasetBitmask.guess(ord('V'),ov.PointNi.fromString(f"{sizeX} {sizeY}"), True).toString()
        assert(bitmask.endswith("01") or bitmask.endswith("10"))
        db=ov.CreateIdx(url=dst, dim=2, dims=[sizeX,sizeY], fields=[field], arco="2mb", compression="zip", bitmask=bitmask)  # create ARCO + zip directly
        print(f"OpenVisus {dst} created")

    else:
        db=ov.LoadDataset('visus.idx')

    T1 = time.time()
    x = 0
    y = 0

    # Iterate through all specified column and row combinations
    for row in range (total_rows-1, -1, -1):
        for col in range (total_cols):
            t1 = time.time()
            # Construct the expected file name
            if scale_factor == 1:
                file_name = f"{panel_name}_{col}_{row}.tif"
            else:
                file_name = f"{panel_name}_{col}_{row}_out.tif"
            file_path = os.path.join(output_idx_dir, file_name)
            
            # Check if the file exists
            if os.path.exists(file_path):
                img_array = load_image_array(file_path)
                # Flip the image vertically
                flipped_array = np.flipud(img_array)
                # Ensure the flipped array is contiguous
                flipped_array = np.ascontiguousarray(flipped_array)
                # Print the file name and shape of the image
                tiles_width = img_array.shape[1]
                tiles_height = img_array.shape[0]
                #print(file_name, tile_width, tile_height)
                x1 = x
                y1 = y
                x2 = x1 + tiles_width
                y2 = y1 + tiles_height
                #print(f"col{col},row{row},{x1},{y1},{x2},{y2}")
                db.write(flipped_array, logic_box=[[x1,y1],[x2,y2]])
                x = x2
                y = y1
                sec=time.time()-t1
                    
        x = 0
        y = y2  

    print("Compressing OpenVisus dataset (CAN BE SLOW!)...")
    T1 = time.time()
    db.compressDataset(["zip"])
    sec_compress=time.time()-T1
    print(f"Compression done in {sec_compress} seconds")



