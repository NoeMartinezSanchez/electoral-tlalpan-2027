"""
datos_campo.py
==============

Persistencia de los **datos reales de campo** de la Pestaña 1 en **MongoDB Atlas**.

Colecciones:
- `secciones`        : geografía electoral real de Tlalpan (importada desde INE).
- `registros_campo`  : visitas / simpatías / quejas-incidencias de brigadistas.
- `incidencias_dia_d`: (fase posterior) incidencias de casillas del Módulo 3.

La conexión se lee de los Secrets (`[MONGO] URI` y opcional `DB`). Todo el acceso
está envuelto en try/except con **degradación elegante**: si Mongo no responde se
devuelve None/DataFrame vacío y se registra el error en consola, sin romper la UI.

Nota de campaña (INE): los registros se catalogan como "simpatías" e "incidencias
comunitarias"; no se guardan datos personales de los ciudadanos.
"""

from typing import Optional

import pandas as pd
import streamlit as st

_CLIENTE = None
_ERROR_CONEXION = None


def obtener_uri() -> str:
    """Lee la URI de conexión de MongoDB Atlas de los Secrets."""
    try:
        return st.secrets['MONGO'].get('URI', '').strip()
    except Exception:
        return ''


def obtener_nombre_db() -> str:
    """Nombre de la base de datos (por defecto 'electoral_tlalpan')."""
    try:
        return st.secrets['MONGO'].get('DB', 'electoral_tlalpan').strip()
    except Exception:
        return 'electoral_tlalpan'


def get_client():
    """
    Devuelve el cliente de MongoDB (con caché) o None si no se puede conectar.
    Si la primera conexión falla, se guarda el error para no reintentar en cada
    render; `reconectar()` permite limpiarlo.
    """
    global _CLIENTE, _ERROR_CONEXION
    if _CLIENTE is not None:
        return _CLIENTE
    if _ERROR_CONEXION is not None:
        return None
    uri = obtener_uri()
    if not uri:
        _ERROR_CONEXION = 'Sin URI configurada ([MONGO] URI en Secrets).'
        print(f'MONGO: {_ERROR_CONEXION}')
        return None
    try:
        from pymongo import MongoClient
        cliente = MongoClient(uri, serverSelectionTimeoutMS=4000)
        cliente.admin.command('ping')  # fuerza la conexión real
        _CLIENTE = cliente
        return _CLIENTE
    except Exception as e:
        _ERROR_CONEXION = str(e)
        print(f'MONGO: no se pudo conectar: {_ERROR_CONEXION}')
        return None


def reconectar() -> None:
    """Limpia la caché del cliente/error para volver a intentar la conexión."""
    global _CLIENTE, _ERROR_CONEXION
    if _CLIENTE is not None:
        try:
            _CLIENTE.close()
        except Exception:
            pass
    _CLIENTE = None
    _ERROR_CONEXION = None


def error_conexion() -> str:
    """Devuelve el mensaje de error de conexión actual (o '')."""
    return _ERROR_CONEXION or ''


def obtener_db():
    """Devuelve la base de datos (o None si no hay conexión)."""
    cliente = get_client()
    if cliente is None:
        return None
    return cliente[obtener_nombre_db()]


def coleccion(nombre: str):
    """Devuelve una colección de la base (o None si no hay conexión)."""
    db = obtener_db()
    if db is None:
        return None
    return db[nombre]


def invalidar_cache_datos() -> None:
    """Limpia las caches de lectura de Mongo (secciones/registros/colonias/resumen)."""
    for fn in (obtener_secciones, obtener_colonias, obtener_registros, obtener_resumen):
        try:
            fn.clear()
        except Exception:
            pass


def conexion_ok() -> bool:
    return get_client() is not None


# ---------------------------------------------------------------------------
# Secciones (geografía electoral real)
# ---------------------------------------------------------------------------

def importar_secciones_ine() -> dict:
    """
    Importa la cartografía del Marco Electoral (IECM) vía `modules.geo` a la
    colección `secciones` de MongoDB (upsert por id_seccion), incluyendo el
    centroide, los atributos (padrón/lista/población) y la geometría simplificada.

    Retorna:
        dict con 'ok' (bool), 'n' (cantidad) y 'mensaje'.
    """
    from modules.geo import generar_csv_ine, parsear_kml_secciones

    df = parsear_kml_secciones()
    if df.empty:
        return {'ok': False, 'n': 0,
                'mensaje': 'No hay geografía electoral disponible (falta el KML '
                           'del Marco Geográfico Electoral del IECM en '
                           'documentos/Marco geografico electoral/).'}
    col = coleccion('secciones')
    if col is None:
        return {'ok': False, 'n': 0, 'mensaje': f'MONGO: {error_conexion()}'}
    try:
        columnas = ['id_seccion', 'nombre', 'distrito', 'distrito_federal',
                    'circunscripcion', 'lat', 'lon', 'poblacion',
                    'padron_electoral', 'lista_nominal', 'tipo_zona', 'area']
        registros = []
        for _, fila in df.iterrows():
            doc = {c: fila[c] for c in columnas}
            geometry = fila.get('geometry_geojson')
            if geometry:
                doc['geometry_geojson'] = geometry
            doc['fuente'] = 'Marco Geográfico Electoral IECM 2021'
            registros.append(doc)
        for reg in registros:
            col.update_one({'id_seccion': reg['id_seccion']},
                           {'$set': reg}, upsert=True)
        # Respaldo ligero en CSV (gitignored) para depuración
        generar_csv_ine()
        invalidar_cache_datos()
        return {'ok': True, 'n': len(registros),
                'mensaje': f'{len(registros)} secciones del IECM importadas a MongoDB.'}
    except Exception as e:
        print(f'MONGO: error al importar secciones: {e}')
        return {'ok': False, 'n': 0, 'mensaje': str(e)}


