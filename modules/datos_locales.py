"""
datos_locales.py
================

Capa de datos **local-first** para la Pestaña 1: almacena secciones, colonias y
registros de campo en CSVs dentro de `data/` (gitignored) para que la app abra y
muestre los datos al instante (sin depender de red en cada render), con
**sincronización opcional a MongoDB Atlas** cuando se quiere persistir para el
equipo (Streamlit Cloud usa filesystem efímero, por lo que el CSV es por sesión
y el dato durable vive en Mongo).

Archivos:
- `data/secciones_ine.csv`   (355 secciones IECM)
- `data/colonias_iecm.csv`   (179 colonias IECM)
- `data/registros_locales.csv` (registros de campo locales)

Los **registros sintéticos** de prueba se escriben con `fuente='real'` (se
integran al dashboard como datos reales) pero con `brigadista='sintetico_*'`
para poder eliminarlos sin tocar los reales.
"""

import hashlib
import os
import random
from datetime import datetime, timedelta

import pandas as pd

RUTA_SECCIONES = os.path.join('data', 'secciones_ine.csv')
RUTA_COLONIAS = os.path.join('data', 'colonias_iecm.csv')
RUTA_REGISTROS = os.path.join('data', 'registros_locales.csv')

COLUMNAS_REGISTROS = ['uid', 'seccion_id', 'tipo', 'intencion', 'queja_texto',
                      'queja_categoria', 'queja_sentimiento', 'brigadista',
                      'colonia', 'colonia_cve', 'fecha', 'fuente']

PREFIJO_SINTETICO = 'sintetico_'


# ---------------------------------------------------------------------------
# Secciones y colonias (CSV rápido; fallback a parsing de geo)
# ---------------------------------------------------------------------------

def _escribir(df: pd.DataFrame, ruta: str) -> None:
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    df.to_csv(ruta, index=False, encoding='utf-8-sig')


def leer_secciones() -> pd.DataFrame:
    """
    Devuelve las secciones en formato de la Pestaña 1 desde `data/secciones_ine.csv`
    (si no existe, las genera desde el KML del IECM). El DataFrame viene con el
    esquema de la app (columna 'id', intencion/cobertura por procesar).

    Retorna:
        pd.DataFrame (vacío si no hay fuentes).
    """
    if os.path.exists(RUTA_SECCIONES):
        try:
            df = pd.read_csv(RUTA_SECCIONES, encoding='utf-8-sig')
        except Exception as e:
            print(f'LOCAL: no se pudo leer secciones CSV: {e}')
            df = pd.DataFrame()
    else:
        from modules.geo import parsear_kml_secciones
        df = parsear_kml_secciones()
        if not df.empty:
            cols = [c for c in df.columns if c != 'geometry_geojson']
            _escribir(df[cols], RUTA_SECCIONES)
    if df.empty or 'id_seccion' not in df.columns:
        return df
    df = df.rename(columns={'id_seccion': 'id'})
    for col, default in (('intencion', 'indeciso'), ('tipo_zona', 'urbana'),
                         ('cobertura', 0.0)):
        if col not in df.columns:
            df[col] = default
    df['cobertura'] = pd.to_numeric(df.get('cobertura', 0.0), errors='coerce').fillna(0.0)
    return df.reset_index(drop=True)


def leer_colonias() -> pd.DataFrame:
    """Devuelve las colonias desde `data/colonias_iecm.csv` (o las genera del SHP)."""
    if os.path.exists(RUTA_COLONIAS):
        try:
            return pd.read_csv(RUTA_COLONIAS, encoding='utf-8-sig')
        except Exception as e:
            print(f'LOCAL: no se pudo leer colonias CSV: {e}')
    from modules.geo import parsear_colonias_iecm
    df = parsear_colonias_iecm()
    if not df.empty:
        cols = [c for c in df.columns if c != 'geometry_geojson']
        _escribir(df[cols], RUTA_COLONIAS)
    return df


