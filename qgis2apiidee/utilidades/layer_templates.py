import os
import urllib.parse
import re
import json
from qgis.core import QgsVectorFileWriter, QgsCoordinateReferenceSystem, QgsMessageLog
from qgis.core import QgsMapLayer
from qgis.utils import Qgis
from qgis.core import QgsProject
from PyQt5 import QtCore





def remove_spaces(txt):
    return '"'.join(it if i % 2 else ''.join(it.split())
                    for i, it in enumerate(txt.split('"')))

def parse_pipe_source_qgis(s):
    """Parse layer source strings coming from QGIS.

    Supports two formats:
    - Pipe-separated: "url: '...|layername=Name'" (or without the leading "url:")
      Returns {'url': ..., 'layername': ...}
    - Ampersand-separated query: "crs=...&dpiMode=...&url=https://..."
      Returns a dict of parsed params (values URL-decoded).
    """
    s = s.strip().rstrip(',')
    m = re.search(r"url\s*:\s*(['\"])(.*)\\1", s)
    if m:
        content = m.group(2)
    else:
        content = re.sub(r'^\s*url\s*:\s*', '', s, flags=re.IGNORECASE).strip("'\"")

    # If pipe-separated parts are present, prefer that parsing
    if '|' in content:
        parts = content.split('|')
        result = {'url': parts[0]}
        for part in parts[1:]:
            if '=' in part:
                k, v = part.split('=', 1)
                result[k] = urllib.parse.unquote(v)
            else:
                result.setdefault('params', []).append(part)
        return result

    # If content contains space-separated tokens (URLs and key=val pairs), parse them.
    if ' ' in content:
        import shlex
        url_pattern = re.compile(r'https?://[^\s]+')
        tokens = shlex.split(content)
        result = {}
        urls = []
        for token in tokens:
            if url_pattern.match(token):
                urls.append(token)
            elif '=' in token:
                k, v = token.split('=', 1)
                v = urllib.parse.unquote(v)
                if k in result:
                    if isinstance(result[k], list):
                        result[k].append(v)
                    else:
                        result[k] = [result[k], v]
                else:
                    result[k] = v
            else:
                # free token, store under 'params'
                result.setdefault('params', []).append(token)

        if urls:
            # keep compatibility: 'url' is first URL, 'urls' contains all
            result['url'] = urls[0]
            if len(urls) > 1:
                result['urls'] = urls
        return result

        # Otherwise, try parsing as an URL-style query string with & separators
    if '&' in content or '=' in content:
        # parse_qsl decodes percent-encoding; keep blank values
        pairs = urllib.parse.parse_qsl(content, keep_blank_values=True)
        result = {}
        for k, v in pairs:
            if k in result:
                # turn repeated keys into lists
                if isinstance(result[k], list):
                    result[k].append(v)
                else:
                    result[k] = [result[k], v]
            else:
                result[k] = v
        return result

    # Fallback: return the raw content as url
    return {'url': content}

def is_layer_source_online(layer_or_uri):
    """Return True if the layer's data source contains an HTTP(S) URL.

    Accepts either a QGIS layer object (e.g. `QgsMapLayer`) or a
    data-source URI string. This treats any occurrence of `http://` or
    `https://` (including URLs inside parameters like `url=` or
    `/vsicurl/`) as remote. Everything else is considered local/relative.
    """
    # Accept a plain URI string
    if isinstance(layer_or_uri, str):
        src = layer_or_uri
    else:
        # Try common layer accessors; fall back gracefully
        try:
            src = layer_or_uri.source()
        except Exception:
            try:
                src = layer_or_uri.dataProvider().dataSourceUri()
            except Exception:
                return False

    if not src:
        return False

    # Decode URL-encoded characters
    src = urllib.parse.unquote(str(src))

    # Quick literal checks
    if 'http://' in src or 'https://' in src:
        return True

    # /vsicurl/http... is used by GDAL to wrap remote files
    if '/vsicurl/http' in src or '/vsicurl/https' in src:
        return True

    # look for url=<http...> patterns in query strings or provider URIs
    m = re.search(r'url=(https?://[^&\s]+)', src, flags=re.IGNORECASE)
    if m:
        return True

    # parse query parameters and check values
    try:
        q = urllib.parse.urlparse(src).query
        params = urllib.parse.parse_qs(q)
        for vals in params.values():
            for v in vals:
                if v.startswith('http://') or v.startswith('https://'):
                    return True
    except Exception:
        pass

    return False


