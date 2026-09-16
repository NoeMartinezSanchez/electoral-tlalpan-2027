"""
manual_csv.py
=============

Procesa archivos CSV exportados con la extensión **Instant Data Scraper**
(Chrome) para Facebook e Instagram y los normaliza al esquema del dashboard de
la Pestaña 2 (`COLUMNAS_POSTS`), para integrarlos junto con los datos reales de
TikTok y X/Twitter.

Las columnas de estos CSVs tienen nombres tipo clase CSS (p.ej. `x1i10hfl href`)
y el contenido está desalineado, por lo que este módulo detecta los **roles** de
cada dato por su contenido (URLs, cadenas largas, métricas "2,1 mil", fechas
relativas "7 h"), no por la posición de la columna.

Flujo:
    1. `detectar_tipo_csv`       -> 'facebook' | 'instagram' | 'desconocido'
    2. `limpiar_csv_facebook` / `limpiar_csv_instagram`
    3. `normalizar_para_dashboard` -> DataFrame con el esquema estándar
    4. `procesar_archivos`       -> orquesta todo y devuelve dfs + errores/avisos

Limitaciones conocidas:
    - Facebook: los CSVs no traen fecha -> `fecha` queda en `NaT` ("Sin fecha").
    - Instagram: la fecha viene relativa ("7 h", "20 h") -> se convierte a
      absoluta en el momento del procesado.
    - `vistas`/`guardados` no están en los CSVs -> 0.
"""

import hashlib
import io
import re
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from modules.social_media import COLUMNAS_POSTS
from modules.social_media_generator import TEMAS_ELECTORALES, clasificar_sentimiento

# ---------------------------------------------------------------------------
# Utilidades de detección de contenido
# ---------------------------------------------------------------------------

_URL_START = ('http://', 'https://', 'data:', 'blob:', 'www.')

# Tokens ruido que nunca son texto de post ni autor
_LABELES_RUIDO = {
    'ver más', 'ver traducción', 'más', '...', '·', 'seguir', 'comentar',
    'compartir', 'repost', 'repostear', 'más opciones', 'el audio está silenciado',
    'facebook', 'm.me', 'publicación compartida', 'comilla angular hacia la derecha',
    'verificado', '¿te interesa esta publicación?', 'anuncio', 'patrocinado',
}


