import arcpy
import os

def scratch_raster(name, uid):
    return os.path.join(arcpy.env.scratchFolder, f"{name}_{uid}.tif")

def scratch_fc(name, uid):
    return os.path.join(arcpy.env.scratchGDB, f"{name}_{uid}")