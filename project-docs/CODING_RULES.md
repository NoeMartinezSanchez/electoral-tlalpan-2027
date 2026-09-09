# REGLAS DE CODIFICACIÓN (Versión Técnica)

## 1. ENTORNO Y DEPENDENCIAS
- Python 3.9+
- Crear venv: `python -m venv venv_electoral`
- Activar venv ANTES de instalar dependencias
- Instalar desde requirements.txt

## 2. ESTRUCTURA DE CÓDIGO

### app.py (Main)
```python
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from modules.data import generar_datos_iniciales, simular_visita
from modules.nlp import clasificar_queja
from modules.ocr import procesar_acta
from utils import mostrar_alertas

# Configuración mobile-first
st.set_page_config(
    page_title="Tlalpan Electoral",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="collapsed"  # Mejor para móvil
)

# Inicializar estado
if 'secciones' not in st.session_state:
    st.session_state.secciones = generar_datos_iniciales()
if 'visitas' not in st.session_state:
    st.session_state.visitas = []
if 'alertas' not in st.session_state:
    st.session_state.alertas = []

def main():
    # Layout responsive
    col_mapa, col_panel = st.columns([2, 1])
    
    with col_mapa:
        mostrar_mapa(st.session_state.secciones)
    
    with col_panel:
        mostrar_panel_control()
        mostrar_alertas(st.session_state.alertas)
        mostrar_seccion_seleccionada()

def mostrar_mapa(df):
    """Genera mapa Folium con marcadores"""
    m = folium.Map(
        location=CONFIG['CENTRO_MAPA'],
        zoom_start=CONFIG['ZOOM_MAPA'],
        control_scale=True
    )
    for _, row in df.iterrows():
        color = CONFIG['COLORES'][row['intencion']]
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=8 + (row['cobertura']/10),
            popup=f"{row['nombre']}<br>Intención: {row['intencion']}<br>Cobertura: {row['cobertura']}%",
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7
        ).add_to(m)
    folium_static(m, width=None, height=500)  # Auto-adaptable

def mostrar_panel_control():
    """Panel de control mobile-friendly"""
    st.subheader("🎯 Simulación")
    if st.button("📱 Nueva Visita", use_container_width=True):
        seccion_id, nuevo_voto, queja = simular_visita(st.session_state.secciones)
        # Actualizar estado
        st.session_state.secciones.loc[seccion_id, 'intencion'] = nuevo_voto
        st.session_state.secciones.loc[seccion_id, 'cobertura'] = min(100, 
            st.session_state.secciones.loc[seccion_id, 'cobertura'] + random.randint(2, 5))
        # Clasificar queja
        categoria, sentimiento = clasificar_queja(queja)
        # Guardar visita
        st.session_state.visitas.append({
            'seccion': seccion_id,
            'queja': queja,
            'categoria': categoria,
            'sentimiento': sentimiento,
            'fecha': datetime.now()
        })
        # Generar alertas si aplica
        generar_alertas(st.session_state.secciones)
        st.rerun()
    
    # Selector de sección (mobile-friendly)
    seccion_seleccionada = st.selectbox(
        "Selecciona sección",
        options=st.session_state.secciones['id'],
        format_func=lambda x: st.session_state.secciones[st.session_state.secciones['id']==x]['nombre'].values[0]
    )

def generar_alertas(df):
    """Genera alertas automáticas"""
    for _, row in df.iterrows():
        if row['cobertura'] < CONFIG['UMBRAL_COBERTURA']:
            st.session_state.alertas.append({
                'seccion': row['id'],
                'tipo': 'Baja cobertura',
                'mensaje': f"Sección {row['nombre']} tiene {row['cobertura']}% de cobertura"
            })
        # ... más lógica
modules/nlp.py
python
from transformers import pipeline
import streamlit as st

CATEGORIAS = ['AGUA', 'SEGURIDAD', 'BACHEO', 'ALUMBRADO', 'CONSTRUCCION_ILEGAL']

@st.cache_resource
def cargar_modelo():
    """Carga el modelo una sola vez (cacheado)"""
    return pipeline(
        "zero-shot-classification",
        model="facebook/bart-large-mnli",
        device=-1  # CPU
    )

def clasificar_queja(texto: str):
    """Clasifica queja y detecta sentimiento"""
    modelo = cargar_modelo()
    resultado = modelo(texto, CATEGORIAS)
    
    # Sentimiento simple (basado en palabras clave)
    palabras_negativas = ['no', 'nunca', 'problema', 'falla', 'robo', 'extorsión', 'peligro']
    if any(palabra in texto.lower() for palabra in palabras_negativas):
        sentimiento = 'negativo'
    elif any(palabra in ['gracias', 'bien', 'mejor', 'funciona'] for palabra in texto.lower()):
        sentimiento = 'positivo'
    else:
        sentimiento = 'neutral'
    
    return resultado['labels'][0], sentimiento
modules/ocr.py
python
import pytesseract
from PIL import Image
import re
import streamlit as st

def procesar_acta(imagen_path):
    """Procesa imagen de acta con OCR"""
    try:
        img = Image.open(imagen_path)
        texto = pytesseract.image_to_string(img, lang='spa')
        
        # Extraer números
        numeros = re.findall(r'\d+', texto)
        if len(numeros) >= 3:
            votos = {
                'partido1': int(numeros[0]),
                'partido2': int(numeros[1]),
                'nulos': int(numeros[2]),
                'total': sum(int(n) for n in numeros[:3])
            }
            
            # Verificar anomalía (simple)
            expected = st.session_state.secciones[st.session_state.secciones['id']==id_seccion]['cobertura'].values[0]
            # ... lógica de anomalía
            
            return votos
        return {'error': 'No se encontraron números'}
    except Exception as e:
        return {'error': str(e)}
utils.py
python
import streamlit as st
from modules.data import CONFIG

def mostrar_alertas(alertas):
    """Muestra alertas en formato mobile-friendly"""
    if alertas:
        st.subheader("⚠️ Alertas")
        for alerta in alertas[-5:]:  # Últimas 5
            st.warning(f"{alerta['seccion']}: {alerta['mensaje']}")
3. MOBILE-FIRST (CRÍTICO PARA DEMO EN TELÉFONO)
Usar use_container_width=True en todos los botones

Altura de mapa: 400-500px (no más)

Fuentes grandes: st.markdown("<h3>", unsafe_allow_html=True)

Evitar sidebar (colapsado por defecto)

Columnas: [2,1] o [1,1] en móvil

Botones con íconos (📱, 🗳️, ⚠️)

4. EJECUCIÓN PARA DEMO MÓVIL
bash
# Terminal
python -m venv venv_electoral
source venv_electoral/bin/activate  # o .\venv_electoral\Scripts\activate
pip install -r requirements.txt
streamlit run app.py --server.enableCORS true --server.enableXsrfProtection false

# En teléfono (misma red WiFi):
# Abrir: http://192.168.x.x:8501  (reemplazar con IP local)
5. REGLAS PARA EL AGENTE
Generar código completo (no pseudo)

Implementar mobile-first desde el inicio

Usar @st.cache_resource para modelos pesados

Incluir manejo de errores (try/except)

Documentar funciones con docstrings

NO generar código que requiera autenticación externa

Priorizar que el demo funcione sobre optimización

text

---

## 📱 **Instrucciones para el Demo en Teléfono**

### Pasos para verlo en tu celular:

1. **Asegúrate de estar en la misma red WiFi**
2. **Ejecuta Streamlit**:
   ```bash
   streamlit run app.py --server.enableCORS true --server.enableXsrfProtection false