def to_local_geojson(layer, apiideeStyle):
    # Recreates the JS loader used to load a local GeoJSON variable and add it to the map
    name = layer['nameLegend_file'].replace(" ", "").replace("-", "_").replace("—","_")
    sourceFolder = layer['sourceFolder']
    file = f"{name}.js"
    visible = str(layer['visible']).lower()
    zindex = layer['zIndex']

    if type(apiideeStyle) != list:
        return f"""
                var js_{name} = document.createElement("script");
                js_{name}.type = "text/javascript";
                js_{name}.async = false;
                js_{name}.src = ".{sourceFolder}/{file}";
                document.head.appendChild(js_{name});
                js_{name}.addEventListener('load', () => {{

                    mapajs.addLayers(
                        new M.layer.GeoJSON({{
                                source: {name}, 
                                name: '{name}',
                                legend: "{name}",
                                extract: true,
                            }}, {{
                            // aplica un estilo a la capa
                                style: {apiideeStyle},
                                visibility: {visible} // capa no visible en el mapa
                            }}, {{
                                opacity: 1 // aplica opacidad a la capa
                            }})
                    );

                    mapajs.getLayers().filter( (layer) => layer.legend == "{name}" )[0].setZIndex({zindex})

                }});
                """ 
    else:
        stylesList = apiideeStyle[1]
        apiideeStyle0 = apiideeStyle[0]
        return f"""
                var js_{name} = document.createElement("script");
                js_{name}.type = "text/javascript";
                js_{name}.async = false;
                js_{name}.src = ".{sourceFolder}/{file}";
                document.head.appendChild(js_{name});
                js_{name}.addEventListener('load', () => {{

                    {stylesList}

                    mapajs.addLayers(
                        new M.layer.GeoJSON({{
                                source: {name}, 
                                name: '{name}',
                                legend: "{name}",
                                extract: true,
                            }}, {{
                            // aplica un estilo a la capa
                                style: {apiideeStyle0},
                                visibility: {visible} // capa no visible en el mapa
                            }}, {{
                                opacity: 1 // aplica opacidad a la capa
                            }})
                    );

                    mapajs.getLayers().filter( (layer) => layer.legend == "{name}" )[0].setZIndex({zindex})

                }});
                """


