"""
analitica_social.py
===================

Funciones puras (sin Streamlit) de análisis estadístico y semántico para el
dashboard de la Pestaña 2 (Redes Sociales). Siguen el patrón de
`modules/analitica.py` (Pestaña 1): lógica en pandas/numpy puro, fácil de
probar unitariamente; la UI vive en `modules/social_media.py`.

Incluye:
    - resumen_sentimiento -> KPIs de sentimiento (positivo/negativo/promedio).
    - alcance_por_tema    -> alcance aproximado (suma de vistas) por tema.
    - frecuencia_palabras -> palabras más repetidas (top N).
    - frecuencia_hashtags -> hashtags más repetidos (top N).
    - extraer_menciones   -> @usuarios mencionados en los textos.
    - analizar_lda        -> temáticas LDA con proyección 2D (MDS) tipo pyLDAvis.
    - alcance_por_tema_lda-> alcance por temática LDA (asignación dominante).
"""

import re
from collections import Counter
from typing import Optional

import numpy as np
import pandas as pd

# Palabras de uso frecuente en español que no aportan al análisis de texto.
# Comparte el criterio con la nube de palabras del dashboard.
STOPWORDS_ES = {
    'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por',
    'un', 'para', 'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'mas', 'pero',
    'sus', 'es', 'este', 'esta', 'hay', 'son', 'estan', 'todo', 'todos',
    'hace', 'muy', 'desde', 'sobre', 'estamos', 'exigimos', 'nos', 'nuestra',
    'nuestro', 'hacia', 'entre', 'ya', 'eso', 'toda', 'cada', 'tienen',
    'estos', 'estas', 'tiene', 'va', 'ser', 'porque', 'cual', 'quien', 'les',
    'me', 'te', 'le', 'mi', 'mis', 'tu', 'sus', 'the', 'and', 'for', 'con',
    'mas', 'bien', 'muy', 'hay', 'este', 'esta', 'estos', 'estas', 'fue',
    'fue', 'estar', 'estaba', 'estan', 'han', 'ha', 'he', 'hemos', 'ya', 'don',
}

# Puntaje numérico por etiqueta de sentimiento (para el "promedio" del KPI).
SCORE_SENTIMIENTO = {'positivo': 1.0, 'neutral': 0.0, 'negativo': -1.0}

_MENCION_RE = re.compile(r'@([A-Za-z0-9_\.]{2,})')
_HASHTAG_RE = re.compile(r'#([\wáéíóúüñ]{2,})')
_TOKEN_RE = re.compile(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,}')


def _tokenizar(texto: str) -> list:
    """
    Tokeniza un texto en palabras significativas (lowercase, >=3 letras y sin
    stopwords). Reutilizable por `frecuencia_palabras` y por el `CountVectorizer`
    del análisis LDA.

    Retorna:
        lista de tokens (str).
    """
    if not texto:
        return []
    return [t for t in _TOKEN_RE.findall(texto.lower())
            if t not in STOPWORDS_ES]


def resumen_sentimiento(df: pd.DataFrame) -> dict:
    """
    Resume la distribución de sentimiento de los posts (positivo/negativo/
    neutral) y calcula el sentimiento promedio en el rango [-1, 1] usando
    `SCORE_SENTIMIENTO`.

    Retorna:
        dict con 'total', 'positivos', 'negativos', 'neutrales',
        'pct_positivo', 'pct_negativo', 'pct_neutral' y 'promedio' (float).
    """
    vacio = {'total': 0, 'positivos': 0, 'negativos': 0, 'neutrales': 0,
             'pct_positivo': 0.0, 'pct_negativo': 0.0, 'pct_neutral': 0.0,
             'promedio': 0.0}
    if df is None or df.empty or 'sentimiento' not in df.columns:
        return vacio
    conteos = df['sentimiento'].value_counts()
    total = int(df.shape[0])
    positivos = int(conteos.get('positivo', 0))
    negativos = int(conteos.get('negativo', 0))
    neutrales = int(conteos.get('neutral', 0))
    puntajes = df['sentimiento'].map(SCORE_SENTIMIENTO).fillna(0.0)
    promedio = float(puntajes.mean())
    return {
        'total': total,
        'positivos': positivos,
        'negativos': negativos,
        'neutrales': neutrales,
        'pct_positivo': round(100.0 * positivos / total, 1) if total else 0.0,
        'pct_negativo': round(100.0 * negativos / total, 1) if total else 0.0,
        'pct_neutral': round(100.0 * neutrales / total, 1) if total else 0.0,
        'promedio': round(promedio, 3),
    }


