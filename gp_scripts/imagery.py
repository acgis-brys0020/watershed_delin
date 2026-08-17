import arcpy
from gp_scripts.utils import (scratch_raster)

def load_imagery(uid, study_area, cell_size):
     image_service = "https://ws.geoservices.lrc.gov.on.ca/arcgis5/rest/services/Elevation/Ontario_DTM_LidarDerived/ImageServer" 
     sa_desc = arcpy.Describe(study_area)

     with arcpy.EnvManager(
            extent = sa_desc.extent,
            cellSize = cell_size,
            snapRaster = image_service
        ):
            layer_name = "image_layer"
            arcpy.management.MakeImageServerLayer(
                in_image_service = image_service,
                out_imageserver_layer = layer_name,
                mosaic_method = "ByAttribute",
                where_clause = f"Resolution_m <= {cell_size}"
            )

            raw_path = scratch_raster("raw", uid)
            arcpy.management.CopyRaster(layer_name, raw_path)

            # Process: Clip Raster (Clip Raster) (management)
            arcpy.AddMessage("Clipping raster...")
            clipped = arcpy.sa.ExtractByMask(raw_path, study_area)
            nbr = arcpy.sa.NbrRectangle(3, 3, "CELL")
            gap_filled = arcpy.sa.Con(
                arcpy.sa.IsNull(clipped),
                arcpy.sa.FocalStatistics(clipped, nbr, "MEAN"),
                clipped
            )

            gap_filled_path = scratch_raster("clipped_fixed", uid)
            gap_filled.save(gap_filled_path)

            # Resample
            arcpy.AddMessage("Resampling...")
            resampled_path = scratch_raster("resampled", uid)
            arcpy.management.Resample(
                in_raster=gap_filled_path, 
                out_raster= resampled_path,
                cell_size= cell_size,
                resampling_type="BILINEAR")
            return resampled_path