# 🗳️ Tlalpan Electoral 2027 — Sistema de Inteligencia Electoral

Demo técnico mobile-first construido con **Streamlit** que simula un sistema de
inteligencia electoral para el proceso electoral intermedio 2027 en Tlalpan.
Incluye **login simple** y, en la Pestaña 2, **extracción de datos reales** de
**TikTok** vía la **Scraping API de Scrapeless** (perfil por @usuario), con
analítica y exportación de resultados sin generación sintética.

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
- Dashboard de analítica sobre posts (TikTok, Facebook, X, Instagram).
- KPIs de engagement, series temporales, nube de palabras por sentimiento,
  top temas, distribución por red y sentimiento en el tiempo.
- Filtros por red social, tema electoral y rango de fechas.
- **Solo datos reales**: el dashboard se alimenta de la extracción de un
  **perfil de TikTok** vía Scrapeless (sin generación sintética). Exportación
  a **CSV** y estructura de resultado en **JSON/CSV**.

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

## 🔐 Autenticación

La app tiene un login simple (usuario + contraseña) que protege el acceso a las
dos pestañas. Las credenciales se leen de `.streamlit/secrets.toml`:

```toml
[AUTH]
USUARIO = "administrador"
CONTRASENA = "1234567890"
```

**Cambiar credenciales en local**: edita `.streamlit/secrets.toml`
(este archivo está en `.gitignore`, no se sube a GitHub).

**Cambiar credenciales en la nube** (Streamlit Cloud): entra a tu app →
`Settings` → `Secrets` y pega el mismo bloque `[AUTH]` para proteger la URL
pública.

**Modo demo**: si no existe `.streamlit/secrets.toml`, la app usa por defecto
`admin` / `tlalpan2027` (sin archivo de secrets) e imprime un aviso por consola.

## 🚀 Extracción real de datos (Scrapeless)

En la **Pestaña 2** puedes alternar entre **Modo demo (sintético)** y
**🔴 Real (Scrapeless)**: el flujo real soportado descarga las publicaciones
recientes de un **perfil de TikTok (@usuario)** —título, texto, hashtags y
engagement (likes, comentarios, compartidos)— e integra los resultados a la
analítica existente (KPIs, series, wordcloud, sentimiento, CSV).

> ⚠️ **Limitaciones del proveedor**: Scrapeless deprecó el actor de búsqueda
> por palabra clave/hashtag de TikTok (`scraper.tiktok.search`) y **no publica
> actor para Instagram**, por lo que ambos ámbitos quedan deshabilitados en la
> app (se muestran con un aviso). Cuando el proveedor publique esos actores,
> se reactivan desde el dict `ACTORES`.

### Dónde pegar tu API Key de Scrapeless

Puedes configurarla en dos lugares (tiene prioridad el archivo):

1. **`.streamlit/secrets.toml`** (recomendado, no se sube a GitHub):

```toml
[SCRAPELESS]
API_KEY = "tu_api_key_real"
```

2. En la app: Pestaña 2 → `🔴 Real (Scrapeless)` → campo `🔑 API Key de
   Scrapeless` (se persiste solo durante la sesión).

### Configuración

El panel permite elegir el **@usuario de TikTok** a monitorear y el **número de
publicaciones** (5–200) a descargar. También muestra la **estimación de
peticiones y costo USD** contra tu **saldo** (consultado con `GET /api/v1/me`).

### Resultados y estructura

Cada extracción exitosa se guarda en `datos_extraidos/` (gitignored):

- `posts_<usuario>_<fecha>.csv` — tabla normalizada que alimenta el dashboard.
- `raw_<usuario>_<fecha>.json` — items crudos devueltos por Scrapeless, para
  decidir qué analítica extraer de la estructura real.

En la app, el expander "🔎 Ver estructura del resultado" muestra un adelanto y
botones **📥 Descargar CSV / JSON** de la última extracción.

La tabla normalizada incluye las columnas `vistas` (reproducciones) y
`guardados` (marcados), además del engagement (`likes + comentarios +
compartidos`) para análisis de alcance y rendimiento.

### Costo y activación

- Scrapeless cobra **solo por peticiones exitosas** (HTTP 200 con JSON válido);
  las cacheadas o fallidas no cuestan.
- Las cuentas nuevas incluyen **~$5 de crédito gratis** (sin tarjeta).
- Sin API Key/saldo o si la llamada falla, la app avisa con el error real de
  Scrapeless (no genera datos falsos). La API Key se lee solo de los Secrets.

### Actores de la API

Centralizados en `modules/scrapeless.py` (dict `ACTORES`). El flujo de perfil
usa dos actores confirmados:

| Paso | Actor | Input |
|---|---|---|
| Resolver perfil | `scraper.tiktok.user.detail` | `unique_id` (sin @) |
| Publicaciones | `scraper.tiktok.user.work` | `sec_uid`, `cursor`, `count` |

## 📁 Estructura del repositorio

```
electoral/
├── app.py                          # Punto de entrada (st.tabs)
├── utils.py                        # CSS mobile-first y centro de alertas
├── modules/
│   ├── auth.py                      # Autenticación (credenciales y validación)
│   ├── data.py                     # Secciones, CONFIG, simulación de visitas
│   ├── nlp.py                      # Clasificación de quejas (zero-shot + reglas)
│   ├── ocr.py                      # Procesamiento de actas (OCR + fallback)
│   ├── scrapeless.py               # Cliente de la Scraping API (saldo, búsqueda, normalización)
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
resultados y visualizaciones son simulados **o extraídos de fuentes públicas vía
Scrapeless** y no representan información real de nómina, preferencias
electorales ni resultados oficiales.