def alcance_por_tema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega por `tema_electoral` el número de posts, el alcance aproximado
    (suma de `vistas`, la única métrica de audiencia disponible en los datos)
    y el engagement (likes + comentarios + compartidos).

    Nota: Facebook/Instagram (carga manual) no traen vistas en el CSV, por lo
    que su alcance queda en 0; la suma real la aportan TikTok y X.

    Retorna:
        pd.DataFrame con 'tema_electoral', 'n_posts', 'alcance' y 'engagement',
        ordenado por alcance descendente.
    """
    columnas = ['tema_electoral', 'n_posts', 'alcance', 'engagement']
    if df is None or df.empty or 'tema_electoral' not in df.columns:
        return pd.DataFrame(columns=columnas)
    datos = df.copy()
    datos['_vistas'] = datos['vistas'] if 'vistas' in datos.columns else 0
    datos['_eng'] = (datos['likes'] if 'likes' in datos.columns else 0)
    if 'comentarios' in datos.columns:
        datos['_eng'] = datos['_eng'] + datos['comentarios']
    if 'compartidos' in datos.columns:
        datos['_eng'] = datos['_eng'] + datos['compartidos']
    columna_size = 'texto' if 'texto' in datos.columns else 'tema_electoral'
    agrupado = datos.groupby('tema_electoral', dropna=False).agg(
        n_posts=(columna_size, 'size'),
        alcance=('_vistas', 'sum'),
        engagement=('_eng', 'sum'),
    ).reset_index()
    agrupado['tema_electoral'] = agrupado['tema_electoral'].fillna('Sin tema')
    return agrupado.sort_values('alcance', ascending=False).reset_index(drop=True)


def frecuencia_palabras(df: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    """
    Cuenta las palabras más repetidas en el texto de los posts (sin stopwords,
    tokens >=3 letras) y devuelve el top N.

    Retorna:
        pd.DataFrame con 'palabra' y 'frecuencia', ordenado desc (vacío si
        no hay texto).
    """
    columnas = ['palabra', 'frecuencia']
    if df is None or df.empty or 'texto' not in df.columns:
        return pd.DataFrame(columns=columnas)
    contador = Counter()
    for texto in df['texto'].dropna().astype(str):
        contador.update(_tokenizar(texto))
    if not contador:
        return pd.DataFrame(columns=columnas)
    return pd.DataFrame(contador.most_common(int(n)), columns=columnas)


def frecuencia_hashtags(df: pd.DataFrame, n: int = 50) -> pd.DataFrame:
    """
    Cuenta los hashtags presentes en el texto de los posts y devuelve el top N.
    Si hay pocos hashtags se devuelven todos (la nube funciona igual).

    Retorna:
        pd.DataFrame con 'hashtag' (sin '#') y 'frecuencia', ordenado desc
        (vacío si no hay hashtags o texto).
    """
    columnas = ['hashtag', 'frecuencia']
    if df is None or df.empty or 'texto' not in df.columns:
        return pd.DataFrame(columns=columnas)
    contador = Counter()
    for texto in df['texto'].dropna().astype(str):
        for h in _HASHTAG_RE.findall(texto):
            contador[h.lower()] += 1
    if not contador:
        return pd.DataFrame(columns=columnas)
    return pd.DataFrame(contador.most_common(int(n)), columns=columnas)


def extraer_menciones(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extrae los @usuarios mencionados en el texto de los posts y los agrupa
    con su número de menciones (orden desc).

    Retorna:
        pd.DataFrame con 'usuario' (incluye '@') y 'menciones'; vacío si no
        hay menciones o texto.
    """
    columnas = ['usuario', 'menciones']
    if df is None or df.empty or 'texto' not in df.columns:
        return pd.DataFrame(columns=columnas)
    contador = Counter()
    for texto in df['texto'].dropna().astype(str):
        for m in _MENCION_RE.findall(texto):
            if len(m) >= 2:
                contador[m.lower()] += 1
    if not contador:
        return pd.DataFrame(columns=columnas)
    items = sorted(contador.items(), key=lambda x: (-x[1], x[0]))
    resultado = pd.DataFrame(items, columns=columnas)
    resultado['usuario'] = '@' + resultado['usuario'].astype(str)
    return resultado.reset_index(drop=True)