@st.cache_data(ttl=30, show_spinner=False)
def obtener_secciones() -> pd.DataFrame:
    """
    Devuelve las secciones reales guardadas en MongoDB como DataFrame.
    Si no hay conexión o datos, devuelve uno vacío.
    """
    col = coleccion('secciones')
    if col is None:
        return pd.DataFrame()
    try:
        docs = list(col.find({}, {'_id': 0}))
        if not docs:
            return pd.DataFrame()
        df = pd.DataFrame(docs)
        df['id_seccion'] = df['id_seccion'].astype(int)
        return df
    except Exception as e:
        print(f'MONGO: error al leer secciones: {e}')
        return pd.DataFrame()


def secciones_para_app() -> tuple:
    """
    Provee el DataFrame de secciones para la app: usa MongoDB (INE) cuando hay
    datos; si no, cae al set ficticio de `modules.data` y avisa.

    Retorna:
        (pd.DataFrame, str): (secciones, origen) con origen en 'ine' | 'demo'.
    """
    df = obtener_secciones()
    if not df.empty:
        df = df.rename(columns={
            'id_seccion': 'id', 'lat': 'lat', 'lon': 'lon',
            'nombre': 'nombre', 'cobertura': 'cobertura'})
        # Compatibilidad con el esquema de la Pestaña 1
        if 'intencion' not in df.columns:
            df['intencion'] = 'indeciso'
        if 'tipo_zona' not in df.columns:
            df['tipo_zona'] = 'urbana'
        if 'cobertura' not in df.columns:
            df['cobertura'] = 0.0
        return df, 'ine'
    from modules.data import generar_datos_iniciales
    return generar_datos_iniciales(), 'demo'


def importar_colonias_iecm() -> dict:
    """
    Importa las colonias del IECM (vía `modules.geo`) a la colección `colonias`
    de MongoDB (upsert por 'cve').

    Retorna:
        dict con 'ok' (bool), 'n' (cantidad) y 'mensaje'.
    """
    from modules.geo import parsear_colonias_iecm

    df = parsear_colonias_iecm()
    if df.empty:
        return {'ok': False, 'n': 0,
                'mensaje': 'No hay capa de colonias (falta '
                           'documentos/inegi/colonias_iecm.shp).'}
    col = coleccion('colonias')
    if col is None:
        return {'ok': False, 'n': 0, 'mensaje': f'MONGO: {error_conexion()}'}
    try:
        for _, fila in df.iterrows():
            doc = {c: fila[c] for c in df.columns}
            doc['fuente'] = 'Colonias IECM (shapefile)'
            col.update_one({'cve': str(fila['cve'])}, {'$set': doc}, upsert=True)
        invalidar_cache_datos()
        return {'ok': True, 'n': len(df),
                'mensaje': f'{len(df)} colonias de Tlalpan importadas a MongoDB.'}
    except Exception as e:
        print(f'MONGO: error al importar colonias: {e}')
        return {'ok': False, 'n': 0, 'mensaje': str(e)}


@st.cache_data(ttl=30, show_spinner=False)
def obtener_colonias() -> pd.DataFrame:
    """
    Devuelve las colonias (de Mongo `colonias` o, si no hay conexión/datos,
    parseando el shapefile del IECM) para alimentar selectores y análisis.

    Retorna:
        pd.DataFrame con cve/nombre/distrito/lat/lon (vacío si nada disponible).
    """
    col = coleccion('colonias')
    if col is not None:
        try:
            docs = list(col.find({}, {'_id': 0}))
            if docs:
                df = pd.DataFrame(docs)
                if 'cve' in df and 'nombre' in df:
                    return df
        except Exception as e:
            print(f'MONGO: error al leer colonias: {e}')
    from modules.geo import parsear_colonias_iecm
    return parsear_colonias_iecm()


# ---------------------------------------------------------------------------
# Registros de campo (visitas / simpatías / quejas)
# ---------------------------------------------------------------------------

