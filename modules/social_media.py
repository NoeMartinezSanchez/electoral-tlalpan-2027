import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

from modules.social_media_generator import TEMAS_ELECTORALES
from modules.analitica_social import (
    STOPWORDS_ES,
    alcance_por_tema,
    alcance_por_tema_lda,
    analizar_lda,
    extraer_menciones,
    frecuencia_hashtags,
    frecuencia_palabras,
    resumen_sentimiento,
)
from utils import mostrar_configuracion_extraccion

COLUMNAS_POSTS = [
    'id_post', 'red_social', 'usuario', 'fecha', 'texto', 'hashtags', 'likes',
    'comentarios', 'compartidos', 'vistas', 'guardados', 'sentimiento',
    'tema_electoral', 'engagement', 'engagement_rate'
]

def df_posts_vacio() -> pd.DataFrame:
    """DataFrame vacío con el esquema estándar de posts (para el primer render)."""
    return pd.DataFrame(columns=COLUMNAS_POSTS)

def color_por_sentimiento(word, font_size, position, orientation, random_state=None, **kwargs):
    """
    Función de color para la WordCloud que resalta palabras clave de sentimientos:
    Verde para positivo, Rojo para negativo, Amarillo/Naranja para neutral.
    """
    word_lower = word.lower()
    
    # Palabras negativas clave
    negativas = [
        'desabasto', 'inseguridad', 'robo', 'baches', 'moches', 'corrupción', 
        'lodo', 'fraude', 'nepotismo', 'extorsión', 'inundaciones', 'sucio', 
        'insostenible', 'desvío', 'detonaciones', 'tráfico', 'accidentes', 'problema',
        'grave', 'lloran', 'cobran', 'ilegal'
    ]
    # Palabras positivas clave
    positivas = [
        'excelente', 'arreglaron', 'digna', 'atentos', 'reforestando', 'genial', 
        'transparencia', 'participación', 'gracias', 'apoyo', 'ayuda', 'limpiar', 
        'eficiente', 'organización'
    ]
    
    if any(w in word_lower for w in negativas):
        return "rgb(239, 68, 68)"  # Rojo (#ef4444)
    elif any(w in word_lower for w in positivas):
        return "rgb(16, 185, 129)"  # Verde (#10b981)
    else:
        return "rgb(245, 158, 11)"  # Ámbar (#f59e0b)

def mostrar_kpis(df):
    """
    Calcula e inyecta KPIs clave para el análisis en tarjetas mobile-friendly.
    """
    col1, col2, col3, col4, col5 = st.columns(5)
    
    total_posts = len(df)
    total_likes = df['likes'].sum() if total_posts > 0 else 0
    total_comments = df['comentarios'].sum() if total_posts > 0 else 0
    total_shares = df['compartidos'].sum() if total_posts > 0 else 0
    
    # Engagement total
    engagement_total = total_likes + total_comments + total_shares
    
    with col1:
        st.metric("📝 Total Posts", f"{total_posts:,}")
    with col2:
        st.metric("❤️ Likes", f"{total_likes:,}")
    with col3:
        st.metric("💬 Comentarios", f"{total_comments:,}")
    with col4:
        st.metric("🔄 Compartidos", f"{total_shares:,}")
    with col5:
        st.metric("📈 Engagement Total", f"{engagement_total:,}")

def fig_evolucion_temporal(df):
    """
    Construye la figura de evolución diaria de las interacciones agregadas.
    Reutilizable por el dashboard y por el PDF (las mismas gráficas).

    Retorna:
        go.Figure o None si no hay datos con fecha.
    """
    if df is None or df.empty or 'fecha' not in df.columns:
        return None
    d = df[df['fecha'].notna()].copy()
    if d.empty or 'likes' not in d.columns:
        return None
    df_daily = d.groupby(d['fecha'].dt.date).agg({
        'likes': 'sum',
        'comentarios': 'sum',
        'compartidos': 'sum',
    }).reset_index()
    if df_daily.empty:
        return None
    df_daily = df_daily.sort_values(by='fecha')
    fig = px.line(
        df_daily,
        x='fecha',
        y=['likes', 'comentarios', 'compartidos'],
        labels={'value': 'Interacciones', 'fecha': 'Fecha', 'variable': 'Métrica'},
        color_discrete_map={
            'likes': '#ef4444',
            'comentarios': '#3b82f6',
            'compartidos': '#10b981'
        }
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=320
    )
    return fig


def mostrar_evolucion_temporal(df):
    """
    Renderiza la evolución diaria de las interacciones agregadas en un gráfico
    de líneas interactivo.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>📈 Evolución de Interacciones</h4>", unsafe_allow_html=True)
    if df.empty:
        st.info("No hay datos suficientes para el rango seleccionado.")
        return
    if 'fecha' not in df.columns or df['fecha'].notna().sum() == 0:
        st.info("Los datos cargados no tienen fecha (Facebook manual) y no se "
                "pueden graficar en la serie temporal.")
        return
    st.caption("Los posts de Facebook (carga manual, sin fecha) no se incluyen "
               "en la serie temporal.")
    fig = fig_evolucion_temporal(df)
    if fig is None:
        st.info("No hay datos suficientes para el rango seleccionado.")
        return
    st.plotly_chart(fig, use_container_width=True)

def _fig_wordcloud(texto: str = '', frecuencias: dict = None, max_words: int = 80,
                   color_func=None, stopwords=None, min_font_size: int = 8):
    """
    Construye una Figura matplotlib con una nube de palabras. Si se pasa
    `frecuencias` (dict -> peso), se construye con `generate_from_frequencies`
    (el tamaño respeta los conteos reales); si no, desde el texto plano.
    Reutilizable por el dashboard y por el PDF.

    Retorna:
        plt.Figure o None si falla o no hay contenido.
    """
    try:
        if frecuencias:
            wc = WordCloud(width=800, height=400, background_color='white',
                           max_words=max_words, random_state=42,
                           min_font_size=min_font_size) \
                .generate_from_frequencies(frecuencias)
        else:
            if not texto or not texto.strip():
                return None
            wc = WordCloud(width=800, height=400, background_color='white',
                           stopwords=stopwords or set(), max_words=max_words,
                           random_state=42, collocations=False,
                           min_font_size=min_font_size).generate(texto)
        if color_func is not None:
            wc.recolor(color_func=color_func)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wc, interpolation='bilinear')
        ax.axis('off')
        return fig
    except Exception as e:
        print(f'WORDCLOUD: No se pudo generar la nube ({e})')
        return None


def mostrar_nube_palabras(df):
    """
    Genera y dibuja una Nube de Palabras a partir del texto de los posts,
    coloreada según sentimientos.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>☁️ Nube de Temas (por sentimiento)</h4>", unsafe_allow_html=True)
    if df.empty or 'texto' not in df.columns:
        st.info("No hay suficientes datos de texto.")
        return
    textos = ' '.join(df['texto'].fillna('').astype(str).tolist())
    fig = _fig_wordcloud(textos, max_words=80, color_func=color_por_sentimiento,
                         stopwords=STOPWORDS_ES)
    if fig is None:
        st.error("No se pudo generar la WordCloud.")
        return
    st.pyplot(fig)
    plt.close(fig)

