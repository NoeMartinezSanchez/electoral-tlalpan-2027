import asyncio
import hashlib
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

# Endpoints de la familia "AI-answer" (scraper.grok, scraper.chatgpt, etc.).
# A diferencia de los actores de sitio (v1), estos usan /api/v2/scraper/execute
# y devuelven un envelope {"status", "task_id", "task_result"}; si la respuesta
# es asíncrona, hay que hacer polling a /api/v2/scraper/result/{task_id}.
ENDPOINT_EJECUTAR_V2 = f'{BASE_URL}/api/v2/scraper/execute'
ENDPOINT_RESULTADO_V2 = f'{BASE_URL}/api/v2/scraper/result/'

# Actor de Grok para extraer posts de X (Twitter). Grok responde a un prompt y
# cita posts de X en x_search_results (NO es un feed completo: es un muestreo de
# lo que Grok considera relevante). No hay un actor dedicado "scraper.x".
ACTOR_GROK = 'scraper.grok'
X_SEARCH_PROMPT_TEMPLATE = 'What has @{usuario} posted on X recently?'
X_PAIS_DEFAULT = 'MX'
X_MODE_DEFAULT = 'MODEL_MODE_FAST'   # también válidos: AUTO y EXPERT
COSTO_GROK = 0.15                    # costo estimado por prompt de Grok (USD)
TIMEOUT_GROK = 120                   # Grok tarda ~16-60 s en responder

# Scraping Browser (WebSocket CDP) para extracción de Instagram
ENDPOINT_BROWSER = 'wss://browser.scrapeless.com/api/v2/browser'
SESSION_TTL = 60            # duración de la sesión del navegador en segundos
PROXY_COUNTRY = 'MX'        # país del proxy de salida (proxies de México)

# API interna de Instagram (web_profile_info). No requiere login: solo hay que
# "primar" una sesión anónima (navegar a instagram.com) y llamar a este endpoint
# con la cabecera X-IG-App-Id y las cookies de sesión (credentials: 'include').
URL_INSTA_BASE = 'https://www.instagram.com'
ENDPOINT_PROFILE_IG = '/api/v1/users/web_profile_info/'
X_IG_APP_ID = '936619743392459'  # ID del cliente web público de Instagram

TIMEOUT_NAVEGAR = 20        # timeout para sembrar cookies (goto a instagram.com)
TIMEOUT_EVALUAR = 15        # timeout para el fetch a la API interna

# Actores de la Scraping API por red social (confirmados en el apidoc público).
# 'busqueda' (palabra clave) de TikTok fue deprecado por Scrapeless. TikTok usa
# actores de la Scraping API; Instagram usa el Scraping Browser (CDP) + la API
# interna web_profile_info (ver extraer_perfil_instagram), no un actor.
ACTORES = {
    'TikTok': {
        'perfil': 'scraper.tiktok.user.detail',
        'publicaciones_perfil': 'scraper.tiktok.user.work',
    },
    'X': {
        'perfil': ACTOR_GROK,  # scraper.grok (familia AI-answer, /api/v2/scraper/execute)
    },
    'Instagram': {},  # Instagram se extrae vía Scraping Browser, NO como actor
}

# Mensajes para los flujos que Scrapeless ya no ofrece
MENSAJE_KEYWORD_NO_SOPORTADA = (
    'La búsqueda por palabra clave/hashtag de TikTok ya no está soportada '
    'por Scrapeless (actor deprecado). Usa el ámbito "Perfil definido" con un @usuario.'
)
MENSAJE_INSTAGRAM_KEYWORD_NO_SOPORTADA = (
    'La búsqueda por palabra clave en Instagram requiere login y no está '
    'soportada en sesión anónima. Usa el ámbito "Perfil definido" con un @usuario.'
)

# Resultados máximos por llamada de búsqueda (base para estimar paginación)
RESULTADOS_POR_LLAMADA = 35

# Posts por defecto en la primera página de perfil de Instagram (web_profile_info
# devuelve la primera tanda de ~12; más páginas requieren GraphQL, muy rate-limitado).
POSTS_PRIMERA_PAGINA_IG = 12

