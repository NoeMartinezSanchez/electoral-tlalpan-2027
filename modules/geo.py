"""
geo.py
======

Carga de la geografía electoral **real** de Tlalpan (Pestaña 1) a partir del
**Marco Geográfico Electoral del IECM 2021** (KML de demarcaciones
territoriales). El archivo clave es:

    documentos/Marco geografico electoral/circunscripcionesDT/12.kml

que contiene las **355 secciones electorales de Tlalpan** con:
- `Sección` (id), `Distrito_Federal`, `Distrito_Local`, `Circunscripción`
- `Padrón_Electoral` y `Lista_Nominal` (corte PE/LN 2021)
- `Población_INEGI_2010`  (NOTA: censo 2010, no 2020)
- Geometría (polígono) en CRS **EPSG:4326 (WGS84 lon/lat)**

Nunca se inventan coordenadas: la fuente es la capa oficial del IECM. Si el
archivo no está disponible, se cae al set ficticio de `modules.data` (demo).

Pendiente (se cruzará después): vivienda y población **Censo 2020** (INEGI) para
métricas de vivienda; el `tipo_zona` es provisional.
"""

import json
import os
import xml.etree.ElementTree as ET

import pandas as pd

try:
    from shapely.geometry import Polygon, mapping as shapely_mapping
    SHAPELY_OK = True
except Exception:
    SHAPELY_OK = False

NS = {'k': 'http://www.opengis.net/kml/2.2'}

RUTA_KML_TLALPAN = os.path.join('documentos', 'Marco geografico electoral',
                                'circunscripcionesDT', '12.kml')
RUTA_SHP_COLONIAS = os.path.join('documentos', 'inegi', 'colonias_iecm.shp')
RUTA_LOCAL_INE = os.path.join('data', 'secciones_ine.csv')

# CSVs de referencia COMMITEADOS (para que funcione en Cloud sin documentos/):
# incluyen la geometría simplificada como columna geometry_geojson (JSON en texto).
RUTA_REF_SECCIONES = os.path.join('referencia', 'marcos', 'secciones_iecm.csv')
RUTA_REF_COLONIAS = os.path.join('referencia', 'marcos', 'colonias_iecm.csv')

TOLERANCIA_SIMPLIFICACION = 0.001  # grados (~110 m)

# Columnas del DataFrame normalizado (Pestaña 1 + Mongo)
COLUMNAS_INE = ['id_seccion', 'nombre', 'distrito', 'distrito_federal',
                'circunscripcion', 'lat', 'lon', 'poblacion',
                'padron_electoral', 'lista_nominal', 'tipo_zona',
                'area', 'geometry_geojson']

# Columnas de la capa de colonias del IECM (documentos/inegi/colonias_iecm.shp)
COLUMNAS_COLONIAS = ['cve', 'nombre', 'distrito', 'lat', 'lon', 'area',
                     'geometry_geojson']


def _coord_lista(anillo) -> list:
    """Convierte un <coordinates> de KML en lista de tuplas (lon, lat)."""
    puntos = []
    for token in anillo.text.strip().split():
        lon, lat, *_rest = token.split(',')
        if lon:
            puntos.append((float(lon), float(lat)))
    return puntos


def _poligono_de_placemark(pm) -> object:
    """Construye el polígono shapely más grande a partir del Placemark."""
    if not SHAPELY_OK:
        return None
    anillos = []
    for outer in pm.findall('.//k:outerBoundaryIs', NS):
        linear = outer.find('k:LinearRing', NS)
        if linear is None:
            continue
        coords = linear.find('k:coordinates', NS)
        if coords is not None and coords.text and coords.text.strip():
            puntos = _coord_lista(coords)
            if len(puntos) >= 4:
                anillos.append(Polygon(puntos))
    if not anillos:
        return None
    return max(anillos, key=lambda p: p.area)


def _centroide_fallback(pm) -> tuple:
    """Centroide aproximado (promedio de vértices) si no hay shapely."""
    xs, ys = [], []
    for outer in pm.findall('.//k:outerBoundaryIs', NS):
        linear = outer.find('k:LinearRing', NS)
        if linear is None:
            continue
        coords = linear.find('k:coordinates', NS)
        if coords is not None and coords.text and coords.text.strip():
            for lon, lat, *_r in (tok.split(',') for tok in coords.text.strip().split()):
                xs.append(float(lon))
                ys.append(float(lat))
    if xs:
        return (sum(xs) / len(xs), sum(ys) / len(ys))
    return (0.0, 0.0)