def _hover_tema(tema: dict) -> str:
    """Texto de hover de una burbuja del plano LDA."""
    prev = f"{tema['prevalencia'] * 100:.1f}%"
    return (f"<b>Tema {tema['id']}</b> · prevalencia {prev}<br>"
            f"Palabras: {' · '.join(tema['palabras'])}")


def mostrar_kpis_sentimiento(df):
    """
    Muestra KPIs básicos de análisis de sentimiento con iconos: positivo,
    negativo, neutral y el sentimiento promedio (rango [-1, 1]) de todos los
    posts de las 4 redes sociales combinadas.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>"
                "🎭 Análisis de Sentimiento (básico)</h4>", unsafe_allow_html=True)
    if df.empty or 'sentimiento' not in df.columns:
        st.info("No hay datos de sentimiento para mostrar.")
        return
    resumen = resumen_sentimiento(df)
    promedio = resumen['promedio']
    if promedio >= 0.15:
        emoji_p, color_p = '😀', '#059669'
    elif promedio <= -0.15:
        emoji_p, color_p = '😞', '#dc2626'
    else:
        emoji_p, color_p = '😐', '#d97706'
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("😀 Positivo", f"{resumen['positivos']:,}",
                  f"{resumen['pct_positivo']}% del total")
    with c2:
        st.metric("😞 Negativo", f"{resumen['negativos']:,}",
                  f"{resumen['pct_negativo']}% del total")
    with c3:
        st.metric("😐 Neutral", f"{resumen['neutrales']:,}",
                  f"{resumen['pct_neutral']}% del total")
    with c4:
        st.markdown(
            f"<div class='info-card' style='text-align:center;height:100%;'>"
            f"<div style='font-size:12px;color:#64748b;font-weight:600;'>"
            f"⚖️ Promedio</div>"
            f"<div style='font-size:22px;font-weight:700;color:{color_p};'>"
            f"{emoji_p} {promedio:+.2f}</div>"
            f"<div style='font-size:11px;color:#94a3b8;'>rango [-1, +1] · "
            f"etiqueta 'sentimiento'</div></div>", unsafe_allow_html=True)


def fig_lda_burbujas(resultado):
    """
    Construye el plano 2D de burbujas de temáticas LDA (estilo pyLDAvis):
    cercanía = distancia entre temas (JS + MDS), tamaño = prevalencia.
    Reutilizable por el dashboard y el PDF.

    Retorna:
        go.Figure con las burbujas.
    """
    temas = (resultado or {}).get('temas') if resultado else None
    if not temas:
        return go.Figure()
    colores = px.colors.qualitative.Safe
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=[t['x'] for t in temas], y=[t['y'] for t in temas],
        mode='markers+text',
        marker=dict(size=[max(14.0, t['prevalencia'] * 900) for t in temas],
                    opacity=0.75,
                    color=[colores[(t['id'] - 1) % len(colores)] for t in temas],
                    line=dict(width=1, color='#0f172a')),
        text=[f"Tema {t['id']}" for t in temas],
        textposition='middle center',
        textfont=dict(size=11, color='#0f172a'),
        hovertext=[_hover_tema(t) for t in temas],
        hoverinfo='text',
    ))
    fig.update_layout(
        height=390,
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
    )
    return fig


@st.cache_data(show_spinner=False, max_entries=16)
def _lda_cached(df, k: int) -> dict:
    """Analiza LDA (cacheado por dataframe sanitizado + nº de temáticas)."""
    return analizar_lda(df, n_topics=int(k))


def _tarjeta_tema(tema: dict) -> str:
    """HTML de una tarjeta compacta con las palabras clave de un tema LDA."""
    return (
        f"<div style='border:1px solid #e2e8f0;border-radius:10px;padding:8px;"
        f"margin-bottom:8px;background:#f8fafc;'>"
        f"<div style='font-weight:600;font-size:12px;color:#059669;'>"
        f"Tema {tema['id']} · prevalencia {tema['prevalencia'] * 100:.1f}%</div>"
        f"<div style='font-size:11px;color:#334155;'>"
        f"{' · '.join(tema['palabras'])}</div></div>"
    )


def mostrar_lda_tematicas(df):
    """
    Análisis de temáticas con LDA representadas como burbujas en un plano 2D
    (estilo pyLDAvis). Muestra las burbujas a la izquierda y, a un lado, las
    tarjetas visibles con las palabras clave de cada tema.

    Retorna:
        dict resultado de `analizar_lda` (o None si no fue posible) para
        reutilizarlo en el alcance por tema y en el PDF.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>"
                "🧩 Temáticas LDA (burbujas 2D)</h4>", unsafe_allow_html=True)
    if df.empty or 'texto' not in df.columns:
        st.info("No hay texto para ejecutar el análisis LDA.")
        return None
    n_textos = int(df['texto'].fillna('').astype(str).str.strip().ne('').sum())
    if n_textos < 15:
        st.info(f"Se necesitan al menos 15 posts con texto para LDA (hay {n_textos}).")
        return None
    k = st.slider("Nº de temáticas (LDA)", 3, 10, 5, 1,
                  help="Ajusta el número de temas latentes a detectar.")
    with st.spinner("Analizando temáticas con LDA..."):
        resultado = _lda_cached(_df_para_cache(df), k)
    if not resultado.get('ok'):
        st.info(resultado.get('error', 'No se pudo ejecutar el análisis LDA.'))
        return None

    col_izq, col_der = st.columns([1.6, 1.0])
    with col_izq:
        fig = fig_lda_burbujas(resultado)
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Cercanía entre burbujas = distancia entre temáticas (JS + MDS); "
                   "tamaño = prevalencia del tema en los posts.")
    with col_der:
        st.caption("Palabras clave por temática")
        for t in resultado['temas']:
            st.markdown(_tarjeta_tema(t), unsafe_allow_html=True)
    return resultado


