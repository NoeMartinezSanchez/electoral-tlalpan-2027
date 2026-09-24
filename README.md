# 🗳️ Tlalpan Electoral 2027 — Sistema de Inteligencia Electoral

Demo técnico mobile-first construido con **Streamlit** que simula un sistema de
inteligencia electoral para el proceso electoral intermedio 2027 en Tlalpan.
Incluye **login simple** y, en la Pestaña 2, **datos reales de redes sociales**:
**TikTok** vía la **Scraping API de Scrapeless** (perfil por @usuario) y
**X/Twitter** vía el actor AI **`scraper.grok`**, además de **carga manual de
CSVs de Facebook/Instagram** (extensión Instant Data Scraper), con analítica y
exportación de resultados sin generación sintética.

## 🧱 Pestañas

### 1. 🗳️ Inteligencia Electoral
- Mapa interactivo (Folium) con las secciones electorales de Tlalpan, coloreadas
  según la intención de voto (💚 a favor, ❤️ en contra, 💛 indeciso).
- Simulación de **visitas de campo** que actualizan cobertura, intención de voto
  y bitácora de quejas en tiempo real.
- Clasificación NLP de quejas vecinales (zero-shot con
  `facebook/bart-large-mnli`) con fallback basado en reglas de palabras clave.
- Centro de alertas automático (baja cobertura, zonas críticas).
- OCR de actas de escrutinio con **pytesseract** (Tesseract) y simulador
  determinista cuando Tesseract no está instalado.
- **Migración a datos reales (Etapa 0)**: la geografía de secciones se carga del
  **Marco Geográfico Electoral del IECM 2021** (`circunscripcionesDT/12.kml`) —
  **355 secciones de Tlalpan** con padrón/lista nominal 2021 y población INEGI
  2010 — y se importa a **MongoDB Atlas** (`modules/geo.py` +
  `modules/datos_campo.py`). Mientras no haya conexión/importación, la app usa el
  set demo y lo indica en la cabecera.
- **Registro real de campo (Etapa 1)**: formulario de brigadista (simpatía /
  visita / queja) que guarda en Mongo e identifica al usuario del login. La
  **cobertura real** se calcula como `registros / Lista_Nominal × 100` y la
  intención por sección como la **moda de simpatías**. Alertas del documento:
  indecisión >40%, cobertura <30% y concentración de quejas de agua (≥3). El
  modo **Demo** (simular visita) queda como opción conmutable.

### 2. 📊 Redes Sociales
- Dashboard de analítica sobre posts (TikTok, X, Facebook, Instagram).
- KPIs de engagement, series temporales, nube de palabras por sentimiento,
  top temas, distribución por red y sentimiento en el tiempo.
- Filtros por red social, tema electoral y rango de fechas.
- **Solo datos reales**, en dos modos:
  - **🔌 Scrapeless (TikTok + X)**: extracción de un **perfil de TikTok**
    (`scraper.tiktok.user.detail` + `user.work`) y de **X/Twitter** (actor AI
    `scraper.grok`, que cita posts recientes —muestreo, no feed completo—). Se
    pueden elegir **una o varias redes por corrida** (multiselect).
  - **📁 CSV manual (Facebook/Instagram)**: los posts de Meta se cargan con los
    CSVs exportados por la extensión **Instant Data Scraper** y se anexan al
    dashboard (Facebook no trae fecha → "Sin fecha"; Instagram convierte la
    fecha relativa a absoluta).
- Exportación a **CSV** y estructura de resultado en **JSON/CSV**.

## 🛠️ Stack técnico

| Tecnología | Uso |
|---|---|
| Python 3.9+ | Lenguaje base |
| Streamlit | Frontend web responsivo (mobile-first) |
| Pandas / NumPy | Manejo y análisis de datos |
| Folium + streamlit-folium | Mapas interactivos |
| Hugging Face `transformers` | Clasificación zero-shot de quejas |
| pytesseract / Tesseract | OCR de actas |
| Plotly / matplotlib / wordcloud | Visualizaciones |
| Playwright | Cliente CDP del Scraping Browser (Instagram/Facebook) |
| MongoDB Atlas (`pymongo`) | Persistencia de datos de campo de la Pestaña 1 |
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

