import os
import urllib.parse
import re
import json
import hashlib
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


def _parse_color(props, keys=('color', 'line_color', 'fill_color')):
    """Return (rgb_str, opacity, width) where width may be None."""
    if not isinstance(props, dict):
        return ('rgb(255,153,0)', 0.6, 2.0)
    for k in keys:
        if k in props:
            parts = props[k].split(',')
            try:
                r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            except Exception:
                r, g, b = 255, 153, 0
            a = float(parts[3]) if len(parts) > 3 else 255
            rgb = f"rgb({r}, {g}, {b})"
            opacity = a / 255 if a else 1.0
            return (rgb, opacity)
    return ('rgb(255,153,0)', 0.6)

def _make_generic_js(fill_rgb, fill_opacity, stroke_rgb, stroke_opacity, stroke_width):
    return '''new M.style.Generic({
        point: {
            fill: { color: '%s', opacity: %s },
            stroke: { color: '%s', opacity: %s, width: %s }
        },
        polygon: {
            fill: { color: '%s', opacity: %s },
            stroke: { color: '%s', opacity: %s, width: %s }
        },
        line: {
            fill: { color: '%s', opacity: %s },
            stroke: { color: '%s', opacity: %s, width: %s }
        }
    })''' % (
        fill_rgb, fill_opacity, stroke_rgb, stroke_opacity, stroke_width,
        fill_rgb, fill_opacity, stroke_rgb, stroke_opacity, stroke_width,
        fill_rgb, fill_opacity, stroke_rgb, stroke_opacity, stroke_width
    )

def QGISStyle2apiideeStyle(qgisLayerLegend):
    """
    Convierte el renderer de QGIS a [style_code, prelude_code].

    - Siempre devuelve una lista: [style_code, prelude_code]
      * style_code: expresión JS (p.ej. 'new M.style.Generic(...)' o 'new M.style.Category(...)')
      * prelude_code: código JS auxiliar (p.ej. 'var style_x = new M.style.Generic(...);') o '' si no aplica
    """
    qgisLayer = None
    if isinstance(qgisLayerLegend, str):
        layers = QgsProject.instance().mapLayersByName(qgisLayerLegend)
        if not layers:
            QgsMessageLog.logMessage(
                f"QGISStyle2apiideeStyle: no layer named {qgisLayerLegend}",
                "QGIS2APIIDEE",
                Qgis.Warning,
            )
            return [_make_generic_js('orange', 0.6, 'red', 0.8, 2), ""]
        qgisLayer = layers[0]
    else:
        qgisLayer = qgisLayerLegend

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
        return [_make_generic_js('orange', 0.6, 'red', 0.8, 2), ""]

    # propiedades por defecto del símbolo (si existen)
    try:
        default_props = renderer.symbol().symbolLayer(0).properties()
    except Exception:
        default_props = {}

    typeStyle = renderer.type() if hasattr(renderer, 'type') else None

    # SINGLE / fallback -> Generic
    if typeStyle == 'singleSymbol' or typeStyle is None:
        fill_rgb, fill_opacity = _parse_color(default_props, keys=('color','fill_color'))
        stroke_rgb, stroke_opacity = _parse_color(default_props, keys=('outline_color','line_color'))
        stroke_width = float(default_props.get('outline_width', 2))
        return [_make_generic_js(fill_rgb, fill_opacity, stroke_rgb, stroke_opacity, stroke_width), ""]

    # BASIC: intentamos componer, pero devolvemos un Generic simple como fallback
    if typeStyle == 'basic':
        try:
            # intentamos extraer alguna info por sub-roles (no obligatoria)
            for style in renderer.styles():
                props = style.symbol().symbolLayer(0).properties()
                fill_rgb, fill_opacity = _parse_color(props, keys=('color','fill_color'))
                stroke_rgb, stroke_opacity = _parse_color(props, keys=('outline_color','line_color'))
                stroke_width = float(props.get('outline_width', 2))
                # devolvemos el primer estilo relevante como Generic (simple, consistente)
                return [_make_generic_js(fill_rgb, fill_opacity, stroke_rgb, stroke_opacity, stroke_width), ""]
        except Exception:
            pass
        # fallback con propiedades por defecto
        fill_rgb, fill_opacity = _parse_color(default_props)
        stroke_rgb, stroke_opacity = _parse_color(default_props, keys=('outline_color','line_color'))
        stroke_width = float(default_props.get('outline_width', 2))
        return [_make_generic_js(fill_rgb, fill_opacity, stroke_rgb, stroke_opacity, stroke_width), ""]

    # CATEGORIZED: devolvemos [style_code, prelude_code]
    if typeStyle == 'categorizedSymbol':
        try:
            legend_attr = renderer.legendClassificationAttribute()
        except Exception:
            legend_attr = getattr(qgisLayer, 'name', 'category')

        prelude_parts = []
        mapping_entries = []
        for cat in renderer.categories():
            val = cat.value()
            try:
                props = cat.symbol().symbolLayer(0).properties()
            except Exception:
                props = {}
            fill_rgb, fill_opacity = _parse_color(props, keys=('color','fill_color'))
            stroke_rgb, stroke_opacity = _parse_color(props, keys=('outline_color','line_color'))
            stroke_width = float(props.get('outline_width', 2))

            var_hash = hashlib.sha1(f"{legend_attr}:{val}".encode()).hexdigest()[:8]
            var_name = f"style_{var_hash}"
            prelude_parts.append(f"var {var_name} = {_make_generic_js(fill_rgb, fill_opacity, stroke_rgb, stroke_opacity, stroke_width)};")
            mapping_entries.append(f"{json.dumps(str(val))}: {var_name}")

        prelude_code = "\n".join(prelude_parts)
        mapping_code = ", ".join(mapping_entries)
        style_code = f'new M.style.Category("{legend_attr}", {{{mapping_code}}})'
        return [style_code, prelude_code]

    # Otros casos -> fallback genérico
    fill_rgb, fill_opacity = _parse_color(default_props)
    stroke_rgb, stroke_opacity = _parse_color(default_props, keys=('outline_color','line_color'))
    stroke_width = float(default_props.get('outline_width', 2))
    return [_make_generic_js(fill_rgb, fill_opacity, stroke_rgb, stroke_opacity, stroke_width), ""]

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