def fig_barras_alcance(datos, y_col: str) -> go.Figure:
    """
    Barra horizontal de alcance (suma de vistas) por tema. Si `datos` trae la
    columna 'palabras', se muestran en el hover.

    Retorna:
        go.Figure o None si no hay datos.
    """
    if datos is None or datos.empty:
        return None
    d = datos.sort_values('alcance', ascending=True)
    fig = px.bar(d, x='alcance', y=y_col, orientation='h',
                 color='alcance', color_continuous_scale='Blues',
                 labels={'alcance': 'Alcance aprox. (vistas)',
                         y_col: 'Tema'})
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=340,
                      showlegend=False)
    fig.update_coloraxes(showscale=False)
    if 'palabras' in d.columns:
        fig.update_traces(
            customdata=d['palabras'].fillna('').astype(str),
            hovertemplate='<b>%{y}</b><br>Alcance: %{x:,.0f}<br>'
                          'Palabras: %{customdata}<extra></extra>')
    return fig


def mostrar_alcance_temas(df, resultado_lda=None):
    """
    Barra horizontal con el alcance aproximado (suma de vistas). Prioriza los
    temas del análisis LDA (asignación dominante) y, si no está disponible,
    degrada a las categorías por palabras clave.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>"
                "🎯 Alcance estimado por tema</h4>", unsafe_allow_html=True)
    agrupado = alcance_por_tema_lda(df, resultado_lda) if (resultado_lda or {}).get('ok') \
        else pd.DataFrame()
    if agrupado.empty:
        agrupado = alcance_por_tema(df)
        if agrupado.empty:
            st.info("No hay datos de alcance por tema.")
            return
        agrupado['tema_lda'] = agrupado['tema_electoral']
        agrupado['palabras'] = ''
        fig = fig_barras_alcance(agrupado, 'tema_lda')
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
        st.caption("Alcance ≈ suma de vistas. LDA no disponible con los datos "
                   "actuales; se usan las categorías por palabras clave. Las "
                   "redes sin métrica de audiencia (FB/IG manual) aportan 0.")
        return
    fig = fig_barras_alcance(agrupado, 'tema_lda')
    if fig is not None:
        st.plotly_chart(fig, use_container_width=True)
    st.caption("Alcance ≈ suma de vistas por temática LDA (asignación dominante). "
               "Las redes sin métrica de audiencia (FB/IG manual) aportan 0.")


def fig_top_palabras(df) -> go.Figure:
    """
    Construye la figura del Top 15 de palabras más repetidas (sin stopwords).
    Reutilizable por el dashboard y el PDF.

    Retorna:
        go.Figure o None si no hay palabras.
    """
    frecuencias = frecuencia_palabras(df, n=15)
    if frecuencias.empty:
        return None
    frecuencias = frecuencias.sort_values('frecuencia', ascending=True)
    fig = px.bar(frecuencias, x='frecuencia', y='palabra', orientation='h',
                 color='frecuencia', color_continuous_scale='Greens',
                 labels={'frecuencia': 'Frecuencia', 'palabra': 'Palabra'})
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=420,
                      showlegend=False)
    fig.update_coloraxes(showscale=False)
    return fig


def mostrar_top_palabras(df):
    """
    Top 15 palabras más repetidas en los textos de los posts (sin stopwords)
    en una gráfica de barras horizontales.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>"
                "🏅 Top 15 palabras más repetidas</h4>", unsafe_allow_html=True)
    fig = fig_top_palabras(df)
    if fig is None:
        st.info("No hay palabras suficientes para graficar.")
        return
    st.plotly_chart(fig, use_container_width=True)


def mostrar_nube_menciones(df):
    """
    Nube de palabras con los @usuarios mencionados en los posts (todas las
    redes); el tamaño respeta el número de menciones reales.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>"
                "👥 Usuarios mencionados en los posts</h4>", unsafe_allow_html=True)
    menciones = extraer_menciones(df)
    if menciones.empty:
        st.info("No hay @usuarios mencionados en los posts.")
        return
    frecuencias = dict(zip(menciones['usuario'].astype(str), menciones['menciones'].astype(int)))
    fig = _fig_wordcloud(frecuencias=frecuencias, max_words=60, min_font_size=8)
    if fig is None:
        st.info("No hay @usuarios mencionados en los posts.")
        return
    st.pyplot(fig)
    plt.close(fig)


def mostrar_nube_hashtags(df):
    """
    Nube de palabras con los hashtags presentes en los posts (todas las
    redes); el tamaño respeta la frecuencia real de cada hashtag.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>"
                "🏷️ Hashtags en los posts</h4>", unsafe_allow_html=True)
    hashtags = frecuencia_hashtags(df)
    if hashtags.empty:
        st.info("No hay hashtags en los posts.")
        return
    frecuencias = dict(zip('#' + hashtags['hashtag'].astype(str),
                           hashtags['frecuencia'].astype(int)))
    fig = _fig_wordcloud(frecuencias=frecuencias, max_words=60, min_font_size=8)
    if fig is None:
        st.info("No hay hashtags en los posts.")
        return
    st.pyplot(fig)
    plt.close(fig)


def _tabla_pdf(datos: list, anchos: list):
    """
    Construye una Table de reportlab con estilo compacto y encabezado verde.
    Reutilizada por `exportar_dashboard_pdf`.
    """
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle
    tabla = Table(datos, colWidths=anchos, repeatRows=1)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#059669')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return tabla


def _png_plotly(fig, width: int = 1100, height: int = 360):
    """
    Convierte una figura Plotly a PNG (motor kaleido) en BytesIO para el PDF.

    Retorna:
        BytesIO o None si la conversión falla.
    """
    from io import BytesIO
    if fig is None:
        return None
    try:
        return BytesIO(fig.to_image(format='png', width=width, height=height, scale=2))
    except Exception as e:
        print(f'PDF: no se pudo rasterizar la figura ({e})')
        return None