## 🚀 Datos reales de redes sociales (Pestaña 2)

En la **Pestaña 2** se integran, sin generación sintética, posts de 4 redes:

| Red | Método | Estado |
|---|---|---|
| **TikTok** | Scraping API de Scrapeless: perfil por @usuario (`scraper.tiktok.user.detail` → `scraper.tiktok.user.work`) | ✅ Operativo (en la UI) |
| **X / Twitter** | Actor AI `scraper.grok` (`POST /api/v2/scraper/execute`): responde al prompt "What has @usuario posted on X recently?" y **cita** posts (`x_search_results` = muestreo, no feed completo; likes/comentarios no expuestos → 0; vistas sí) | ✅ Operativo (en la UI) |
| **Instagram** | Scraping Browser (WebSocket CDP) + API interna `web_profile_info`, sin login | ⚠️ Implementado pero **bloqueado por Meta** desde egress de datacenter (`401 require_login`); no en la UI |
| **Facebook** | Scraping Browser + JSON de hidratación de Relay (`__typename` `User`/`Story`) | ⚠️ Implementado pero **bloqueado por Meta** (HTML sin nodos `Story`); no en la UI |

### Unión de los 4 datasets

- Un **solo DataFrame** `posts_sociales` con el esquema estándar
  (`COLUMNAS_POSTS`); cada red aporta las columnas que tiene y las que no quedan
  en **0** (Facebook/Instagram manuales: `vistas`/`guardados` = 0; X: likes/
  comentarios = 0).
- **Facebook no trae fecha** → `NaT` → se muestra **"Sin fecha"** y queda **fuera
  de las series temporales** (el filtro de rango de fechas solo restringe filas
  con fecha; las sin fecha siempre se muestran).
- **Instagram** trae fecha relativa ("7 h", "20 h") que se convierte a **absoluta**
  al procesar.
- El engagement/`engagement_rate` usa la misma fórmula para todas las redes
  (`engagement = likes + comentarios + compartidos`; base 1,000 simulada).

### 📁 Carga manual de Facebook/Instagram (Instant Data Scraper)

Dado el bloqueo de Meta, los posts de Facebook e Instagram se integran de forma
**manual** desde el modo **"📁 CSV manual (Facebook/Instagram)"** del panel:

1. Exporta los posts con la extensión **Instant Data Scraper** (Chrome).
2. Sube los CSVs en la app (uno por red).
3. `modules/manual_csv.py` detecta el formato por **contenido** (no por columnas
   CSS), limpia métricas ("2,1 mil" → 2100), convierte fechas relativas y
   normaliza al esquema del dashboard.
4. Los posts **se anexan** a los datos de TikTok/X ya cargados.

El botón "🧹 Limpiar datos" restablece el dashboard.

> ⚠️ **Limitación de la extracción automática de Meta (2026)**: desde egress de
> datacenter, Meta bloquea el render/sesión anónima (Instagram responde
> `401 require_login`; Facebook sirve HTML sin nodos `Story` en el JSON de
> hidratación). No es un bug del código: el flujo queda con degradación elegante
> (errores claros, sin crash). La extracción automática de Meta requeriría un
> plan con **proxy residencial** o migrar la extracción a Apify.

### Dónde pegar tu API Key de Scrapeless

Se lee **solo desde los Secrets** (no hay campo en la UI):

```toml
[SCRAPELESS]
API_KEY = "tu_api_key_real"
```

### Configuración

- **🔌 Scrapeless**: multiselect para elegir **TikTok, X o ambas**, con el
  @usuario y el número de publicaciones por red. Muestra la **estimación de
  peticiones y costo USD** contra tu **saldo** (`GET /api/v1/me`).
- **📁 CSV manual**: dos uploaders (Facebook e Instagram) + botón "📁 Procesar
  CSVs".

### Resultados y estructura

Cada extracción procesada se guarda en `datos_extraidos/` (gitignored):

- `posts_<red>_<usuario>_<fecha>.csv` — tabla normalizada que alimenta el dashboard.
- `raw_<red>_<usuario>_<fecha>.json` — items crudos de Scrapeless.

