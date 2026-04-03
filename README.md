# QGIS2API-IDEE

Complemento para QGIS que mejora la experiencia de usuario a la hora de crear visualizadores con API-CNIG.

Realiza, para aquellas fuentes de datos compatibles, un mapeo entre las fuentes cargadas en el mapa de QGIS y las fuentes que están dadas de alta en API-CNIG. Además, descarga en un objeto JS aquellos datos en local evitando problemas de CORS.

El código exportado se encuentra sin minimizar para permitir una edición posterior del visualizador. La documentación para añadir y modificar contenido del visualizador se encuentra en la sección de **URL del proyecto API-CNIG**

### Instalación

1. La primera forma de instalar este complemento es directamente desde QGIS  (complementos -> administrar e instalar complementos). Si se realiza mediante este punto, es importante habilitar los complementos experimentales para poder utilizarlo (complementos -> administrar e instalar complementos´-> configuración -> habilitar también los complementos experimentales)

2. Desde el repositorio oficial de complementos [https://plugins.qgis.org/plugins/qgis2apiidee/](https://plugins.qgis.org/plugins/qgis2apiidee/). Se descargaría el zip y se importaría desde complementos -> administrar e instalar complementos -> instalar a partir de zip.


3. Desde este repositorio, en la parte de despliegues (releases):  [https://github.com/IngenieroGeomatico/QGIS2API-IDEE/releases](https://github.com/IngenieroGeomatico/QGIS2API-IDEE/releases). Una vez descargado, se instalaría en QGIS desde complementos -> administrar e instalar complementos -> instalar a partir de zip.

### ¿Qué permite hacer este complemento?

1. Seleccionar las capas a exportar y su visibilidad inicial
2. Personalizar el visualizador con una serie de controles del mapa
3. Seleccionar una carpeta de exportación del visualizador y los datos utilizados.

### URL del proyecto API-CNIG

- Página oficial del proyecto: [https://plataforma.idee.es/cnig-api](https://plataforma.idee.es/cnig-api)

- API-DOC: [https://componentes.cnig.es/api-core/doc/](https://componentes.cnig.es/api-core/doc/)

- Repositorio del código: [https://github.com/IGN-CNIG/API-CNIG](https://github.com/IGN-CNIG/API-CNIG)

- Complementos o extensiones: [https://componentes.cnig.es/api-core/test.html](https://componentes.cnig.es/api-core/test.html)

- Documentación en formato WIKI: [https://github.com/IGN-CNIG/API-CNIG/wiki](https://github.com/IGN-CNIG/API-CNIG/wiki)

- Ejemplos de uso: [https://componentes.cnig.es/GaleriaEjemplos_apiidee/](https://componentes.cnig.es/GaleriaEjemplos_apiidee/)