def _png_matplotlib(fig_plt):
    """
    Convierte una Figura de matplotlib a PNG (BytesIO) para el PDF, cerrando
    la figura al terminar.

    Retorna:
        BytesIO o None si la conversión falla.
    """
    from io import BytesIO
    if fig_plt is None:
        return None
    buf = BytesIO()
    try:
        fig_plt.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    except Exception as e:
        print(f'PDF: no se pudo guardar la gráfica matplotlib ({e})')
        return None
    finally:
        plt.close(fig_plt)
    buf.seek(0)
    return buf


def _flujo_imagen(buf, max_width: int = 520):
    """
    Convierte un PNG (BytesIO) en un flowable Image de reportlab preservando
    la proporción (aspect) de la imagen original.

    Retorna:
        reportlab Image o None si no hay PNG.
    """
    from PIL import Image as PILImage
    from reportlab.platypus import Image as RLImage
    if buf is None:
        return None
    buf.seek(0)
    try:
        with PILImage.open(buf) as im:
            w, h = im.size
    except Exception as e:
        print(f'PDF: no se pudo leer la imagen ({e})')
        return None
    if w <= 0 or h <= 0:
        return None
    aspect = h / w
    width = min(max_width, w)
    height = width * aspect
    if height > 700:
        height = 700
        width = height / aspect
    buf.seek(0)
    return RLImage(buf, width=width, height=height)


# --- Builders matplotlib de FALLBACK para el PDF ---------------------------------
# Se usan cuando kaleido/`fig.to_image` falla (p.ej. en la nube), para que cada
# sección del PDF SIEMPRE lleve una imagen equivalente a la gráfica del dashboard.

def _fig_mpl_lineas(df):
    """Fallback matplotlib de la evolución diaria de interacciones."""
    if df is None or df.empty or 'fecha' not in df.columns:
        return None
    d = df[df['fecha'].notna()]
    if d.empty:
        return None
    a = d.groupby(d['fecha'].dt.date).agg({
        'likes': 'sum', 'comentarios': 'sum', 'compartidos': 'sum'}).sort_index()
    if a.empty:
        return None
    fig, ax = plt.subplots(figsize=(9, 4), dpi=110)
    ax.plot(a.index, a['likes'], color='#ef4444', label='Likes', linewidth=1.8)
    ax.plot(a.index, a['comentarios'], color='#3b82f6', label='Comentarios', linewidth=1.8)
    ax.plot(a.index, a['compartidos'], color='#10b981', label='Compartidos', linewidth=1.8)
    ax.set_ylabel('Interacciones')
    ax.legend(fontsize=8)
    ax.grid(True, linestyle='--', alpha=0.4)
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    return fig


def _fig_mpl_pie(df):
    """Fallback matplotlib del pastel de distribución por red social."""
    if df is None or df.empty or 'red_social' not in df.columns:
        return None
    redes = df['red_social'].value_counts()
    if redes.empty:
        return None
    colores = {'TikTok': '#ff0050', 'Facebook': '#1877f2',
               'Instagram': '#c13584', 'X': '#1DA1F2'}
    fig, ax = plt.subplots(figsize=(5.2, 3.6), dpi=110)
    ax.pie(redes, labels=redes.index, autopct='%1.0f%%',
           colors=[colores.get(r, '#64748b') for r in redes.index],
           startangle=90, textprops={'fontsize': 8})
    ax.set_aspect('equal')
    fig.tight_layout()
    return fig


def _fig_mpl_barras(datos, y_col: str):
    """Fallback matplotlib de la barra horizontal de alcance por tema."""
    if datos is None or datos.empty or 'alcance' not in datos.columns:
        return None
    d = datos.sort_values('alcance', ascending=True)
    fig, ax = plt.subplots(figsize=(9, max(3.2, 0.5 * len(d) + 1.2)), dpi=110)
    ax.barh(d[y_col], d['alcance'], color='#3b82f6')
    ax.set_xlabel('Alcance aprox. (vistas)')
    ax.grid(True, axis='x', linestyle='--', alpha=0.4)
    fig.tight_layout()
    return fig


def _fig_mpl_barras_top(df):
    """Fallback matplotlib del Top 15 de palabras más repetidas."""
    frec = frecuencia_palabras(df, n=15)
    if frec.empty:
        return None
    d = frec.sort_values('frecuencia')
    fig, ax = plt.subplots(figsize=(9, max(3.4, 0.5 * len(d) + 1.4)), dpi=110)
    ax.barh(d['palabra'], d['frecuencia'], color='#10b981')
    ax.set_xlabel('Frecuencia')
    ax.grid(True, axis='x', linestyle='--', alpha=0.4)
    fig.tight_layout()
    return fig


def _fig_mpl_area(df):
    """Fallback matplotlib de la tendencia de sentimiento en el tiempo."""
    if df is None or df.empty or 'fecha' not in df.columns or 'sentimiento' not in df.columns:
        return None
    d = df[df['fecha'].notna()]
    if d.empty:
        return None
    pivot = d.groupby([d['fecha'].dt.date, 'sentimiento']).size() \
        .unstack(fill_value=0).sort_index()
    if pivot.empty:
        return None
    orden = [c for c in ('positivo', 'negativo', 'neutral') if c in pivot.columns]
    colores = {'positivo': '#10b981', 'negativo': '#ef4444', 'neutral': '#f59e0b'}
    fig, ax = plt.subplots(figsize=(9, 4), dpi=110)
    ax.stackplot(pivot.index, [pivot[c] for c in orden],
                 labels=orden, colors=[colores[c] for c in orden], alpha=0.85)
    ax.set_ylabel('Cantidad')
    ax.legend(loc='upper left', fontsize=8)
    ax.grid(True, linestyle='--', alpha=0.4)
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    return fig


def _fig_mpl_lda(resultado):
    """Fallback matplotlib del plano de burbujas de temáticas LDA."""
    temas = (resultado or {}).get('temas') if resultado else None
    if not temas:
        return None
    hex_colores = ['#a6cee3', '#1f78b4', '#b2df8a', '#33a02c', '#fb9a99',
                   '#e31a1c', '#fdbf6f', '#ff7f00', '#cab2d6', '#6a3d9a']
    fig, ax = plt.subplots(figsize=(8.5, 5), dpi=110)
    for t in temas:
        ax.scatter(t['x'], t['y'], s=900 + t['prevalencia'] * 8000, alpha=0.75,
                   color=hex_colores[(t['id'] - 1) % len(hex_colores)],
                   edgecolors='#0f172a', linewidths=0.8)
        ax.annotate(f"Tema {t['id']}", (t['x'], t['y']),
                    color='#0f172a', fontsize=9, ha='center', va='center')
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel('Plano 2D (distancia JS + MDS)')
    fig.tight_layout()
    return fig


