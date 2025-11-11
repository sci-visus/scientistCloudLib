import sys
import os
import shutil
import codecs
from bs4 import BeautifulSoup


# if Google API KEY is changes, then this function can fix slam.html
def fixAPIKey( htmlFile):
    #from __future__ import division, unicode_literals
    if (htmlFile):
        #htmlFile = "/Volumes/TenGigaViSUSAg/2021Season/MapIR/20210527_MAPIR_02/Calibrated_4/VisusSlamFiles/slamcopy.html"
        shutil.copyfile(htmlFile, htmlFile + ".bk")

        f = codecs.open(htmlFile + ".bk", 'r', 'utf-8')
        contents = f.read()

        soup = BeautifulSoup(contents, 'html.parser')
        scriptToChange = soup.script
        # GOOGLE API KEY, if it changes, can use this to fix old files..
        scriptToChange[
            "src"] = u"https://maps.googleapis.com/maps/api/js?libraries=visualization&key=AIzaSyBSEW6Qkk4BLRweoafVfSd48HmbLU04Xw0"

        f2 = codecs.open(htmlFile, 'w', 'utf-8')
        f2.write(str(soup))
        f2.close()
        f.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print('usage: python fixAPIKey.py <slam.html>')
    else:
        fixAPIKey(sys.argv[1])