# Costo estimado por petición en USD (ajústalo según tu plan de créditos)
COSTO_POR_PETICION = {
    'TikTok': 0.02,
    'Instagram': 0.025,
}
# Costo estimado por sesión de Scraping Browser (Instagram). La sesión contempla
# la navegación a instagram.com + la llamada a la API interna, todo en una sola
# sesión CDP de ~60 s.
COSTO_SESION_BROWSER = 0.05


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
    Obtiene la API Key de Scrapeless desde .streamlit/secrets.toml
    (sección [SCRAPELESS] -> API_KEY) o desde los Secrets del Cloud.

    Retorna:
        str con la key configurada, o '' si no hay ninguna.
    """
    try:
        key_secrets = st.secrets['SCRAPELESS']['API_KEY'].strip()
        if key_secrets:
            return key_secrets
    except Exception:
        pass
    return ''


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


# --- Extracción de Instagram (Scraping Browser + API interna) ----------------

# JavaScript inyectado en la sesión CDP. Navegamos a instagram.com para que el
# navegador remoto acuñe las cookies anónimas (csrftoken/mid) y luego llamamos a
# la API interna web_profile_info en same-origin con `credentials: 'include'`.
# Instagram hace "double-submit CSRF": la cabecera X-CSRFToken debe coincidir
# con la cookie csrftoken, por lo que se lee de document.cookie y se inyecta.
_JS_FETCH_PERFIL = r"""
async (arg) => {
  const { usuario, appId } = arg;
  try {
    // Leer la cookie csrftoken para el double-submit CSRF.
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    const csrf = m ? m[1] : '';
    const url = '/api/v1/users/web_profile_info/?username='
      + encodeURIComponent(usuario);
    const resp = await fetch(url, {
      method: 'GET',
      credentials: 'include',
      headers: {
        // Cabeceras que el cliente web real de Instagram envía; sin ellas el
        // endpoint suele responder 401/403 o un muro de login.
        'User-Agent': navigator.userAgent,
        'X-IG-App-Id': appId,
        'X-CSRFToken': csrf,
        'X-Requested-With': 'XMLHttpRequest',
        'X-ASBD-ID': '198387',
        'Referer': 'https://www.instagram.com/' + encodeURIComponent(usuario) + '/',
        'Accept': '*/*',
        'Accept-Language': navigator.language + ',' + navigator.language + ';q=0.9',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
      },
    });
    const contentType = resp.headers.get('content-type') || '';
    const text = await resp.text();
    let json = null;
    if (contentType.indexOf('json') !== -1) {
      try { json = JSON.parse(text); } catch (e) { json = null; }
    }
    return {
      status: resp.status,
      content_type: contentType,
      body: text,
      json: json,
      final_url: window.location.href,
      cookies: document.cookie,
    };
  } catch (err) {
    // status -1 => el fetch falló dentro del navegador (red/bloqueo).
    return { status: -1, content_type: '', body: '',
             json: null, final_url: window.location.href,
             cookies: '', error: String((err && err.message) || err) };
  }
}
"""


def _url_browser(api_key: str, pais: str = PROXY_COUNTRY) -> str:
    """
    Construye la URL de conexión WebSocket del Scraping Browser de Scrapeless.

    Retorna:
        str con la URL CDP incluyendo token, sessionTTL y proxyCountry.
    """
    return f'{ENDPOINT_BROWSER}?token={api_key}&sessionTTL={SESSION_TTL}&proxyCountry={pais}'


def _caption_instagram(node: dict) -> str:
    """Extrae el texto del caption de un nodo de post de Instagram."""
    caption = ''
    caption_edges = (node.get('edge_media_to_caption') or {}).get('edges') or []
    if caption_edges:
        caption = (caption_edges[0].get('node') or {}).get('text') or ''
    return caption


def _item_instagram(node: dict, usuario: str) -> dict:
    """
    Convierte un nodo de la grilla `edge_owner_to_timeline_media` al esquema de
    item que entiende `normalizar_posts` para la red 'Instagram' (mismas llaves:
    caption, username, like_count, comment_count, timestamp, post_id).
    Incluye campos adicionales (display_url, imagenes, is_video, tipo) sin romper
    la normalización, útiles para el renderizado del perfil.

    Retorna:
        dict normalizable (item de un post de Instagram).
    """
    caption = _caption_instagram(node)
    likes = ((node.get('edge_liked_by') or {}).get('count')) or 0
    comentarios = ((node.get('edge_media_to_comment') or {}).get('count')) or 0
    # Carruseles (GraphSidecar): cada hijo trae su propia display_url.
    imagenes = []
    sidecar = node.get('edge_sidecar_to_children') or {}
    if sidecar.get('edges'):
        imagenes = [c.get('node', {}).get('display_url')
                    for c in sidecar['edges'] if c.get('node', {}).get('display_url')]
    display_url = node.get('display_url')
    if display_url and not imagenes:
        imagenes = [display_url]
    # id_post del esquema es int; Instagram expone tanto un 'id' numérico (str)
    # como un 'shortcode' alfanumérico. Se prioriza el id numérico y se guarda
    # el shortcode aparte para trazabilidad.
    return {
        'post_id': node.get('id') or node.get('shortcode'),
        'shortcode': node.get('shortcode'),
        'caption': caption,
        'username': str(usuario).lstrip('@'),
        'like_count': int(likes),
        'comment_count': int(comentarios),
        'timestamp': node.get('taken_at_timestamp'),
        'hashtags': extraer_hashtags(caption),
        'display_url': display_url,
        'imagenes': imagenes,
        'is_video': bool(node.get('is_video')),
        'tipo': 'video' if node.get('is_video') else 'imagen',
    }


def _mensaje_instagram_http(status: int, body) -> str:
    """
    Construye un mensaje de error claro a partir de un HTTP status de la API de
    Instagram y del cuerpo de la respuesta (que suele traer el motivo real, por
    ejemplo `require_login` o "Please wait a few minutes..."). Distingue el muro
    de login/rate-limit de Instagram de un fallo de autenticación genérico.

    Retorna:
        str con el mensaje en español.
    """
    texto = body if isinstance(body, str) else (json.dumps(body) if body else '')
    motivo = None
    if texto:
        try:
            info = json.loads(texto)
        except (json.JSONDecodeError, ValueError):
            info = None
        if isinstance(info, dict):
            if info.get('require_login') or 'wait a few minutes' in (
                    info.get('message') or '').lower():
                motivo = ('Instagram bloqueó la sesión anónima y pide esperar unos '
                          'minutos antes de reintentar.')
            elif info.get('message'):
                motivo = f"Instagram: {info['message']}"
    if status == 429:
        return motivo or 'Rate limit - esperar'
    if status in (401, 403):
        # 401/403 suele ser un bloqueo de la sesión anónima o de la IP, no un
        # problema de la API Key de Scrapeless (la conexión CDP ya fue válida).
        return motivo or 'Error de autenticación (sesión anónima de Instagram bloqueada)'
    return motivo or f'La API de Instagram respondió HTTP {status}.'


def _interpretar_resultado_ig(resultado, usuario: str, limite: int) -> dict:
    """
    Traduce el diccionario devuelto por el JavaScript inyectado a un resultado
    final con 'profile', 'posts' y manejo de errores conocido. En sesión anónima
    follower_count/following_count pueden venir en 0 (Instagram los oculta para
    algunos perfiles); se documentan como 'no disponible'.

    Retorna:
        dict con 'success', 'profile' (opcional), 'posts' (lista) y 'error'.
    """
    if not isinstance(resultado, dict):
        return {'success': False, 'profile': None, 'posts': [],
                'error': 'Respuesta vacía de la API interna de Instagram.'}

    status = resultado.get('status')
    url_final = resultado.get('final_url') or ''
    body = resultado.get('body') or ''
    js = resultado.get('json')

    # Login-wall: Instagram redirige a /accounts/login/ en sesiones inválidas.
    if re.search(r'/accounts/login|/login', url_final) or (
            status == 200 and not js and 'log in' in body.lower()):
        return {'success': False, 'profile': None, 'posts': [],
                'error': 'Redirigido a login - sesión inválida.'}
    if status == -1:
        return {'success': False, 'profile': None, 'posts': [],
                'error': 'El fetch a la API interna falló dentro de la sesión.'}
    if status == 404:
        return {'success': False, 'profile': None, 'posts': [],
                'error': 'Perfil no encontrado'}
    if status in (401, 403, 429):
        # Puede ser un bloqueo temporal de la sesión anónima/IP: se marca para
        # reintentar (una vez) con otra IP de salida.
        return {'success': False, 'profile': None, 'posts': [],
                'error': _mensaje_instagram_http(status, body),
                'reintentar': True}
    if status != 200:
        return {'success': False, 'profile': None, 'posts': [],
                'error': f'La API de Instagram respondió HTTP {status}.'}

    user = (js or {}).get('data', {}).get('user') if js else None
    if not user:
        # Respuesta JSON sin usuario: perfil inexistente o bloqueado.
        return {'success': False, 'profile': None, 'posts': [],
                'error': 'Perfil no encontrado'}
    if user.get('is_private'):
        return {'success': False, 'profile': None, 'posts': [],
                'error': 'Perfil privado'}

    # --- Perfil ---
    seguidores = int(user.get('follower_count') or 0)
    siguiendo = int(user.get('following_count') or 0)
    publicaciones = int((user.get('edge_owner_to_timeline_media') or {})
                        .get('count') or user.get('media_count') or 0)
    profile = {
        'usuario': f'@{usuario}',
        'nombre': user.get('full_name') or usuario,
        'bio': user.get('biography') or '',
        'avatar_url': user.get('profile_pic_url_hd') or user.get('profile_pic_url'),
        'seguidores': seguidores,
        'siguiendo': siguiendo,
        'publicaciones': publicaciones,
        'es_privado': bool(user.get('is_private')),
        'verificado': bool(user.get('is_verified')),
        # En sesión anónima Instagram puede ocultar los contadores (0).
        'seguidores_disponibles': seguidores > 0,
        'siguiendo_disponibles': siguiendo > 0,
    }

    # --- Posts (grilla de la primera página) ---
    grid = (user.get('edge_owner_to_timeline_media') or {}).get('edges') or []
    page_info = ((user.get('edge_owner_to_timeline_media') or {})
                 .get('page_info') or {})
    posts = [_item_instagram(n.get('node') or {}, usuario)
             for n in grid if n.get('node')]
    posts = posts[:int(limite)] if limite else posts
    print(f'SCRAPELESS: Instagram @{usuario} -> {len(posts)} posts, '
          f'{seguidores} seguidores.')
    return {
        'success': True,
        'profile': profile,
        'posts': posts,
        'error': None,
        'has_next_page': bool(page_info.get('has_next_page')),
        'end_cursor': page_info.get('end_cursor'),
    }


async def _intento_perfil_ig(usuario: str, limite: int, api_key: str,
                             pais: str = PROXY_COUNTRY) -> dict:
    """
    Un solo intento de sesión CDP: conecta al Scraping Browser, siembra las
    cookies anónimas navegando a instagram.com y hace fetch a la API interna
    `web_profile_info`. Cierra SIEMPRE la sesión en `finally` para no dejar
    navegadores colgados (cuestan créditos por TTL).

    Retorna:
        dict idéntico al de `_interpretar_resultado_ig` (success/profile/posts/
        error/reintentar).
    """
    from playwright.async_api import async_playwright

    browser = None
    aurora = None
    try:
        aurora = await async_playwright().start()
        browser = await aurora.chromium.connect_over_cdp(_url_browser(api_key, pais))
        contextos = browser.contexts
        if contextos:
            contexto = contextos[0]
            pagina = contexto.pages[0] if contexto.pages else await contexto.new_page()
        else:
            contexto = await browser.new_context()
            pagina = await contexto.new_page()

        # 1) Sembrar cookies anónimas (csrftoken/mid) navegando a instagram.com.
        try:
            await asyncio.wait_for(
                pagina.goto(f'{URL_INSTA_BASE}/', wait_until='domcontentloaded'),
                TIMEOUT_NAVEGAR)
            # Pequeña espera para que el servidor acuñe y entregue las cookies.
            await pagina.wait_for_timeout(3000)
        except Exception as e:
            # Si falla la navegación base seguimos: a veces el fetch aún funciona
            # si ya hay cookies; se registra como advertencia, no como error fatal.
            print(f'SCRAPELESS: Instagram - navegación base con advertencia: {e}')

        # 2) Llamar a la API interna web_profile_info dentro de la misma sesión.
        try:
            resultado = await asyncio.wait_for(
                pagina.evaluate(_JS_FETCH_PERFIL,
                                {'usuario': usuario, 'appId': X_IG_APP_ID}),
                TIMEOUT_EVALUAR)
        except asyncio.TimeoutError:
            return {'success': False, 'profile': None, 'posts': [],
                    'error': 'Tiempo de espera agotado'}
        except Exception as e:
            print(f'SCRAPELESS: Instagram - error en evaluate: {e}')
            return {'success': False, 'profile': None, 'posts': [],
                    'error': f'Error al ejecutar el fetch: {e}'}

        return _interpretar_resultado_ig(resultado, usuario, limite)
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if aurora:
            try:
                await aurora.stop()
            except Exception:
                pass


async def _extraer_perfil_ig_async(usuario: str, limite: int, api_key: str) -> dict:
    """
    Orquesta la extracción de Instagram con reintento ante bloqueos temporales
    de la sesión anónima/IP: si Instagram responde 401/403/429 (require_login,
    rate limit), se reintenta una vez con otra IP de salida (proxyCountry) antes
    de reportar el error. No requiere login de Instagram.

    Retorna:
        dict con 'success', 'profile', 'posts' y 'error'.
    """
    paises = [PROXY_COUNTRY, 'US']
    resultado = {'success': False, 'profile': None, 'posts': [],
                 'error': 'Sin intentos de extracción realizados'}
    for intento, pais in enumerate(paises):
        resultado = await _intento_perfil_ig(usuario, limite, api_key, pais=pais)
        if resultado.get('reintentar') and intento < len(paises) - 1:
            print(f'SCRAPELESS: Instagram - bloqueo temporal con proxy {pais}, '
                  f'reintentando con otra IP...')
            await asyncio.sleep(3)
            continue
        resultado.pop('reintentar', None)
        return resultado
    resultado.pop('reintentar', None)
    return resultado


def extraer_perfil_instagram(usuario: str, limite: int = POSTS_PRIMERA_PAGINA_IG,
                             api_key: Optional[str] = None) -> dict:
    """
    Extrae los datos públicos de un perfil de Instagram y sus posts recientes
    usando el Scraping Browser de Scrapeless (WebSocket CDP) + la API interna
    `web_profile_info`. No requiere login de Instagram; basta la API Key de
    Scrapeless (misma que para TikTok).

    Nota: en sesión anónima `follower_count`/`following_count` pueden venir en 0
    para algunos perfiles; se señalan como 'no disponible' en el profile.

    Retorna:
        dict con 'success' (bool), 'profile' (dict del perfil), 'posts' (lista
        de items normalizables) y 'error' (str o None).
    """
    api_key = api_key or obtener_api_key()
    if not api_key:
        return {'success': False, 'profile': None, 'posts': [],
                'error': 'No hay API Key configurada'}
    usuario = str(usuario).strip().lstrip('@')
    if not usuario:
        return {'success': False, 'profile': None, 'posts': [],
                'error': 'Usuario de Instagram vacío'}
    try:
        return asyncio.run(_extraer_perfil_ig_async(usuario, int(limite), api_key))
    except Exception as e:
        print(f'SCRAPELESS: Instagram - fallo no controlado: {e}')
        return {'success': False, 'profile': None, 'posts': [],
                'error': f'Error inesperado en la extracción: {e}'}


# --- Extracción de X (Twitter) con el actor AI scraper.grok ------------------

def ejecutar_grok(input_dict: dict, api_key: str,
                  max_polls: int = 30, poll_interval: int = 4) -> dict:
    """
    Ejecuta el actor `scraper.grok` (familia AI-answer) contra
    `POST /api/v2/scraper/execute`. Maneja respuestas síncronas (el envelope
    llega completo con `task_result`) y asíncronas (solo `task_id`, se hace
    polling a `/api/v2/scraper/result/{task_id}` hasta max_polls).

    Retorna:
        dict con task_result (via 'task_result') o {'error': ...} ante fallo.
    """
    status, body = _llamar_api(ENDPOINT_EJECUTAR_V2, api_key,
                               {'actor': ACTOR_GROK, 'input': input_dict},
                               timeout=TIMEOUT_GROK)
    if status == 200:
        mensaje = _mensaje_error(body)
        if mensaje:
            return {'error': mensaje}
        if (body or {}).get('task_result'):
            return body
        task_id = (body or {}).get('task_id')
        if not task_id:
            return {'error': 'Respuesta de Grok sin task_result ni task_id'}
        for intento in range(max_polls):
            time.sleep(poll_interval)
            status, body = _llamar_api(f'{ENDPOINT_RESULTADO_V2}{task_id}',
                                       api_key, timeout=TIMEOUT_GROK)
            if status == 200:
                mensaje = _mensaje_error(body)
                if mensaje:
                    return {'error': mensaje}
                if (body or {}).get('task_result'):
                    return body
            elif status not in (201, 202):
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


def _normalizar_item_x(post: dict, usuario: str) -> dict:
    """
    Mapea un post crudo de `x_search_results` al esquema de item que entiende
    `normalizar_posts` para X (mismas llaves: caption, username, timestamp).
    `x_search_results` solo expone view_count; likes/comentarios/compartidos/
    guardados no están disponibles y se fijan en 0.

    Retorna:
        dict con el item normalizable de un post de X.
    """
    texto = (post.get('text') or '').strip()
    if not post.get('post_id') and post.get('url'):
        # El post_id suele estar al final de la URL del post.
        segmento = str(post['url']).rstrip('/').split('/')[-1]
        if segmento.isdigit():
            post = dict(post, post_id=segmento)
    return {
        'post_id': post.get('post_id'),
        'caption': texto,
        'text': texto,
        'username': post.get('user_name') or usuario.lstrip('@'),
        'name': post.get('name') or '',
        'timestamp': post.get('create_time'),
        'view_count': int(post.get('view_count') or 0),
        'hashtags': extraer_hashtags(texto),
        'url': post.get('url') or '',
        'profile_image_url': post.get('profile_image_url') or '',
    }


def _deduplicar_posts_x(posts_crudos: list, usuario: str) -> list:
    """
    Desduplica los posts crudos de x_search_results usando como llaves tanto el
    `post_id` como un hash estable del texto (por si llegan duplicados sin id o
    con textos idénticos).

    Nota: NO se filtra por user_name. En la práctica el handle real del perfil
    puede diferir del consultado (por ejemplo al preguntar por @gobiernocdmx,
    Grok cita al usuario real @GobCDMX), por lo que un filtro estricto por
    user_name descartaría los posts válidos. Grok ya acota sus citas al perfil
    pedido por el prompt.

    Retorna:
        lista desduplicada de diccionarios crudos.
    """
    vistos = set()
    resultado = []
    for post in posts_crudos or []:
        if not isinstance(post, dict):
            continue
        claves = []
        if post.get('post_id'):
            claves.append(str(post['post_id']))
        if post.get('text'):
            claves.append(hashlib.md5(
                str(post['text']).strip().lower().encode('utf-8')).hexdigest()[:8])
        if not claves:
            continue
        # Se descarta si alguna llave ya se vio (duplicado por id o por texto).
        if any(c in vistos for c in claves):
            continue
        vistos.update(claves)
        resultado.append(post)
    return resultado


def normalizar_posts_x(posts_crudos: list, usuario: str) -> list:
    """
    Normaliza la lista cruda de posts de X (x_search_results de Grok) a items
    con el esquema del dashboard. Los posts provienen de las CITAS de Grok, no
    es un feed completo del perfil.

    Retorna:
        lista de items normalizables (vía normalizar_posts) del usuario.
    """
    items = [_normalizar_item_x(post, usuario)
             for post in _deduplicar_posts_x(posts_crudos, usuario)]
    # Conservar solo posts con contenido o id (evitar filas vacías en el DF)
    return [i for i in items if i['caption'] or i['post_id']]


def extraer_posts_x(usuario: str, limite: int = 20,
                    api_key: Optional[str] = None,
                    pais: str = X_PAIS_DEFAULT) -> dict:
    """
    Extrae posts recientes de un usuario de X (Twitter) usando el actor AI
    `scraper.grok`. Grok responde al prompt "What has @<usuario> posted on X
    recently?" y cita los posts que considera relevantes en `x_search_results`
    (muestreo, no feed completo). Reutiliza la API Key de Scrapeless.
    Nota: like_count/comment_count no están disponibles en esta API (0).

    Retorna:
        dict con 'success' (bool), 'posts' (items ya normalizables) y 'error'.
    """
    api_key = api_key or obtener_api_key()
    if not api_key:
        return {'success': False, 'posts': [], 'error': 'No hay API Key configurada'}
    usuario = str(usuario).strip().lstrip('@')
    if not usuario:
        return {'success': False, 'posts': [], 'error': 'Usuario de X vacío'}
    prompt = X_SEARCH_PROMPT_TEMPLATE.format(usuario=usuario)
    print(f'SCRAPELESS: X @{usuario} - prompt: {prompt}')
    resultado = ejecutar_grok(
        {'prompt': prompt, 'country': pais, 'mode': X_MODE_DEFAULT}, api_key)
    if 'error' in resultado:
        return {'success': False, 'posts': [], 'error': resultado['error']}
    task = resultado.get('task_result') or {}
    posts_crudos = task.get('x_search_results') or []
    if not posts_crudos:
        return {'success': False, 'posts': [],
                'error': f"No se encontraron posts de '{usuario}' en las citas de Grok"}
    items = normalizar_posts_x(posts_crudos, usuario)[:int(limite)]
    print(f'SCRAPELESS: X @{usuario} -> {len(items)} posts (de {len(posts_crudos)} crudos).')
    if not items:
        return {'success': False, 'posts': [],
                'error': f"No se encontraron posts de '{usuario}' en las citas de Grok"}
    return {'success': True, 'posts': items, 'error': None}


def ejecutar_plan(plan: list, api_key: Optional[str] = None) -> dict:
    """
    Ejecuta un plan de extracción real. Flujos soportados:
    - TikTok perfil (`scraper.tiktok.user.detail` + `scraper.tiktok.user.work`).
    - Instagram perfil (Scraping Browser / CDP + API interna `web_profile_info`).
    La búsqueda por palabra clave queda fuera (deprecada o sin soporte anónimo).

    Retorna:
        dict con 'df' (DataFrame normalizado), 'posts_obtenidos', 'errores',
        'error' y 'perfil_instagram' (perfil extraído, si el plan es de Instagram).
    """
    api_key = api_key or obtener_api_key()
    frames = []
    items_crudos = []
    errores = []
    perfil_instagram = None
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
        elif red == 'Instagram' and ambito == 'perfil':
            res_ig = extraer_perfil_instagram(objetivo, limite, api_key=api_key)
            items = res_ig.get('posts') or []
            perfil_instagram = res_ig.get('profile')
            error = res_ig.get('error')
        elif red == 'Instagram':
            error = {'error': MENSAJE_INSTAGRAM_KEYWORD_NO_SOPORTADA}
            items = []
        elif red in ('X', 'Twitter') and ambito == 'perfil':
            res_x = extraer_posts_x(objetivo, limite, api_key=api_key)
            items = res_x.get('posts') or []
            error = res_x.get('error')
        elif red in ('X', 'Twitter'):
            error = {'error': MENSAJE_KEYWORD_NO_SOPORTADA}
            items = []
        else:
            continue
        if error:
            errores.append(f'{red}: {error}')
            continue
        if items:
            items_crudos.extend(items)
            frames.append(normalizar_posts(red, items))
    if not frames:
        mensaje = '; '.join(errores) if errores else \
            'El plan no produjo datos (revisa el @usuario y las redes activas).'
        print(f'SCRAPELESS: plan sin resultados -> {mensaje}')
        return {'df': None, 'posts_obtenidos': 0, 'items': [], 'errores': errores,
                'error': mensaje, 'perfil_instagram': perfil_instagram}
    df = pd.concat(frames, ignore_index=True)
    if errores:
        print(f'SCRAPELESS: plan con errores parciales -> {errores}')
    return {'df': df, 'posts_obtenidos': len(df), 'items': items_crudos,
            'errores': errores, 'error': None, 'perfil_instagram': perfil_instagram}


# --- Estimación de costo -----------------------------------------------------

def estimar_costo(plan: list, balance: Optional[float] = None) -> dict:
    """
    Estima el número de peticiones y el costo aproximado en USD de un plan,
    comparándolo contra el saldo disponible.
    - TikTok: cuenta peticiones a la Scraping API (actor por el perfil + páginas).
    - Instagram: cuenta una única sesión de Scraping Browser (navegación + fetch).
    - X: cuenta un único prompt al actor AI scraper.grok.

    Retorna:
        dict con 'peticiones', 'costo_usd', 'balance' y 'alcanza'.
    """
    peticiones, costo = 0, 0.0
    for config in plan:
        if not (config.get('activo') and config.get('consulta')):
            continue
        if config.get('red') == 'Instagram' and config.get('ambito') == 'perfil':
            # Una sesión CDP contempla la navegación a instagram.com y la llamada
            # a la API interna para la primera página de posts.
            peticiones += 1
            costo += COSTO_SESION_BROWSER
            continue
        if config.get('red') in ('X', 'Twitter') and config.get('ambito') == 'perfil':
            # Un prompt de Grok (la respuesta cita los posts detectados).
            peticiones += 1
            costo += COSTO_GROK
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
        return _obtener(item, 'description', 'desc', 'title') or ''
    caption = _obtener(item, 'caption_text', 'caption')
    if isinstance(caption, dict):
        return caption.get('text') or ''
    return caption or _obtener(item, 'text') or ''


def _autor_item(item, red):
    if red == 'TikTok':
        return _obtener(item, 'profile_username', 'nickname', 'uniqueId', default='') or \
            ((item.get('author') or {}).get('uniqueId') or '')
    autor = _obtener(item, 'username', default='')
    if not autor:
        autor = (item.get('owner') or {}).get('username') or ''
    return autor


def _stats_tiktok(item):
    stats = item.get('stats') or {}
    return {
        'likes': int(item.get('like_count') or stats.get('diggCount') or 0),
        'comentarios': int(item.get('comment_count') or stats.get('commentCount') or 0),
        'compartidos': int(item.get('share_count') or stats.get('shareCount') or 0),
        'vistas': int(item.get('play_count') or stats.get('playCount') or 0),
        'guardados': int(item.get('collect_count') or stats.get('collectCount') or 0),
    }


def _stats_instagram(item):
    return {
        'likes': int(_obtener(item, 'like_count', 'likes') or 0),
        'comentarios': int(_obtener(item, 'comment_count', 'comments') or 0),
        'compartidos': int(_obtener(item, 'share_count', 'shares') or 0),
        'vistas': 0,
        'guardados': 0,
    }


def _stats_x(item):
    """Estadísticas de X: la API de Grok solo expone view_count (vistas)."""
    return {
        'likes': 0,
        'comentarios': 0,
        'compartidos': 0,
        'vistas': int(_obtener(item, 'view_count', 'views') or 0),
        'guardados': 0,
    }


def _stats_por_red(red: str, item) -> dict:
    """Selecciona el extractor de estadísticas según la red social del item."""
    if red == 'TikTok':
        return _stats_tiktok(item)
    if red in ('X', 'Twitter'):
        return _stats_x(item)
    return _stats_instagram(item)


def _extraer_fecha(item):
    marca = _obtener(item, 'create_time', 'createTime', 'taken_at', 'timestamp')
    if marca is None:
        return datetime.now()
    if isinstance(marca, (int, float)):
        return datetime.fromtimestamp(marca)
    try:
        # Se normaliza a naive (UTC) para mantener consistencia con el demo
        return datetime.fromisoformat(str(marca).replace('Z', '+00:00')).replace(tzinfo=None)
    except (ValueError, TypeError):
        return datetime.now()


def extraer_hashtags_item(item) -> list:
    """Hashtags del item si vienen como lista (con '#'), o extraídos del texto."""
    tags = _obtener(item, 'hashtags', default=None)
    verso = re.findall(r'#([\wáéíóúñü]+)', _texto_item(item, 'TikTok'))
    if isinstance(tags, list) and tags:
        return [str(t).lstrip('#') for t in tags]
    return verso


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


def _id_numerico(valor, indice: int, default: int = 100000) -> int:
    """
    Convierte un identificador de post a int de forma robusta. Los ids de TikTok
    ya son numéricos; los de Instagram pueden venir como 'id' numérico (str) o
    'shortcode' alfanumérico. Si no es numérico, se deriva un id estable a partir
    de un hash del valor original.

    Retorna:
        int con el id del post.
    """
    try:
        cadena = str(valor or '')
        if cadena.lstrip('-').isdigit():
            return int(cadena)
        # shortcode de Instagram -> hash md5 estable truncado a 8 hex chars
        return int(hashlib.md5(cadena.encode('utf-8')).hexdigest()[:8], 16)
    except (TypeError, ValueError):
        return default + indice


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
        estadisticas = _stats_por_red(red, item)
        id_valor = _obtener(item, 'post_id', 'id', 'pk', default=0)
        id_post = _id_numerico(id_valor, i)
        registros.append({
            'id_post': id_post,
            'red_social': red,
            'usuario': f'@{autor}' if autor and not autor.startswith('@') else (autor or f'usuario_{i + 1}'),
            'fecha': _extraer_fecha(item),
            'texto': texto,
            'hashtags': extraer_hashtags_item(item) if red == 'TikTok' else extraer_hashtags(texto),
            'likes': estadisticas['likes'],
            'comentarios': estadisticas['comentarios'],
            'compartidos': estadisticas['compartidos'],
            'vistas': estadisticas['vistas'],
            'guardados': estadisticas['guardados'],
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