def _df_para_cache(df: pd.DataFrame) -> pd.DataFrame:
    """
    Devuelve una copia del DataFrame con las columnas no-hasheables (listas,
    p.ej. `hashtags`) convertidas a string, para que st.cache_data pueda
    hashear la entrada sin caer al fallback de pickle en `exportar_dashboard_pdf`.
    """
    if df is None or df.empty:
        return df
    copia = df.copy()
    for col in copia.columns:
        if copia[col].map(lambda v: isinstance(v, (list, dict))).any():
            copia[col] = copia[col].map(
                lambda v: repr(v) if isinstance(v, (list, dict)) else v)
    return copia


@st.cache_data(show_spinner=False, max_entries=8)
def exportar_dashboard_pdf(df: pd.DataFrame, nota_filtros: str = '',
                           k_lda: int = 0) -> bytes:
    """
    Genera un PDF que replica la disposición del dashboard de la Pestaña 2:
    KPIs y todas las gráficas del dashboard (mismas figuras Plotly → PNG vía
    kaleido) organizadas en filas de 2 tarjetas como la grilla del panel, más
    las tablas resumen. Cada sección tiene fallback a matplotlib por si kaleido
    no puede rasterizar, de modo que SIEMPRE se incrustan imágenes.

    Retorna:
        bytes del PDF listo para `st.download_button`.
    """
    from io import BytesIO
    from datetime import datetime
    import matplotlib
    try:
        matplotlib.use('Agg')
    except Exception:
        pass
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (HRFlowable, Paragraph, SimpleDocTemplate,
                                    Spacer, Table, TableStyle)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=15 * mm,
                            rightMargin=15 * mm, topMargin=13 * mm,
                            bottomMargin=13 * mm)
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle('Titulo', parent=estilos['Title'], fontSize=16,
                            textColor=colors.HexColor('#0f172a'), spaceAfter=4)
    h2 = ParagraphStyle('H2', parent=estilos['Heading2'], fontSize=12,
                        spaceBefore=10, spaceAfter=4,
                        textColor=colors.HexColor('#059669'))
    cuerpo = ParagraphStyle('Cuerpo', parent=estilos['BodyText'], fontSize=9,
                            leading=12)
    h3_card = ParagraphStyle('H3Card', parent=estilos['BodyText'],
                             fontName='Helvetica-Bold', fontSize=10.5, leading=13,
                             textColor=colors.HexColor('#0f172a'))
    caption_card = ParagraphStyle('CapCard', parent=estilos['BodyText'],
                                  fontSize=7.5, leading=9,
                                  textColor=colors.HexColor('#64748b'))
    ancho_col = 254

    historia = []

    def _imagen_flowable(fig_plotly=None, fig_mpl=None, width=1100, height=360,
                         max_width=240):
        """Convierte una sección a imagen: intenta Plotly (kaleido) y si falla
        usa el fallback matplotlib. Retorna flowable Image o None."""
        flujo = None
        if fig_plotly is not None:
            flujo = _flujo_imagen(_png_plotly(fig_plotly, width=width, height=height),
                                  max_width=max_width)
        if flujo is None and fig_mpl is not None:
            flujo = _flujo_imagen(_png_matplotlib(fig_mpl), max_width=max_width)
        return flujo

    def _tarjeta(titulo_txt, flujo=None, tabla=None, caption=None):
        """Flujos de una tarjeta (encabezado + caption + imagen/tabla)."""
        celdas = [Paragraph(titulo_txt, h3_card)]
        if caption:
            celdas.append(Paragraph(caption, caption_card))
        if flujo is not None:
            celdas.append(Spacer(1, 3))
            celdas.append(flujo)
        if tabla is not None:
            celdas.append(Spacer(1, 3))
            celdas.append(tabla)
        return celdas

    def _fila(izq, der):
        """Dos tarjetas al lado (como la grilla del dashboard), si hay contenido."""
        if (not izq) and (not der):
            return
        vacio = [Paragraph('', caption_card)]
        fila = Table([[izq or vacio, der or vacio]], colWidths=[ancho_col, ancho_col])
        fila.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 0.8, colors.HexColor('#cbd5e1')),
            ('INNERGRID', (0, 0), (-1, -1), 0.6, colors.HexColor('#dbe3ec')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        historia.append(Spacer(1, 6))
        historia.append(fila)

    # --- Encabezado ---------------------------------------------------------
    historia.append(Paragraph('Dashboard de Redes Sociales', titulo))
    historia.append(Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                              cuerpo))
    if nota_filtros:
        historia.append(Paragraph(f"Filtros aplicados: {nota_filtros}", cuerpo))
    historia.append(Spacer(1, 4))
    historia.append(HRFlowable(width='100%', thickness=1.2,
                               color=colors.HexColor('#059669')))

    # --- KPIs y sentimiento -------------------------------------------------
    historia.append(Paragraph('KPIs y sentimiento', h2))
    resumen = resumen_sentimiento(df)
    if df.empty:
        total = likes = coment = compart = vistas_tot = 0
    else:
        total = int(len(df))
        likes = int(df['likes'].sum()) if 'likes' in df.columns else 0
        coment = int(df['comentarios'].sum()) if 'comentarios' in df.columns else 0
        compart = int(df['compartidos'].sum()) if 'compartidos' in df.columns else 0
        vistas_tot = int(df['vistas'].sum()) if 'vistas' in df.columns else 0
    engagement = likes + coment + compart
    historia.append(_tabla_pdf([
        ['Métrica', 'Valor', 'Métrica', 'Valor'],
        ['Total posts', f'{total:,}', 'Likes', f'{likes:,}'],
        ['Comentarios', f'{coment:,}', 'Compartidos', f'{compart:,}'],
        ['Engagement total', f'{engagement:,}', 'Alcance (vistas)', f'{vistas_tot:,}'],
        ['Sentimiento promedio', f"{resumen['promedio']:+.2f}",
         'Positivos / Negativos', f"{resumen['positivos']} / {resumen['negativos']}"],
    ], [110, 95, 110, 95]))

    # --- Contenido común (secciones reutilizables) --------------------------
    resultado_lda = None
    if k_lda:
        resultado_lda = analizar_lda(df, n_topics=int(k_lda))
    lda_ok = bool(resultado_lda and resultado_lda.get('ok'))

    # Nube de temas
    nube_flow = None
    if not df.empty and 'texto' in df.columns:
        nube_flow = _imagen_flowable(
            fig_mpl=_fig_wordcloud(
                ' '.join(df['texto'].fillna('').astype(str).tolist()),
                max_words=80, color_func=color_por_sentimiento,
                stopwords=STOPWORDS_ES))

    # Menciones y hashtags
    menciones = extraer_menciones(df)
    menc_flow = None
    if not menciones.empty:
        menc_flow = _imagen_flowable(
            fig_mpl=_fig_wordcloud(
                frecuencias=dict(zip(menciones['usuario'].astype(str),
                                     menciones['menciones'].astype(int))),
                max_words=60, min_font_size=8))

    hashtags = frecuencia_hashtags(df)
    hash_flow = None
    if not hashtags.empty:
        hash_flow = _imagen_flowable(
            fig_mpl=_fig_wordcloud(
                frecuencias=dict(zip('#' + hashtags['hashtag'].astype(str),
                                     hashtags['frecuencia'].astype(int))),
                max_words=60, min_font_size=8))

    # --- FILA 1: Evolución | Nube de temas ----------------------------------
    _fila(
        _tarjeta('Evolución de interacciones',
                 flujo=_imagen_flowable(fig_evolucion_temporal(df),
                                        _fig_mpl_lineas(df), height=380)),
        _tarjeta('Nube de temas (por sentimiento)', flujo=nube_flow),
    )

    # --- FILA 2: Temáticas LDA | Distribución por red -----------------------
    lda_tabla = None
    lda_flujo = None
    if lda_ok:
        lda_tabla = _tabla_pdf(
            [['Tema', 'Preval.', 'Palabras clave']] + [
                [f"Tema {t['id']}", f"{t['prevalencia'] * 100:.1f}%",
                 ', '.join(t['palabras'])] for t in resultado_lda['temas']],
            [48, 52, 145])
        lda_flujo = _imagen_flowable(fig_lda_burbujas(resultado_lda),
                                     _fig_mpl_lda(resultado_lda), height=430)
    _fila(
        _tarjeta('Temáticas LDA (burbujas 2D)',
                 flujo=lda_flujo, tabla=lda_tabla,
                 caption=None if lda_ok else 'LDA no disponible con los datos actuales.'),
        _tarjeta('Distribución por red social',
                 flujo=_imagen_flowable(fig_distribucion_redes(df),
                                        _fig_mpl_pie(df), width=900, height=340)),
    )

    # --- FILA 3: Alcance por tema | Top 15 palabras --------------------------
    if lda_ok:
        agrupado_alcance = alcance_por_tema_lda(df, resultado_lda)
        if agrupado_alcance.empty:
            agrupado_alcance = alcance_por_tema(df)
            if not agrupado_alcance.empty:
                agrupado_alcance['tema_lda'] = agrupado_alcance['tema_electoral']
                agrupado_alcance['palabras'] = ''
    else:
        agrupado_alcance = alcance_por_tema(df)
        if not agrupado_alcance.empty:
            agrupado_alcance['tema_lda'] = agrupado_alcance['tema_electoral']
            agrupado_alcance['palabras'] = ''
    alcance_flow = None
    if not agrupado_alcance.empty:
        alcance_flow = _imagen_flowable(fig_barras_alcance(agrupado_alcance, 'tema_lda'),
                                        _fig_mpl_barras(agrupado_alcance, 'tema_lda'),
                                        height=380)
    _fila(
        _tarjeta('Alcance estimado por tema (suma de vistas)', flujo=alcance_flow,
                 caption=None if alcance_flow else 'No hay datos de alcance por tema.'),
        _tarjeta('Top 15 palabras más repetidas',
                 flujo=_imagen_flowable(fig_top_palabras(df),
                                        _fig_mpl_barras_top(df), height=450)),
    )

    # --- FILA 4: Usuarios mencionados | Hashtags -----------------------------
    _fila(
        _tarjeta('Usuarios mencionados', flujo=menc_flow,
                 caption=None if menc_flow else 'No hay @usuarios mencionados en los posts.'),
        _tarjeta('Hashtags en los posts', flujo=hash_flow,
                 caption=None if hash_flow else 'No hay hashtags en los posts.'),
    )

    # --- FILA 5: Tendencia de sentimiento | Últimas publicaciones ------------
    tend_flow = _imagen_flowable(fig_sentimiento_temporal(df), _fig_mpl_area(df),
                                 height=380)
    ult_tabla = None
    if not df.empty:
        df_ult = df.sort_values('fecha', ascending=False, na_position='last') \
            .head(10) if 'fecha' in df.columns else df.head(10)
        filas = [['Fecha', 'Red', 'Texto', 'Likes']]
        for _, r in df_ult.iterrows():
            fecha = 'Sin fecha'
            try:
                if pd.notna(r.get('fecha')):
                    fecha = pd.Timestamp(r['fecha']).strftime('%Y-%m-%d %H:%M')
            except (TypeError, ValueError):
                fecha = 'Sin fecha'
            filas.append([fecha, str(r.get('red_social', '')),
                          str(r.get('texto', ''))[:48].replace('\n', ' '),
                          f"{int(r.get('likes') or 0)}"])
        ult_tabla = _tabla_pdf(filas, [84, 40, 100, 24])
    _fila(
        _tarjeta('Tendencia de sentimiento en el tiempo', flujo=tend_flow,
                 caption=None if tend_flow else 'No hay datos con fecha.'),
        _tarjeta('Últimas publicaciones (resumen)', tabla=ult_tabla),
    )

    doc.build(historia)
    buffer.seek(0)
    return buffer.getvalue()

