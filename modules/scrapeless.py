import json
import math
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Optional

import pandas as pd
import streamlit as st

from modules.social_media_generator import TEMAS_ELECTORALES, clasificar_sentimiento

# --- Configuración de la API de Scrapeless ---------------------------------
HOST = 'api.scrapeless.com'
BASE_URL = f'https://{HOST}'
ENDPOINT_SOLICITUD = f'{BASE_URL}/api/v1/scraper/request'
ENDPOINT_RESULTADO = f'{BASE_URL}/api/v1/scraper/result/'
ENDPOINT_SALDO = f'{BASE_URL}/api/v1/me'

# Actores de la Scraping API por red social (confirmados en el apidoc público).
# 'busqueda' (palabra clave) de TikTok fue deprecado por Scrapeless y no hay
# actor público para Instagram; el flujo real soportado es el perfil de TikTok.
ACTORES = {
    'TikTok': {
        'perfil': 'scraper.tiktok.user.detail',
        'publicaciones_perfil': 'scraper.tiktok.user.work',
    },
    'Instagram': {},
}

# Mensajes para los flujos que Scrapeless ya no ofrece
MENSAJE_KEYWORD_NO_SOPORTADA = (
    'La búsqueda por palabra clave/hashtag de TikTok ya no está soportada '
    'por Scrapeless (actor deprecado). Usa el ámbito "Perfil definido" con un @usuario.'
)
MENSAJE_INSTAGRAM_NO_SOPORTADO = 'Instagram no cuenta con actor público en Scrapeless (por ahora).'

# Resultados máximos por llamada de búsqueda (base para estimar paginación)
RESULTADOS_POR_LLAMADA = 35

# Costo estimado por petición en USD (ajústalo según tu plan de créditos)
COSTO_POR_PETICION = {
    'TikTok': 0.02,
    'Instagram': 0.025,
}


# --- Helpers de respuesta ---------------------------------------------------

def _llamar_api(url, api_key, payload=None, timeout=60):
    """
    Ejecuta una petición HTTP contra la API de Scrapeless con la cabecera x-api-token.
    Retorna:
        tuple (status, body). body es el JSON parseado, o {'raw': ...} si no es JSON.
    """
    headers = {'x-api-token': api_key, 'Content-Type': 'application/json'}
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers=headers,
        method='POST' if payload is not None else 'GET'
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            cuerpo = resp.read().decode('utf-8')
            status = resp.status
        try:
            return status, json.loads(cuerpo)
        except (json.JSONDecodeError, ValueError):
            return status, {'raw': cuerpo}
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except Exception:
            return e.code, {'error': e.reason}


def _obtener(item, *llaves, default=None):
    """Busca el primer valor no nulo probando varias llaves de un dict."""
    if not isinstance(item, dict):
        return default
    for llave in llaves:
        valor = item.get(llave, default)
        if valor is not None:
            return valor
    return default


# --- Funciones públicas de la API -------------------------------------------

def obtener_api_key() -> str:
    """
    Obtiene la API Key de Scrapeless: primero desde .streamlit/secrets.toml
    (sección [SCRAPELESS] -> API_KEY) y después desde el campo de la UI
    (st.session_state.scrapeless_api_key).

    Retorna:
        str con la key configurada, o '' si no hay ninguna.
    """
    try:
        key_secrets = st.secrets['SCRAPELESS']['API_KEY'].strip()
        if key_secrets:
            return key_secrets
    except Exception:
        pass
    return st.session_state.get('scrapeless_api_key', '').strip()


def obtener_balance(api_key: str) -> Optional[dict]:
    """
    Consulta el saldo de créditos del usuario (GET /api/v1/me). Esta consulta
    no cuesta créditos.

    Retorna:
        dict con 'creditos', 'excesos', 'plan' y 'usuario', o None si falla.
    """
    if not api_key:
        return None
    try:
        status, body = _llamar_api(ENDPOINT_SALDO, api_key, timeout=20)
        if status != 200:
            return None
        return {
            'creditos': float(body.get('credits') or 0),
            'excesos': float(body.get('excessCredits') or 0),
            'plan': body.get('plan') or {},
            'usuario': body.get('userId') or '',
        }
    except Exception as e:
        print(f'SCRAPELESS: No se pudo consultar el saldo ({e}).')
        return None


