import arcpy
import os
from gp_scripts.hydrology import get_stream_stats
from dataclasses import dataclass

@dataclass
class ReportOutput:
    html: str
    longest_stream: str

def generate_report(uid, watershed_new, streams, snap_pour, html_template, resampled_path):
    import datetime

    output_html = os.path.join(arcpy.env.scratchFolder, f"Watershed_Report_{uid}.html")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %I:%M %p")
    ws_area = 0

    #Find watershed area
    ws_area = sum(row[0] for row in arcpy.da.SearchCursor(watershed_new, ["SHAPE@AREA"]))
    ws_area = round(ws_area / 10_000, 2)

    stats = get_stream_stats(
        uid, 
        watershed_new, 
        streams, 
        snap_pour,
        resampled_path
    )

    final_html_content = html_template.format(
        date_generated = now_str,
        ws_area = ws_area,
        stream_reach = stats.length,
        elevation_difference = stats.elevation_drop
    )

    with open(output_html, "w", encoding = "utf-8") as html_file:
        html_file.write(final_html_content)
    if not os.path.exists(output_html):
        raise Exception("HTML report was not created.")
    
    return ReportOutput(
        html = output_html, 
        longest_stream = stats.longest_stream)

html_template = """<!DOCTYPE html>
<html>
    <head>
        <meta charset = "utf-8">
        <title>Watershed Analysis Report</title>
        <style>
                body {{
                    font-family: 'Trebuchet MS', 'Lucida Sans Unicode', 'Lucida Grande', 'Lucida Sans', Arial, sans-serif;
                    padding: 1rem;
                    max-width: 900px;
                }}
                h1 {{
                    color: #62A6A5;
                    margin-bottom: 0.5rem;
                }} 
                hr {{
                    border: None;
                    border-bottom: dashed 2px; 
                   }}
                .date {{
                    font-style: italic;
                    color: darkslategray;
                }}
        </style>
    </head>
    <body>
        <h1>Watershed Analysis Results</h1>
        <div class = "date">Report generated {date_generated}</div>
        <hr>
        <div class = "summary">
            <p><strong>Watershed area:</strong> {ws_area} hectares</sup></p>
            <p><strong>Stream length:</strong> {stream_reach} m</p>
            <p><strong>Elevation difference*:</strong> {elevation_difference}</p>
            <p>*From headwater of longest stream to the watershed outlet.</p>
        </div>
    </body>
</html>
"""