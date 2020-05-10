from typing import Optional, List

import branca as bc
import folium as fl


def add_categorical_legend(
    folium_map: fl.Map,
    title: str,
    colors: List[str],
    labels: List[str],
) -> fl.Map:
    """
    Given a Folium map, add to it a categorical legend with the given title, colors, and corresponding labels.
    The given colors and labels will be listed in the legend from top to bottom.
    Return the resulting map.

    Based on `this example <http://nbviewer.jupyter.org/gist/talbertc-usgs/18f8901fc98f109f2b71156cf3ac81cd>`_.
    """
    # Error check
    if len(colors) != len(labels):
        raise ValueError("colors and labels must have the same length.")

    color_by_label = dict(zip(labels, colors))

    # Make legend HTML
    template = f"""
    {{% macro html(this, kwargs) %}}

    <!doctype html>
    <html lang="en">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
    </head>
    <body>
    <div id='maplegend' class='maplegend'>
      <div class='legend-title'>{title}</div>
      <div class='legend-scale'>
        <ul class='legend-labels'>
    """

    for label, color in color_by_label.items():
        template += f"<li><span style='background:{color}'></span>{label}</li>"

    template += """
        </ul>
      </div>
    </div>

    </body>
    </html>

    <style type='text/css'>
      .maplegend {
        position: absolute;
        z-index:9999;
        background-color: rgba(255, 255, 255, 1);
        border-radius: 5px;
        border: 2px solid #bbb;
        padding: 10px;
        font-size:12px;
        right: 10px;
        bottom: 20px;
      }
      .maplegend .legend-title {
        text-align: left;
        margin-bottom: 5px;
        font-weight: bold;
        font-size: 90%;
        }
      .maplegend .legend-scale ul {
        margin: 0;
        margin-bottom: 5px;
        padding: 0;
        float: left;
        list-style: none;
        }
      .maplegend .legend-scale ul li {
        font-size: 80%;
        list-style: none;
        margin-left: 0;
        line-height: 18px;
        margin-bottom: 2px;
        }
      .maplegend ul.legend-labels li span {
        display: block;
        float: left;
        height: 16px;
        width: 30px;
        margin-right: 5px;
        margin-left: 0;
        border: 0px solid #ccc;
        }
      .maplegend .legend-source {
        font-size: 80%;
        color: #777;
        clear: both;
        }
      .maplegend a {
        color: #777;
        }
    </style>
    {% endmacro %}
    """

    macro = bc.element.MacroElement()
    macro._template = bc.element.Template(template)
    folium_map.get_root().add_child(macro)

    return folium_map
