"""
tests/test_scrapeless_plan.py
=============================

Pruebas sin red de la capa de extracción de Scrapeless (`modules/scrapeless.py`)
para el ámbito "palabra clave": estimación de costo, prompts de X, mapeo de
items de búsqueda de TikTok y degradación elegante (errores claros, sin crash).

Ejecutar desde la raíz del repo:
    python -m pytest tests/test_scrapeless_plan.py -v
"""

import pandas as pd

from modules.scrapeless import (
    COSTO_GROK,
    COSTO_POR_PETICION,
    X_SEARCH_PROMPT_KEYWORD_TEMPLATE,
    _item_tiktok_buscador,
    buscar_posts_tiktok,
    estimar_costo,
    extraer_posts_x,
    normalizar_posts,
)


def _plan_keyword():
    return [
        {'red': 'TikTok', 'ambito': 'keyword', 'activo': True,
         'consulta': 'agua', 'limite': 70},
        {'red': 'X', 'ambito': 'keyword', 'activo': True,
         'consulta': 'tlalpan', 'limite': 30},
    ]


def test_prompt_keyword_x():
    prompt = X_SEARCH_PROMPT_KEYWORD_TEMPLATE.format(keyword='desabasto')
    assert 'desabasto' in prompt
    assert prompt.lower().startswith('what has been posted on x')


def test_estimar_costo_keyword():
    est = estimar_costo(_plan_keyword(), balance=1.0)
    # TikTok keyword: ceil(70/35)=2 llamadas de actor; X keyword: 1 prompt de Grok.
    assert est['peticiones'] == 3
    esperado = 2 * COSTO_POR_PETICION['TikTok'] + COSTO_GROK
    assert abs(est['costo_usd'] - esperado) < 1e-6
    assert est['alcanza'] is True


def test_estimar_costo_x_perfil_sigue_grok():
    plan = [{'red': 'X', 'ambito': 'perfil', 'activo': True,
             'consulta': 'gobernador', 'limite': 30}]
    est = estimar_costo(plan, balance=None)
    assert est['peticiones'] == 1
    assert est['costo_usd'] == COSTO_GROK


def test_item_tiktok_buscador_normaliza():
    video = {
        'id': '7301234567890',
        'desc': 'El agua #desabasto en Tlalpan',
        'createTime': 1700000000000,  # milisegundos
        'author': {'uniqueId': 'cuenta_agua', 'nickname': 'Cuenta Agua'},
        'stats': {'playCount': 1200, 'diggCount': 30, 'commentCount': 4,
                  'shareCount': 2, 'collectCount': 7},
    }
    item = _item_tiktok_buscador(video)
    assert item['id'] == '7301234567890'
    assert item['desc'].startswith('El agua')
    # createTime en ms se convierte a segundos para _extraer_fecha.
    assert item['create_time'] == 1700000000
    assert item['author']['uniqueId'] == 'cuenta_agua'
    assert item['stats']['playCount'] == 1200


def test_normalizar_posts_tiktok_buscador():
    item = _item_tiktok_buscador({
        'id': '730001',
        'desc': 'El desabasto de agua es grave #Agua',
        'createTime': 1700000000,
        'author': {'uniqueId': 'cuenta_x', 'nickname': 'Cuenta'},
        'stats': {'playCount': 500, 'diggCount': 10, 'commentCount': 1,
                  'shareCount': 0, 'collectCount': 2},
    })
    df = normalizar_posts('TikTok', [item])
    assert not df.empty
    fila = df.iloc[0]
    assert fila['red_social'] == 'TikTok'
    assert fila['usuario'] == '@cuenta_x'
    assert fila['vistas'] == 500
    assert fila['likes'] == 10
    assert 'agua' in fila['hashtags'] or 'Agua' in fila['hashtags']
    assert pd.notna(fila['fecha'])


def test_buscar_tiktok_palabra_clave_vacia():
    # Sin red: consulta vacía debe devolver error claro, no lanzar excepción.
    items, error = buscar_posts_tiktok('   ', limite=10, api_key='dummy-key')
    assert items == []
    assert error and 'vacía' in (error.get('error') or '')


def test_extraer_x_palabra_clave_vacia():
    res = extraer_posts_x('', limite=10, api_key='dummy-key', keyword='   ')
    assert res['success'] is False
    assert 'vacía' in (res['error'] or '')