def fig_sentimiento_temporal(df) -> go.Figure:
    """
    Construye la tendencia del sentimiento en el tiempo (positivo/negativo/
    neutral) como gráfico de área. Reutilizable por el dashboard y el PDF.

    Retorna:
        go.Figure o None si no hay datos con fecha.
    """
    if df is None or df.empty or 'sentimiento' not in df.columns or 'fecha' not in df.columns:
        return None
    d = df[df['fecha'].notna()]
    if d.empty:
        return None
    df_sentiment = d.groupby([d['fecha'].dt.date, 'sentimiento']).size() \
        .reset_index(name='count')
    df_sentiment.columns = ['Fecha', 'Sentimiento', 'Cantidad']
    df_sentiment = df_sentiment.sort_values(by='Fecha')
    if df_sentiment.empty:
        return None
    fig = px.area(
        df_sentiment,
        x='Fecha',
        y='Cantidad',
        color='Sentimiento',
        color_discrete_map={
            'positivo': '#10b981',
            'negativo': '#ef4444',
            'neutral': '#f59e0b'
        }
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=320
    )
    return fig


def mostrar_sentimiento_temporal(df):
    """
    Muestra la tendencia del sentimiento (positivo/negativo/neutral) en el
    tiempo con un gráfico de área.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>📈 Tendencia de Sentimiento en el Tiempo</h4>", unsafe_allow_html=True)
    if df.empty:
        st.info("Sin datos de sentimientos en el rango seleccionado.")
        return
    if 'fecha' not in df.columns or df['fecha'].notna().sum() == 0:
        st.info("Los datos cargados no tienen fecha (Facebook manual) y no se "
                "pueden graficar en la tendencia de sentimiento.")
        return
    fig = fig_sentimiento_temporal(df)
    if fig is None:
        st.info("Sin datos de sentimientos en el rango seleccionado.")
        return
    st.plotly_chart(fig, use_container_width=True)


def fig_distribucion_redes(df) -> go.Figure:
    """
    Construye el gráfico de pastel con la distribución de posts por red social.
    Solo pinta las redes presentes en los datos. Reutilizable por el PDF.

    Retorna:
        go.Figure o None si no hay datos.
    """
    if df is None or df.empty or 'red_social' not in df.columns:
        return None
    redes = df['red_social'].value_counts().reset_index()
    redes.columns = ['Red Social', 'Cantidad']
    if redes.empty:
        return None
    fig = px.pie(
        redes,
        values='Cantidad',
        names='Red Social',
        color='Red Social',
        color_discrete_map={
            'TikTok': '#ff0050',
            'Facebook': '#1877f2',
            'Instagram': '#c13584',
            'X': '#1DA1F2'
        }
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=320
    )
    return fig


def mostrar_distribucion_redes(df):
    """
    Muestra el porcentaje de posts distribuidos por canal de red social.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>📱 Distribución por Red Social</h4>", unsafe_allow_html=True)
    fig = fig_distribucion_redes(df)
    if fig is None:
        st.info("Sin datos de canales sociales.")
        return
    st.plotly_chart(fig, use_container_width=True)