def _mensaje_error(body):
    """
    Extrae un mensaje de error de un body de respuesta de Scrapeless si existe.
    Scrapeless a veces responde HTTP 200 con un body tipo {'code': N, 'message': ...},
    por lo que hay que revisar el contenido además del código HTTP.

    Retorna:
        str con el mensaje, o None si el body no parece un error.
    """
    if not isinstance(body, dict):
        return None
    if body.get('success') is False:
        return body.get('message') or str(body.get('error') or 'Respuesta fallida')
    codigo = body.get('code')
    if codigo is not None and codigo not in (200, 0):
        return (body.get('message') or body.get('msg') or body.get('error')
                or f'Código de error: {codigo}')
    return None


def ejecutar_actor(actor: str, input_dict: dict, api_key: str,
                   max_polls: int = 25, poll_interval: int = 3,
                   progress=None) -> dict:
    """
    Ejecuta un actor de la Scraping API de Scrapeless. Maneja respuestas
    síncronas (HTTP 200) y asíncronas (HTTP 201, con polling hasta max_polls).

    Retorna:
        dict con los datos del actor, o {'error': ...} en caso de fallo.
    """
    status, body = _llamar_api(
        ENDPOINT_SOLICITUD, api_key, {'actor': actor, 'input': input_dict}
    )
    if status == 200:
        mensaje = _mensaje_error(body)
        if mensaje:
            return {'error': mensaje}
        return body
    if status == 201:
        task_id = (body or {}).get('taskId')
        if not task_id:
            return {'error': 'Respuesta asíncrona sin taskId'}
        for intento in range(max_polls):
            if progress:
                progress((intento + 1) / max_polls)
            time.sleep(poll_interval)
            status, body = _llamar_api(f'{ENDPOINT_RESULTADO}{task_id}', api_key)
            if status == 200:
                mensaje = _mensaje_error(body)
                return {'error': mensaje} if mensaje else body
            if status != 201:
                mensaje = _mensaje_error(body)
                return {'error': mensaje or f'HTTP {status}'}
        return {'error': f'Tiempo de espera agotado tras {max_polls} intentos'}
    mensajes_http = {
        400: 'Parámetros inválidos (400)',
        401: 'API Key no autorizada (401)',
        429: 'Rate limit excedido (429)',
        500: 'Error interno del servidor (500)',
    }
    detalle = _mensaje_error(body) or (body or {}).get('error') \
        or (body or {}).get('message') or ''
    return {'error': mensajes_http.get(status, f'HTTP {status}')
                     + (f': {detalle}' if detalle else '')}


# --- Búsqueda por palabra clave / hashtag -----------------------------------

def buscar_posts_tiktok(keyword: str, limite: int = 35, api_key: Optional[str] = None):
    """
    Búsqueda por palabra clave/hashtag de TikTok (fase 1 original).
    Scrapeless depreco el actor de búsqueda, por lo que este flujo ya no es
    posible por la API; se conserva únicamente como máscara informativa.

    Retorna:
        tuple (items, error): lista vacía y el mensaje de no soportado.
    """
    return [], {'error': MENSAJE_KEYWORD_NO_SOPORTADA}


