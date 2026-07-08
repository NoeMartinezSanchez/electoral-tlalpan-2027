# PROYECTO: Sistema Electoral Tlalpan 2027 - Demo Técnico

## OBJETIVO
Prototipo funcional en 7 días con Streamlit, Folium y Transformers. Demo mobile-first.

## STACK TÉCNICO
- **Frontend**: Streamlit (responsivo, mobile-ready)
- **Mapas**: Folium + streamlit-folium (interactivo)
- **Datos**: Pandas, NumPy (datos sintéticos)
- **NLP**: Hugging Face transformers (zero-shot)
- **OCR**: Tesseract (local) o pytesseract
- **Estado**: session_state de Streamlit

## ARQUITECTURA (3 módulos)

### Módulo 1: Mapa Dinámico
- Folium centrado en Tlalpan [19.2889, -99.1689], zoom 12
- Marcadores coloreados por intención: VERDE (a favor), ROJO (en contra), AMARILLO (indeciso)
- Popup: nombre, % cobertura, última visita
- Actualización en tiempo real con `st.rerun()` o `st.experimental_rerun()`

### Módulo 2: NLP en Quejas
- Modelo: `facebook/bart-large-mnli` (zero-shot)
- Categorías: AGUA, SEGURIDAD, BACHEO, ALUMBRADO, CONSTRUCCION_ILEGAL
- Caching con `@st.cache_resource` para evitar recarga del modelo
- Microsegmentación al seleccionar sección

### Módulo 3: OCR en Actas
- `pytesseract` con idioma español (`lang='spa'`)
- Extracción simple con regex `\d+` (demo)
- Comparación con datos esperados (umbral 5% anomalía)

## FLUJO DE DEMO (3 pasos)
1. Cargar datos sintéticos (10 secciones)
2. Simular visitas → actualizar mapa y clasificar quejas
3. Subir acta → OCR → mostrar resultados

## MOBILE-FIRST (CRÍTICO)
- Usar `st.set_page_config(layout="wide")` pero con columnas adaptables
- Mapas con altura fija (400px) y scroll
- Botones grandes (touch-friendly)
- Evitar hover, usar clicks en móvil

## ESTRUCTURA DE CARPETAS
electoral/
├── project-docs/
│ ├── PROJECT_CONTEXT.md
│ ├── DATA_STRUCTURE.md
│ └── CODING_RULES.md
├── app.py # Main
├── modules/
│ ├── nlp.py # Clasificación de quejas
│ ├── ocr.py # Procesamiento de actas
│ └── data.py # Generación de datos
├── utils.py # Helpers
├── requirements.txt
└── .env # Variables de entorno (opcional)

text

## ENTORNO VIRTUAL (IMPORTANTE)
- Crear venv: `python -m venv venv_electoral`
- Activar: `source venv_electoral/bin/activate` (Linux/Mac) o `venv_electoral\Scripts\activate` (Windows)
- Instalar: `pip install -r requirements.txt`
- Ejecutar: `streamlit run app.py`

## NOTA PARA EL AGENTE
- Generar código ejecutable, no pseudo-código
- Usar `st.session_state` para persistencia
- Implementar mobile-first desde el principio
- NO usar APIs externas con autenticación (todo local)

# PROYECTO: Sistema Electoral Tlalpan 2027 - Demo Completo

## OBJETIVO GENERAL
Prototipo funcional con dos pestañas:
1. **Pestaña 1**: Sistema de inteligencia electoral (mapa, visitas, NLP, OCR)
2. **Pestaña 2**: Dashboard de análisis de redes sociales (TikTok, Facebook, X, Instagram)

## ARQUITECTURA DE LA PESTAÑA 2: REDES SOCIALES