def _layer_wfs(uri, name, layer, apiideeStyle):
    return f"""

            {apiideeStyle[1]}

            mapajs.addWFS(
                new IDEE.layer.WFS({{
                    url: '{layer['sourceParams_url']}',
                    name: '{layer['sourceParams_typename']}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }},{{
                    style: {apiideeStyle[0]},
                    visibility: {str(layer['visible']).lower()},
                }})
            );
            mapajs.getLayers().filter((layer) => layer.legend == "{name}")[0].setZIndex({layer['zIndex']})
        """


def _layer_geojson(layer, name, apiideeStyle):
    return f"""

            {apiideeStyle[1]}

            mapajs.addLayers(
                new IDEE.layer.GeoJSON({{
                    url: '{layer['sourceParams_url']}',
                    name: '{layer['sourceParams_layername']}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }},{{
                    style: {apiideeStyle[0]},
                    visibility: {str(layer['visible']).lower()},
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


def _layer_ogc_api_features(uri, name, layer,apiideeStyle):
    return f"""

            {apiideeStyle[1]}
             
            mapajs.addOGCAPIFeatures(
                new IDEE.layer.OGCAPIFeatures({{
                    url: '{layer['sourceParams_url']}/collections/',
                    name: '{layer['sourceParams_typename']}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }},{{
                    style: {apiideeStyle[0]},
                    visibility: {str(layer['visible']).lower()},
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


def _layer_mvt(url, name, layer,apiideeStyle):
    return f"""

            {apiideeStyle[1]}

            
            mapajs.addMVT(
                new IDEE.layer.MVT({{
                    url: '{url}',
                    name: '{name}',
                    visibility: {str(layer['visible']).lower()},
                    legend: '{name}',
                }},{{
                    style: {apiideeStyle[0]},
                    visibility: {str(layer['visible']).lower()},
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


    if tipo == 'XYZ': 
        url = urllib.parse.unquote(get_url_param(uri, 'url'))
        return _layer_xyz(url, name, layer) 
    elif tipo == 'TMS':
        url = urllib.parse.unquote(get_url_param(uri, 'url'))
        return _layer_tms(url, name, layer)
    elif tipo == 'GeoTIFF':
        return _layer_geotiff(uri, name, layer)
    elif tipo == 'WMTS':
        return _layer_wmts(uri, name, layer)
    elif tipo == 'WMS':
        return _layer_wms(uri, name, layer)
    elif tipo == 'OGC WFS (Web Feature Service)':
        qgis_layer_obj = layer.get('QGISlayer', None)
        if qgis_layer_obj is not None:
            apiideeStyle = QGISStyle2apiideeStyle(qgis_layer_obj)
        else:
            apiideeStyle = QGISStyle2apiideeStyle(layer['nameLegend'])
        return _layer_wfs(uri, name, layer, apiideeStyle)
    elif tipo == 'GeoJSON':
        qgis_layer_obj = layer.get('QGISlayer', None)
        if qgis_layer_obj is not None:
            apiideeStyle = QGISStyle2apiideeStyle(qgis_layer_obj)
        else:
            apiideeStyle = QGISStyle2apiideeStyle(layer['nameLegend'])
        return _layer_geojson(layer, name, apiideeStyle)
    elif tipo == 'Memory storage':
        return _layer_memory(layer, name)
    elif tipo == 'OGC API - Features':
        qgis_layer_obj = layer.get('QGISlayer', None)
        if qgis_layer_obj is not None:
            apiideeStyle = QGISStyle2apiideeStyle(qgis_layer_obj)
        else:
            apiideeStyle = QGISStyle2apiideeStyle(layer['nameLegend'])
        return _layer_ogc_api_features(uri, name, layer, apiideeStyle)
    elif tipo == 'LIBKML':
        return _layer_libkml(layer, name)
    elif tipo == 'MVT':
        url = get_url_param(uri, 'url')
        qgis_layer_obj = layer.get('QGISlayer', None)
        if qgis_layer_obj is not None:
            apiideeStyle = QGISStyle2apiideeStyle(qgis_layer_obj)
        else:
            apiideeStyle = QGISStyle2apiideeStyle(layer['nameLegend'])
        return _layer_mvt(url, name, layer, apiideeStyle)
    elif tipo == 'MapLibre':
        url = get_url_param(uri, 'styleUrl')
        return _layer_maplibre(url, name, layer)
    elif layer['QGISlayer'].type() == QgsMapLayer.VectorLayer:
        return _layer_vector(layer, name)
    else:
        return ''