def mostrar_ultimos_posts(df, n=10):
    """
    Muestra los posts más recientes filtrados en un contenedor tabular scrollable.
    """
    st.markdown(f"<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>📋 Monitoreo de Publicaciones Recientes ({min(n, len(df))})</h4>", unsafe_allow_html=True)
    if df.empty:
        st.info("No hay posts que cumplan con los filtros.")
        return
        
    df_mostrar = df[['fecha', 'red_social', 'usuario', 'texto', 'likes', 'comentarios', 'sentimiento']].copy()
    # Posts sin fecha (Facebook manual) -> "Sin fecha"; se ordenan al final
    df_mostrar['fecha_etiqueta'] = df_mostrar['fecha'].dt.strftime('%Y-%m-%d %H:%M').fillna('Sin fecha')
    df_mostrar = df_mostrar.sort_values(
        by='fecha', ascending=False, na_position='last')
    df_mostrar['fecha'] = df_mostrar['fecha_etiqueta']
    df_mostrar = df_mostrar.drop(columns=['fecha_etiqueta'])

    st.dataframe(
        df_mostrar.head(n),
        use_container_width=True,
        hide_index=True
    )

def mostrar_dashboard_redes_sociales():
    """
    Punto de entrada principal para el renderizado de la Pestaña 2.
    Define los controles de filtrado y actualiza la visualización de analíticas.
    """
    st.markdown("<h2 style='font-size: 22px; font-weight: 700; margin-top: 10px; margin-bottom: 2px;'>📊 Dashboard de Redes Sociales</h2>", unsafe_allow_html=True)
    st.caption("Monitoreo estadístico y semántico de datos reales: TikTok (Scraping API), "
               "X/Twitter (actor AI scraper.grok) y Facebook/Instagram (carga manual de "
               "CSV con Instant Data Scraper)")

    # 0.0 Badge de carga manual si hay posts de Facebook/Instagram o si el origen
    # fue la carga manual de CSVs
    df_session = st.session_state.get('posts_sociales')
    origen_manual = st.session_state.get('posts_origen') == 'manual'
    hay_manual = df_session is not None and not df_session.empty \
        and 'red_social' in df_session.columns \
        and df_session['red_social'].isin(['Facebook', 'Instagram']).any()
    if origen_manual or hay_manual:
        st.markdown('<span style="background:#6b7280;color:#fff;padding:3px 10px;'
                    'border-radius:9999px;font-size:12px;font-weight:600;">📁 Carga '
                    'manual (Facebook/Instagram)</span>', unsafe_allow_html=True)
        st.caption("Posts de Facebook/Instagram subidos con Instant Data Scraper. "
                   "Los de Facebook no tienen fecha (se ven como 'Sin fecha'); "
                   "Instagram usa fecha relativa convertida a absoluta.")
        st.markdown("<hr style='margin: 10px 0; border: 0; border-top: 1px solid #e2e8f0;'>",
                    unsafe_allow_html=True)

    # 0.1 Badge de X/Twitter si ya hay posts de X en los datos cargados
    if df_session is not None and not df_session.empty \
            and 'red_social' in df_session.columns \
            and (df_session['red_social'] == 'X').any():
        st.markdown('<span style="background:#1DA1F2;color:#fff;padding:3px 10px;'
                    'border-radius:9999px;font-size:12px;font-weight:600;">𝕏 X (Twitter) · '
                    'Extracción real vía Grok</span>', unsafe_allow_html=True)
        st.caption("Mostrando posts citados por Grok (muestreo, no feed completo). "
                   "Likes/comentarios no disponibles en esta API (0); vistas sí.")
        st.markdown("<hr style='margin: 10px 0; border: 0; border-top: 1px solid #e2e8f0;'>",
                    unsafe_allow_html=True)

    # 0. Panel de configuración de extracción real / carga manual (Scrapeless)
    mostrar_configuracion_extraccion()

    # 1. Inicializar posts en session_state (vacío hasta la primera extracción)
    if 'posts_sociales' not in st.session_state:
        st.session_state.posts_sociales = df_posts_vacio()

    # 2. Controles superiores (Filtros de Red y Tema)
    col_control1, col_control2, col_control3 = st.columns([2, 2, 1])
    
    with col_control1:
        red_seleccionada = st.selectbox(
            "Filtrar por Red Social:",
            ["Todas", "TikTok", "X", "Facebook", "Instagram"],
            key="filtro_red_social"
        )
    with col_control2:
        tema_seleccionado = st.selectbox(
            "Filtrar por Tema Político:",
            ["Todos"] + list(TEMAS_ELECTORALES.keys()),
            key="filtro_tema_electoral"
        )
    with col_control3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        st.caption("Datos reales")

    # 3. Controles secundarios: Rango de fechas y Exportación CSV
    df_actual = st.session_state.posts_sociales.copy()
    if df_actual.empty:
        st.info("📭 Aún no hay datos. Ejecuta una extracción real con un @usuario de TikTok "
                "o de X, o sube los CSVs de Facebook/Instagram en el panel de carga.")
        return
    # Fechas válidas (los posts manuales de Facebook no tienen fecha -> NaT)
    rango_fechas = None
    min_date = None
    max_date = None
    fechas_validas = df_actual['fecha'].dropna()
    if not fechas_validas.empty:
        min_date = fechas_validas.min().date()
        max_date = fechas_validas.max().date()

    col_sub1, col_sub2 = st.columns([3, 1])
    with col_sub1:
        if min_date is None or max_date is None:
            st.caption("🗓️ No hay fechas en los datos (posts de Facebook manuales "
                       "sin fecha). No se aplica filtro de rango.")
        else:
            rango_fechas = st.date_input(
                "Filtrar por Rango de Fechas:",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date,
                key="filtro_fechas"
            )
    with col_sub2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        # Preparar descarga de CSV
        csv_data = df_actual.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Exportar CSV",
            data=csv_data,
            file_name=f"scraping_redes_tlalpan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime='text/csv',
            use_container_width=True,
            key="btn_descargar_csv"
        )

    # 4. Procesar filtrado sobre el DataFrame
    df_filtrado = df_actual.copy()
    if red_seleccionada != "Todas":
        df_filtrado = df_filtrado[df_filtrado['red_social'] == red_seleccionada]
        
    if tema_seleccionado != "Todos":
        df_filtrado = df_filtrado[df_filtrado['tema_electoral'] == tema_seleccionado]
        
    if isinstance(rango_fechas, (tuple, list)) and len(rango_fechas) == 2:
        start_date, end_date = rango_fechas
        fecha_valida = df_filtrado['fecha'].notna()
        # Las filas sin fecha (Facebook manual) SIEMPRE se conservan; el rango
        # solo restringe las filas que sí tienen fecha.
        df_filtrado = df_filtrado[
            (~fecha_valida) | (
                (fecha_valida) &
                (df_filtrado['fecha'].dt.date >= start_date) &
                (df_filtrado['fecha'].dt.date <= end_date)
            )
        ]

    st.markdown("<hr style='margin: 15px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)
    
    # 5. Renderizar KPIs principales (engagement)
    mostrar_kpis(df_filtrado)

    # 5b. KPIs básicos de sentimiento (iconos + promedio)
    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    mostrar_kpis_sentimiento(df_filtrado)

    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

    # 6. Grid de gráficos principal
    g_col1, g_col2 = st.columns(2)
    with g_col1:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_evolucion_temporal(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        resultado_lda = mostrar_lda_tematicas(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)

    with g_col2:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_nube_palabras(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_distribucion_redes(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)

    # 7. Alcance por tema (LDA) y top de palabras
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    a_col1, a_col2 = st.columns(2)
    with a_col1:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_alcance_temas(df_filtrado, resultado_lda)
        st.markdown('</div>', unsafe_allow_html=True)
    with a_col2:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_top_palabras(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)

    # 8. Nubes de usuarios mencionados y hashtags
    n_col1, n_col2 = st.columns(2)
    with n_col1:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_nube_menciones(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)
    with n_col2:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_nube_hashtags(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)

    # 9. Sección de tendencias temporales y tabla detallada
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

    t_col1, t_col2 = st.columns([1.7, 1.3])
    with t_col1:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_sentimiento_temporal(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)
    with t_col2:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_ultimos_posts(df_filtrado, n=10)
        st.markdown('</div>', unsafe_allow_html=True)

    # 10. Exportar PDF de resultados
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    st.markdown('<div class="info-card">', unsafe_allow_html=True)
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>"
                "📄 Exportar resultados (PDF)</h4>", unsafe_allow_html=True)
    partes_filtro = []
    if red_seleccionada != 'Todas':
        partes_filtro.append(f'red: {red_seleccionada}')
    if tema_seleccionado != 'Todos':
        partes_filtro.append(f'tema: {tema_seleccionado}')
    if isinstance(rango_fechas, (tuple, list)) and len(rango_fechas) == 2:
        partes_filtro.append(f"fechas: {rango_fechas[0]} a {rango_fechas[1]}")
    nota_filtros = ', '.join(partes_filtro) if partes_filtro else 'sin filtros'
    k_lda = len(resultado_lda['temas']) if resultado_lda else 0
    st.download_button(
        label="📄 Descargar PDF de los resultados del dashboard",
        data=exportar_dashboard_pdf(_df_para_cache(df_filtrado), nota_filtros, k_lda),
        file_name=f"dashboard_redes_tlalpan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mime='application/pdf',
        use_container_width=True,
        key='btn_exportar_pdf',
    )
    st.caption("El PDF incluye exactamente las gráficas del dashboard (burbujas "
               "LDA, alcance por tema, nubes, tendencias) más las tablas resumen "
               "de KPIs y últimas publicaciones, con los filtros actuales.")
    st.markdown('</div>', unsafe_allow_html=True)