def _distancia_js(p: np.ndarray, q: np.ndarray) -> float:
    """
    Distancia de Jensen-Shannon (raíz cuadrada de la divergencia JS) entre dos
    distribuciones de probabilidad. Se usa para medir qué tan separados están
    los temas entre sí.

    Retorna:
        float >= 0 con la distancia simétrica.
    """
    p = np.asarray(p, dtype=float) + 1e-12
    q = np.asarray(q, dtype=float) + 1e-12
    p = p / p.sum()
    q = q / q.sum()
    m = 0.5 * (p + q)
    def kl(a, b):
        return float(np.sum(a * np.log(a / b)))
    divergencia = 0.5 * kl(p, m) + 0.5 * kl(q, m)
    # Guarda contra redondeo de punto flotante que deja un valor ~-1e-16.
    if divergencia < 0:
        divergencia = 0.0
    return float(np.sqrt(divergencia))


def _matriz_distancia_js(theta: np.ndarray) -> np.ndarray:
    """
    Matriz simétrica de distancias Jensen-Shannon entre todas las parejas de
    temas (filas de theta).

    Retorna:
        np.ndarray (k, k) con la diagonal en 0.
    """
    k = theta.shape[0]
    d = np.zeros((k, k))
    for i in range(k):
        for j in range(i + 1, k):
            v = _distancia_js(theta[i], theta[j])
            d[i, j] = v
            d[j, i] = v
    return d


def analizar_lda(df: pd.DataFrame, n_topics: int = 5, max_features: int = 5000,
                 min_df: int = 2, random_state: int = 42, max_iter: int = 25) -> dict:
    """
    Ejecuta un análisis de temáticas Latent Dirichlet Allocation sobre el texto
    de los posts y devuelve las temáticas con su proyección en un plano 2D
    (tipo pyLDAvis) usando distancia Jensen-Shannon + escalado multidimensional
    (MDS). El radio de la burbuja se deriva de la prevalencia del tema.

    Retorna:
        dict con 'ok' (bool) y, si funciona, 'n_posts', 'temas' (lista con
        'id', 'palabras' [top 8], 'prevalencia', 'x', 'y') y 'doc_topico'
        (pd.Series alineada a `df.index` con el tema dominante 0..k-1 por fila,
        o -1 en filas sin texto); si no, 'error' (str) para degradación
        elegante en la UI.
    """
    resultado_error = lambda msg: {'ok': False, 'error': msg}  # noqa: E731
    if df is None or df.empty or 'texto' not in df.columns:
        return resultado_error('No hay posts con texto para analizar.')
    textos = df['texto'].dropna().astype(str)
    textos = textos[textos.str.strip() != '']
    if len(textos) < 15:
        return resultado_error(
            f'Se necesitan al menos 15 posts con texto para un análisis LDA '
            f'confiable (hay {len(textos)}).')
    try:
        from sklearn.decomposition import LatentDirichletAllocation
        from sklearn.feature_extraction.text import CountVectorizer
        from sklearn.manifold import MDS

        vectorizador = CountVectorizer(max_features=int(max_features),
                                       min_df=int(min_df),
                                       lowercase=False,
                                       tokenizer=_tokenizar,
                                       token_pattern=None)
        matriz = vectorizador.fit_transform(textos)
        n_topics = max(2, int(n_topics))
        if matriz.shape[1] < n_topics:
            return resultado_error(
                f'Vocabulario insuficiente ({matriz.shape[1]} palabras) para '
                f'{n_topics} temáticas; reduce el número de temáticas.')
        lda = LatentDirichletAllocation(n_components=n_topics, random_state=random_state,
                                        max_iter=int(max_iter))
        phi = lda.fit_transform(matriz)  # distribución documento -> tema
        # Asignación del tema dominante por post (alineado al índice original;
        # las filas sin texto quedan en -1).
        dominante = phi.argmax(axis=1)
        doc_topico = pd.Series(np.full(len(df), -1, dtype=int), index=df.index)
        doc_topico.loc[textos.index] = dominante
        componentes = lda.components_    # (k, vocabulario) conteos crudos
        suma = componentes.sum(axis=1, keepdims=True)
        suma[suma == 0] = 1.0
        theta = componentes / suma       # distribución palabra -> tema (normalizada)
        palabras = vectorizador.get_feature_names_out()

        temas = []
        for k in range(theta.shape[0]):
            idx = theta[k].argsort()[::-1][:8]
            temas.append({
                'id': k + 1,
                'palabras': [str(palabras[i]) for i in idx],
                'prevalencia': float(phi[:, k].mean()),
            })

        distancias = _matriz_distancia_js(theta)
        mds = MDS(n_components=2, metric='precomputed', metric_mds=True,
                  n_init=1, init='random', max_iter=300,
                  random_state=random_state, normalized_stress='auto')
        coords = mds.fit_transform(distancias)
        for tema, (x, y) in zip(temas, coords):
            tema['x'] = float(x)
            tema['y'] = float(y)

        return {'ok': True, 'n_posts': int(len(textos)),
                'temas': temas, 'doc_topico': doc_topico}
    except Exception as e:
        print(f'ANALITICA_SOCIAL: LDA falló -> {e}')
        return resultado_error(f'No se pudo ejecutar el análisis LDA: {e}')


