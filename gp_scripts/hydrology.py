import arcpy
import os
from gp_scripts.utils import (scratch_raster, scratch_fc)
from dataclasses import dataclass
base_dir = os.path.dirname(__file__)

@dataclass
class HydroOutputs:
    watershed: str
    streams: str
    snap_pour: str

@dataclass
class RasterOutputs:
     flowdir_path : str
     flowacc_raster : object
     strahler_order_path: str

@dataclass
class Segment:
    from_node: int
    to_node: int
    length: float
    order: int

@dataclass
class StreamStats:
    length: float
    longest_stream: str
    elevation_drop: float

def hydro_raster_tools(uid, threshold, resampled_path):
    arcpy.AddMessage("Filling sinks...")
    filled_path = scratch_raster("filled", uid)
    filled = arcpy.sa.Fill(resampled_path)
    filled.save(filled_path)
        
    arcpy.AddMessage("Deriving flow direction...")
    flowdir = arcpy.sa.FlowDirection(in_surface_raster = filled_path, flow_direction_type = "D8")
    flowdir_path = scratch_raster("flowdir", uid)
    flowdir.save(flowdir_path)

    arcpy.AddMessage("Deriving flow accumulation...")
    flowacc = arcpy.sa.FlowAccumulation(flowdir_path)
    flowacc_path = scratch_raster("flowacc", uid)
    flowacc.save(flowacc_path)
    flowacc_raster = arcpy.Raster(flowacc_path)

    arcpy.AddMessage("Creating stream network...")
    streamnet = arcpy.sa.Con(
        flowacc_raster > threshold,
        1)
    streamnet_path = scratch_raster("streamnet", uid)
    streamnet.save(streamnet_path)

    arcpy.AddMessage("Determining stream order...")
    strahler_order = arcpy.sa.StreamOrder(
        in_stream_raster = streamnet_path,
        in_flow_direction_raster = flowdir_path,
        order_method = "STRAHLER"
    )
    strahler_order_path = scratch_raster("strahler_order", uid)
    strahler_order.save(strahler_order_path)
    return RasterOutputs(
            flowdir_path = flowdir_path,
            flowacc_raster = flowacc_raster,
            strahler_order_path = strahler_order_path
    )

def hydro_vector_tools(uid, strahler_order_path, pourpoint, flowacc_raster, flowdir_path, run_ws):
    watershed = None
    snap_pour = None
    watershed_poly_path = None
    arcpy.AddMessage("Creating vectorized stream network...")
    stream_path = scratch_fc("streamnet", uid)
    arcpy.sa.StreamToFeature(
        in_stream_raster = strahler_order_path,
        in_flow_direction_raster = flowdir_path,
        out_polyline_features = stream_path,
    )
    if run_ws:
        pourpoint_fc = scratch_fc("pourpoint_input", uid)
        arcpy.management.CopyFeatures(
            pourpoint,
            pourpoint_fc
        )
        raster_snap_pp = arcpy.sa.SnapPourPoint(
            in_pour_point_data = pourpoint_fc,
            in_accumulation_raster = flowacc_raster,
            snap_distance = 50
        )
        pour_outpath = scratch_raster("pourpoint", uid)
        raster_snap_pp.save(pour_outpath)
        snap_pour = scratch_fc("snap_pourpoint", uid)
        arcpy.conversion.RasterToPoint(
                pour_outpath,
                snap_pour,
                "VALUE"
        )
        arcpy.AddMessage("converted raster to point")
        watershed = arcpy.sa.Watershed(
            flowdir_path,
            pour_outpath,
            "VALUE"
        )

        watershed_path = scratch_raster("watershed", uid)
        watershed.save(watershed_path)
        arcpy.AddMessage("Creating vectorized watershed...")
        watershed_poly_path = scratch_fc("watershed", uid)
        arcpy.conversion.RasterToPolygon(
            watershed_path,
            watershed_poly_path,
            "SIMPLIFY"
        )
        arcpy.AddMessage("created vector watershed")

    return HydroOutputs(
            watershed = watershed_poly_path, 
            streams = stream_path, 
            snap_pour = snap_pour)

