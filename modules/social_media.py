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
    analizar_lda,
    extraer_menciones,
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

def mostrar_evolucion_temporal(df):
    """
    Renderiza la evolución diaria de las interacciones agregadas en un gráfico de líneas interactivo.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>📈 Evolución de Interacciones</h4>", unsafe_allow_html=True)
    if df.empty:
        st.info("No hay datos suficientes para el rango seleccionado.")
        return
    # Posts sin fecha (Facebook manual) no entran en la serie temporal
    df = df[df['fecha'].notna()]
    if df.empty:
        st.info("Los datos cargados no tienen fecha (Facebook manual) y no se "
                "pueden graficar en la serie temporal.")
        return
    st.caption("Los posts de Facebook (carga manual, sin fecha) no se incluyen "
               "en la serie temporal.")
        
    df_daily = df.groupby(df['fecha'].dt.date).agg({
        'likes': 'sum',
        'comentarios': 'sum',
        'compartidos': 'sum'
    }).reset_index()
    
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
    st.plotly_chart(fig, use_container_width=True)

def mostrar_nube_palabras(df):
    """
    Genera y dibuja una Nube de Palabras a partir del texto de los posts, 
    coloreada según sentimientos.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>☁️ Nube de Temas (por sentimiento)</h4>", unsafe_allow_html=True)
    if df.empty:
        st.info("No hay suficientes datos de texto.")
        return
        
    textos = ' '.join(df['texto'].values)
    
    # Stopwords de uso frecuente en español (compartido con el análisis de texto)
    stopwords_es = STOPWORDS_ES
    
    try:
        wordcloud = WordCloud(
            width=800, 
            height=400, 
            background_color='white',
            stopwords=stopwords_es,
            max_words=80,
            random_state=42
        ).generate(textos)
        
        # Aplicar recoloración personalizada por sentimiento
        wordcloud.recolor(color_func=color_por_sentimiento)
        
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wordcloud, interpolation='bilinear')
        ax.axis('off')
        st.pyplot(fig)
        plt.close(fig)
    except Exception as e:
        st.error(f"No se pudo generar la WordCloud: {e}")

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


def mostrar_lda_tematicas(df):
    """
    Análisis de temáticas con LDA representadas como burbujas en un plano 2D
    (estilo pyLDAvis): la cercanía entre burbujas refleja la distancia entre
    temáticas (Jensen-Shannon + MDS) y el tamaño su prevalencia.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>"
                "🧩 Temáticas LDA (burbujas 2D)</h4>", unsafe_allow_html=True)
    if df.empty or 'texto' not in df.columns:
        st.info("No hay texto para ejecutar el análisis LDA.")
        return
    n_textos = int(df['texto'].fillna('').astype(str).str.strip().ne('').sum())
    if n_textos < 15:
        st.info(f"Se necesitan al menos 15 posts con texto para LDA (hay {n_textos}).")
        return
    k = st.slider("Nº de temáticas (LDA)", 3, 10, 5, 1,
                  help="Ajusta el número de temas latentes a detectar.")
    with st.spinner("Analizando temáticas con LDA..."):
        resultado = analizar_lda(df, n_topics=k)
    if not resultado.get('ok'):
        st.info(resultado.get('error', 'No se pudo ejecutar el análisis LDA.'))
        return
    temas = resultado['temas']
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
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Cercanía entre burbujas = distancia entre temáticas (JS + MDS); "
               "tamaño = prevalencia del tema en los posts.")
    with st.expander("🔎 Palabras clave por temática"):
        for t in temas:
            st.markdown(f"**Tema {t['id']}** · prevalencia {t['prevalencia'] * 100:.1f}%  \n"
                        f"`{' · '.join(t['palabras'])}`")


def mostrar_alcance_temas(df):
    """
    Barra horizontal con el alcance aproximado (suma de vistas) por tema
    electoral. Facebook/Instagram (CSV manual) no traen vistas y aportan 0.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>"
                "🎯 Alcance estimado por tema</h4>", unsafe_allow_html=True)
    agrupado = alcance_por_tema(df)
    if agrupado.empty:
        st.info("No hay datos de alcance por tema.")
        return
    agrupado = agrupado.sort_values('alcance', ascending=True)
    fig = px.bar(agrupado, x='alcance', y='tema_electoral', orientation='h',
                 color='alcance', color_continuous_scale='Blues',
                 labels={'alcance': 'Alcance aprox. (vistas)',
                         'tema_electoral': 'Tema'})
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=340,
                      showlegend=False)
    fig.update_coloraxes(showscale=False)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Alcance ≈ suma de vistas (plays TikTok + view_count X). "
               "Las redes sin métrica de audiencia (FB/IG manual) aportan 0.")