# ---------------------------------------------------------------------------
# Registros de campo (CSV local)
# ---------------------------------------------------------------------------

def leer_registros() -> pd.DataFrame:
    """Lee los registros de campo locales desde el CSV (vacío si no existe)."""
    if not os.path.exists(RUTA_REGISTROS):
        return pd.DataFrame(columns=COLUMNAS_REGISTROS)
    try:
        df = pd.read_csv(RUTA_REGISTROS, encoding='utf-8-sig')
    except Exception:
        return pd.DataFrame(columns=COLUMNAS_REGISTROS)
    for col in COLUMNAS_REGISTROS:
        if col not in df.columns:
            df[col] = ''
    return df.reset_index(drop=True)


def agregar_registro(doc: dict) -> dict:
    """Anexa un registro de campo al CSV local (generic uid si hace falta)."""
    df = leer_registros()
    fila = {col: doc.get(col, '') for col in COLUMNAS_REGISTROS}
    if not fila['uid']:
        base = f"{fila['seccion_id']}|{fila['tipo']}|{fila['queja_texto']}|{fila['fecha']}"
        fila['uid'] = hashlib.md5(base.encode('utf-8')).hexdigest()[:16]
    df = pd.concat([df, pd.DataFrame([fila])], ignore_index=True)
    _escribir(df, RUTA_REGISTROS)
    return {'ok': True, 'n': len(df)}


def _uid_default(fila) -> str:
    base = f"{fila.get('seccion_id')}|{fila.get('tipo')}|" \
           f"{fila.get('queja_texto')}|{fila.get('fecha')}"
    return hashlib.md5(base.encode('utf-8')).hexdigest()[:16]


def sincronizar_a_mongo() -> dict:
    """
    Sube los registros locales a MongoDB Atlas (`registros_campo`) evitando
    duplicados (por 'uid'). Es el paso que hace durable el dato en Cloud.

    Retorna:
        dict con 'ok', 'n' (insertados), 'skip' y 'mensaje'.
    """
    df = leer_registros()
    if df.empty:
        return {'ok': False, 'n': 0, 'skip': 0,
                'mensaje': 'No hay registros locales para sincronizar.'}
    from modules.datos_campo import coleccion, conexion_ok, error_conexion
    if not conexion_ok():
        return {'ok': False, 'n': 0, 'skip': 0,
                'mensaje': f'Mongo no conectado: {error_conexion()}'}
    col = coleccion('registros_campo')
    insertados, omitidos = 0, 0
    for _, r in df.iterrows():
        uid = str(r.get('uid') or '') or _uid_default(r)
        if col.count_documents({'uid': uid}) > 0:
            omitidos += 1
            continue
        try:
            seccion = int(float(r.get('seccion_id') or 0))
        except (TypeError, ValueError):
            seccion = 0
        doc = {
            'uid': uid,
            'seccion_id': seccion,
            'tipo': r.get('tipo', ''),
            'intencion': r.get('intencion') or None,
            'queja_texto': str(r.get('queja_texto') or ''),
            'queja_categoria': str(r.get('queja_categoria') or ''),
            'queja_sentimiento': str(r.get('queja_sentimiento') or 'neutral'),
            'brigadista': str(r.get('brigadista') or ''),
            'colonia': r.get('colonia') or None,
            'colonia_cve': str(r.get('colonia_cve') or ''),
            'fecha': str(r.get('fecha') or datetime.now().isoformat()),
            'fuente': 'real',
            'origen': 'local',
        }
        col.insert_one(doc)
        insertados += 1
    return {'ok': True, 'n': insertados, 'skip': omitidos,
            'mensaje': f'{insertados} registros sincronizados a Mongo '
                       f'({omitidos} ya existían).'}


def limpiar_sinteticos() -> dict:
    """Elimina del CSV local los registros con brigadista prefijo 'sintetico_'."""
    df = leer_registros()
    if df.empty:
        return {'ok': True, 'n': 0}
    mascara = df['brigadista'].astype(str).str.startswith(PREFIJO_SINTETICO)
    eliminados = int(mascara.sum())
    df = df[~mascara].reset_index(drop=True)
    _escribir(df, RUTA_REGISTROS)
    return {'ok': True, 'n': eliminados}