En la terminal, busca la IP local (ej: http://192.168.1.100:8501)

En tu teléfono, abre el navegador y escribe esa IP

Guarda el enlace en favoritos para acceso rápido

Consejos para la presentación:
✅ Usa el teléfono en horizontal para mejor visualización

✅ Los botones grandes son fáciles de tocar

✅ El mapa es táctil (puedes hacer zoom con dedos)

✅ Prepara un guión de 3 minutos:

"Aquí tenemos el mapa de Tlalpan con las 10 secciones"
"Presiono 'Nueva Visita' y vemos cómo se actualiza en tiempo real"
"Selecciono una sección y veo las quejas de los vecinos"
"Subo un acta de escrutinio y el sistema extrae los votos con OCR"


```markdown
# REGLAS DE CODIFICACIÓN - PESTAÑA 2: REDES SOCIALES

## 1. ESTRUCTURA DE app.py (con pestañas)
```python
import streamlit as st

st.set_page_config(page_title="Tlalpan Electoral 2027", layout="wide")

# Crear pestañas
tab1, tab2 = st.tabs(["🗳️ Inteligencia Electoral", "📊 Redes Sociales"])

with tab1:
    # TODO: Código actual de la Pestaña 1
    pass

with tab2:
    # TODO: Código de la Pestaña 2
    from modules.social_media import mostrar_dashboard_redes_sociales
    mostrar_dashboard_redes_sociales()
2. Módulo social_media.py (Estructura base)
python
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

@st.cache_data
def generar_datos_iniciales(n=500):
    """Genera datos sintéticos de redes sociales (cacheado)"""
    from modules.social_media_generator import generar_posts
    return generar_posts(n)

def mostrar_dashboard_redes_sociales():
    """Página principal del dashboard de redes sociales"""
    st.header("📊 Análisis de Redes Sociales")
    st.caption("Simulación de scraping: TikTok, Facebook, X, Instagram")
    
    # Inicializar datos
    if 'posts_sociales' not in st.session_state:
        st.session_state.posts_sociales = generar_datos_iniciales(500)
    
    # Controles
    col_control1, col_control2, col_control3 = st.columns([2, 1, 1])
    with col_control1:
        red_seleccionada = st.selectbox(
            "Red Social",
            ["Todas", "TikTok", "Facebook", "X", "Instagram"]
        )
    with col_control2:
        tema_seleccionado = st.selectbox(
            "Tema",
            ["Todos"] + list(TEMAS_ELECTORALES.keys())
        )
    with col_control3:
        if st.button("🔄 Actualizar Datos", use_container_width=True):
            with st.spinner("Generando nuevos posts..."):
                nuevos_posts = generar_datos_iniciales(500)
                st.session_state.posts_sociales = nuevos_posts
                st.success(f"✅ {len(nuevos_posts)} posts generados")
    
    # Filtrar datos
    df = st.session_state.posts_sociales.copy()
    if red_seleccionada != "Todas":
        df = df[df['red_social'] == red_seleccionada]
    if tema_seleccionado != "Todos":
        df = df[df['tema_electoral'] == tema_seleccionado]
    
    # KPIs
    mostrar_kpis(df)
    
    # Visualizaciones (2 columnas)
    col1, col2 = st.columns(2)
    with col1:
        mostrar_evolucion_temporal(df)
        mostrar_top_temas(df)
    with col2:
        mostrar_nube_palabras(df)
        mostrar_distribucion_redes(df)
    
    # Sentimiento y tabla
    col3, col4 = st.columns([2, 1])
    with col3:
        mostrar_sentimiento_temporal(df)
    with col4:
        mostrar_ultimos_posts(df)
3. Funciones de Visualización
python
def mostrar_kpis(df):
    """Muestra tarjetas con KPIs"""
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("📝 Total Posts", len(df))
    with col2:
        st.metric("❤️ Likes", f"{df['likes'].sum():,}")
    with col3:
        st.metric("💬 Comentarios", f"{df['comentarios'].sum():,}")
    with col4:
        st.metric("🔄 Compartidos", f"{df['compartidos'].sum():,}")
    with col5:
        engagement = (df['likes'] + df['comentarios'] + df['compartidos']).sum()
        st.metric("📈 Engagement", f"{engagement:,}")

def mostrar_evolucion_temporal(df):
    """Gráfico de línea temporal con Plotly"""
    df_daily = df.groupby(df['fecha'].dt.date).agg({
        'likes': 'sum',
        'comentarios': 'sum',
        'compartidos': 'sum'
    }).reset_index()
    
    fig = px.line(df_daily, x='fecha', y=['likes', 'comentarios', 'compartidos'],
                  title='Evolución de Interacciones en el Tiempo',
                  labels={'value': 'Interacciones', 'fecha': 'Fecha'})
    st.plotly_chart(fig, use_container_width=True)

def mostrar_nube_palabras(df):
    """Genera nube de palabras con colores por sentimiento"""
    text = ' '.join(df['texto'].values)
    wordcloud = WordCloud(width=800, height=400, background_color='white').generate(text)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wordcloud, interpolation='bilinear')
    ax.axis('off')
    st.pyplot(fig)

