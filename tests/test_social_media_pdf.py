"""
tests/test_social_media_pdf.py
==============================

Pruebas del PDF del dashboard de la Pestaña 2 (`modules/social_media.py`):
verifican que las gráficas del dashboard (o sus fallbacks de matplotlib)
quedan incrustadas como imágenes y que TODAS las secciones aparecen, incluso
cuando kaleido no puede rasterizar (se simula haciendo fallar `_png_plotly`).

Ejecutar desde la raíz del repo:
    python -m pytest tests/test_social_media_pdf.py -v
"""

import warnings
from io import BytesIO

import numpy as np
import pandas as pd
import pytest
from pypdf import PdfReader

import modules.social_media as sm
from modules.analitica_social import analizar_lda

SECCIONES = [
    'Evolución de interacciones',
    'Nube de temas',
    'Temáticas LDA',
    'Distribución por red social',
    'Alcance estimado por tema',
    'Top 15 palabras más repetidas',
    'Usuarios mencionados',
    'Hashtags en los posts',
    'Tendencia de sentimiento',
    'Últimas publicaciones',
]


def _df_pdf() -> pd.DataFrame:
    """DataFrame de prueba con las 4 columnas clave y textos variados."""
    rng = np.random.default_rng(11)
    bases = [
        'El desabasto de agua es grave #Agua #Pipas @agua_tlalpan',
        'La inseguridad aumenta con los robos #Seguridad @policia_tlalpan',
        'excelente servicio de la policia hoy #Gracias @gobtlalpan #Participacion',
    ]
    filas = []
    for i in range(60):
        texto = bases[int(rng.integers(0, 3))]
        filas.append({
            'id_post': i,
            'red_social': ['TikTok', 'X', 'Facebook'][i % 3],
            'usuario': '@c',
            'fecha': pd.Timestamp('2026-07-01') + pd.Timedelta(hours=i),
            'texto': texto,
            'hashtags': [],
            'likes': int(rng.integers(0, 100)),
            'comentarios': int(rng.integers(0, 50)),
            'compartidos': int(rng.integers(0, 20)),
            'vistas': int(rng.integers(0, 9000)),
            'guardados': 0,
            'sentimiento': 'negativo' if 'grave' in texto else 'positivo',
            'tema_electoral': 'Agua' if 'agua' in texto else 'Seguridad',
            'engagement': 0,
            'engagement_rate': 0.0,
        })
    return pd.DataFrame(filas)


def _extraer(pdf_bytes):
    """Páginas, nº de imágenes incrustadas y texto extraído del PDF."""
    lector = PdfReader(BytesIO(pdf_bytes))
    texto = ' '.join((p.extract_text() or '') for p in lector.pages)
    imagenes = sum(len(list(p.images)) for p in lector.pages)
    return len(lector.pages), imagenes, texto


@pytest.fixture()
def pdf_df() -> pd.DataFrame:
    """DataFrame sanitizado para que el caché de st.cache_data lo hashee."""
    return sm._df_para_cache(_df_pdf())


def test_pdf_incluye_todas_las_secciones_con_fallback(pdf_df, monkeypatch):
    """Con kaleido 'roto', cada sección cae al fallback matplotlib pero aparece."""
    monkeypatch.setattr(sm, '_png_plotly',
                        lambda fig, width=1100, height=360: None)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        pdf = sm.exportar_dashboard_pdf(pdf_df, 'filtros de prueba', k_lda=0)
    assert pdf[:5] == b'%PDF-'
    _paginas, imagenes, texto = _extraer(pdf)
    faltantes = [s for s in SECCIONES if s not in texto]
    assert not faltantes, f'Secciones ausentes del PDF: {faltantes}'
    assert imagenes >= 7, f'Demasiado pocas imágenes embebidas ({imagenes})'


def test_pdf_quita_tlalpan_2027(pdf_df, monkeypatch):
    """El título del PDF ya no incluye '- Tlalpan 2027'."""
    monkeypatch.setattr(sm, '_png_plotly',
                        lambda fig, width=1100, height=360: None)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        pdf = sm.exportar_dashboard_pdf(pdf_df, 'sin filtros', k_lda=0)
    _paginas, _imagenes, texto = _extraer(pdf)
    assert 'Dashboard de Redes Sociales' in texto
    assert 'Tlalpan 2027' not in texto


def test_fallback_mpl_builders(pdf_df):
    """Los builders matplotlib de cada sección devuelven Figura (o None sin datos)."""
    assert sm._fig_mpl_lineas(pdf_df) is not None
    assert sm._fig_mpl_pie(pdf_df) is not None
    assert sm._fig_mpl_barras_top(pdf_df) is not None
    assert sm._fig_mpl_area(pdf_df) is not None
    agrupado = sm.alcance_por_tema(pdf_df)
    if not agrupado.empty:
        agrupado['tema_lda'] = agrupado['tema_electoral']
        assert sm._fig_mpl_barras(agrupado, 'tema_lda') is not None
    # Sin datos devuelven None (degradación elegante), no excepciones
    assert sm._fig_mpl_lineas(pd.DataFrame()) is None
    assert sm._fig_mpl_pie(pd.DataFrame()) is None
    assert sm._fig_mpl_area(pd.DataFrame()) is None


def test_fig_mpl_lda(pdf_df):
    """El fallback del plano de burbujas LDA funciona con resultado válido."""
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        res = analizar_lda(pdf_df, n_topics=3)
    if res.get('ok'):
        assert sm._fig_mpl_lda(res) is not None
    assert sm._fig_mpl_lda({'ok': False}) is None
    assert sm._fig_mpl_lda(None) is None