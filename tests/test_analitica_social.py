"""
tests/test_analitica_social.py
=============================

Pruebas unitarias de las funciones puras de análisis del dashboard de la
Pestaña 2 (`modules/analitica_social.py`): sentimiento, alcance por tema,
frecuencia de palabras, menciones y análisis LDA (con degradación elegante).

Ejecutar desde la raíz del repo:
    python -m pytest tests/test_analitica_social.py -v
"""

import warnings

import numpy as np
import pandas as pd
import pytest

from modules.analitica_social import (
    alcance_por_tema,
    alcance_por_tema_lda,
    analizar_lda,
    extraer_menciones,
    frecuencia_hashtags,
    frecuencia_palabras,
    resumen_sentimiento,
)

COLUMNAS = [
    'id_post', 'red_social', 'usuario', 'fecha', 'texto', 'hashtags', 'likes',
    'comentarios', 'compartidos', 'vistas', 'guardados', 'sentimiento',
    'tema_electoral', 'engagement', 'engagement_rate'
]


def _df_posts(n: int = 60) -> pd.DataFrame:
    """DataFrame de prueba con posts de varias redes y textos variados."""
    rng = np.random.default_rng(7)
    bases = [
        'El desabasto de agua es grave, las pipas no llegan hoy @agua_tlalpan #Agua #Pipas',
        'La inseguridad aumenta con los robos en el transporte publico @policia_tlalpan #Seguridad',
        'excelente servicio de la policia en mi colonia hoy gracias @gobtlalpan #Gracias',
    ]
    filas = []
    for i in range(n):
        texto = bases[int(rng.integers(0, len(bases)))]
        filas.append({
            'id_post': i,
            'red_social': ['TikTok', 'X', 'Facebook'][i % 3],
            'usuario': '@cuenta',
            'fecha': pd.Timestamp('2026-07-01') + pd.Timedelta(hours=i),
            'texto': texto,
            'hashtags': ['#agua'] if 'agua' in texto else [],
            'likes': int(rng.integers(0, 100)),
            'comentarios': int(rng.integers(0, 50)),
            'compartidos': int(rng.integers(0, 20)),
            'vistas': int(rng.integers(0, 9000)),
            'guardados': 0,
            'sentimiento': 'negativo' if 'grave' in texto
                           else ('positivo' if 'excelente' in texto else 'neutral'),
            'tema_electoral': 'Agua' if 'agua' in texto
                              else ('Seguridad' if 'seguridad' in texto else 'Participación'),
            'engagement': 0,
            'engagement_rate': 0.0,
        })
    return pd.DataFrame(filas)[COLUMNAS]


def test_resumen_sentimiento():
    df = _df_posts()
    resumen = resumen_sentimiento(df)
    assert resumen['total'] == len(df)
    assert resumen['positivos'] + resumen['negativos'] + resumen['neutrales'] == resumen['total']
    assert -1.0 <= resumen['promedio'] <= 1.0
    # Etiquetas conocidas: ambos extremos presentes en los textos de prueba
    assert resumen['positivos'] > 0 and resumen['negativos'] > 0


def test_resumen_sentimiento_vacio():
    resumen = resumen_sentimiento(pd.DataFrame())
    assert resumen['total'] == 0 and resumen['promedio'] == 0.0


def test_alcance_por_tema():
    df = _df_posts()
    agrupado = alcance_por_tema(df)
    assert list(agrupado.columns) == ['tema_electoral', 'n_posts', 'alcance', 'engagement']
    assert set(agrupado['tema_electoral']) <= {'Agua', 'Seguridad', 'Participación'}
    # El alcance es la suma de vistas: no puede ser negativo
    assert (agrupado['alcance'] >= 0).all()
    # Está ordenado desc por alcance
    assert agrupado['alcance'].is_monotonic_decreasing


def test_frecuencia_palabras():
    df = _df_posts()
    frec = frecuencia_palabras(df, n=15)
    assert list(frec.columns) == ['palabra', 'frecuencia']
    assert len(frec) <= 15
    assert frec['frecuencia'].iloc[0] >= frec['frecuencia'].iloc[-1]
    # Las stopwords no deben aparecer en el resultado
    assert 'de' not in frec['palabra'].tolist()