def QGISStyle2apiideeStyle(qgisLayerLegend):
    # Port of the style conversion logic from the dialog into utilidades
    # Accept either a layer name (string) or an actual QgsMapLayer instance.
    qgisLayer = None
    if isinstance(qgisLayerLegend, str):
        layers = QgsProject.instance().mapLayersByName(qgisLayerLegend)
        if not layers:
            QgsMessageLog.logMessage(
                f"QGISStyle2apiideeStyle: no layer named {qgisLayerLegend}",
                "QGIS2APIIDEE",
                Qgis.Warning,
            )
            # Return a sensible default style if the layer can't be found
            return '''new M.style.Generic({
                            point: {
                                fill: {
                                    color: 'orange',
                                    opacity: 0.6,
                                },
                                stroke: {
                                    color: 'red',
                                    opacity: 0.8,
                                    width: 2, 
                                }
                            },
                            polygon: {
                                fill: {
                                    color: 'orange',
                                    opacity: 0.6,
                                },
                                stroke: {
                                    color: 'red',
                                    opacity: 0.8,
                                    width: 2, 
                                }
                            },
                            line: {
                                fill: {
                                    color: 'orange',
                                    opacity: 0.6,
                                },
                                stroke: {
                                    color: 'red',
                                    opacity: 0.8,
                                    width: 2, 
                                }
                            }
                        })'''
        qgisLayer = layers[0]
    else:
        # assume it's already a QgsMapLayer-like object
        qgisLayer = qgisLayerLegend

    # Some layer types (or invalid objects) may not have a renderer
    try:
        renderer = qgisLayer.renderer()
    except Exception:
        renderer = None

    if renderer is None:
        QgsMessageLog.logMessage(
            f"QGISStyle2apiideeStyle: layer renderer is None for {getattr(qgisLayer, 'name', qgisLayerLegend)}",
            "QGIS2APIIDEE",
            Qgis.Warning,
        )
        return '''new M.style.Generic({
                            point: {
                                fill: {
                                    color: 'orange',
                                    opacity: 0.6,
                                },
                                stroke: {
                                    color: 'red',
                                    opacity: 0.8,
                                    width: 2, 
                                }
                            },
                            polygon: {
                                fill: {
                                    color: 'orange',
                                    opacity: 0.6,
                                },
                                stroke: {
                                    color: 'red',
                                    opacity: 0.8,
                                    width: 2, 
                                }
                            },
                            line: {
                                fill: {
                                    color: 'orange',
                                    opacity: 0.6,
                                },
                                stroke: {
                                    color: 'red',
                                    opacity: 0.8,
                                    width: 2, 
                                }
                            }
                        })'''

    typeStyle = renderer.type()

    try:
        legendClassificationAttribute = qgisLayer.renderer().legendClassificationAttribute()
    except Exception:
        legendClassificationAttribute = "- - -"

    try:
        propertiesStyle = qgisLayer.renderer().symbol().symbolLayer(0).properties()
    except Exception:
        propertiesStyle = "- - -"

    try:
        CategorizedSymbolStyle = qgisLayer.renderer().symbol().symbolLayer(0).properties()
    except Exception:
        CategorizedSymbolStyle = "- - -"

    returnStyleDefault = True

    if typeStyle == 'singleSymbol':
        if 'color' in propertiesStyle:
            fillColorRGBA_list = propertiesStyle['color'].split(',')
        else:
            fillColorRGBA_list = [255, 153, 0, 255/2]

        fillColorRGB = 'rgb({r}, {g}, {b})'.format(
            r=int(fillColorRGBA_list[0]),
            g=int(fillColorRGBA_list[1]),
            b=int(fillColorRGBA_list[2]),
        )
        fillOpacity = int(fillColorRGBA_list[3]) / 255

        if 'outline_color' in propertiesStyle:
            strokeColorRGBA_list = propertiesStyle['outline_color'].split(',')
        else:
            strokeColorRGBA_list = [255, 102, 0, 255]

        strokeColorRGB = 'rgb({r}, {g}, {b})'.format(
            r=int(strokeColorRGBA_list[0]),
            g=int(strokeColorRGBA_list[1]),
            b=int(strokeColorRGBA_list[2]),
        )
        strokeOpacity = int(strokeColorRGBA_list[3]) / 255

        if 'outline_color' in propertiesStyle and 'outline_width' in propertiesStyle:
            strokeWidth = float(propertiesStyle['outline_width'])
        else:
            strokeWidth = float(2)

        apiideeStyle = '''new M.style.Generic({{
                                            point: {{
                                                fill: {{
                                                    color: '{fillColorRGB}',
                                                    opacity: {fillOpacity},
                                                }},
                                                stroke: {{
                                                    color: '{strokeColorRGB}',
                                                    opacity: {strokeOpacity},
                                                    width: {strokeWidth}, 
                                                }}
                                            }},
                                            polygon: {{
                                                fill: {{
                                                    color: '{fillColorRGB}',
                                                    opacity: {fillOpacity},
                                                }},
                                                stroke: {{
                                                    color: '{strokeColorRGB}',
                                                    opacity: {strokeOpacity},
                                                    width: {strokeWidth}, 
                                                }}
                                            }},
                                            line: {{
                                                fill: {{
                                                    color: '{fillColorRGB}',
                                                    opacity: {fillOpacity},
                                                }},
                                                stroke: {{
                                                    color: '{strokeColorRGB}',
                                                    opacity: {strokeOpacity},
                                                    width: {strokeWidth}, 
                                                }}
                                            }}
                                        }})'''.format(
                                                fillColorRGB=fillColorRGB,
                                                fillOpacity=fillOpacity,
                                                strokeColorRGB=strokeColorRGB,
                                                strokeOpacity=strokeOpacity,
                                                strokeWidth=strokeWidth,
                                        )
        returnStyleDefault = False

    elif typeStyle == 'basic':
        lineStyle = 'line:{}'
        polygonStyle = 'polygon:{}'
        pointStyle = 'point:{}'
        for style in qgisLayer.renderer().styles():
            propertiesStyle = style.symbol().symbolLayer(0).properties()

            if 'color' in propertiesStyle:
                fillColorRGBA_list = propertiesStyle['color'].split(',')
            else:
                fillColorRGBA_list = [255, 153, 0, 255/2]

            fillColorRGB = 'rgb({r}, {g}, {b})'.format(
                r=int(fillColorRGBA_list[0]),
                g=int(fillColorRGBA_list[1]),
                b=int(fillColorRGBA_list[2]),
            )
            fillOpacity = int(fillColorRGBA_list[3]) / 255

            if 'outline_color' in propertiesStyle:
                strokeColorRGBA_list = propertiesStyle['outline_color'].split(',')
            else:
                strokeColorRGBA_list = [255, 102, 0, 255]

            strokeColorRGB = 'rgb({r}, {g}, {b})'.format(
                r=int(strokeColorRGBA_list[0]),
                g=int(strokeColorRGBA_list[1]),
                b=int(strokeColorRGBA_list[2]),
            )
            strokeOpacity = int(strokeColorRGBA_list[3]) / 255

            if 'outline_color' in propertiesStyle and 'outline_width' in propertiesStyle:
                strokeWidth = float(propertiesStyle['outline_width'])
            else:
                strokeWidth = float(2)

            if str(style.symbol().type()) == 'SymbolType.Fill':
                polygonStyle = '''
                    polygon: {{
                                fill: {{
                                    color: '{fillColorRGB}',
                                    opacity: {fillOpacity},
                                }},
                                stroke: {{
                                    color: '{strokeColorRGB}',
                                    opacity: {strokeOpacity},
                                    width: {strokeWidth}, 
                                }}
                            }}
                '''.format(
                                fillColorRGB=fillColorRGB,
                                fillOpacity=fillOpacity,
                                strokeColorRGB=strokeColorRGB,
                                strokeOpacity=strokeOpacity,
                                strokeWidth=strokeWidth,
                        )
                returnStyleDefault = False

            elif str(style.symbol().type()) == 'SymbolType.Line':
                lineStyle = '''
                    line: {{
                                fill: {{
                                    color: '{fillColorRGB}',
                                    opacity: {fillOpacity},
                                }},
                                stroke: {{
                                    color: '{strokeColorRGB}',
                                    opacity: {strokeOpacity},
                                    width: {strokeWidth}, 
                                }}
                            }}
                '''.format(
                                fillColorRGB=fillColorRGB,
                                fillOpacity=fillOpacity,
                                strokeColorRGB=strokeColorRGB,
                                strokeOpacity=strokeOpacity,
                                strokeWidth=strokeWidth,
                        )
                returnStyleDefault = False

            elif str(style.symbol().type()) == 'SymbolType.Marker':
                pointStyle = '''
                    point: {{
                                fill: {{
                                    color: '{fillColorRGB}',
                                    opacity: {fillOpacity},
                                }},
                                stroke: {{
                                    color: '{strokeColorRGB}',
                                    opacity: {strokeOpacity},
                                    width: {strokeWidth}, 
                                }}
                            }}
                '''.format(
                                fillColorRGB=fillColorRGB,
                                fillOpacity=fillOpacity,
                                strokeColorRGB=strokeColorRGB,
                                strokeOpacity=strokeOpacity,
                                strokeWidth=strokeWidth,
                        )
                returnStyleDefault = False
            else:
                continue

        apiideeStyle = '''new M.style.Generic({{
                                    {point},
                                    {polygon},
                                    {line}
                        }})'''.format(
                                point=pointStyle,
                                polygon=polygonStyle,
                                line=lineStyle
                        )

    elif typeStyle == 'categorizedSymbol':
        apiideeStyleCategoric = ""
        categoricList = {}
        i = 0
        for categoria in qgisLayer.renderer().categories():
            i += 1
            valueAtribute = categoria.value()
            propertiesStyle = categoria.symbol().symbolLayer(0).properties()

            if 'color' in propertiesStyle:
                fillColorRGBA_list = propertiesStyle['color'].split(',')
            elif 'line_color' in propertiesStyle:
                fillColorRGBA_list = propertiesStyle['line_color'].split(',')
            else:
                fillColorRGBA_list = [255, 153, 0, 255/2]

            fillColorRGB = 'rgb({r}, {g}, {b})'.format(
                r=int(fillColorRGBA_list[0]),
                g=int(fillColorRGBA_list[1]),
                b=int(fillColorRGBA_list[2]),
            )
            fillOpacity = int(fillColorRGBA_list[3]) / 255

            if 'outline_color' in propertiesStyle:
                strokeColorRGBA_list = propertiesStyle['outline_color'].split(',')
            elif 'line_color' in propertiesStyle:
                strokeColorRGBA_list = propertiesStyle['line_color'].split(',')
            else:
                strokeColorRGBA_list = [255, 102, 0, 255]

            strokeColorRGB = 'rgb({r}, {g}, {b})'.format(
                r=int(strokeColorRGBA_list[0]),
                g=int(strokeColorRGBA_list[1]),
                b=int(strokeColorRGBA_list[2]),
            )
            strokeOpacity = int(strokeColorRGBA_list[3]) / 255

            if 'outline_color' in propertiesStyle and 'outline_width' in propertiesStyle:
                strokeWidth = float(propertiesStyle['outline_width'])
            else:
                strokeWidth = float(2)

            categoricList[valueAtribute] = "__{}_{}__".format(legendClassificationAttribute, i)
            apiideeStyle_category = ''' 
                                    var {legendClassificationAttribute}_{i} = new M.style.Generic({{
                                        point: {{
                                            fill: {{
                                                color: '{fillColorRGB}',
                                                opacity: {fillOpacity},
                                            }},
                                            stroke: {{
                                                color: '{strokeColorRGB}',
                                                opacity: {strokeOpacity},
                                                width: {strokeWidth}, 
                                            }}
                                        }},
                                        polygon: {{
                                            fill: {{
                                                color: '{fillColorRGB}',
                                                opacity: {fillOpacity},
                                            }},
                                            stroke: {{
                                                color: '{strokeColorRGB}',
                                                opacity: {strokeOpacity},
                                                width: {strokeWidth}, 
                                            }}
                                        }},
                                        line: {{
                                            fill: {{
                                                color: '{fillColorRGB}',
                                                opacity: {fillOpacity},
                                            }},
                                            stroke: {{
                                                color: '{strokeColorRGB}',
                                                opacity: {strokeOpacity},
                                                width: {strokeWidth}, 
                                            }}
                                        }}
                                    }}) \n'''.format(
                                            legendClassificationAttribute=legendClassificationAttribute,
                                            i=i,
                                            fillColorRGB=fillColorRGB,
                                            fillOpacity=fillOpacity,
                                            strokeColorRGB=strokeColorRGB,
                                            strokeOpacity=strokeOpacity,
                                            strokeWidth=strokeWidth,
                                    )

            apiideeStyleCategoric += apiideeStyle_category

        apiideeStyle = """new M.style.Category("{name}", {list})""".format(name=legendClassificationAttribute, list=categoricList)
        apiideeStyle = apiideeStyle.replace("'__","").replace("__'","")
        apiideeStyle = [apiideeStyle, apiideeStyleCategoric]
        returnStyleDefault = False

    if returnStyleDefault:
        apiideeStyle = '''new M.style.Generic({{
                            point: {{
                                fill: {{
                                    color: '{fillColorRGB}',
                                    opacity: {fillOpacity},
                                }},
                                stroke: {{
                                    color: '{strokeColorRGB}',
                                    opacity: {strokeOpacity},
                                    width: {strokeWidth}, 
                                }}
                            }},
                            polygon: {{
                                fill: {{
                                    color: '{fillColorRGB}',
                                    opacity: {fillOpacity},
                                }},
                                stroke: {{
                                    color: '{strokeColorRGB}',
                                    opacity: {strokeOpacity},
                                    width: {strokeWidth}, 
                                }}
                            }},
                            line: {{
                                fill: {{
                                    color: '{fillColorRGB}',
                                    opacity: {fillOpacity},
                                }},
                                stroke: {{
                                    color: '{strokeColorRGB}',
                                    opacity: {strokeOpacity},
                                    width: {strokeWidth}, 
                                }}
                            }}
                        }})'''.format(
                                fillColorRGB='orange',
                                fillOpacity=0.6,
                                strokeColorRGB='red',
                                strokeOpacity=0.8,
                                strokeWidth=2,
                        )

    return apiideeStyle