def parsear_kml_secciones(ruta: str = RUTA_KML_TLALPAN) -> pd.DataFrame:
    """
    Parsea un KML de secciones del Marco Geográfico Electoral (IECM) y extrae,
    por sección: id, distritos, padrón/lista nominal, población INEGI 2010,
    centroide (lat, lon), área y geometría simplificada (GeoJSON).

    Retorna:
        pd.DataFrame con las columnas de `COLUMNAS_INE` (vacío si no hay archivo).
    """
    if not os.path.exists(ruta):
        print(f'ADVERTENCIA: no existe el KML del marco electoral: {ruta}')
        return pd.DataFrame()
    # Preferir el CSV de referencia COMMITEADO (funciona en Cloud sin documentos/)
    df_ref = _leer_csv_referencia(RUTA_REF_SECCIONES, 'secciones')
    if not df_ref.empty:
        return df_ref
    try:
        tree = ET.parse(ruta)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f'ADVERTENCIA: no se pudo parsear el KML: {e}')
        return pd.DataFrame()

    filas = []
    for pm in root.findall('.//k:Placemark', NS):
        datos = {s.get('name'): (s.text or '').strip()
                 for s in pm.findall('.//k:SimpleData', NS)}
        seccion = datos.get('Sección', '')
        if not seccion or not seccion.isdigit():
            continue  # Placemarks resumen (Demarcación/Distrito) sin sección
        poligono = _poligono_de_placemark(pm)
        if poligono is not None:
            lon, lat = poligono.centroid.x, poligono.centroid.y
            area = poligono.area
            geometry_geojson = shapely_mapping(
                poligono.simplify(TOLERANCIA_SIMPLIFICACION,
                                  preserve_topology=True))
        else:
            lon, lat = _centroide_fallback(pm)
            area = 0.0
            geometry_geojson = None
        id_sec = int(seccion)
        nombre = f"Sección {id_sec} · {datos.get('Demarcación_Territorial', 'Tlalpan')}"
        filas.append({
            'id_seccion': id_sec,
            'nombre': nombre,
            'distrito': datos.get('Distrito_Local', ''),
            'distrito_federal': datos.get('Distrito_Federal', ''),
            'circunscripcion': datos.get('Circunscripción', ''),
            'lat': lat,
            'lon': lon,
            'poblacion': int(datos.get('Población_INEGI_2010') or 0),
            'padron_electoral': int(datos.get('Padrón_Electoral') or 0),
            'lista_nominal': int(datos.get('Lista_Nominal') or 0),
            'tipo_zona': 'urbana',  # provisional; se refinará con INEGI 2020
            'area': area,
            'geometry_geojson': geometry_geojson,
        })
    df = pd.DataFrame(filas, columns=COLUMNAS_INE)
    if df.empty:
        return df
    df['id_seccion'] = df['id_seccion'].astype(int)
    return df.sort_values('id_seccion').reset_index(drop=True)


def _leer_csv_ine(ruta: str) -> pd.DataFrame:
    """Lee el CSV normalizado de secciones (sin geometría)."""
    for encoding in ('utf-8-sig', 'latin-1'):
        try:
            return pd.read_csv(ruta, encoding=encoding)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    raise ValueError(f'No se pudo decodificar {ruta}')


