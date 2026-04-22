import os
import urllib.parse
from qgis.core import QgsVectorFileWriter, QgsCoordinateReferenceSystem, QgsMessageLog
from qgis.core import QgsMapLayer
from qgis.utils import Qgis
from qgis.core import QgsProject
from PyQt5 import QtCore


def remove_spaces(txt):
    return '"'.join(it if i % 2 else ''.join(it.split())
                    for i, it in enumerate(txt.split('"')))


def to_local_geojson(layer, layerGJSON, apiideeStyle):
    # Recreates the JS loader used to load a local GeoJSON variable and add it to the map
    name = layer['nameLegend'].replace(" ", "").replace("—", "_")
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
    qgisLayer = QgsProject.instance().mapLayersByName(qgisLayerLegend)[0]

    typeStyle = qgisLayer.renderer().type()

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


def save_vector_layer_as_geojson(layer, export_folder, name):
    path = f"{export_folder}/{name}.js"
    options = ["COORDINATE_PRECISION=6"]
    e, err = QgsVectorFileWriter.writeAsVectorFormat(
        layer, path + '_tmp', "utf-8",
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
                    url: '{uri}',
                    name: '{name}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_wms(uri, name, layer):
    return f"""
            mapajs.addWMS(
                new IDEE.layer.WMS({{
                    url: '{uri}',
                    name: '{name}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_wfs(uri, name, layer):
    return f"""
            mapajs.addWFS(
                new IDEE.layer.WFS({{
                    url: '{uri}',
                    name: '{name}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_geojson(layer, name):
    return f"""
            mapajs.addGeoJSON(
                new IDEE.layer.GeoJSON({{
                    url: '{layer['dataSourceUri']}',
                    name: '{name}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_memory(layer, name):
    return f"""
            // Capa en memoria: {name}
        """


def _layer_ogc_api_features(uri, name, layer):
    return f"""
            mapajs.addOGCAPIFeatures(
                new IDEE.layer.OGCAPIFeatures({{
                    url: '{uri}',
                    name: '{name}',
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
                    url: '{layer['dataSourceUri']}',
                    name: '{name}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
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
                    styleUrl: '{url}',
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
    name = layer['nameLegend'].replace(" ", "").replace("—", "_")
    uri = layer['dataSourceUri']

    if tipo == 'XYZ':
        url = urllib.parse.unquote(get_url_param(uri, 'url'))
        return _layer_xyz(url, name, layer)
    elif tipo == 'TMS':
        url = urllib.parse.unquote(get_url_param(uri, 'url'))
        return _layer_tms(url, name, layer)
    elif tipo == 'GeoTIFF':
        url = uri.replace("/vsicurl/", "")
        return _layer_geotiff(url, name, layer)
    elif tipo == 'WMTS':
        return _layer_wmts(uri, name, layer)
    elif tipo == 'WMS':
        return _layer_wms(uri, name, layer)
    elif tipo == 'OGC WFS (Web Feature Service)':
        return _layer_wfs(uri, name, layer)
    elif tipo == 'GeoJSON':
        return _layer_geojson(layer, name)
    elif tipo == 'Memory storage':
        return _layer_memory(layer, name)
    elif tipo == 'OGC API - Features':
        return _layer_ogc_api_features(uri, name, layer)
    elif tipo == 'LIBKML':
        return _layer_libkml(layer, name)
    elif tipo == 'MVT':
        url = get_url_param(uri, 'url')
        return _layer_mvt(url, name, layer)
    elif tipo == 'MapLibre':
        url = get_url_param(uri, 'styleUrl')
        return _layer_maplibre(url, name, layer)
    elif layer['QGISlayer'].type() == QgsMapLayer.VectorLayer:
        return _layer_vector(layer, name)
    else:
        return ''