def save_vector_layer_as_geojson(layer, name):
    path = f"{layer['exportFolderSources']}/{name}.js"
    options = ["COORDINATE_PRECISION=6"]
    # `layer` here is a dict coming from the JSON representation; the actual
    # QgsVectorLayer object is stored under the 'QGISlayer' key.
    qgis_layer = layer.get('QGISlayer', layer)
    e, err = QgsVectorFileWriter.writeAsVectorFormat(
        qgis_layer, path + '_tmp', "utf-8",
        QgsCoordinateReferenceSystem("EPSG:4326"),
        'GeoJson', 0, layerOptions=options
    )
    if e == QgsVectorFileWriter.NoError:
        with open(path, mode="w", encoding="utf8") as f:
            f.write(f"var {name} = ")
            with open(path + '_tmp', encoding="utf8") as tmpFile:
                for line in tmpFile:
                    f.write(line.strip("\n\t "))
        try:
            os.remove(path + '_tmp')
        except Exception:
            pass
        return name
    else:
        QgsMessageLog.logMessage(
            f"Could not write json file {path}: {err}",
            "QGIS2APIIDEE", level=Qgis.Critical)
        return None


def get_url_param(uri, param, sep='&'):
    try:
        return next(filter(lambda k: f'{param}=' in k, uri.split(sep))).split('=')[1]
    except StopIteration:
        return None