def mostrar_top_palabras(df):
    """
    Top 15 palabras más repetidas en los textos de los posts (sin stopwords)
    en una gráfica de barras horizontales.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>"
                "🏅 Top 15 palabras más repetidas</h4>", unsafe_allow_html=True)
    frecuencias = frecuencia_palabras(df, n=15)
    if frecuencias.empty:
        st.info("No hay palabras suficientes para graficar.")
        return
    frecuencias = frecuencias.sort_values('frecuencia', ascending=True)
    fig = px.bar(frecuencias, x='frecuencia', y='palabra', orientation='h',
                 color='frecuencia', color_continuous_scale='Greens',
                 labels={'frecuencia': 'Frecuencia', 'palabra': 'Palabra'})
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10), height=420,
                      showlegend=False)
    fig.update_coloraxes(showscale=False)
    st.plotly_chart(fig, use_container_width=True)


def mostrar_nube_menciones(df):
    """
    Nube de palabras con los @usuarios mencionados en los posts (todas las
    redes).
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>"
                "👥 Usuarios mencionados en los posts</h4>", unsafe_allow_html=True)
    menciones = extraer_menciones(df)
    if menciones.empty:
        st.info("No hay @usuarios mencionados en los posts.")
        return
    texto_menciones = ' '.join(menciones['usuario'].astype(str).tolist())
    try:
        wc = WordCloud(width=800, height=400, background_color='white',
                       max_words=60, random_state=42, collocations=False,
                       min_font_size=8).generate(texto_menciones)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.imshow(wc, interpolation='bilinear')
        ax.axis('off')
        st.pyplot(fig)
        plt.close(fig)
    except Exception as e:
        st.error(f"No se pudo generar la nube de menciones: {e}")


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


def _imagen_pdf_donut(resumen: dict):
    """
    Donut de distribución de sentimiento como imagen PNG (BytesIO) para el PDF.

    Retorna:
        BytesIO o None si no hay datos de sentimiento.
    """
    from io import BytesIO
    import matplotlib.pyplot as plt
    valores = [resumen['positivos'], resumen['neutrales'], resumen['negativos']]
    if not any(valores):
        return None
    fig, ax = plt.subplots(figsize=(3.4, 2.0), dpi=140)
    ax.pie(valores, labels=['Positivo', 'Neutral', 'Negativo'],
           colors=['#10b981', '#f59e0b', '#ef4444'],
           startangle=90, counterclock=False,
           wedgeprops=dict(width=0.45),
           autopct=lambda p: f'{p:.0f}%', textprops={'fontsize': 7})
    ax.set_aspect('equal')
    buf = BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', transparent=True)
    plt.close(fig)
    buf.seek(0)
    return buf


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