# ---------------------------------------------------------------------------
# Registros sintéticos de prueba (local-first)
# ---------------------------------------------------------------------------

_CATALOGO_QUEJAS = [
    ('AGUA', 'No hay agua desde el martes, las pipas no llegan'),
    ('AGUA', 'El tinaco lleva semanas vacío y las pipas cobran caro'),
    ('AGUA', 'El agua sale con lodo y basura del tinaco'),
    ('AGUA', 'Las pipas del gobierno nunca llegaron a la colonia'),
    ('BACHEO', 'Hay un bache enorme en la esquina y ya causó un accidente'),
    ('BACHEO', 'La calle está llena de hoyos y baches desde hace meses'),
    ('ALUMBRADO', 'La luz de la calle se apaga cada noche, es peligroso'),
    ('ALUMBRADO', 'El alumbrado público no funciona en toda la cuadra'),
    ('CONSTRUCCION_ILEGAL', 'Están construyendo ilegalmente en el terreno baldío'),
    ('CONSTRUCCION_ILEGAL', 'La construcción ilegal está tapando el drenaje'),
    ('SEGURIDAD', 'Me extorsionaron por teléfono ayer por la noche'),
    ('SEGURIDAD', 'Vecinos reportan robos a casa habitación en la cuadra'),
    ('SEGURIDAD', 'Hay personas sospechosas merodeando por la tarde'),
]

_BRIGADISTAS_SINTETICOS = ['sintetico_J1', 'sintetico_J2',
                           'sintetico_J3', 'sintetico_J4']


def _clasificar_regla(texto: str):
    """Clasificación por reglas (equivalente al fallback de modules.nlp)."""
    t = (texto or '').lower()
    if any(p in t for p in ('agua', 'pipa', 'tinaco', 'lluvia', 'drenaje',
                            'lodo', 'cobran')):
        return 'AGUA'
    if any(p in t for p in ('bache', 'hoyo', 'calle', 'pavimento',
                            'accidente', 'carril')):
        return 'BACHEO'
    if any(p in t for p in ('luz', 'alumbrado', 'foco', 'oscuridad',
                            'obscuro', 'oscura', 'obscuridad')):
        return 'ALUMBRADO'
    if any(p in t for p in ('construcción', 'construccion', 'terreno', 'obra',
                            'edificio', 'ilegal', 'tapando')):
        return 'CONSTRUCCION_ILEGAL'
    return 'SEGURIDAD'


def _sentimiento_regla(texto: str) -> str:
    t = (texto or '').lower()
    neg = ('no', 'nunca', 'problema', 'falla', 'robo', 'extorsión',
           'extorsion', 'peligro', 'accidente', 'ilegal', 'amenaza',
           'peor', 'malo', 'vacío', 'vacio')
    pos = ('gracias', 'bien', 'mejor', 'funciona', 'ayuda', 'apoyo',
           'excelente', 'rápido', 'rapido')
    if any(p in t for p in neg):
        return 'negativo'
    if any(p in t for p in pos):
        return 'positivo'
    return 'neutral'


