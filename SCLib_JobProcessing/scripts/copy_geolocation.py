
import sys
import math
import slampy.gps_utils
from OpenVisus import *
import xml.etree.ElementTree as ET
from pyproj import Proj, transform, Geod
from shapely.geometry import Point, LineString


inputFile = sys.argv[1]
outputFile = sys.argv[2]

tree = ET.parse(inputFile)
physic_box_str = tree.getroot().attrib['physic_box']
physic_box = [float(x) for x in physic_box_str.split(' ')]

logic_box_str = tree.getroot().attrib['logic_box']
logic_box = [float(x) for x in logic_box_str.split(' ')]

minLatLon = slampy.gps_utils.GPSUtils.unitToGPS(physic_box[0], physic_box[2])
maxLatLon = slampy.gps_utils.GPSUtils.unitToGPS(physic_box[1], physic_box[3])

print(minLatLon)
print(maxLatLon)
minCrs = transform(Proj(init='epsg:4326'), Proj(init='epsg:3857'), minLatLon[1], minLatLon[0])

diag_line = LineString([Point(minLatLon[1], minLatLon[0]),
                        Point(maxLatLon[1], maxLatLon[0])])
diag_dist = Geod(ellps="WGS84").geometry_length(diag_line)

pixel_w = logic_box[2] - logic_box[0]
pixel_h = logic_box[3] - logic_box[1]
pixel_dist = math.sqrt(pixel_w*pixel_w + pixel_h*pixel_h)

pixels_per_meter = pixel_dist / diag_dist

idx = IdxFile()
idx.load(outputFile)
idx.metadata.setValue("crs_name", "epsg:3857") # web mercator
idx.metadata.setValue("crs_offset", " ".join((str(minCrs[0]),str(minCrs[1]))))
idx.metadata.setValue("crs_scale", str(pixels_per_meter))
idx.save(outputFile)