def _columna_geometry(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte la columna geometry_geojson (JSON en texto) a dicts."""
    if 'geometry_geojson' in df.columns:
        def _parsea(v):
            if isinstance(v, dict):
                return v
            if pd.isna(v) or not v:
                return None
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        df['geometry_geojson'] = df['geometry_geojson'].apply(_parsea)
    return df


def _leer_csv_referencia(ruta: str, nombre: str) -> pd.DataFrame:
    """
    Lee un CSV de referencia COMMITEADO (referencia/marcos/*.csv) y convierte la
    geometría JSON en texto a dicts. Devuelve vacío si no existe/falla.
    """
    if not os.path.exists(ruta):
        print(f'ADVERTENCIA: no existe el CSV de referencia {ruta}')
        return pd.DataFrame()
    try:
        df = pd.read_csv(ruta, encoding='utf-8-sig')
        return _columna_geometry(df).reset_index(drop=True)
    except Exception as e:
        print(f'ADVERTENCIA: no se pudo leer {ruta}: {e}')
        return pd.DataFrame()


def generar_csv_ine(ruta_salida: str = RUTA_LOCAL_INE) -> dict:
    """
    Genera `data/secciones_ine.csv` (sin geometría) a partir del KML del IECM.
    Útil como respaldo ligero y para depuración.

    Retorna:
        dict con 'ok', 'n' y 'ruta'.
    """
    df = parsear_kml_secciones()
    if df.empty:
        return {'ok': False, 'n': 0, 'ruta': ruta_salida}
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)
    columnas_csv = [c for c in COLUMNAS_INE if c != 'geometry_geojson']
    df[columnas_csv].to_csv(ruta_salida, index=False, encoding='utf-8-sig')
    print(f'GEO: CSV de secciones generado en {ruta_salida} ({len(df)} secciones).')
    return {'ok': True, 'n': len(df), 'ruta': ruta_salida}


def descargar_secciones_ine() -> pd.DataFrame:
    """
    Devuelve las secciones reales de Tlalpan: si existe `data/secciones_ine.csv`
    lo usa; si no, parsea el KML del IECM (fuente completa, incluye geometría).

    Retorna:
        pd.DataFrame con las secciones (vacío si no hay ninguna fuente).
    """
    if os.path.exists(RUTA_LOCAL_INE):
        try:
            df = _leer_csv_ine(RUTA_LOCAL_INE)
            # geometry_geojson no viaja en CSV
            df['geometry_geojson'] = None
            return df
        except Exception as e:
            print(f'ADVERTENCIA: no se pudo leer {RUTA_LOCAL_INE}: {e}')
    return parsear_kml_secciones()


def cargar_secciones_ine() -> tuple:
    """
    Punto de entrada principal: devuelve las secciones reales del IECM o el
    fallback de demo.

    Retorna:
        (pd.DataFrame, str): tupla con el DataFrame y el origen
        ('ine' | 'demo').
    """
    df = descargar_secciones_ine()
    if not df.empty:
        return df, 'ine'
    from modules.data import generar_datos_iniciales
    return generar_datos_iniciales(), 'demo'


def parsear_colonias_iecm(ruta: str = RUTA_SHP_COLONIAS) -> pd.DataFrame:
    """
    Parsea las colonias del IECM y devuelve las **colonias de Tlalpan** con:
    código (`CVEUT`), nombre (`NOMUT`), distrito local (`DTTOLOC`), centroide
    (EPSG:4326), área y geometría simplificada (GeoJSON). Como fuente se prefiere
    el CSV de referencia COMMITEADO (`referencia/marcos/colonias_iecm.csv`) y,
    si no existe, el shapefile local (`documentos/inegi/colonias_iecm.shp`).

    Retorna:
        pd.DataFrame con las columnas de `COLUMNAS_COLONIAS` (vacío si no hay
        archivo o no se pudo leer).
    """
    df_ref = _leer_csv_referencia(RUTA_REF_COLONIAS, 'colonias')
    if not df_ref.empty:
        return df_ref
    if not os.path.exists(ruta):
        print(f'ADVERTENCIA: no existe el shapefile de colonias: {ruta}')
        return pd.DataFrame()
    try:
        import geopandas as gpd
        gdf = gpd.read_file(ruta)
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        gdf['NOMDT'] = gdf['NOMDT'].fillna('').astype(str).str.upper()
        tlp = gdf[gdf['NOMDT'] == 'TLALPAN'].copy()
        filas = []
        for _, fila in tlp.iterrows():
            geom = fila['geometry']
            lon, lat = geom.centroid.x, geom.centroid.y
            geometry_geojson = shapely_mapping(
                geom.simplify(TOLERANCIA_SIMPLIFICACION, preserve_topology=True)) \
                if SHAPELY_OK else None
            filas.append({
                'cve': str(fila['CVEUT']),
                'nombre': str(fila['NOMUT']),
                'distrito': str(fila['DTTOLOC']),
                'lat': lat,
                'lon': lon,
                'area': geom.area,
                'geometry_geojson': geometry_geojson,
            })
        df = pd.DataFrame(filas, columns=COLUMNAS_COLONIAS)
        return df.sort_values('nombre').reset_index(drop=True)
    except Exception as e:
        print(f'ADVERTENCIA: no se pudo leer el shapefile de colonias: {e}')
        return pd.DataFrame()