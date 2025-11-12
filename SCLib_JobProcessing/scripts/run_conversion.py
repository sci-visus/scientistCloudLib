#!/usr/bin/env python3
"""
Dataset Conversion Script
Converts various sensor data formats to IDX format for visualization.

Replaces the legacy run_slampy.sh script with a cleaner Python implementation.
"""

import os
import sys
import shutil
import subprocess
import logging
import argparse
import tempfile
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ConversionError(Exception):
    """Custom exception for conversion errors."""
    pass


class DatasetConverter:
    """Main class for dataset conversion operations."""
    
    def __init__(self, input_dir: str, output_dir: str, sensor_type: str, 
                 conversion_params: Optional[Dict[str, Any]] = None,
                 upload_to_aws: bool = False):
        """
        Initialize converter.
        
        Args:
            input_dir: Directory containing files to convert
            output_dir: Directory where converted files will be placed
            sensor_type: Type of sensor (IDX, TIFF, TIFF_RGB, 4D_NEXUS, etc.)
            conversion_params: Optional conversion parameters (for 4D_NEXUS)
            upload_to_aws: Whether to upload to AWS after conversion
        """
        self.input_dir = Path(input_dir).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.sensor_type = sensor_type.upper().strip()
        
        # Map common sensor type variations to standard types
        sensor_type_mapping = {
            'RGB': 'RGB DRONE',  # RGB should use RGB DRONE (slampy) conversion, not TIFF_RGB
            'MAPIR': 'MAPIR DRONE',  # MapIR should use MapIR DRONE conversion
            'TIFF RGB': 'TIFF_RGB',
            'TIFFRGB': 'TIFF_RGB',
        }
        if self.sensor_type in sensor_type_mapping:
            original_type = self.sensor_type
            self.sensor_type = sensor_type_mapping[self.sensor_type]
            logger.info(f"Mapped sensor type '{original_type}' to '{self.sensor_type}'")
        
        self.conversion_params = conversion_params or {}
        self.upload_to_aws = upload_to_aws
        
        # Script directory (where this script is located)
        self.script_dir = Path(__file__).parent
        
        # Validate paths
        if not self.input_dir.exists():
            raise ConversionError(f"Input directory does not exist: {input_dir}")
        
        # Create output directory if it doesn't exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.output_dir, 0o777)
    
    def convert(self) -> None:
        """Run the conversion process."""
        logger.info(f"Starting conversion: {self.input_dir} -> {self.output_dir}")
        logger.info(f"Sensor type: {self.sensor_type}")
        
        try:
            # Unzip files if needed
            self._unzip_if_needed()
            
            # Run conversion based on sensor type
            if self.sensor_type == "IDX":
                self._convert_idx()
            elif self.sensor_type == "RGB DRONE":
                self._convert_rgb_drone()
            elif self.sensor_type == "MAPIR DRONE":
                self._convert_mapir_drone()
            elif self.sensor_type == "TIFF":
                self._convert_tiff()
            elif self.sensor_type == "TIFF_RGB":
                self._convert_tiff_rgb()
            elif self.sensor_type in ("4D_NEXUS", "NEXUS"):
                self._convert_4d_nexus()
            elif self.sensor_type == "HDF5":
                self._convert_hdf5()
            elif self.sensor_type == "NETCDF":
                self._convert_netcdf()
            else:
                raise ConversionError(f"Unknown sensor type: {self.sensor_type}")
            
            # Fix permissions
            self._fix_permissions(self.input_dir)
            self._fix_permissions(self.output_dir)
            os.chmod(self.output_dir, 0o777)
            
            # Upload to AWS if requested
            if self.upload_to_aws:
                self._upload_to_aws(self.input_dir)
                self._upload_to_aws(self.output_dir)
            
            logger.info("Conversion completed successfully")
            
        except Exception as e:
            logger.error(f"Conversion failed: {e}", exc_info=True)
            raise
    
    def _unzip_if_needed(self) -> None:
        """Unzip .zip and .7z files in the input directory."""
        logger.info("Checking for compressed files...")
        
        # Handle .7z files
        for archive in self.input_dir.glob("*.7z"):
            logger.info(f"Unzipping 7z archive: {archive}")
            self._extract_archive(archive, "7z")
        
        # Handle .zip files
        for archive in self.input_dir.glob("*.zip"):
            logger.info(f"Unzipping zip archive: {archive}")
            self._extract_archive(archive, "zip")
    
    def _extract_archive(self, archive_path: Path, archive_type: str) -> None:
        """Extract an archive file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            try:
                if archive_type == "7z":
                    subprocess.run(
                        ["7z", "x", str(archive_path), f"-o{temp_path}"],
                        check=True,
                        capture_output=True
                    )
                elif archive_type == "zip":
                    subprocess.run(
                        ["unzip", str(archive_path), "-d", str(temp_path)],
                        check=True,
                        capture_output=True
                    )
                else:
                    raise ConversionError(f"Unknown archive type: {archive_type}")
                
                # Move contents from temp directory to input directory
                extracted_items = list(temp_path.iterdir())
                
                if len(extracted_items) == 1 and extracted_items[0].is_dir():
                    # Single subdirectory - move its contents up
                    shutil.move(str(extracted_items[0]), str(self.input_dir / extracted_items[0].name))
                else:
                    # Multiple items - move everything
                    for item in extracted_items:
                        dest = self.input_dir / item.name
                        if item.is_dir():
                            if dest.exists():
                                # Merge directories
                                for subitem in item.rglob("*"):
                                    rel_path = subitem.relative_to(item)
                                    dest_subitem = dest / rel_path
                                    dest_subitem.parent.mkdir(parents=True, exist_ok=True)
                                    if subitem.is_file():
                                        shutil.copy2(subitem, dest_subitem)
                            else:
                                shutil.move(str(item), str(dest))
                        else:
                            shutil.move(str(item), str(dest))
                
                # Remove the archive
                archive_path.unlink()
                logger.info(f"Successfully extracted and removed {archive_path}")
                
            except subprocess.CalledProcessError as e:
                raise ConversionError(f"Failed to extract {archive_path}: {e.stderr.decode()}")
    
    def _convert_idx(self) -> None:
        """Handle IDX files - mostly just copy and organize."""
        logger.info("Processing IDX files")
        
        # Skip if it's a mod_visus link
        if "mod_visus" in str(self.input_dir):
            logger.info("Skipping conversion - is link to server")
            return
        
        # Copy files
        if self.input_dir.is_dir():
            logger.info(f"Copying contents from {self.input_dir} to {self.output_dir}")
            for item in self.input_dir.iterdir():
                if item.name.startswith('.'):
                    continue
                dest = self.output_dir / item.name
                if item.is_dir():
                    if dest.exists():
                        # Merge directories
                        for subitem in item.rglob("*"):
                            rel_path = subitem.relative_to(item)
                            dest_subitem = dest / rel_path
                            dest_subitem.parent.mkdir(parents=True, exist_ok=True)
                            if subitem.is_file():
                                shutil.copy2(subitem, dest_subitem)
                    else:
                        shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
        else:
            # Single file
            dest = self.output_dir / self.input_dir.name
            if dest.exists() and dest.is_dir():
                # Move contents up
                for item in dest.iterdir():
                    shutil.move(str(item), str(self.output_dir / item.name))
                dest.rmdir()
            else:
                shutil.copy2(self.input_dir, dest)
        
        # Handle slam.html
        slam_html = self.output_dir / "slam.html"
        if slam_html.exists():
            logger.info("Fixing visus Google MIDX")
            fix_script = self.script_dir / "fixVisusGoogleMIDX.py"
            if fix_script.exists():
                subprocess.run(["python3", str(fix_script), str(slam_html)], check=True)
        
        # Handle visus.midx -> visus.idx symlink
        visus_midx = self.output_dir / "visus.midx"
        visus_idx = self.output_dir / "visus.idx"
        if visus_midx.exists() and not visus_idx.exists():
            logger.info(f"Creating symlink: {visus_midx} -> {visus_idx}")
            visus_idx.symlink_to(visus_midx)
        
        # Move visus.idx to top level if found buried
        found_idx = next(self.output_dir.rglob("visus.idx"), None)
        if found_idx and found_idx.parent != self.output_dir:
            logger.info(f"Moving visus.idx to top level: {found_idx}")
            shutil.move(str(found_idx), str(self.output_dir / "visus.idx"))
        
        # Move visus directory to top level if found buried
        found_visus = next(self.output_dir.rglob("visus"), None)
        if found_visus and found_visus.is_dir() and found_visus.parent != self.output_dir:
            logger.info(f"Moving visus directory to top level: {found_visus}")
            shutil.move(str(found_visus), str(self.output_dir / "visus"))
        
        # Handle .idx files with matching directories
        for idx_file in self.output_dir.rglob("*.idx"):
            if "visus.idx" in str(idx_file):
                continue
            
            idx_dir = idx_file.parent
            base_name = idx_file.stem
            corresponding_dir = idx_dir / base_name
            
            if corresponding_dir.exists() and corresponding_dir.is_dir():
                logger.info(f"Found matching pair: {idx_file} and {corresponding_dir}")
                # Copy idx to visus.idx
                shutil.copy2(idx_file, self.output_dir / "visus.idx")
                # Move directory to visus
                if (self.output_dir / "visus").exists():
                    shutil.rmtree(self.output_dir / "visus")
                shutil.move(str(corresponding_dir), str(self.output_dir / "visus"))
                # Fix permissions
                os.chmod(self.output_dir / "visus.idx", 0o644)
                os.chmod(self.output_dir / "visus", 0o755)
                for file in (self.output_dir / "visus").rglob("*"):
                    if file.is_file():
                        os.chmod(file, 0o644)
                break
    
    def _convert_rgb_drone(self) -> None:
        """Convert RGB drone images using slampy."""
        logger.info("Converting RGB drone images")
        
        # Run slampy batch conversion
        subprocess.run(
            ["python3", "-m", "slampy", "--image-dir", str(self.input_dir),
             "--cache-dir", str(self.output_dir), "--batch"],
            check=True
        )
        
        # Convert midx to idx
        visus_midx = self.output_dir / "visus.midx"
        visus_idx = self.output_dir / "visus.idx"
        if visus_midx.exists():
            subprocess.run(
                ["python3", "-m", "slampy", "midx-to-idx",
                 "--midx", str(visus_midx), "--idx", str(visus_idx)],
                check=True
            )
        
        # Copy geolocation
        copy_geo_script = self.script_dir / "copy_geolocation.py"
        if copy_geo_script.exists() and visus_midx.exists() and visus_idx.exists():
            subprocess.run(
                ["python3", str(copy_geo_script), str(visus_midx), str(visus_idx)],
                check=True
            )
    
    def _convert_mapir_drone(self) -> None:
        """Convert MapIR drone images."""
        logger.info("Converting MapIR drone images")
        
        # Find target files for calibration
        target_files = list(self.input_dir.glob("target*"))
        found_target = False
        
        if target_files:
            target_file = target_files[0]
            logger.info(f"Found target file: {target_file}")
            
            calibrated_dir = self.output_dir / "Calibrated"
            calibrated_dir.mkdir(exist_ok=True)
            
            # Run MapIR calibration
            mapir_script = self.script_dir / "MapIRCalibration" / "MAPIR_CalibrateImages.py"
            if mapir_script.exists():
                subprocess.run(
                    ["python3", str(mapir_script),
                     "--target", str(target_file),
                     "--path", str(self.input_dir),
                     "--output", str(calibrated_dir)],
                    check=True
                )
            
            # Remove target files from calibrated directory
            for target in calibrated_dir.glob("target*"):
                target.unlink()
            
            # Run slampy on calibrated images
            subprocess.run(
                ["python3", "-m", "slampy", "--image-dir", str(calibrated_dir),
                 "--cache-dir", str(self.output_dir), "--batch"],
                check=True
            )
            found_target = True
        
        if not found_target:
            logger.info("No target file found, running slampy without calibration")
            subprocess.run(
                ["python3", "-m", "slampy", "--image-dir", str(self.input_dir),
                 "--cache-dir", str(self.output_dir), "--batch"],
                check=True
            )
        
        # Convert midx to idx with NDVI field
        visus_midx = self.output_dir / "visus.midx"
        visus_idx = self.output_dir / "visus.idx"
        if visus_midx.exists():
            ndvi_field = (
                "data=Array.toNumPy(voronoi());"
                "data = data.astype(numpy.float32);"
                "orange,cyan,NIR=data[:,:,0],data[:,:,1],data[:,:,2];"
                "import matplotlib;import cv2, numpy;"
                "NDVI_u = (NIR - orange);"
                "NDVI_d = (NIR + orange)+.001;"
                "NDVI = NDVI_u / NDVI_d;"
                "NDVI = (NDVI+1.0)/2.0;"
                "gray = numpy.float32(NDVI);"
                "sandpt = (255/255.0, 238/255.0, 204/255.0);"
                "lawngreenpt = (51/255.0, 153/255.0, 51/255.0);"
                "greenpt = (0/255.0, 102/255.0, 0/255.0);"
                "darkgreenpt=(0, 51/255.0, 0);"
                "redPt = (153/255.0, 0, 0);"
                "orangept = (255/255.0, 204/255.0, 128/255.0);"
                "cdictN = [ redPt, orangept,sandpt,greenpt, darkgreenpt ];"
                "nodesN =[0.0,0.25,0.5,0.75,1.0,];"
                "cmapN = matplotlib.colors.LinearSegmentedColormap.from_list(\"mycmap\", list(zip(nodesN, cdictN)));"
                "out = numpy.uint8(cmapN(gray)*255);"
                "out = out[...,:3];"
                "output=Array.fromNumPy(out,TargetDim=2);"
            )
            subprocess.run(
                ["python3", "-m", "slampy", "midx-to-idx",
                 "--field", ndvi_field,
                 "--midx", str(visus_midx), "--idx", str(visus_idx)],
                check=True
            )
            
            # Copy geolocation
            copy_geo_script = self.script_dir / "copy_geolocation.py"
            if copy_geo_script.exists():
                subprocess.run(
                    ["python3", str(copy_geo_script), str(visus_midx), str(visus_idx)],
                    check=True
                )
    
    def _convert_tiff(self) -> None:
        """Convert TIFF stacks to IDX."""
        logger.info("Converting TIFF stacks")
        
        os.chmod(self.input_dir, 0o777)
        
        # List all tif files
        extensions = ["tif", "tiff", "TIFF", "TIF"]
        for ext in extensions:
            for file in self.input_dir.glob(f"*.{ext}"):
                logger.info(f"Found TIFF file: {file}")
        
        # Run conversion script
        convert_script = self.script_dir / "convert_tif_to_idx.py"
        if not convert_script.exists():
            # Try parent directory
            convert_script = self.script_dir.parent / "convert_tif_to_idx.py"
        
        if convert_script.exists():
            subprocess.run(
                ["python3", str(convert_script), str(self.input_dir)],
                check=True
            )
        else:
            raise ConversionError(f"Conversion script not found: convert_tif_to_idx.py")
        
        # Copy visus* and metadata* files to output
        for pattern in ["visus*", "metadata*"]:
            for item in self.input_dir.glob(pattern):
                if item.is_file():
                    shutil.copy2(item, self.output_dir / item.name)
                elif item.is_dir():
                    dest = self.output_dir / item.name
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
        
        # Remove visus* files from input
        for item in self.input_dir.glob("visus*"):
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    
    def _convert_tiff_rgb(self) -> None:
        """Convert TIFF RGB stacks to IDX."""
        logger.info("Converting TIFF RGB stacks")
        
        os.chmod(self.input_dir, 0o777)
        
        # List all tif files
        extensions = ["tif", "tiff", "TIFF", "TIF"]
        for ext in extensions:
            for file in self.input_dir.glob(f"*.{ext}"):
                logger.info(f"Found TIFF file: {file}")
        
        # Run conversion script
        convert_script = self.script_dir / "convert_tif_to_idx_rgb.py"
        if not convert_script.exists():
            convert_script = self.script_dir.parent / "convert_tif_to_idx_rgb.py"
        
        if convert_script.exists():
            subprocess.run(
                ["python3", str(convert_script), str(self.input_dir)],
                check=True
            )
        else:
            raise ConversionError(f"Conversion script not found: convert_tif_to_idx_rgb.py")
        
        # Copy visus* and metadata* files to output
        for pattern in ["visus*", "metadata*"]:
            for item in self.input_dir.glob(pattern):
                if item.is_file():
                    shutil.copy2(item, self.output_dir / item.name)
                elif item.is_dir():
                    dest = self.output_dir / item.name
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
        
        # Remove visus* files from input
        for item in self.input_dir.glob("visus*"):
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    
    def _convert_4d_nexus(self) -> None:
        """Convert 4D NEXUS files to IDX."""
        logger.info("Converting 4D NEXUS files")
        
        os.chmod(self.input_dir, 0o777)
        
        # List all nexus files
        extensions = ["nxs", "h5", "hdf5", "hdf"]
        for ext in extensions:
            for file in self.input_dir.glob(f"*.{ext}"):
                logger.info(f"Found NEXUS file: {file}")
        
        # Run conversion script
        convert_script = self.script_dir / "convert_4dnexus_to_idx.py"
        if not convert_script.exists():
            convert_script = self.script_dir.parent / "convert_4dnexus_to_idx.py"
        
        if convert_script.exists():
            cmd = ["python3", str(convert_script), str(self.input_dir)]
            
            # Add conversion parameters if provided
            if self.conversion_params:
                params_str = json.dumps(self.conversion_params)
                cmd.extend(["--params", params_str])
            
            subprocess.run(cmd, check=True)
        else:
            raise ConversionError(f"Conversion script not found: convert_4dnexus_to_idx.py")
        
        # Copy all files to output
        for item in self.input_dir.iterdir():
            if item.name.startswith('.'):
                continue
            dest = self.output_dir / item.name
            if item.is_file():
                shutil.copy2(item, dest)
            elif item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
    
    def _convert_hdf5(self) -> None:
        """Convert HDF5 files to IDX."""
        logger.info("Converting HDF5 files")
        
        os.chmod(self.input_dir, 0o777)
        
        # List all hdf5 files
        extensions = ["nxs", "h5", "hdf5", "hdf"]
        for ext in extensions:
            for file in self.input_dir.glob(f"*.{ext}"):
                logger.info(f"Found HDF5 file: {file}")
        
        # Run conversion script
        convert_script = self.script_dir / "convert_hdf5_to_idx.py"
        if not convert_script.exists():
            convert_script = self.script_dir.parent / "convert_hdf5_to_idx.py"
        
        if convert_script.exists():
            subprocess.run(
                ["python3", str(convert_script), str(self.input_dir)],
                check=True
            )
        else:
            raise ConversionError(f"Conversion script not found: convert_hdf5_to_idx.py")
        
        # Copy all files to output
        for item in self.input_dir.iterdir():
            if item.name.startswith('.'):
                continue
            dest = self.output_dir / item.name
            if item.is_file():
                shutil.copy2(item, dest)
            elif item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
    
    def _convert_netcdf(self) -> None:
        """Convert NetCDF files to IDX."""
        logger.info("Converting NetCDF files")
        
        os.chmod(self.input_dir, 0o777)
        
        # Find all .nc files
        nc_files = list(self.input_dir.glob("*.nc"))
        
        if not nc_files:
            raise ConversionError("No NetCDF files found in input directory")
        
        # Run conversion script for each file
        convert_script = self.script_dir / "convert_netcdf_to_idx.py"
        if not convert_script.exists():
            convert_script = self.script_dir.parent / "convert_netcdf_to_idx.py"
        
        if convert_script.exists():
            for nc_file in nc_files:
                logger.info(f"Converting {nc_file}")
                subprocess.run(
                    ["python3", str(convert_script), "", str(nc_file)],
                    check=True,
                    cwd=str(self.input_dir)
                )
            
            # Copy visus* files to output
            for item in self.input_dir.glob("visus*"):
                if item.is_file():
                    shutil.copy2(item, self.output_dir / item.name)
                elif item.is_dir():
                    dest = self.output_dir / item.name
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(item, dest)
            
            # Remove visus* files from input
            for item in self.input_dir.glob("visus*"):
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
        else:
            raise ConversionError(f"Conversion script not found: convert_netcdf_to_idx.py")
    
    def _fix_permissions(self, directory: Path) -> None:
        """Fix permissions for a directory and its contents."""
        logger.info(f"Fixing permissions for: {directory}")
        
        if not directory.exists():
            logger.warning(f"Directory does not exist: {directory}")
            return
        
        # Fix directory permissions
        for root, dirs, files in os.walk(directory):
            os.chmod(root, 0o755)
            for d in dirs:
                os.chmod(Path(root) / d, 0o755)
            for f in files:
                os.chmod(Path(root) / f, 0o644)
        
        os.chmod(directory, 0o755)
    
    def _upload_to_aws(self, directory: Path) -> None:
        """Upload directory to AWS S3."""
        if not self.upload_to_aws:
            return
        
        logger.info(f"Uploading to AWS: {directory}")
        
        # Get last two directory components
        parts = directory.parts
        if len(parts) >= 2:
            last_two = f"{parts[-2]}/{parts[-1]}"
        else:
            last_two = parts[-1]
        
        bucket_path = f"s3://utah/visstore/datasets/{last_two}"
        
        try:
            subprocess.run(
                ["aws", "s3", "sync",
                 "--profile", "sealstorage",
                 "--no-verify-ssl",
                 "--endpoint-url", "https://maritime.sealstorage.io/api/v0/s3",
                 str(directory), bucket_path],
                check=True,
                capture_output=True
            )
            logger.info(f"Successfully uploaded to {bucket_path}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"AWS upload failed: {e.stderr.decode()}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Convert sensor data to IDX format",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("input_dir", help="Input directory containing files to convert")
    parser.add_argument("output_dir", help="Output directory for converted files")
    parser.add_argument("sensor_type", help="Sensor type (IDX, TIFF, TIFF_RGB, 4D_NEXUS, etc.)")
    parser.add_argument("--params", help="Conversion parameters (JSON string, for 4D_NEXUS)")
    parser.add_argument("--upload-aws", action="store_true", help="Upload to AWS after conversion")
    
    args = parser.parse_args()
    
    # Parse conversion parameters if provided
    conversion_params = None
    if args.params:
        try:
            conversion_params = json.loads(args.params)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in --params: {e}")
            sys.exit(1)
    
    try:
        converter = DatasetConverter(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            sensor_type=args.sensor_type,
            conversion_params=conversion_params,
            upload_to_aws=args.upload_aws
        )
        converter.convert()
        logger.info("run_conversion done")
        sys.exit(0)
    except ConversionError as e:
        logger.error(f"Conversion error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

