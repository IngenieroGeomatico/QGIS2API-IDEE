import os
import urllib.parse
from qgis.core import QgsVectorFileWriter, QgsCoordinateReferenceSystem, QgsMessageLog
from qgis.core import QgsMapLayer
from qgis.utils import Qgis


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