def alcance_por_tema_lda(df: pd.DataFrame, resultado: Optional[dict]) -> pd.DataFrame:
    """
    Agrega el alcance aproximado (suma de vistas) y el engagement **por tema
    LDA**, asignando cada post a su temática dominante (`doc_topico` del
    resultado de `analizar_lda`). La gráfica se acopla dinámicamente a los
    temas encontrados (los mismos del plano de burbujas).

    Retorna:
        pd.DataFrame con 'tema_lda' (etiqueta "Tema N"), 'palabras'
        (top del tema), 'n_posts', 'alcance' y 'engagement', ordenado por
        alcance desc. Vacío si no hay LDA válido o el df no lo soporta.
    """
    columnas = ['tema_lda', 'palabras', 'n_posts', 'alcance', 'engagement']
    if df is None or df.empty or 'texto' not in df.columns:
        return pd.DataFrame(columns=columnas)
    if not resultado or not resultado.get('ok'):
        return pd.DataFrame(columns=columnas)
    doc_topico = resultado.get('doc_topico')
    if doc_topico is None or len(doc_topico) != len(df):
        return pd.DataFrame(columns=columnas)
    temas_por_id = {t['id']: t for t in resultado.get('temas', [])}

    datos = df.copy()
    datos['_tema'] = doc_topico.values
    datos['_vistas'] = datos['vistas'] if 'vistas' in datos.columns else 0
    datos['_eng'] = (datos['likes'] if 'likes' in datos.columns else 0)
    if 'comentarios' in datos.columns:
        datos['_eng'] = datos['_eng'] + datos['comentarios']
    if 'compartidos' in datos.columns:
        datos['_eng'] = datos['_eng'] + datos['compartidos']
    base_size = 'tema_electoral' if 'tema_electoral' in datos.columns else 'texto'

    agrupado = datos.groupby('_tema', dropna=False).agg(
        n_posts=(base_size, 'size'),
        alcance=('_vistas', 'sum'),
        engagement=('_eng', 'sum'),
    ).reset_index()

    def _info(tema_idx: int):
        if tema_idx == -1:
            return 'Sin texto', ''
        tema = temas_por_id.get(int(tema_idx) + 1)
        if not tema:
            return f'Tema {int(tema_idx) + 1}', ''
        return (f"Tema {tema['id']}", ', '.join(tema['palabras']))

    info = agrupado['_tema'].map(_info)
    agrupado['tema_lda'] = [i[0] for i in info]
    agrupado['palabras'] = [i[1] for i in info]
    return agrupado[columnas].sort_values('alcance', ascending=False).reset_index(drop=True)