def _cadena(valor) -> str:
    """Convierte un valor crudo a string limpio (o '')."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ''
    texto = str(valor).strip()
    # Valores "Not a Number" que pandas convierte a float de texto corto
    if texto.lower() in ('nan', 'none', 'nat'):
        return ''
    return texto


def _es_url(valor: str) -> bool:
    return valor.startswith(_URL_START)


def _token_ruido(valor: str) -> bool:
    return valor.lower() in _LABELES_RUIDO or len(valor) <= 1


def _es_metrica(valor: str) -> bool:
    """
    Indica si una cadena parece una métrica numérica: entero, "1.234", "2,1 mil",
    "1.2K", "3,8 M". Las fechas relativas ("7 h") NO cuentan como métrica.
    """
    v = valor.strip().lower()
    if not v:
        return False
    if re.match(r'^\d+\s*(min|h|d|sem|mes|a)\b', v):
        return False
    return bool(re.match(r'^[\d.,]+\s*(mil|k|m|b)?\s*$', v))


def _numeros_de_fila(fila) -> list:
    """Devuelve las métricas numéricas de una fila (todas las columnas, en orden)."""
    numeros = []
    for valor in fila:
        texto = _cadena(valor)
        if texto and _es_metrica(texto):
            numeros.append(convertir_metrica_a_numero(texto))
    return numeros


# ---------------------------------------------------------------------------
# Conversores
# ---------------------------------------------------------------------------

def _numero_decimal(parte: str, separador_decimal: str) -> float:
    """Convierte '2,1' o '1.2' a float según el separador decimal detectado."""
    parte = parte.replace(' ', '')
    if separador_decimal == ',':
        parte = parte.replace('.', '').replace(',', '.')
    else:
        parte = parte.replace(',', '')
    try:
        return float(parte)
    except ValueError:
        return 0.0


def convertir_metrica_a_numero(texto) -> int:
    """
    Convierte una métrica de texto a número entero:
    - "2,1 mil"  -> 2100
    - "1.2 mil"  -> 1200
    - "1,2 M"   -> 1_200_000
    - "1.2K"    -> 1200
    - "1,234" / "1.234" -> 1234 (miles en inglés/español)
    - "53"      -> 53
    Si no se puede parsear devuelve 0 (y se registra aviso por el llamador).

    Retorna:
        int con la métrica numérica.
    """
    v = _cadena(texto).lower().replace('\u00a0', ' ').strip()
    if not v:
        return 0

    m = re.match(r'^([\d.,]+)\s*(mil|k)\b\s*$', v)
    if m:
        parte, unidad = m.groups()
        sep = ',' if (',' in parte and '.' not in parte) else '.'
        factor = 1000.0
        return int(round(_numero_decimal(parte, sep) * factor))

    m = re.match(r'^([\d.,]+)\s*m\b\s*$', v)
    if m:
        parte = m.group(1)
        sep = ',' if (',' in parte and '.' not in parte) else '.'
        return int(round(_numero_decimal(parte, sep) * 1_000_000))

    # Miles con separador (en o es): "1,234" / "1.234"
    m = re.match(r'^\d{1,3}(?:[.,]\d{3})+$', v)
    if m:
        return int(v.replace('.', '').replace(',', ''))

    # Decimal simple sin sufijo (raro en métricas), se trunca a entero
    m = re.match(r'^([\d.,]+)$', v)
    if m:
        parte = m.group(1)
        sep = ',' if (',' in parte and '.' not in parte) else '.'
        return int(round(_numero_decimal(parte, sep)))

    try:
        return int(float(v))
    except ValueError:
        return 0


def convertir_fecha_relativa(texto) -> Optional[datetime]:
    """
    Convierte una fecha relativa de Instagram a fecha absoluta (naive, hora local):
    - "7 h", "20 h"  -> now - 7h / - 20h
    - "1 d", "2 d"   -> now - 1d / - 2d
    - "5 min"        -> now - 5min
    - "1 sem"        -> now - 7d
    - "1 mes"        -> now - 30d
    - "1 a"          -> now - 365d
    También acepta timestamps ISO/sin formato (los devuelve tal cual).
    Si no parsea devuelve None (se mostrará como "Sin fecha").

    Retorna:
        datetime o None.
    """
    v = _cadena(texto)
    if not v:
        return None
    m = re.match(r'(?i)^\s*(\d+)\s*(min|minutos?|h|hrs?|horas?|d|días?|dias?|sem|semanas?|mes|meses?|a|años?)\s*$', v)
    if m:
        cantidad = int(m.group(1))
        unidad = m.group(2).lower()
        ahora = datetime.now()
        if unidad.startswith('min'):
            return ahora - timedelta(minutes=cantidad)
        if unidad.startswith('h'):
            return ahora - timedelta(hours=cantidad)
        if unidad.startswith('d'):
            return ahora - timedelta(days=cantidad)
        if unidad.startswith('sem'):
            return ahora - timedelta(weeks=cantidad)
        if unidad.startswith('mes'):
            return ahora - timedelta(days=30 * cantidad)
        if unidad.startswith('a'):
            return ahora - timedelta(days=365 * cantidad)
    # Timestamps que ya son fecha
    try:
        return datetime.fromisoformat(v.replace('Z', '+00:00')).replace(tzinfo=None)
    except ValueError:
        pass
    try:
        numero = float(v)
        if numero > 10_000_000_000:  # epoch en ms
            numero = numero / 1000
        return datetime.fromtimestamp(numero)
    except (ValueError, OSError, OverflowError):
        return None


# ---------------------------------------------------------------------------
# Detección del tipo de CSV
# ---------------------------------------------------------------------------

def detectar_tipo_csv(df: pd.DataFrame) -> str:
    """
    Detecta de qué red proviene un CSV de Instant Data Scraper basándose en el
    contenido de las celdas (no en los nombres de columna, que son clases CSS).

    Retorna:
        'facebook' | 'instagram' | 'desconocido'.
    """
    if df is None or df.empty:
        return 'desconocido'
    celdas = ' '.join(_cadena(v).lower() for v in df.head(12).values.flatten())
    if 'instagram.com/p/' in celdas or 'instagram.com/reels/' in celdas \
            or 'repostear' in celdas or 'verificado' in celdas:
        return 'instagram'
    if 'facebook.com' in celdas or 'fbcdn.net' in celdas or 'compartido con:' in celdas:
        return 'facebook'
    return 'desconocido'


# ---------------------------------------------------------------------------
# Limpieza de Facebook
# ---------------------------------------------------------------------------

def _candidatos_nombre(row) -> list:
    """Candidatos a autor (nombres cortos, no-URL, no-ruido, no-métrica)."""
    nombres = []
    for valor in row:
        texto = _cadena(valor)
        if not texto or _es_url(texto) or _token_ruido(texto) or _es_metrica(texto):
            continue
        if len(texto) > 50:
            continue
        if 'compartido con' in texto.lower():
            continue
        nombres.append(texto)
    return nombres


def _es_nombre_persona(texto: str) -> bool:
    """Heurística: nombre de persona (palabras comenzando en mayúsculas)."""
    palabras = texto.split()
    if not (1 <= len(palabras) <= 6):
        return False
    conectores = {'de', 'del', 'y', 'la', 'el', 'con', 'a', 'en', 'di'}
    partes_nombre = 0
    for p in palabras:
        limpia = re.sub(r'[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]', '', p)
        if not limpia:
            continue
        if limpia[0].isupper() or limpia.lower() in conectores:
            partes_nombre += 1
    return partes_nombre >= max(1, len(palabras) - 1)


def _extraer_autor_facebook(row) -> str:
    """Elige el mejor candidato a autor de una fila de Facebook."""
    nombres = _candidatos_nombre(row)
    if not nombres:
        return ''
    order = sorted(nombres, key=lambda n: (
        -int(_es_nombre_persona(n)),   # nombres de persona primero
        len(n),                        # de preferencia corto
    ))
    return order[0] if order else (nombres[0] if nombres else '')


def _extraer_texto(row) -> str:
    """Busca el caption: cadena más larga que no sea URL, ruido ni métrica."""
    mejor = ''
    for valor in row:
        texto = _cadena(valor)
        if not texto or _es_url(texto) or _token_ruido(texto) or _es_metrica(texto):
            continue
        if 'compartido con' in texto.lower():
            continue
        if len(texto) > len(mejor):
            mejor = texto
    return mejor


def _buscar_por_contenido(row, substrings: tuple) -> str:
    """Devuelve el primer valor de la fila que contenga alguno de los substrings."""
    for valor in row:
        texto = _cadena(valor)
        if any(s in texto.lower() for s in substrings):
            return texto
    return ''


def limpiar_csv_facebook(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia un CSV crudo de Facebook (Instant Data Scraper) y lo convierte a un
    DataFrame homogéneo con columnas:
    `usuario, texto, fecha, likes, comentarios, compartidos, imagen, url_post`.

    - Deduplica por (usuario, texto) y (usuario, url_post).
    - Las métricas "1.2 mil" se convierten a números; las no parseables a 0.
    - Facebook no trae fecha -> `fecha` queda en None (NaT en el dashboard).

    Retorna:
        pd.DataFrame limpio de posts de Facebook.
    """
    filas = []
    for _, fila_raw in df.iterrows():
        fila = list(fila_raw)
        autor = _extraer_autor_facebook(fila)
        texto = _extraer_texto(fila)
        numeros = _numeros_de_fila(fila)
        likes = numeros[0] if len(numeros) > 0 else 0
        comentarios = numeros[1] if len(numeros) > 1 else 0
        compartidos = numeros[2] if len(numeros) > 2 else 0
        imagen = _buscar_por_contenido(fila, ('scontent.', 'fbcdn.net'))
        url_post = _buscar_por_contenido(fila, ('/photo/?fbid=', '/posts/', '/videos/',
                                                '/reels/', '/groups/'))
        visibilidad = _buscar_por_contenido(fila, ('compartido con',))
        if not texto and not autor:
            continue
        filas.append({
            'usuario': autor,
            'texto': texto,
            'fecha': None,
            'likes': likes,
            'comentarios': comentarios,
            'compartidos': compartidos,
            'imagen': imagen,
            'url_post': url_post,
            'visibilidad': visibilidad,
        })
    salida = pd.DataFrame(filas, columns=[
        'usuario', 'texto', 'fecha', 'likes', 'comentarios', 'compartidos',
        'imagen', 'url_post', 'visibilidad'])
    salida = salida.drop_duplicates(
        subset=['usuario', 'texto', 'url_post'], keep='first')
    return salida.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Limpieza de Instagram
