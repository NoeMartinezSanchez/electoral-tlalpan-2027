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
RUTA_LOCAL_INE = os.path.join('data', 'secciones_ine.csv')
TOLERANCIA_SIMPLIFICACION = 0.001  # grados (~110 m)

# Columnas del DataFrame normalizado (Pestaña 1 + Mongo)
COLUMNAS_INE = ['id_seccion', 'nombre', 'distrito', 'distrito_federal',
                'circunscripcion', 'lat', 'lon', 'poblacion',
                'padron_electoral', 'lista_nominal', 'tipo_zona',
                'area', 'geometry_geojson']


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