def mostrar_top_temas(df):
    """Top 10 temas electorales en barras horizontales"""
    temas = df['tema_electoral'].value_counts().head(10)
    fig = px.bar(x=temas.values, y=temas.index, orientation='h',
                 title='Top 10 Temas de Interés Electoral',
                 labels={'x': 'Número de Posts', 'y': 'Tema'})
    st.plotly_chart(fig, use_container_width=True)

def mostrar_sentimiento_temporal(df):
    """Sentimiento a lo largo del tiempo (áreas)"""
    df_sentiment = df.groupby([df['fecha'].dt.date, 'sentimiento']).size().reset_index(name='count')
    fig = px.area(df_sentiment, x='fecha', y='count', color='sentimiento',
                  title='Evolución del Sentimiento en el Tiempo',
                  labels={'fecha': 'Fecha', 'count': 'Número de Posts'})
    st.plotly_chart(fig, use_container_width=True)

def mostrar_distribucion_redes(df):
    """Distribución por red social (pastel)"""
    redes = df['red_social'].value_counts()
    fig = px.pie(values=redes.values, names=redes.index,
                 title='Distribución por Red Social')
    st.plotly_chart(fig, use_container_width=True)

def mostrar_ultimos_posts(df, n=10):
    """Muestra tabla con los últimos posts"""
    st.subheader("📋 Últimos Posts")
    st.dataframe(
        df[['fecha', 'red_social', 'usuario', 'texto', 'likes', 'comentarios']]
        .sort_values('fecha', ascending=False)
        .head(n),
        use_container_width=True,
        hide_index=True
    )