# ---------------------------------------------------------------------------

def _extraer_usuario_instagram(row) -> str:
    """Handle de Instagram (patrón típico de usuario). """
    mejor = ''
    for valor in row:
        texto = _cadena(valor)
        if _es_url(texto) or not texto:
            continue
        if re.match(r'^@?[a-zA-Z][a-zA-Z0-9_.]{0,29}$', texto) and not _token_ruido(texto):
            if len(texto) < len(mejor) or not mejor:
                mejor = texto.lstrip('@')
    return mejor


def _extraer_fecha_instagram(row) -> Optional[datetime]:
    """Primera fecha relativa ("7 h") o timestamp de la fila."""
    for valor in row:
        texto = _cadena(valor)
        if re.match(r'(?i)^\s*\d+\s*(min|h|d|sem|mes|a)\b', texto):
            return convertir_fecha_relativa(texto)
    return None


def _extraer_imagen_instagram(row) -> str:
    """Prefiere la imagen/media del post (última URL de imagen) si existe."""
    urls_imagen = []
    for valor in row:
        texto = _cadena(valor)
        if texto.startswith(('https://instagram.f', 'https://scontent')) \
                and re.search(r'\.(jpg|jpeg|png|webp)(\?|$)', texto.lower()):
            if 'emoji' not in texto.lower():
                urls_imagen.append(texto)
    if urls_imagen:
        return urls_imagen[-1]  # la imagen del post suele ir después del avatar
    return ''