### 1. Simulación de Recolección de Datos
- **Datos sintéticos**: Generar posts simulados con atributos realistas
- **Estructura de datos**:
  - `id_post`: int (identificador único)
  - `red_social`: str ('TikTok', 'Facebook', 'X', 'Instagram')
  - `usuario`: str (nombre de usuario)
  - `fecha`: datetime (fecha del post)
  - `texto`: str (contenido del post)
  - `hashtags`: list[str] (hashtags utilizados)
  - `likes`: int (número de likes)
  - `comentarios`: int (número de comentarios)
  - `compartidos`: int (número de shares/retweets)
  - `sentimiento`: str ('positivo', 'negativo', 'neutral')
  - `tema_electoral`: str (categoría política)

- **Cantidad**: Generar 500-1000 posts por actualización
- **Temas electorales predefinidos**:
  - Agua
  - Seguridad
  - Transporte
  - Vivienda
  - Empleo
  - Educación
  - Salud
  - Medio Ambiente
  - Corrupción
  - Participación Ciudadana

### 2. Dashboard de Análisis
- **KPIs en tarjetas**:
  - Total de posts
  - Total de likes
  - Total de comentarios
  - Total de compartidos
  - Engagement rate (likes+comentarios+compartidos / posts)

- **Visualizaciones**:
  1. Evolución temporal (línea de tiempo interactiva con Plotly)
  2. Nube de palabras (WordCloud con colores por sentimiento)
  3. Sentimiento a lo largo del tiempo (gráfico de áreas)
  4. Top 10 temas de interés electoral (barras horizontales)
  5. Distribución por red social (gráfico de pastel)
  6. Tabla de posts recientes (scrollable)

### 3. Interactividad
- **Filtros**:
  - Selector de red social (Todas/TikTok/Facebook/X/Instagram)
  - Selector de tema electoral
  - Rango de fechas (date picker)
- **Botón "Actualizar Datos"**: Regenera datos sintéticos (simula scraping)
- **Exportar**: Botón para descargar datos en CSV

### 4. Simulación de Scraping
- Al presionar "Actualizar Datos":
  1. Generar 500 nuevos posts aleatorios
  2. Aplicar NLP para clasificar sentimiento y temas
  3. Actualizar todas las visualizaciones en tiempo real
  4. Mostrar mensaje: "Datos actualizados: X posts nuevos"

## TECNOLOGÍAS PARA PESTAÑA 2
- **WordCloud**: `wordcloud` + `matplotlib`
- **Gráficos interactivos**: `plotly.express` (para evolución y distribución)
- **Procesamiento de texto**: `transformers` (zero-shot para temas)
- **Cache**: `@st.cache_data` para datos generados

## ESTRUCTURA DE CARPETAS (Actualizada)
electoral/
├── project-docs/
│ ├── PROJECT_CONTEXT.md
│ ├── DATA_STRUCTURE.md
│ └── CODING_RULES.md
├── app.py # Main con st.tabs()
├── modules/
│ ├── nlp.py # Clasificación de quejas (Pestaña 1)
│ ├── ocr.py # OCR de actas (Pestaña 1)
│ ├── data.py # Datos de secciones (Pestaña 1)
│ └── social_media.py # TODO: Lógica de redes sociales (Pestaña 2)
├── pages/ # Alternativa a tabs (opcional)
│ └── social_media_dashboard.py
└── requirements.txt

text

## DISEÑO DE LA INTERFAZ (Pestaña 2)
- **Layout**: 2 columnas
  - Columna izquierda (70%): Visualizaciones
  - Columna derecha (30%): Controles y filtros
- **Color scheme**: Azul/verde para datos positivos, rojo para negativos
- **Mobile-first**: Adaptable a teléfonos
- **Actualización**: Mostrar spinner mientras se generan datos

## FLUJO DE USUARIO
1. Usuario abre Pestaña 2
2. Ve dashboard con datos pre-cargados (500 posts)
3. Aplica filtros (red social, tema, fechas)
4. Presiona "Actualizar Datos" → se generan 500 nuevos posts
5. Todas las visualizaciones se actualizan automáticamente
6. Puede exportar datos a CSV
