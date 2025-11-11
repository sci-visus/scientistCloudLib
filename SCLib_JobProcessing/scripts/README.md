# Conversion Scripts

This directory contains scripts for converting various sensor data formats to IDX format for visualization in the ScientistCloud dashboards.

## Main Script

### `run_conversion.py`
Main Python-based conversion script that replaces the legacy `run_slampy.sh` shell script. Provides better error handling, logging, and maintainability.

**Usage:**
```bash
python3 run_conversion.py <input_dir> <output_dir> <sensor_type> [--params JSON] [--upload-aws]
```

**Arguments:**
- `input_dir`: Directory containing files to convert
- `output_dir`: Directory where converted files will be placed
- `sensor_type`: Type of sensor (IDX, TIFF, TIFF_RGB, 4D_NEXUS, HDF5, NETCDF, RGB DRONE, MAPIR DRONE)
- `--params`: Optional JSON string with conversion parameters (for 4D_NEXUS)
- `--upload-aws`: Upload to AWS after conversion (optional)

**Example:**
```bash
python3 run_conversion.py /mnt/visus_datasets/upload/uuid /mnt/visus_datasets/converted/uuid TIFF_RGB
```

## Conversion Scripts

### Format-Specific Converters

- **`convert_tif_to_idx.py`**: Converts TIFF image stacks to IDX format
- **`convert_tif_to_idx_rgb.py`**: Converts RGB TIFF image stacks to IDX format
- **`convert_4dnexus_to_idx.py`**: Converts 4D NEXUS files to IDX format
- **`convert_hdf5_to_idx.py`**: Converts HDF5 files to IDX format
- **`convert_netcdf_to_idx.py`**: Converts NetCDF files to IDX format

### Helper Scripts

- **`fixVisusGoogleMIDX.py`**: Fixes visus Google MIDX files
- **`copy_geolocation.py`**: Copies geolocation data from MIDX to IDX files

### MapIR Calibration

The `MapIRCalibration/` directory contains scripts for calibrating MapIR drone images:
- **`MAPIR_CalibrateImages.py`**: Main calibration script for MapIR images
- Additional calibration utilities and configuration files

## Sensor Types Supported

1. **IDX**: IDX files (mostly copying and organizing)
2. **TIFF**: TIFF image stacks
3. **TIFF_RGB**: RGB TIFF image stacks
4. **4D_NEXUS**: 4D NEXUS files (supports conversion parameters)
5. **HDF5**: HDF5 files
6. **NETCDF**: NetCDF files
7. **RGB DRONE**: RGB drone images (uses slampy)
8. **MAPIR DRONE**: MapIR drone images (uses MapIR calibration + slampy)

## Features

- **Automatic unzipping**: Handles .zip and .7z archives
- **Permission fixing**: Automatically fixes file permissions
- **Error handling**: Better error messages and logging
- **AWS upload**: Optional upload to AWS S3 after conversion
- **Backward compatible**: Falls back to shell script if Python version not found

## Integration

The conversion script is called by `SCLib_BackgroundService.py` when processing conversion jobs. The background service:
1. Receives conversion job from the job queue
2. Calls `run_conversion.py` with appropriate parameters
3. Monitors the conversion process
4. Updates job status on completion

## Dependencies

The conversion scripts require:
- Python 3.x
- OpenVisus library
- numpy
- Various image processing libraries (rasterio, tifffile, matplotlib)
- slampy (for drone image processing)
- pyproj, shapely (for geolocation)

## Notes

- All scripts are executable (`chmod +x`)
- Scripts should be run from the scripts directory or with full paths
- The scripts directory is referenced relative to `SCLib_JobProcessing/scripts/`
- Conversion parameters for 4D_NEXUS are passed as JSON strings

