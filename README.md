# 🗳️ Tlalpan Electoral 2027 — Sistema de Inteligencia Electoral

Demo técnico mobile-first construido con **Streamlit** que simula un sistema de
inteligencia electoral para el proceso electoral intermedio 2027 en Tlalpan.
Toda la data es **sintética**: no consume APIs externas, no requiere
autenticación y funciona 100% local.

## 🧱 Pestañas

### 1. 🗳️ Inteligencia Electoral
- Mapa interactivo (Folium) con 10 secciones electorales de Tlalpan, coloreadas
  según la intención de voto (💚 a favor, ❤️ en contra, 💛 indeciso).
- Simulación de **visitas de campo** que actualizan cobertura, intención de voto
  y bitácora de quejas en tiempo real.
- Clasificación NLP de quejas vecinales (zero-shot con
  `facebook/bart-large-mnli`) con fallback basado en reglas de palabras clave.
- Centro de alertas automático (baja cobertura, zonas críticas).
- OCR de actas de escrutinio con **pytesseract** (Tesseract) y simulador
  determinista cuando Tesseract no está instalado.

### 2. 📊 Redes Sociales
- Dashboard de analítica sobre posts simulados (TikTok, Facebook, X, Instagram).
- KPIs de engagement, series temporales, nube de palabras por sentimiento,
  top temas, distribución por red y sentimiento en el tiempo.
- Filtros por red social, tema electoral y rango de fechas.
- Botón de actualización que simula *scraping* (genera 500–800 posts nuevos) y
  **exportación a CSV**.

## 🛠️ Stack técnico

| Tecnología | Uso |
|---|---|
| Python 3.9+ | Lenguaje base |
| Streamlit | Frontend web responsivo (mobile-first) |
| Pandas / NumPy | Generación y manejo de datos sintéticos |
| Folium + streamlit-folium | Mapas interactivos |
| Hugging Face `transformers` | Clasificación zero-shot de quejas |
| pytesseract / Tesseract | OCR de actas |
| Plotly / matplotlib / wordcloud | Visualizaciones |
| Faker | Datos sintéticos en español (`es_MX`) |

## 🚀 Instalación y ejecución

```bash
# 1. Crear y activar el entorno virtual
python -m venv venv_electoral
venv_electoral\Scripts\activate            # Windows
# source venv_electoral/bin/activate       # Linux / macOS

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar la app
streamlit run app.py
```

### 📱 Demo en teléfono
Para abrir la app desde un celular en la misma red WiFi:

```bash
streamlit run app.py --server.enableCORS true --server.enableXsrfProtection false
```

Luego abre `http://192.168.x.x:8501` (la IP local que muestra la terminal) en el
navegador del teléfono.

> **Nota**: la primera ejecución descarga el modelo NLP de Hugging Face
> (`facebook/bart-large-mnli`, ~1.6 GB). Si no hay conexión o memoria, el
> sistema cae a un clasificador por reglas sin interrumpir el demo.

### ☁️ Versión desplegada
Disponible en: <https://electoral-tlalpan-2027.streamlit.app/>

## 📁 Estructura del repositorio

```
electoral/
├── app.py                          # Punto de entrada (st.tabs)
├── utils.py                        # CSS mobile-first y centro de alertas
├── modules/
│   ├── data.py                     # Secciones, CONFIG, simulación de visitas
│   ├── nlp.py                      # Clasificación de quejas (zero-shot + reglas)
│   ├── ocr.py                      # Procesamiento de actas (OCR + fallback)
│   ├── social_media.py             # Dashboard de redes sociales (Pestaña 2)
│   └── social_media_generator.py   # Generador de posts sintéticos
├── project-docs/                   # Especificación, contratos de datos y reglas
├── requirements.txt
└── .gitignore
```

## 📚 Documentación

- `project-docs/PROJECT_CONTEXT.md` — contexto y arquitectura del demo
- `project-docs/DATA_STRUCTURE.md` — contratos de datos (secciones, posts, actas)
- `project-docs/CODING_RULES.md` — reglas de codificación para el agente

## ⚖️ Aviso

Proyecto **demostrativo** para fines de prototipo y capacitación. Los datos,
resultados y visualizaciones son simulados y no representan información real de
nómina, preferencias electorales ni resultados oficiales.