4. DEPENDENCIAS ADICIONALES
txt
# Añadir a requirements.txt
wordcloud>=1.9.0
plotly>=5.14.0
matplotlib>=3.7.0
Faker>=18.0.0
5. REGLAS PARA EL AGENTE
La Pestaña 2 debe ser independiente de la Pestaña 1 (no compartir estado)

Usar @st.cache_data para datos generados (no cachear visualizaciones)

Todos los gráficos deben ser interactivos (Plotly)

Implementar diseño mobile-first

Mostrar spinners durante generación de datos

Incluir botón de exportación a CSV (opcional)

Generar 500-1000 posts por actualización

Los datos deben ser realistas y variados

NOTA ACTUALIZADA (extracción real): la Pestaña 2 es real-only. NO generar posts
sintéticos de redes sociales. Los datos llegan de Scrapeless:
- TikTok: Scraping API sobre un perfil (`user.detail` + `user.work`).
- Instagram: Scraping Browser (CDP) + API interna `web_profile_info`, sin login
  de Instagram. Guardados/vistas no disponibles en sesión anónima (0).
- X/Twitter: actor AI `scraper.grok` (`/api/v2/scraper/execute`). Los posts son
  CITAS de Grok (muestreo, no feed completo); likes/comentarios no disponibles
  (0), vistas vía `view_count`.
Resultados normalizados a las columnas de `COLUMNAS_POSTS` y guardados en
`datos_extraidos/`. Todo nuevo flujo de extracción debe mantener manejo de
errores (404/privado/401-403/429/login-wall/timeout) y docstrings en español.