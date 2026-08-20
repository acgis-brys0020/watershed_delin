# -*- coding: utf-8 -*-
"""
=================================================
Tool Name: AgErosion Watershed Delineator
Source: 
Author: Sian Bryson
Organization: OMAFA Environmental Management Branch
Date: 2026-07-09
ArcGIS Version: 3.5.4

Description: 
    Creates a stream network, watershed, and hydrology report based on DEM imagery. 

Parameters:
    study_area:         Feature record set      Input       Polygon study area
    pourpoint:          Feature record set      Input       Outlet/pourpoint
    cell_size:          String                  Input       Image resolution
    threshold:          Integer                 Input       Stream threshold
    streamnet_output:   Feature class           Input       Derived stream network
    watershed_output:   Feature class           Input       Delineated watershed
    longest_stream:     Feature class           Input       Longest stream from the stream net
    html_report:        File                    Input       HTML Report with stream/watershed stats

Usage:
    Intended for use with areas no larger than one or two farm fields.
=================================================
"""

import sys
import arcpy
import os
import uuid
arcpy.CheckOutExtension("Spatial")

from gp_scripts.imagery import load_imagery
from gp_scripts.hydrology import (
    hydro_raster_tools,
    hydro_vector_tools
)
from gp_scripts.report import (generate_report, html_template)

class Toolbox:
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Watershed Delineator"
        self.alias = "watershed_delineator"

        # List of tool classes associated with this toolbox
        self.tools = [WatershedDelineator]

class WatershedDelineator(object):
    def __init__(self):
        """Generates a stream network and delineates a watershed from DTM imagery."""
        self.label = "Watershed Delineator"
        self.description = "Generates a stream network and delineates a watershed from DTM imagery."

    def getParameterInfo(self):
        study_area = arcpy.Parameter(
            name = 'study_area',
            displayName = 'Study Area',
            datatype = 'GPFeatureRecordSetLayer',
            direction = 'Input',
            parameterType = 'Required'
        )
        study_area.filter.list = ["Polygon"]
        
        pourpoint = arcpy.Parameter(
            name = 'pourpoint',
            displayName = 'Outlet/pour point ⚠️REQUIRED FOR WATERSHED, OPTIONAL FOR STREAM NET⚠️',
            datatype = 'GPFeatureRecordSetLayer',
            direction = 'Input',
            parameterType = 'Optional'
        )
        pourpoint.filter.list = ["Point"]

        cell_size = arcpy.Parameter(
            name = 'cell_size',
            displayName = 'Cell size for resampling',
            datatype = 'GPString',
            direction = 'Input',
            parameterType = 'Required'
        )
        cell_size.filter.type = "ValueList"
        cell_size.filter.list = ["1m", "2m", "5m (DEBUGGING)"]
        cell_size.value = "5m (DEBUGGING)"

        threshold = arcpy.Parameter(
            name = 'threshold',
            displayName = 'Stream threshold',
            datatype = 'GPLong',
            direction = 'Input',
            parameterType = 'Optional'
        )
        threshold.value = 1000

        streamnet_output = arcpy.Parameter(
            name = 'streamnet_output',
            displayName = 'Stream network',
            datatype = 'DEFeatureClass',
            direction = 'Output',
            parameterType = 'Derived'
        )
        stream_sym = os.path.join(os.path.dirname(os.path.abspath(__file__)), "streamnet.lyrx")
        if os.path.exists(stream_sym):
             streamnet_output.symbology = stream_sym
        streamnet_output.schema.clone = False

        watershed_output = arcpy.Parameter(
            name = 'watershed_output',
            displayName = 'Watershed',
            datatype = 'DEFeatureClass',
            direction = 'Output',
            parameterType = 'Derived'
        )

        longest_stream = arcpy.Parameter(
             name = "longest_stream",
             displayName = "Longest Stream Path",
             datatype = "DEFeatureClass",
             direction = "Output",
             parameterType = "Derived"
        )
        html_report = arcpy.Parameter(
             name = "html_report",
             displayName = "HTML Report",
             datatype = "DEFile",
             direction = "Output",
             parameterType = "Derived"
        )

        run_watershed = arcpy.Parameter(
            name = 'run_watershed',
            displayName = 'Create only stream network or network + watershed',
            datatype = 'GPString',
            direction = 'Input',
            parameterType = 'Required'
        )
        run_watershed.filter.type = "ValueList"
        run_watershed.filter.list = ["Stream network only", "Stream network and watershed"]
        run_watershed.value = "Stream network and watershed"
        ws_sym = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watershed.lyrx")
        if os.path.exists(ws_sym):
             watershed_output.symbology = ws_sym
        watershed_output.schema.clone = False
        
        params = [run_watershed, study_area, pourpoint, cell_size, threshold, streamnet_output, watershed_output, html_report, longest_stream]
        return params
    
    def execute(self, parameters, messages):
        
        uid = str(uuid.uuid4())[:8]
        params = {p.name: p for p in parameters}
        #Retrieve parameters
        arcpy.AddMessage(
            f"pourpoint.valueAsText = {params['pourpoint'].valueAsText}"
        )
        study_area = params["study_area"].value
        pourpoint = params["pourpoint"].value
        label_map = {"1m" : 1, "2m" : 2, "5m (DEBUGGING)" : 5}
        label_user_selection = params["cell_size"].valueAsText
        cell_size = label_map[label_user_selection]
        threshold = params["threshold"].value
        run_ws_map = {"Stream network only" : False, "Stream network and watershed" : True}
        run_watershed_userselect = params["run_watershed"].valueAsText
        run_ws = run_ws_map[run_watershed_userselect]

        if run_ws and not pourpoint:
            raise arcpy.ExecuteError("A pour point is required when delineating a watershed.")


        arcpy.env.overwriteOutput = True
        #Load imagery
        resampled_path = load_imagery(uid, study_area, cell_size)

        #Perform raster based hydrological analysis
        raster = hydro_raster_tools(uid, threshold, resampled_path)
        
        #Return vectorized hydro features
        hydro = hydro_vector_tools(
            uid,
            raster.strahler_order_path,
            pourpoint,
            raster.flowacc_raster,
            raster.flowdir_path,
            run_ws
        )

        # GENERATE REPORT --------------------------------------
        if run_ws:
            report = generate_report(
                uid, 
                hydro.watershed, 
                hydro.streams, 
                hydro.snap_pour,
                html_template, 
                resampled_path)
            params["watershed_output"].value = hydro.watershed
            params["html_report"].value = report.html
            params["longest_stream"].value = report.longest_stream
        else:
            params["watershed_output"].value = None
            params["html_report"].value = None
            params["longest_stream"].value = None

        params["streamnet_output"].value = hydro.streams
        