def _layer_xyz(url, name, layer):
    return f"""
            mapajs.addXYZ(
                new IDEE.layer.XYZ({{
                    url: '{url}',
                    name: '{name}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_tms(url, name, layer):
    return f"""
            mapajs.addTMS(
                new IDEE.layer.TMS({{
                    url: '{url}',
                    name: '{name}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_geotiff(url, name, layer):
    return f"""
            mapajs.addGeoTIFF(
                new IDEE.layer.GeoTIFF({{
                    url: '{url}',
                    name: '{name}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_wmts(uri, name, layer):
    return f"""
            mapajs.addWMTS(
                new IDEE.layer.WMTS({{
                    url: '{layer['sourceParams_url']}',
                    name: '{layer['sourceParams_layers']}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                    useCapabilities:false,
                    matrixSet: '{layer['sourceParams_tileMatrixSet']}',
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_wms(uri, name, layer):
    return f"""
            mapajs.addWMS(
                new IDEE.layer.WMS({{
                    url: '{layer['sourceParams_url']}',
                    name: '{layer['sourceParams_layers']}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                    useCapabilities:false,
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_wfs(uri, name, layer):
    return f"""
            mapajs.addWFS(
                new IDEE.layer.WFS({{
                    url: '{layer['sourceParams_url']}',
                    name: '{layer['sourceParams_typename']}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_geojson(layer, name):
    return f"""
            mapajs.addLayers(
                new IDEE.layer.GeoJSON({{
                    url: '{layer['sourceParams_url']}',
                    name: '{layer['sourceParams_layername']}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_memory(layer, name):
    name = save_vector_layer_as_geojson(layer, name)
    # Prefer passing the actual QgsMapLayer object if available to avoid
    # lookups by name (which may fail for temporary layers).
    qgis_layer_obj = layer.get('QGISlayer', None)
    if qgis_layer_obj is not None:
        apiideeStyle = QGISStyle2apiideeStyle(qgis_layer_obj)
    else:
        apiideeStyle = QGISStyle2apiideeStyle(layer['nameLegend'])
    layerString = to_local_geojson(layer, apiideeStyle)
    return layerString


def _layer_ogc_api_features(uri, name, layer):
    return f"""
            mapajs.addOGCAPIFeatures(
                new IDEE.layer.OGCAPIFeatures({{
                    url: '{layer['sourceParams_url']}/collections/',
                    name: '{layer['sourceParams_typename']}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_libkml(layer, name):
    return f"""
            mapajs.addKML(
                new IDEE.layer.KML({{
                    url: '{layer['sourceParams_url']}',
                    layers: '{layer['sourceParams_layername']}',
                    name: '{name}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }},{{
                    extractStyles:true
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_mvt(url, name, layer):
    return f"""
            mapajs.addMVT(
                new IDEE.layer.MVT({{
                    url: '{url}',
                    name: '{name}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_maplibre(url, name, layer):
    return f"""
            mapajs.addMapLibre(
                new IDEE.layer.MapLibre({{
                    url: '{url}',
                    name: '{name}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_vector(layer, name):
    return f"""
            // Capa vectorial: {name}
        """


def JSONLayer2StringLayer(layer):
    tipo = layer['layerSourceType']
    name =  layer['nameLegend'].replace(" ", "").replace("-", "_").replace("—","_")
    layer['nameLegend_file'] = name
    uri = layer['dataSourceUri']

    is_online = is_layer_source_online(uri)
    if not is_online:
        tipo = 'Memory storage'
    else:
        uri = uri.replace("/vsicurl/", "").replace("/http", "http").replace("file://", "")
        layer['dataSourceUri'] = layer['dataSourceUri'].replace("/vsicurl/", "").replace("/http", "http").replace("file://", "")
        json_parse_uri_values = parse_pipe_source_qgis(layer['dataSourceUri'])
        if json_parse_uri_values:
            for key, value in json_parse_uri_values.items():
                layer[f"sourceParams_{key}"] = value
                print(f"sourceParams_{key}", value)


    #TODO: aplicar estilos a las capas vectoriales

    if tipo == 'XYZ': #OK
        url = urllib.parse.unquote(get_url_param(uri, 'url'))
        return _layer_xyz(url, name, layer) 
    elif tipo == 'TMS': #OK
        url = urllib.parse.unquote(get_url_param(uri, 'url'))
        return _layer_tms(url, name, layer)
    elif tipo == 'GeoTIFF': #OK
        return _layer_geotiff(uri, name, layer)
    elif tipo == 'WMTS':  #OK
        return _layer_wmts(uri, name, layer)
    elif tipo == 'WMS':  #OK
        return _layer_wms(uri, name, layer)
    elif tipo == 'OGC WFS (Web Feature Service)': #OK
        return _layer_wfs(uri, name, layer)
    elif tipo == 'GeoJSON': #OK
        return _layer_geojson(layer, name)
    elif tipo == 'Memory storage': #OK
        return _layer_memory(layer, name)
    elif tipo == 'OGC API - Features': #OK
        return _layer_ogc_api_features(uri, name, layer)
    elif tipo == 'LIBKML': #OK
        return _layer_libkml(layer, name)
    elif tipo == 'MVT': #OK
        url = get_url_param(uri, 'url')
        return _layer_mvt(url, name, layer)
    elif tipo == 'MapLibre': #OK
        url = get_url_param(uri, 'styleUrl')
        return _layer_maplibre(url, name, layer)
    elif layer['QGISlayer'].type() == QgsMapLayer.VectorLayer:
        return _layer_vector(layer, name)
    else:
        return ''


