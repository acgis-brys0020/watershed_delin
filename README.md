# watershed_delin
A watershed delineation tool intended to automate AgErosion workflows. Created Summer 2026 by Sian Bryson for a summer SEO position with OMAFA.

**Author**: Sian Bryson

**Organization**: OMAFA Environmental Management Branch, Soils GIS & Technologies unit

**Date**: 2026-08-17

**ArcGIS Version**: 3.5.4

## About
Uses 0.5m LiDAR-derived DTM imagery as its base data. Pulls imagery from an Ontario GeoHub ArcGIS REST server and resamples/clips to a desired resolution and extent.

Runs a standard watershed delineation workflow, then returns a set of feature layers and an HTML report to the user.

**Disclaimer**: Microsoft Copilot was used for debugging; there may be uncaught errors. 

## How to use
This script is the source code for a pyt ArcPy Toolbox, which is uploaded to ArcGIS Enterprise as a web geoprocessing service. 
1. Add toolbox to ArcGIS Pro
2. Run the tool
3. Use the history item from a successful run to upload or overwrite a geoprocessing tool to Enterprise. 

Refer to the attached guide for more information and help troubleshooting.
