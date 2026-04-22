from PyQt5.QtWidgets import QTableWidgetItem, QHBoxLayout, QWidget, QCheckBox
from PyQt5 import QtCore
from qgis.core import QgsMapLayer


def create_checkbox_widget(checked=True):
    cb = QCheckBox()
    cb.setChecked(checked)
    layout = QHBoxLayout()
    layout.addWidget(cb)
    layout.setAlignment(cb, QtCore.Qt.AlignCenter)
    widget = QWidget()
    widget.setLayout(layout)
    return widget


def get_layer_type_str(layer):
    if layer.type() == QgsMapLayer.VectorLayer:
        return "Vector"
    elif layer.type() == QgsMapLayer.RasterLayer:
        return "Ráster"
    elif layer.type() == QgsMapLayer.VectorTileLayer:
        return "Vector"
    else:
        return "---"


def get_layer_storage_type(layer):
    uri = layer.dataProvider().dataSourceUri()
    if uri == '':
        uri = layer.source()

    t = layer.type()

    if t == QgsMapLayer.VectorLayer:
        try:
            return layer.dataProvider().storageType()
        except:
            return '---'

    if t == QgsMapLayer.VectorTileLayer:
        if "styleUrl=" in uri:
            return "MapLibre"
        elif "%7By%7D" in uri or "{y}" in uri:
            return "MVT"
        else:
            return "---"

    if t == QgsMapLayer.RasterLayer:
        if "%7By%7D" in uri or "{y}" in uri:
            return "XYZ"
        if "%7B-y%7D" in uri or "{-y}" in uri:
            return "TMS"
        if "tileMatrixSet" in uri:
            return "WMTS"
        try:
            if ("GeoTIFF" in layer.htmlMetadata() and "/vsicurl/" in uri):
                return "GeoTIFF"
        except:
            pass
        if not 'url=' in uri:
            return "---"
        if layer.providerType() == 'wms':
            return "WMS"
        return "---"

    return "---"


def add_layer_row(table, layer):
    rowPosition = table.rowCount()
    table.insertRow(rowPosition)

    # Overlay selector
    table.setCellWidget(rowPosition, 0, create_checkbox_widget(True))

    # Visible selector
    table.setCellWidget(rowPosition, 1, create_checkbox_widget(True))

    # Layer type
    item = QTableWidgetItem(get_layer_type_str(layer))
    item.setTextAlignment(QtCore.Qt.AlignCenter)
    table.setItem(rowPosition, 2, item)

    # Storage / source type
    storage = get_layer_storage_type(layer)
    item = QTableWidgetItem(storage)
    item.setTextAlignment(QtCore.Qt.AlignCenter)
    table.setItem(rowPosition, 3, item)

    # Layer name
    item = QTableWidgetItem(layer.name())
    item.setTextAlignment(QtCore.Qt.AlignCenter)
    table.setItem(rowPosition, 4, item)
