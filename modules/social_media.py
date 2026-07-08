import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# Importar generador sintético
from modules.social_media_generator import generar_posts, TEMAS_ELECTORALES

@st.cache_data
def generar_datos_iniciales(n=500):
    """
    Genera datos sintéticos de redes sociales (cacheado).
    """
    return generar_posts(n)

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
    
    # Stopwords de uso frecuente en español
    stopwords_es = set([
        'de', 'la', 'que', 'el', 'en', 'y', 'a', 'los', 'del', 'se', 'las', 'por', 'un', 'para',
        'con', 'no', 'una', 'su', 'al', 'lo', 'como', 'más', 'pero', 'sus', 'es', 'este', 'esta',
        'está', 'hay', 'son', 'están', 'todo', 'todos', 'hace', 'muy', 'desde', 'sobre', 'estamos',
        'exigimos', 'nos', 'nuestra', 'nuestro', 'hacia', 'entre', 'ya', 'esta', 'eso', 'toda',
        'cada', 'tienen', 'esta', 'este', 'estos', 'estas', 'tiene', 'tienen'
    ])
    
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

def mostrar_top_temas(df):
    """
    Muestra los 10 temas de interés electoral más frecuentes en un gráfico de barras horizontales.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>📊 Top Temas de Interés Electoral</h4>", unsafe_allow_html=True)
    if df.empty:
        st.info("No hay datos para graficar.")
        return
        
    temas = df['tema_electoral'].value_counts().head(10).reset_index()
    temas.columns = ['Tema', 'Posts']
    
    # Ordenar ascendente para que en horizontal el mayor quede arriba
    temas = temas.sort_values(by='Posts', ascending=True)
    
    fig = px.bar(
        temas, 
        x='Posts', 
        y='Tema', 
        orientation='h',
        color='Tema',
        color_discrete_sequence=px.colors.qualitative.Safe
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        height=320
    )
    st.plotly_chart(fig, use_container_width=True)

def mostrar_sentimiento_temporal(df):
    """
    Muestra la tendencia del sentimiento (positivo/negativo/neutral) en el tiempo con un gráfico de área.
    """
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-bottom: 5px;'>📈 Tendencia de Sentimiento en el Tiempo</h4>", unsafe_allow_html=True)
    if df.empty:
        st.info("Sin datos de sentimientos en el rango seleccionado.")
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
            'X': '#0f1419'
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
    df_mostrar['fecha'] = df_mostrar['fecha'].dt.strftime('%Y-%m-%d %H:%M')
    
    st.dataframe(
        df_mostrar.sort_values(by='fecha', ascending=False).head(n),
        use_container_width=True,
        hide_index=True
    )

def mostrar_dashboard_redes_sociales():
    """
    Punto de entrada principal para el renderizado de la Pestaña 2.
    Define los controles de filtrado y actualiza la visualización de analíticas.
    """
    st.markdown("<h2 style='font-size: 22px; font-weight: 700; margin-top: 10px; margin-bottom: 2px;'>📊 Dashboard de Redes Sociales</h2>", unsafe_allow_html=True)
    st.caption("Monitoreo estadístico y semántico en canales digitales (Simulación de Scraping)")
    
    # 1. Inicializar posts en session_state si no existen (500 posts iniciales)
    if 'posts_sociales' not in st.session_state:
        st.session_state.posts_sociales = generar_datos_iniciales(600)
        
    # 2. Controles superiores (Filtros de Red, Tema y Actualización de Scraping)
    col_control1, col_control2, col_control3 = st.columns([2, 2, 1])
    
    with col_control1:
        red_seleccionada = st.selectbox(
            "Filtrar por Red Social:",
            ["Todas", "TikTok", "Facebook", "X", "Instagram"],
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
        if st.button("🔄 Actualizar Datos", use_container_width=True, key="btn_actualizar_scraping"):
            with st.spinner("Simulando scraping y ejecutando NLP..."):
                # Generar entre 500 y 800 posts aleatorios nuevos
                nuevos_datos = generar_posts(random.randint(500, 800))
                st.session_state.posts_sociales = nuevos_datos
                st.toast(f"¡Scraping completado! {len(nuevos_datos)} posts importados.", icon="✅")
                st.rerun()

    # 3. Controles secundarios: Rango de fechas y Exportación CSV
    df_actual = st.session_state.posts_sociales.copy()
    min_date = df_actual['fecha'].min().date()
    max_date = df_actual['fecha'].max().date()
    
    col_sub1, col_sub2 = st.columns([3, 1])
    with col_sub1:
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
        df_filtrado = df_filtrado[
            (df_filtrado['fecha'].dt.date >= start_date) & 
            (df_filtrado['fecha'].dt.date <= end_date)
        ]

    st.markdown("<hr style='margin: 15px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)
    
    # 5. Renderizar KPIs principales
    mostrar_kpis(df_filtrado)
    
    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
    
    # 6. Renderizar Grid de Gráficos (Diseño adaptable de Streamlit)
    g_col1, g_col2 = st.columns(2)
    with g_col1:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_evolucion_temporal(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_top_temas(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with g_col2:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_nube_palabras(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        mostrar_distribucion_redes(df_filtrado)
        st.markdown('</div>', unsafe_allow_html=True)

    # 7. Renderizar Sección de tendencias temporales y tabla detallada
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
import random
