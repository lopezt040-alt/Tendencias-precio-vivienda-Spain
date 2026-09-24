# Tendencias de vivienda en España

Scripts en Python para obtener, almacenar y clasificar datos de precios de venta y alquiler de vivienda en España, y para ver qué características se buscan más.

## Contenido

| Archivo | Qué hace |
|---|---|
| `tendencias_vivienda.py` | Descarga índices de precios de venta y alquiler del INE y el interés de búsqueda por características (terraza, ascensor, garaje...) desde Google Trends. Genera CSV. |
| `cargar_serpavi.py` | Carga el Excel del SERPAVI (Ministerio de Vivienda) en SQLite, pasándolo de formato ancho a largo. |
| `almacenar_clasificar.py` | Guarda datos en SQLite y los clasifica por nivel de precio (cuartiles) y tendencia (variación interanual). |

## Instalación

```
pip install -r requirements.txt
```

## Uso

### 1. Índices del INE y búsquedas (Google Trends)

```
python tendencias_vivienda.py
```

Genera `precios_venta.csv`, `precios_alquiler.csv` y `busquedas_caracteristicas.csv`.

> Comprueba los IDs de tabla del INE en la constante `INE_TABLAS` del script antes de usarlo. Se pueden verificar en [ine.es](https://www.ine.es).

### 2. Alquiler por municipio con el SERPAVI

1. Descarga el Excel **"BD Sistema Estatal Índices de Alquiler de Vivienda"** desde la [página del SERPAVI](https://www.mivau.gob.es/vivienda/alquila-bien-es-tu-derecho/serpavi) del Ministerio de Vivienda y Agenda Urbana.
2. Cárgalo y clasifícalo:

```
python cargar_serpavi.py ARCHIVO.xlsx --hoja Municipios --tipologia VC
python almacenar_clasificar.py clasificar --tipo alquiler_municipios --lag 1
python almacenar_clasificar.py resumen --tipo alquiler_municipios
```

- `--hoja`: `CCAA`, `Provincias`, `Municipios`, `Distritos` o `Secciones censales` (la última es muy pesada).
- `--tipologia`: `VC` (vivienda colectiva, pisos) o `VU` (unifamiliar o rural).
- `--lag`: periodos hacia atrás para calcular la variación (1 en datos anuales, 4 en trimestrales).

### 3. Cargar otros CSV o Excel

```
python almacenar_clasificar.py cargar precios_venta.csv --fuente INE --tipo venta \
    --territorio serie --periodo fecha --valor valor
python almacenar_clasificar.py clasificar --tipo venta --lag 4
```

## Clasificación

- **Nivel de precio:** bajo, medio, alto o muy alto (cuartiles dentro del conjunto cargado).
- **Tendencia:** bajada (< -1 %), estable (-1 % a 1 %), subida moderada (1 % a 5 %) o subida fuerte (> 5 %). Los umbrales se pueden cambiar al principio de `almacenar_clasificar.py`.

## Limitaciones

- En municipios pequeños la variación anual es muy volátil, porque el SERPAVI exige un mínimo de 10 viviendas por territorio. Interprétala con cuidado.
- Los datos del INE son índices (base 100), no euros. Los euros por m² del alquiler proceden del SERPAVI.
- No se hace scraping de portales inmobiliarios, porque incumple sus condiciones de uso.

## Fuentes de datos

- INE: índices de precios de vivienda y de alquiler.
- Ministerio de Vivienda y Agenda Urbana: SERPAVI.
- Google Trends, a través de `pytrends`.

Los datos pertenecen a sus respectivos organismos. Consulta sus condiciones de reutilización.