def limpiar_csv_instagram(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia un CSV crudo de Instagram (Instant Data Scraper) y lo convierte a un
    DataFrame homogéneo con columnas:
    `usuario, texto, fecha, likes, comentarios, compartidos, imagen, url_post`.

    - Deduplica por (usuario, texto) y (usuario, url_post).
    - La fecha relativa ("7 h", "1 d") se convierte a absoluta.
    - 'Repostear' (reposts) se mapea a compartidos; vistas/guardados quedan en 0.

    Retorna:
        pd.DataFrame limpio de posts de Instagram.
    """
    filas = []
    for _, fila_raw in df.iterrows():
        fila = list(fila_raw)
        usuario = _extraer_usuario_instagram(fila)
        texto = _extraer_texto(fila)
        fecha = _extraer_fecha_instagram(fila)
        numeros = _numeros_de_fila(fila)
        # En el CSV de IG las métricas salen en orden: likes, comentarios, repostes
        likes = numeros[0] if len(numeros) > 0 else 0
        comentarios = numeros[1] if len(numeros) > 1 else 0
        compartidos = numeros[2] if len(numeros) > 2 else 0
        imagen = _extraer_imagen_instagram(fila)
        url_post = _buscar_por_contenido(fila, ('instagram.com/p/', 'instagram.com/reels/'))
        verificado = any(_cadena(v).lower() == 'verificado' for v in fila)
        if not texto and not usuario:
            continue
        filas.append({
            'usuario': usuario,
            'texto': texto,
            'fecha': fecha,
            'likes': likes,
            'comentarios': comentarios,
            'compartidos': compartidos,
            'imagen': imagen,
            'url_post': url_post,
            'verificado': verificado,
        })
    salida = pd.DataFrame(filas, columns=[
        'usuario', 'texto', 'fecha', 'likes', 'comentarios', 'compartidos',
        'imagen', 'url_post', 'verificado'])
    salida = salida.drop_duplicates(
        subset=['usuario', 'texto', 'url_post'], keep='first')
    return salida.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Normalización al esquema del dashboard
# ---------------------------------------------------------------------------

def _clasificar_tema(texto: str) -> str:
    """Asigna un tema electoral por coincidencia de keywords (best-effort)."""
    t_min = texto.lower()
    for tema, keywords in TEMAS_ELECTORALES.items():
        if any(k in t_min for k in keywords):
            return tema
    return 'Participación'


def _id_post(red: str, usuario: str, texto: str, url: str) -> int:
    """id_post numérico estable derivado de (red|usuario|texto|url)."""
    base = f'{red.lower()}|{usuario.lower()}|{texto[:160].lower()}|{url}'
    return int(hashlib.md5(base.encode('utf-8')).hexdigest()[:8], 16)


def normalizar_para_dashboard(df_limpio: pd.DataFrame, red_social: str) -> pd.DataFrame:
    """
    Convierte un DataFrame limpio (de `limpiar_csv_facebook` o
    `limpiar_csv_instagram`) al esquema `COLUMNAS_POSTS` del dashboard,
    reutilizando `clasificar_sentimiento` y `TEMAS_ELECTORALES`.

    - `fecha`: None (Facebook) -> NaT; IG relativa -> ya absoluta.
    - `vistas`/`guardados` = 0 (no están en los CSVs).
    - `engagement` y `engagement_rate` con la misma fórmula que
      `modulos.scrapeless.normalizar_posts` (base 1,000 impresiones).

    Retorna:
        pd.DataFrame con las columnas de `COLUMNAS_POSTS`.
    """
    filas = []
    for _, limpia in df_limpio.iterrows():
        texto = _cadena(limpia.get('texto'))
        usuario = _cadena(limpia.get('usuario'))
        fecha = limpia.get('fecha')
        likes = int(limpia.get('likes') or 0)
        comentarios = int(limpia.get('comentarios') or 0)
        compartidos = int(limpia.get('compartidos') or 0)
        if not texto and not usuario and not fecha:
            continue
        engagement = likes + comentarios + compartidos
        filas.append({
            'id_post': _id_post(red_social, usuario, texto, _cadena(limpia.get('url_post'))),
            'red_social': red_social,
            'usuario': f'@{usuario}' if usuario and not usuario.startswith('@') else usuario,
            'fecha': fecha,
            'texto': texto,
            'hashtags': re.findall(r'#\w+', texto),
            'likes': likes,
            'comentarios': comentarios,
            'compartidos': compartidos,
            'vistas': 0,
            'guardados': 0,
            'sentimiento': clasificar_sentimiento(texto),
            'tema_electoral': _clasificar_tema(texto),
            'engagement': engagement,
            'engagement_rate': round((engagement / 1000.0) * 100, 2),
        })
    df = pd.DataFrame(filas, columns=list(COLUMNAS_POSTS))
    df['usuario'] = df['usuario'].fillna('')
    df['fecha'] = pd.to_datetime(df['fecha'], errors='coerce')
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------

def _leer_csv(datos) -> pd.DataFrame:
    """Lee un CSV desde una ruta, UploadedFile o bytes, con fallo de encoding."""
    if isinstance(datos, str):
        fuente: object = datos
    elif hasattr(datos, 'getvalue'):
        fuente = io.BytesIO(datos.getvalue())
    elif hasattr(datos, 'read'):
        fuente = io.BytesIO(datos.read())
    else:
        fuente = io.BytesIO(bytes(datos or b''))
    for encoding in ('utf-8-sig', 'latin-1'):
        try:
            if hasattr(fuente, 'seek'):
                fuente.seek(0)
            return pd.read_csv(fuente, encoding=encoding)
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
    raise ValueError('No se pudo decodificar el CSV')


def procesar_archivos(fb=None, ig=None) -> dict:
    """
    Orquesta la carga de dos archivos CSV (Facebook e Instagram) de Instant Data
    Scraper: detecta tipo, limpia, normaliza al esquema del dashboard y devuelve
    los DataFrames listos para anexar a `posts_sociales`.

    Retorna:
        dict con 'fb' (df normalizado o vacío), 'ig' (df normalizado o vacío),
        'errores' (lista) y 'avisos' (lista).
    """
    errores = []
    avisos = []
    df_fb = pd.DataFrame(columns=COLUMNAS_POSTS)
    df_ig = pd.DataFrame(columns=COLUMNAS_POSTS)

    for nombre, archivo, red in (('Facebook', fb, 'facebook'),
                                 ('Instagram', ig, 'instagram')):
        if archivo is None:
            continue
        try:
            crudo = _leer_csv(archivo)
        except Exception as e:
            errores.append(f'{nombre}: no se pudo leer el archivo ({e})')
            continue
        if crudo.empty:
            errores.append(f'{nombre}: El archivo está vacío')
            continue
        tipo = detectar_tipo_csv(crudo)
        if tipo != red:
            errores.append(
                f'{nombre}: Formato no reconocido. Verifica que sea de Instant '
                f'Data Scraper ({tipo!r}).')
            continue
        if red == 'facebook':
            limpio = limpiar_csv_facebook(crudo)
            if limpio.empty:
                errores.append('Facebook: no se pudieron extraer posts del CSV')
                continue
            df_fb = normalizar_para_dashboard(limpio, 'Facebook')
            if limpio['fecha'].isna().all():
                avisos.append('Facebook sin fecha (se muestra como "Sin fecha", '
                              'no se incluye en la serie temporal).')
        elif red == 'instagram':
            limpio = limpiar_csv_instagram(crudo)
            if limpio.empty:
                errores.append('Instagram: no se pudieron extraer posts del CSV')
                continue
            df_ig = normalizar_para_dashboard(limpio, 'Instagram')
            avisos.append('Fechas de Instagram convertidas de relativas a '
                          'absolutas en el momento del procesado.')

    return {'fb': df_fb, 'ig': df_ig, 'errores': errores, 'avisos': avisos}