def buscar_posts_perfil_tiktok(usuario: str, limite: int = 35, api_key: Optional[str] = None):
    """
    Recopila las publicaciones públicas recientes de un usuario de TikTok.
    Flujo de 2 actores confirmados en Scrapeless:
    - `scraper.tiktok.user.detail` (unique_id) resuelve el `sec_uid`.
    - `scraper.tiktok.user.work` (sec_uid, cursor, count) devuelve `items[]`.
    Solo avanza de página si la propia respuesta indica `has_more` y trae un
    `cursor` (no se inventan campos de continuación).

    Retorna:
        tuple (items, error): items crudos de la API y error (None si OK).
    """
    api_key = api_key or obtener_api_key()
    if not api_key:
        return [], {'error': 'No hay API Key configurada'}

    perfil = ejecutar_actor(ACTORES['TikTok']['perfil'],
                            {'unique_id': usuario.lstrip('@')}, api_key)
    if 'error' in perfil:
        return [], {'error': perfil['error']}
    sec_uid = perfil.get('sec_uid')
    if not sec_uid:
        return [], {'error': f'No se pudo obtener el sec_uid del usuario @{usuario}'}

    items = []
    cursor = '0'
    restante = min(int(limite), 200)
    while restante > 0:
        cantidad = min(RESULTADOS_POR_LLAMADA, restante)
        resultado = ejecutar_actor(ACTORES['TikTok']['publicaciones_perfil'], {
            'sec_uid': sec_uid,
            'cursor': cursor,
            'count': cantidad,
        }, api_key)
        if 'error' in resultado:
            return items, {'error': resultado['error']}
        pagina = resultado.get('items') or resultado.get('data') or []
        if not pagina:
            break
        items.extend(pagina)
        restante -= len(pagina)
        if resultado.get('has_more') is not True or not resultado.get('cursor'):
            break
        cursor = str(resultado['cursor'])
    return items[:int(limite)], None


def ejecutar_plan(plan: list, api_key: Optional[str] = None) -> dict:
    """
    Ejecuta un plan de extracción real. El flujo soportado hoy es el perfil de
    TikTok (ámbito 'perfil'); Instagram y la búsqueda por palabra clave quedan
    fuera porque Scrapeless no los publica, y se reportan como errores claros.

    Retorna:
        dict con 'df' (DataFrame normalizado), 'posts_obtenidos', 'errores' y 'error'.
    """
    api_key = api_key or obtener_api_key()
    frames = []
    errores = []
    for config in plan:
        if not (config.get('activo') and config.get('consulta')):
            continue
        red = config['red']
        ambito = config.get('ambito', 'perfil')
        objetivo = config['consulta'].strip().lstrip('@')
        limite = int(config.get('limite') or RESULTADOS_POR_LLAMADA)
        if red == 'TikTok' and ambito == 'perfil':
            items, error = buscar_posts_perfil_tiktok(objetivo, limite, api_key=api_key)
        elif red == 'TikTok':
            error = {'error': MENSAJE_KEYWORD_NO_SOPORTADA}
            items = []
        elif red == 'Instagram':
            error = {'error': MENSAJE_INSTAGRAM_NO_SOPORTADO}
            items = []
        else:
            continue
        if error:
            errores.append(f'{red}: {error}')
            continue
        if items:
            frames.append(normalizar_posts(red, items))
    if not frames:
        mensaje = '; '.join(errores) if errores else \
            'El plan no produjo datos (revisa el @usuario y las redes activas).'
        print(f'SCRAPELESS: plan sin resultados -> {mensaje}')
        return {'df': None, 'posts_obtenidos': 0, 'errores': errores, 'error': mensaje}
    df = pd.concat(frames, ignore_index=True)
    if errores:
        print(f'SCRAPELESS: plan con errores parciales -> {errores}')
    return {'df': df, 'posts_obtenidos': len(df), 'errores': errores, 'error': None}


# --- Estimación de costo -----------------------------------------------------

def estimar_costo(plan: list, balance: Optional[float] = None) -> dict:
    """
    Estima el número de peticiones y el costo aproximado en USD de un plan,
    comparándolo contra el saldo disponible.

    Retorna:
        dict con 'peticiones', 'costo_usd', 'balance' y 'alcanza'.
    """
    peticiones, costo = 0, 0.0
    for config in plan:
        if not (config.get('activo') and config.get('consulta')):
            continue
        llamadas = max(1, math.ceil(
            int(config.get('limite') or RESULTADOS_POR_LLAMADA) / RESULTADOS_POR_LLAMADA
        ))
        if config.get('ambito') == 'perfil':
            llamadas += 1  # resolución del perfil (user.detail) + páginas
        peticiones += llamadas
        costo += llamadas * COSTO_POR_PETICION.get(config['red'], 0.02)
    costo = round(costo, 2)
    alcanza = True if balance is None else balance >= costo
    return {'peticiones': peticiones, 'costo_usd': costo, 'balance': balance, 'alcanza': alcanza}