En la app, el expander "🔎 Ver estructura del resultado" muestra un adelanto y
botones **📥 Descargar CSV / JSON** de la última extracción.

La tabla normalizada incluye las columnas `vistas` (reproducciones) y
`guardados` (marcados), además del engagement (`likes + comentarios +
compartidos`) para análisis de alcance y rendimiento.

### Costo y activación

- Scrapeless cobra por peticiones de la Scraping API y sesiones del **Scraping
  Browser** (Instagram/Facebook ≈ $0.05–0.10 por página); el actor AI
  `scraper.grok` cobra por prompt (~$0.10–0.30).
- Sin API Key/saldo o si la llamada falla, la app avisa con el error real
  (no genera datos falsos). La API Key se lee solo de los Secrets.

### Actores de la API

Centralizados en `modules/scrapeless.py` (dict `ACTORES`):

| Red | Actor/Mecanismo |
|---|---|
| TikTok (perfil) | `scraper.tiktok.user.detail` → `scraper.tiktok.user.work` (Scraping API v1) |
| X / Twitter | `scraper.grok` (AI-answer, `POST /api/v2/scraper/execute`) |
| Instagram | Scraping Browser (CDP) + API interna `web_profile_info` (fuera de la UI) |
| Facebook | Scraping Browser + JSON de hidratación de Relay (fuera de la UI) |

## 🗳️ Datos de campo (Pestaña 1) — MongoDB Atlas

La **Pestaña 1** persiste los datos reales de la campaña en **MongoDB Atlas**
(módulos `modules/geo.py` y `modules/datos_campo.py`):

- Colección `secciones` — **355 secciones electorales de Tlalpan** importadas del
  **Marco Geográfico Electoral del IECM 2021** (`circunscripcionesDT/12.kml`),
  con `padron_electoral`/`lista_nominal` (corte 2021), `Población_INEGI_2010`,
  centroide y geometría simplificada.
- Colección `registros_campo` — visitas / simpatías / quejas-incidencias de
  brigadistas (etiquetadas como "simpatías" e "incidencias comunitarias", sin
  datos personales, según la nota de campaña INE).

Configura los Secrets:

```toml
[MONGO]
URI = "mongodb+srv://<db_username>:<password>@<cluster>.mongodb.net/?retryWrites=true&w=majority"
DB = "electoral_tlalpan"
```

> Para usar geografía real: pulsa **"🔄 Importar secciones INE/IECM"** en la app
> (parsea el KML del IECM y escribe en `secciones` de Mongo; también genera
> `data/secciones_ine.csv` como respaldo). Mientras no haya conexión a Mongo o
> importación, la app usa el set demo y lo avisa en la cabecera.
>
> **Pendiente**: vivienda y población Censo 2020 (INEGI) para métricas de
> vivienda; `padrón/list`a tienen **corte 2021** y `Población_INEGI_2010` es del
> censo 2010.

## 📁 Estructura del repositorio

```
electoral/
├── app.py                          # Punto de entrada (st.tabs)
├── utils.py                        # CSS mobile-first y centro de alertas
├── modules/
│   ├── auth.py                      # Autenticación (credenciales y validación)
│   ├── data.py                     # Secciones demo, CONFIG, simulación de visitas
│   ├── geo.py                      # Cartografía electoral INE (secciones reales)
│   ├── datos_campo.py              # Persistencia MongoDB Atlas (secciones, registros de campo)
│   ├── nlp.py                      # Clasificación de quejas (zero-shot + reglas)
│   ├── ocr.py                      # Procesamiento de actas (OCR + fallback)
│   ├── scrapeless.py               # Cliente Scraping API/Browser (TikTok, X, Instagram, Facebook)
│   ├── manual_csv.py               # Carga manual de CSVs Facebook/Instagram (Instant Data Scraper)
│   ├── social_media.py             # Dashboard de redes sociales (Pestaña 2)
│   └── social_media_generator.py   # Generador de posts sintéticos (legacy)
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
resultados y visualizaciones son simulados, extraídos de fuentes públicas vía
Scrapeless o cargados manualmente por el usuario, y no representan información
real de nómina, preferencias electorales ni resultados oficiales.