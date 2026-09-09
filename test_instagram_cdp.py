#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_instagram_cdp.py
=====================

Prueba de la extracción REAL de Instagram via Scraping Browser (CDP) + la API
interna `web_profile_info`. Usa la función `extraer_perfil_instagram()` de
modules/scrapeless.py (la misma que usa la Pestaña 2).

Flujo:
    1. Leer la API Key de .streamlit/secrets.toml (sección [SCRAPELESS]).
    2. Llamar a `extraer_perfil_instagram()` (conecta a
       wss://browser.scrapeless.com/api/v2/browser, siembra cookies anónimas en
       instagram.com y hace fetch a la API interna).
    3. Mostrar el perfil y los posts normalizados extraídos.
    4. Manejar errores gracefulmente (404, privado, 401/403, 429, login-wall,
       timeout).

Requisitos:
    pip install playwright

Uso:
    python test_instagram_cdp.py [usuario]
    python test_instagram_cdp.py municipiotlalpan

Nota: NO hace falta `playwright install`: nos conectamos al navegador remoto de
Scrapeless via `connect_over_cdp` (sin Chromium local).
"""

import argparse
import os
import re
import sys
from pathlib import Path

# Fuerza salida UTF-8 en consolas Windows para no romper con caracteres
# especiales (emoji, acentos). Si el código de páginas no lo soporta, degrada.
try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, ValueError):
    pass

PROFILE_USER = 'municipiotlalpan'   # perfil por defecto (público)


def leer_api_key(path: str = '.streamlit/secrets.toml') -> str:
    """
    Lee la API Key de Scrapeless del archivo de secrets del proyecto.

    Retorna:
        str con la API key, o '' si no existe.
    """
    ruta = Path(path)
    if not ruta.exists():
        print(f'[ERROR] No existe el archivo de secrets: {ruta.resolve()}')
        return ''
    texto = ruta.read_text(encoding='utf-8')
    m = re.search(r'\[SCRAPELESS\](.*?)(?:\[[A-Z_]+\]|\Z)', texto, re.DOTALL)
    seccion = m.group(1) if m else texto
    m_key = re.search(r'API_KEY\s*=\s*["\']([^"\']+)["\']', seccion)
    if not m_key:
        print('[ERROR] No se encontró la llave API_KEY en la sección [SCRAPELESS].')
        return ''
    return m_key.group(1).strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Prueba de extracción de Instagram via Scraping Browser + web_profile_info.')
    parser.add_argument('usuario', nargs='?', default=PROFILE_USER,
                        help=f'Perfil público de Instagram a extraer (default: {PROFILE_USER})')
    parser.add_argument('--limite', type=int, default=12,
                        help='Número máximo de posts a extraer (default: 12)')
    args = parser.parse_args()
    usuario = args.usuario.strip().lstrip('@')

    api_key = os.environ.get('SCRAPELESS_API_KEY', '').strip() or leer_api_key()
    if not api_key:
        print('[ERROR] No hay API key configurada en .streamlit/secrets.toml '
              '(sección [SCRAPELESS] -> API_KEY).')
        sys.exit(1)

    print('=' * 64)
    print('PRUEBA: Scraping Browser (CDP) + API interna web_profile_info')
    print('=' * 64)
    print(f'API Key     : {api_key[:8]}... (oculta, {len(api_key)} chars)')
    print(f'Perfil      : @{usuario}')
    print(f'Límite posts: {args.limite}')
    print('-' * 64)

    from modules.scrapeless import extraer_perfil_instagram

    resultado = extraer_perfil_instagram(usuario, limite=args.limite, api_key=api_key)

    if not resultado.get('success'):
        print('\n' + '=' * 64)
        print('RESULTADO: FALLO')
        print('=' * 64)
        print(f'Error : {resultado.get("error")}')
        print('-' * 64)
        print('Sugerencias:')
        if 'no encontrado' in (resultado.get('error') or ''):
            print('  - El perfil no existe o fue desactivado (404).')
        elif 'privado' in (resultado.get('error') or ''):
            print('  - El perfil es privado; solo se puede extraer perfiles públicos.')
        elif 'autenticación' in (resultado.get('error') or ''):
            print('  - Revisa la API Key de Scrapeless y el saldo en app.scrapeless.com.')
        elif 'Rate limit' in (resultado.get('error') or ''):
            print('  - Instagram limitó las peticiones; espera unos minutos y reintenta.')
        elif 'login' in (resultado.get('error') or ''):
            print('  - La sesión fue redirigida a login; vuelve a intentar en unos minutos.')
        elif 'tiempo' in (resultado.get('error') or '').lower():
            print('  - La sesión CDP excedió el timeout; reintenta con menos posts.')
        sys.exit(1)

    perfil = resultado.get('profile') or {}
    posts = resultado.get('posts') or []

    # --- Perfil ---
    print('\n[1] PERFIL')
    print(f'    Usuario       : {perfil.get("usuario")}')
    print(f'    Nombre        : {perfil.get("nombre")}')
    print(f'    Bio           : {(perfil.get("bio") or "")[:200]}')
    seg = (f"{perfil.get('seguidores', 0):,}"
           if perfil.get('seguidores_disponibles') else 'No disponible')
    sig = (f"{perfil.get('siguiendo', 0):,}"
           if perfil.get('siguiendo_disponibles') else 'No disponible')
    print(f'    Seguidores    : {seg}')
    print(f'    Siguiendo     : {sig}')
    print(f'    Publicaciones : {perfil.get("publicaciones", 0):,}')
    print(f'    Verificado    : {"Sí" if perfil.get("verificado") else "No"}')
    print(f'    Avatar URL    : {perfil.get("avatar_url")}')

    # --- Posts ---
    print(f'\n[2] POSTS ({len(posts)} extraídos de la primera página)')
    for i, post in enumerate(posts, 1):
        print(f'    {i:>2}. [{post.get("tipo")}] {post.get("post_id")} '
              f'- likes={post.get("like_count")} com={post.get("comment_count")}')
        caption = (post.get('caption') or '')[:160].replace('\n', ' ')
        if caption:
            print(f'        caption: {caption}')
        print(f'        fecha  : {post.get("timestamp")} | img: {bool(post.get("display_url"))}')

    print('\n' + '=' * 64)
    print('RESULTADO: ✅ ÉXITO — se extrajo perfil y posts reales de Instagram')
    print('=' * 64)


if __name__ == '__main__':
    main()