def best_path(arcid, segments, upstream_of):
    #From the upstream_of list, gets all segments directly upstream of the current segment
    candidates = upstream_of.get(arcid, [])
    #If there are no upstream segments, the current segment is a headwater
    if not candidates:
        return [arcid]
    
    best_path_result = None
    best_score = None
    
    for candidate in candidates:
        path = best_path(candidate, segments, upstream_of)
        full_path = [arcid] + path

        score = (
            max(segments[seg].order for seg in full_path),
            sum(segments[seg].length for seg in full_path)
        )
        if best_score is None or score > best_score:
            best_score = score
            best_path_result = full_path

    return best_path_result

def elevation_difference(stream_fc, dem):
    with arcpy.da.SearchCursor(stream_fc, ["SHAPE@"]) as cursor:
        line = next(cursor)[0]

    start = line.firstPoint
    end = line.lastPoint

    start_elevation = float(arcpy.management.GetCellValue(dem, f"{start.X} {start.Y}").getOutput(0))
    end_elevation = float(arcpy.management.GetCellValue(dem, f"{end.X} {end.Y}").getOutput(0))

    return round((start_elevation - end_elevation), 2)

def get_stream_stats(uid, watershed, streams, snap_pour, resampled_path):
    #Only look at streams within the watershed
    streams_ws = scratch_fc("stream_ws", uid)
    
    arcpy.AddMessage(f"snap_pour = {snap_pour}")
    arcpy.AddMessage(f"snap_pour exists = {arcpy.Exists(snap_pour)}")

    arcpy.analysis.Clip(streams, watershed, streams_ws)
    
    pp_layer = f"pp_layer_{uid}"
    arcpy.management.MakeFeatureLayer(
        snap_pour,
        pp_layer
    )
    
    arcpy.management.MakeFeatureLayer(
        streams_ws,
        "streams_lyr"
    )
    
    arcpy.AddMessage(
        f"Stream features: {arcpy.management.GetCount(streams_ws)[0]}"
    )

    arcpy.AddMessage(
        f"Pour points: {arcpy.management.GetCount(pp_layer)[0]}"
    )

    #Grab stream segment that overlaps with the pourpoint
    arcpy.management.SelectLayerByLocation(
        "streams_lyr",
        "WITHIN_A_DISTANCE",
        pp_layer,
        "10 Meters"
    )
    
    arcpy.AddMessage(
        f"Selected streams: {arcpy.management.GetCount('streams_lyr')[0]}"
    )

    #Grabs outlet segment based on where the pour point is located
    with arcpy.da.SearchCursor("streams_lyr", ["ARCID"]) as cursor:
        row = next(cursor, None)
        if row is None:
            raise Exception("No stream segment found at outlet location.")
        outlet_arcid = row[0]

    #Build connectivity graph with all segments

    segments = {}

    #Create a dictionary of all segments and record their node connectivity
    with arcpy.da.SearchCursor(streams_ws,["ARCID", "FROM_NODE", "TO_NODE", "Shape_Length", "GRID_CODE"]) as cursor:
        for arcid, from_node, to_node, shape_length, grid_code in cursor:
            segments[arcid] = Segment(
                from_node = abs(from_node),
                to_node = abs(to_node),
                length = shape_length,
                order = grid_code
            )

    #Build a lookup of segments that terminate at each node
    node_lookup = {}
    for arcid, seg in segments.items():
        if seg.to_node not in node_lookup:
            node_lookup[seg.to_node] = []
        node_lookup[seg.to_node].append(arcid)

    #For each segment, find all segments whose TO_NODE matches this segment's FROM_NODE.
    #These segments are directly upstream.
    upstream_of = {}
    for arcid, seg in segments.items():
        upstream_of[arcid] = node_lookup.get(seg.from_node, [])

    main_stem_ids = best_path(outlet_arcid,segments, upstream_of)

    where = f"ARCID IN ({','.join(map(str, main_stem_ids))})"

    main_stem_length = round(sum(segments[arcid].length for arcid in main_stem_ids), 2)
    longest_stream_fc = scratch_fc("longest_stream", uid)
    arcpy.analysis.Select(streams_ws, longest_stream_fc, where)
    longest_stream = scratch_fc("longest_stream_dissolved", uid)
    arcpy.management.UnsplitLine(longest_stream_fc, longest_stream)
    
    elev_difference = elevation_difference(longest_stream, resampled_path)

    return StreamStats(
        length = main_stem_length,
        longest_stream = longest_stream,
        elevation_drop = elev_difference
    )