@st.cache_data(show_spinner=False, max_entries=12)
def exportar_dashboard_pdf(df: pd.DataFrame, nota_filtros: str = '') -> bytes:
    """
    Genera un PDF (reportlab + minigráficos matplotlib) con los resultados del
    dashboard: KPIs, distribución por red, sentimiento, alcance por tema,
    palabras más repetidas y menciones. Se cachea por contenido del DataFrame.

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
    from reportlab.platypus import (HRFlowable, Image, Paragraph,
                                    SimpleDocTemplate, Spacer)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=16 * mm,
                            rightMargin=16 * mm, topMargin=14 * mm,
                            bottomMargin=14 * mm)
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle('Titulo', parent=estilos['Title'], fontSize=16,
                            textColor=colors.HexColor('#0f172a'), spaceAfter=4)
    h2 = ParagraphStyle('H2', parent=estilos['Heading2'], fontSize=12,
                        spaceBefore=12, spaceAfter=4,
                        textColor=colors.HexColor('#059669'))
    cuerpo = ParagraphStyle('Cuerpo', parent=estilos['BodyText'], fontSize=9,
                            leading=12)
    historia = []

    historia.append(Paragraph('Dashboard de Redes Sociales — Tlalpan 2027', titulo))
    historia.append(Paragraph(f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                              cuerpo))
    if nota_filtros:
        historia.append(Paragraph(f"Filtros aplicados: {nota_filtros}", cuerpo))
    historia.append(Spacer(1, 4))
    historia.append(HRFlowable(width='100%', thickness=1.2,
                               color=colors.HexColor('#059669')))

    # --- KPIs y sentimiento ---
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
    historia.append(_tabla_pdf([
        ['Métrica', 'Valor', 'Métrica', 'Valor'],
        ['Total posts', f'{total:,}', 'Likes', f'{likes:,}'],
        ['Comentarios', f'{coment:,}', 'Compartidos', f'{compart:,}'],
        ['Alcance (vistas)', f'{vistas_tot:,}', 'Sentimiento promedio',
         f"{resumen['promedio']:+.2f}"],
        ['Positivos', str(resumen['positivos']), 'Negativos', str(resumen['negativos'])],
    ], [90, 110, 110, 110]))
    imagen = _imagen_pdf_donut(resumen)
    if imagen:
        historia.append(Spacer(1, 6))
        historia.append(Image(imagen, width=150, height=88))

    # --- Distribución por red ---
    if not df.empty and 'red_social' in df.columns:
        historia.append(Paragraph('Distribución por red social', h2))
        agg = [('posts', 'red_social', 'size')]
        for col, nombre in (('likes', 'likes'), ('comentarios', 'comentarios'),
                            ('compartidos', 'compartidos'), ('vistas', 'vistas')):
            agg.append((nombre, col, 'sum') if col in df.columns else (nombre, 'red_social', 'size'))
        por_red = df.groupby('red_social', dropna=False).agg(**{
            k: (c, op) for k, c, op in agg}).reset_index()
        filas = [['Red social', 'Posts', 'Likes', 'Com.', 'Compart.', 'Vistas']]
        for _, r in por_red.iterrows():
            filas.append([str(r['red_social']),
                          f"{int(r['posts']):,}", f"{int(r['likes']):,}",
                          f"{int(r['comentarios']):,}", f"{int(r['compartidos']):,}",
                          f"{int(r['vistas']):,}"])
        historia.append(_tabla_pdf(filas, [90, 55, 70, 70, 80, 80]))

    # --- Alcance por tema ---
    alcance = alcance_por_tema(df)
    if not alcance.empty:
        historia.append(Paragraph('Alcance estimado por tema (suma de vistas)', h2))
        filas = [['Tema', 'Posts', 'Alcance (vistas)', 'Engagement']]
        for _, r in alcance.iterrows():
            filas.append([str(r['tema_electoral']), f"{int(r['n_posts']):,}",
                          f"{int(r['alcance']):,}", f"{int(r['engagement']):,}"])
        historia.append(_tabla_pdf(filas, [150, 60, 110, 110]))

    # --- Top palabras y menciones ---
    frecuencias = frecuencia_palabras(df, n=15)
    if not frecuencias.empty:
        historia.append(Paragraph('Top 15 palabras más repetidas', h2))
        filas = [['#', 'Palabra', 'Frecuencia']]
        for i, (_, r) in enumerate(frecuencias.iterrows(), start=1):
            filas.append([str(i), str(r['palabra']), f"{int(r['frecuencia']):,}"])
        historia.append(_tabla_pdf(filas, [35, 220, 100]))
    menciones = extraer_menciones(df)
    if not menciones.empty:
        historia.append(Paragraph('Usuarios mencionados (top 10)', h2))
        filas = [['#', 'Usuario', 'Menciones']]
        for i, (_, r) in enumerate(menciones.head(10).iterrows(), start=1):
            filas.append([str(i), str(r['usuario']), f"{int(r['menciones']):,}"])
        historia.append(_tabla_pdf(filas, [35, 200, 120]))

    doc.build(historia)
    buffer.seek(0)
    return buffer.getvalue()

def mostrar_sentimiento_temporal(df):
    """
    Muestra la tendencia del sentimiento (positivo/negativo/neutral) en el tiempo con un gráfico de área.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>📈 Tendencia de Sentimiento en el Tiempo</h4>", unsafe_allow_html=True)
    if df.empty:
        st.info("Sin datos de sentimientos en el rango seleccionado.")
        return
    # Posts sin fecha (Facebook manual) se excluyen del análisis temporal
    df = df[df['fecha'].notna()]
    if df.empty:
        st.info("Los datos cargados no tienen fecha (Facebook manual) y no se "
                "pueden graficar en la tendencia de sentimiento.")
        return
        
    # Agrupar por día y sentimiento
    df_sentiment = df.groupby([df['fecha'].dt.date, 'sentimiento']).size().reset_index(name='count')
    df_sentiment.columns = ['Fecha', 'Sentimiento', 'Cantidad']
    df_sentiment = df_sentiment.sort_values(by='Fecha')
    
    fig = px.area(
        df_sentiment, 
        x='Fecha', 
        y='Cantidad', 
        color='Sentimiento',
        color_discrete_map={
            'positivo': '#10b981',  # Verde
            'negativo': '#ef4444',  # Rojo
            'neutral': '#f59e0b'   # Amarillo
        }
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=320
    )
    st.plotly_chart(fig, use_container_width=True)

def mostrar_distribucion_redes(df):
    """
    Muestra el porcentaje de posts distribuidos por canal de red social.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>📱 Distribución por Red Social</h4>", unsafe_allow_html=True)
    if df.empty:
        st.info("Sin datos de canales sociales.")
        return
        
    redes = df['red_social'].value_counts().reset_index()
    redes.columns = ['Red Social', 'Cantidad']
    
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
        mostrar_lda_tematicas(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)

    with g_col2:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_nube_palabras(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_distribucion_redes(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)

    # 7. Alcance por tema y top de palabras
    st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
    a_col1, a_col2 = st.columns(2)
    with a_col1:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_alcance_temas(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)
    with a_col2:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_top_palabras(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)

    # 8. Nube de usuarios mencionados
    st.markdown('<div class="info-card">', unsafe_allow_html=True)
    mostrar_nube_menciones(df_filtrado)
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
    st.download_button(
        label="📄 Descargar PDF de los resultados del dashboard",
        data=exportar_dashboard_pdf(_df_para_cache(df_filtrado), nota_filtros),
        file_name=f"dashboard_redes_tlalpan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mime='application/pdf',
        use_container_width=True,
        key='btn_exportar_pdf',
    )
    st.caption("El PDF incluye KPIs, distribución por red, sentimiento, alcance "
               "por tema, top de palabras y menciones con los filtros actuales.")
    st.markdown('</div>', unsafe_allow_html=True)