def insertar_registro(registro: dict) -> dict:
    """
    Inserta un registro de campo real en la colección `registros_campo`.
    El registro debe etiquetarse como simpatía/incidencia (nota INE).

    Retorna:
        dict con 'ok' (bool) y 'id'/'error'.
    """
    col = coleccion('registros_campo')
    if col is None:
        return {'ok': False, 'error': f'MONGO: {error_conexion()}'}
    try:
        resultado = col.insert_one(registro)
        invalidar_cache_datos()
        return {'ok': True, 'id': str(resultado.inserted_id)}
    except Exception as e:
        print(f'MONGO: error al insertar registro: {e}')
        return {'ok': False, 'error': str(e)}


@st.cache_data(ttl=30, show_spinner=False)
def obtener_registros(seccion_id: Optional[int] = None) -> pd.DataFrame:
    """Devuelve los registros de campo (globalmente o de una sección)."""
    col = coleccion('registros_campo')
    if col is None:
        return pd.DataFrame()
    try:
        filtro = {'seccion_id': int(seccion_id)} if seccion_id is not None else {}
        docs = list(col.find(filtro, {'_id': 0}))
        return pd.DataFrame(docs) if docs else pd.DataFrame()
    except Exception as e:
        print(f'MONGO: error al leer registros: {e}')
        return pd.DataFrame()


def estado_secciones(secciones_df: pd.DataFrame,
                     registros_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula el estado real por sección a partir de los registros de campo:
    - `cobertura` = registros (visitas+simpatías+quejas) / Lista_Nominal * 100
      (cap 100; 0 si no hay base o registros).
    - `intencion` = moda de las simpatías registradas ('indeciso' sin datos).

    Retorna:
        copia de `secciones_df` con 'cobertura' y 'intencion' reales.
    """
    df = secciones_df.copy()
    df['cobertura'] = 0.0
    df['intencion'] = 'indeciso'
    if df.empty or 'id' not in df.columns:
        return df
    if registros_df is None or registros_df.empty or 'seccion_id' not in registros_df.columns:
        return df

    # Cobertura por sección (base: lista_nominal cuando exista)
    conteo = registros_df['seccion_id'].value_counts()
    if 'lista_nominal' in df.columns:
        bases = df.set_index('id')['lista_nominal'].astype(float)
        coberturas = pd.Series(0.0, index=df['id'])
        for sid, n in conteo.items():
            base = bases.get(sid, 0.0)
            cb = min(100.0, n / base * 100.0) if base and base > 0 else 0.0
            coberturas.loc[sid] = cb
        df['cobertura'] = coberturas.reindex(df['id']).fillna(0.0).values

    # Intención por moda de simpatías
    simpatias = registros_df[
        (registros_df['tipo'] == 'simpatia')
        & registros_df['intencion'].notna()]
    if not simpatias.empty:
        moda = (simpatias.groupby('seccion_id')['intencion']
                .agg(lambda s: s.mode().iloc[0] if not s.mode().empty else None)
                .dropna())
        df['intencion'] = df['id'].map(moda).fillna('indeciso').values
    return df


@st.cache_data(ttl=30, show_spinner=False)
def obtener_resumen() -> dict:
    """
    Resumen agregado de los registros de campo (totales por tipo, categoría,
    orientación de simpatías y secciones con registro).

    Retorna:
        dict con totales (vacío si no hay conexión/datos).
    """
    col = coleccion('registros_campo')
    if col is None:
        return {}
    try:
        docs = list(col.find({}, {'_id': 0, 'tipo': 1, 'intencion': 1,
                                  'queja_categoria': 1, 'seccion_id': 1}))
        if not docs:
            return {'total': 0, 'por_tipo': {}, 'por_categoria': {},
                    'simpatias': {}, 'quejas': 0, 'secciones_con_registro': 0,
                    'capitulo': ''}
        df = pd.DataFrame(docs)
        por_tipo = df['tipo'].value_counts().to_dict() if 'tipo' in df else {}
        por_categoria = (df['queja_categoria'].value_counts().to_dict()
                         if 'queja_categoria' in df else {})
        simpatias = {}
        if 'intencion' in df:
            simpatias = df[df['tipo'] == 'simpatia']['intencion'] \
                .value_counts().to_dict()
        quejas = int((df['tipo'] == 'queja').sum())
        secciones_con_registro = int(df['seccion_id'].nunique())
        return {'total': len(df), 'por_tipo': por_tipo,
                'por_categoria': por_categoria, 'simpatias': simpatias,
                'quejas': quejas, 'secciones_con_registro': secciones_con_registro}
    except Exception as e:
        print(f'MONGO: error en resumen: {e}')
        return {}


def limpiar_registros() -> dict:
    """Elimina todos los registros de campo (acción destructiva con confirmación)."""
    col = coleccion('registros_campo')
    if col is None:
        return {'ok': False, 'error': f'MONGO: {error_conexion()}'}
    try:
        resultado = col.delete_many({})
        invalidar_cache_datos()
        return {'ok': True, 'n': resultado.deleted_count}
    except Exception as e:
        return {'ok': False, 'error': str(e)}