# --- Normalización al esquema del dashboard ----------------------------------

def _texto_item(item, red):
    if red == 'TikTok':
        return _obtener(item, 'desc', 'title') or ''
    caption = _obtener(item, 'caption_text', 'caption')
    if isinstance(caption, dict):
        return caption.get('text') or ''
    return caption or _obtener(item, 'text') or ''


def _autor_item(item, red):
    if red == 'TikTok':
        return _obtener(item, 'nickname', 'uniqueId', default='') or \
            ((item.get('author') or {}).get('uniqueId') or '')
    autor = _obtener(item, 'username', default='')
    if not autor:
        autor = (item.get('owner') or {}).get('username') or ''
    return autor


def _stats_tiktok(item):
    stats = item.get('stats') or {}
    return {
        'likes': int(stats.get('diggCount') or 0),
        'comentarios': int(stats.get('commentCount') or 0),
        'compartidos': int(stats.get('shareCount') or 0),
    }


def _stats_instagram(item):
    return {
        'likes': int(_obtener(item, 'like_count', 'likes') or 0),
        'comentarios': int(_obtener(item, 'comment_count', 'comments') or 0),
        'compartidos': int(_obtener(item, 'share_count', 'shares') or 0),
    }


def _extraer_fecha(item):
    marca = _obtener(item, 'createTime', 'taken_at', 'timestamp')
    if marca is None:
        return datetime.now()
    if isinstance(marca, (int, float)):
        return datetime.fromtimestamp(marca)
    try:
        return datetime.fromisoformat(str(marca).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return datetime.now()


def extraer_hashtags(texto: str) -> list:
    """Extrae los hashtags de un texto de publicación."""
    if not texto:
        return []
    return re.findall(r'#([\wáéíóúñü]+)', texto)


def clasificar_tema(texto: str) -> str:
    """
    Clasifica el tema electoral de un texto usando las keywords de TEMAS_ELECTORALES.

    Retorna:
        str con el tema con más coincidencias, o 'Participación' si no hay.
    """
    texto_lower = texto.lower()
    mejor_tema, mejor_score = 'Participación', 0
    for tema, keywords in TEMAS_ELECTORALES.items():
        coincidencias = sum(1 for kw in keywords if kw in texto_lower)
        if coincidencias > mejor_score:
            mejor_score, mejor_tema = coincidencias, tema
    return mejor_tema


def normalizar_posts(red: str, items: list) -> pd.DataFrame:
    """
    Convierte los resultados crudos de Scrapeless al esquema estándar del
    DataFrame de posts que usa la Pestaña 2 (mismas columnas que el generador
    sintético). Reutiliza el clasificador de sentimiento y los temas electorales.

    Retorna:
        pd.DataFrame con las columnas estándar (vacío si no hay items).
    """
    registros = []
    for i, item in enumerate(items):
        texto = _texto_item(item, red)
        autor = _autor_item(item, red)
        estadisticas = _stats_tiktok(item) if red == 'TikTok' else _stats_instagram(item)
        id_post = int(_obtener(item, 'id', 'pk', default=0) or 100000 + i)
        registros.append({
            'id_post': id_post,
            'red_social': red,
            'usuario': f'@{autor}' if autor and not autor.startswith('@') else (autor or f'usuario_{i + 1}'),
            'fecha': _extraer_fecha(item),
            'texto': texto,
            'hashtags': extraer_hashtags(texto),
            'likes': estadisticas['likes'],
            'comentarios': estadisticas['comentarios'],
            'compartidos': estadisticas['compartidos'],
            'sentimiento': clasificar_sentimiento(texto),
            'tema_electoral': clasificar_tema(texto),
        })
    if not registros:
        return pd.DataFrame()
    df = pd.DataFrame(registros)
    df['engagement'] = df['likes'] + df['comentarios'] + df['compartidos']
    # Engagement rate simulado relativo a 1,000 "impresiones" (sin seguidores reales)
    df['engagement_rate'] = round((df['engagement'] / 1000.0) * 100, 2)
    return df