def _generar_lote_sintetico(n: int, secciones: pd.DataFrame,
                            colonias: pd.DataFrame, rng: random.Random) -> pd.DataFrame:
    """
    (Puro, testeable) Genera `n` registros sintéticos de campo:
    - tipos 45% visita / 30% simpatía / 25% queja; intenciones 45/35/20.
    - ~30% de quejas AGUA; fechas en los últimos 30 días.
    - Colonia asignada ~80% según el distrito local de la sección.
    Marcados con `fuente='real'` y `brigadista='sintetico_*'`.
    """
    ahora = datetime.now()
    secciones = secciones.reset_index(drop=True)
    ids = secciones['id'].tolist()
    mapa_seccion = {(int(r['id'])): r for _, r in secciones.iterrows()}
    colonias_por_distrito = {}
    if not colonias.empty and 'distrito' in colonias.columns:
        for dto, grp in colonias.groupby(colonias['distrito'].astype(str)):
            colonias_por_distrito[dto] = grp[['nombre', 'cve']].to_dict('records')

    filas = []
    for i in range(n):
        seccion_id = rng.choice(ids)
        fila_sec = mapa_seccion.get(int(seccion_id))
        distrito = ''
        if fila_sec is not None and 'distrito' in fila_sec.index:
            distrito = str(fila_sec['distrito'])
        peso_tipo = rng.random()
        if peso_tipo < 0.45:
            tipo = 'visita'
        elif peso_tipo < 0.75:
            tipo = 'simpatia'
        else:
            tipo = 'queja'

        intencion = None
        texto = ''
        categoria = ''
        if tipo in ('visita', 'simpatia'):
            intencion = rng.choices(['a_favor', 'indeciso', 'en_contra'],
                                    weights=[0.45, 0.35, 0.20], k=1)[0]
        else:
            categoria, texto = rng.choice(_CATALOGO_QUEJAS)
            if rng.random() < 0.5:  # texto conque ya lleva contexto
                texto += rng.choice([' en la colonia', '', ' desde temprano', ''])

        sentimiento = _sentimiento_regla(texto) if texto else 'neutral'
        # Colonia ~80%, coherente con el distrito local de la sección
        colonia = None
        colonia_cve = ''
        if colonias_por_distrito and rng.random() < 0.8:
            pool = colonias_por_distrito.get(distrito, [])
            if not pool and colonias_por_distrito:
                pool = list(rng.choice(list(colonias_por_distrito.values())))
            if pool:
                elegida = rng.choice(pool)
                colonia = elegida['nombre']
                colonia_cve = str(elegida.get('cve', ''))

        minutos = rng.randint(0, 30 * 1440)
        fecha = ahora - timedelta(minutes=minutos, seconds=rng.randint(0, 3599))
        uid = f'S{i:06d}'
        filas.append({
            'uid': uid,
            'seccion_id': int(seccion_id),
            'tipo': tipo,
            'intencion': intencion,
            'queja_texto': texto,
            'queja_categoria': categoria or ('SIN_QUEJA' if tipo != 'queja' else categoria),
            'queja_sentimiento': sentimiento,
            'brigadista': _BRIGADISTAS_SINTETICOS[i % len(_BRIGADISTAS_SINTETICOS)],
            'colonia': colonia,
            'colonia_cve': colonia_cve,
            'fecha': fecha.isoformat(),
            'fuente': 'real',
        })
    return pd.DataFrame(filas, columns=COLUMNAS_REGISTROS)


def sembrar_sinteticos(n: int = 500, semilla: int = 2027) -> dict:
    """
    Genera `n` registros sintéticos y los anexa al CSV local (reemplazando los
    sintéticos previos). No requiere Mongo.

    Retorna:
        dict con 'ok', 'n' y 'mensaje'.
    """
    rng = random.Random(semilla)
    secciones = leer_secciones()
    if secciones.empty or 'id' not in secciones.columns:
        return {'ok': False, 'n': 0,
                'mensaje': 'No hay secciones locales (genera primero '
                           'data/secciones_ine.csv con el KML del IECM).'}
    colonias = leer_colonias()
    lotes = _generar_lote_sintetico(n, secciones, colonias, rng)
    df = leer_registros()
    if not df.empty:
        mascara = df['brigadista'].astype(str).str.startswith(PREFIJO_SINTETICO)
        df = df[~mascara]
    df = pd.concat([df, lotes], ignore_index=True)
    _escribir(df, RUTA_REGISTROS)
    return {'ok': True, 'n': n,
            'mensaje': f'{n} registros sintéticos generados en local '
                       '(usa "Sincronizar a Mongo" para persistirlos en Cloud).'}