def test_extraer_menciones():
    df = _df_posts()
    menciones = extraer_menciones(df)
    assert list(menciones.columns) == ['usuario', 'menciones']
    usuarios = menciones['usuario'].str.replace('@', '', regex=False).tolist()
    assert 'agua_tlalpan' in usuarios
    assert all(m > 0 for m in menciones['menciones'])


def test_extraer_menciones_sin_menciones():
    df = _df_posts().assign(texto='post sin menciones')
    menciones = extraer_menciones(df)
    assert menciones.empty


def test_frecuencia_hashtags():
    df = _df_posts()
    hashtags = frecuencia_hashtags(df)
    assert list(hashtags.columns) == ['hashtag', 'frecuencia']
    assert 'agua' in hashtags['hashtag'].tolist()
    assert all(f > 0 for f in hashtags['frecuencia'])
    # Sin hashtags -> DataFrame vacío
    assert frecuencia_hashtags(df.assign(texto='post sin etiquetas ninguno')).empty


def test_analizar_lda_ok():
    df = _df_posts(n=80)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        resultado = analizar_lda(df, n_topics=4)
    assert resultado['ok'] is True
    assert resultado['n_posts'] == len(df)
    assert len(resultado['temas']) == 4
    for tema in resultado['temas']:
        assert {'id', 'palabras', 'prevalencia', 'x', 'y'} <= set(tema)
        assert 0 <= tema['prevalencia'] <= 1
        assert tema['palabras']
    # doc_topico alineado al DataFrame original
    assert 'doc_topico' in resultado
    assert len(resultado['doc_topico']) == len(df)
    assert resultado['doc_topico'].index.equals(df.index)
    assert set(resultado['doc_topico'].unique()) <= set(range(4))
    assert (resultado['doc_topico'] == -1).sum() == 0  # ningún texto vacío en la muestra


def test_analizar_lda_doc_topico_sin_texto():
    df = _df_posts(n=80)
    df.loc[0, 'texto'] = ''
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        resultado = analizar_lda(df, n_topics=3)
    if resultado.get('ok'):
        # La fila sin texto no participa del modelo y queda marcada en -1
        assert resultado['doc_topico'].loc[0] == -1
        assert (resultado['doc_topico'] == -1).sum() == 1


def test_alcance_por_tema_lda():
    df = _df_posts(n=80)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        resultado = analizar_lda(df, n_topics=3)
    assert resultado['ok']
    agrupado = alcance_por_tema_lda(df, resultado)
    assert list(agrupado.columns) == ['tema_lda', 'palabras', 'n_posts', 'alcance', 'engagement']
    assert len(agrupado) == len(resultado['temas'])
    assert (agrupado['alcance'] >= 0).all()
    # La suma de n_posts debe reproducir el total usado por LDA
    assert agrupado['n_posts'].sum() == resultado['n_posts']
    # Con resultado inválido -> DataFrame vacío
    assert alcance_por_tema_lda(df, {'ok': False, 'error': 'x'}).empty
    assert alcance_por_tema_lda(df, None).empty


def test_alcance_por_tema_lda_bucket_sin_texto():
    df = _df_posts(n=50)
    df.loc[0, 'texto'] = ''
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        resultado = analizar_lda(df, n_topics=3)
    if resultado.get('ok'):
        agrupado = alcance_por_tema_lda(df, resultado)
        # La fila sin texto va a su propio bucket (no se pierde su alcance)
        assert 'Sin texto' in agrupado['tema_lda'].tolist()
        assert agrupado['n_posts'].sum() == len(df)


def test_analizar_lda_degradado():
    # Con pocos posts debe devolver error claro, no lanzar excepción
    resultado = analizar_lda(_df_posts(n=5), n_topics=3)
    assert resultado['ok'] is False
    assert resultado['error']


def test_analizar_lda_df_vacio():
    resultado = analizar_lda(pd.DataFrame(), n_topics=3)
    assert resultado['ok'] is False