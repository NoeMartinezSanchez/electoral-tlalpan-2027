# ESTRUCTURA DE DATOS (Sintéticos)

## 1. SECCIONES (10 iniciales)
```python
secciones = pd.DataFrame({
    'id': [3450, 3451, 3452, 3453, 3454, 3455, 3456, 3457, 3458, 3459],
    'nombre': ['Villa Coapa', 'Jardines Montaña', 'San Miguel Topilejo', 
               'San Andrés Totoltepec', 'Coapa Centro', 'Mesa Los Hornos',
               'Fuentes Tlalpan', 'Topilejo Centro', 'Coapa Residencial', 'Parres'],
    'lat': [19.2889, 19.2750, 19.2100, 19.2200, 19.2800, 19.2550, 19.2680, 19.2150, 19.2900, 19.2400],
    'lon': [-99.1689, -99.1750, -99.1900, -99.1850, -99.1600, -99.1780, -99.1720, -99.1950, -99.1620, -99.1800],
    'intencion': ['a_favor', 'indeciso', 'en_contra', 'indeciso', 'a_favor', 
                  'en_contra', 'indeciso', 'en_contra', 'a_favor', 'indeciso'],
    'cobertura': [65.4, 30.2, 45.8, 22.1, 70.3, 55.0, 40.5, 60.7, 80.1, 25.6],
    'tipo_zona': ['urbana', 'urbana', 'rural', 'rural', 'urbana', 'rural', 'urbana', 'rural', 'urbana', 'rural']
})
2. VISITAS (generadas en tiempo real)
python
visita = {
    'id_visita': int,
    'id_seccion': int,  # FK a secciones
    'fecha': datetime.now(),
    'voto': 'a_favor' | 'en_contra' | 'indeciso',
    'queja_texto': str,  # Texto libre
    'queja_categoria': str,  # AGUA | SEGURIDAD | BACHEO | ALUMBRADO | CONSTRUCCION_ILEGAL
    'queja_sentimiento': 'positivo' | 'negativo' | 'neutral'
}
3. QUEJAS PRE-CARGADAS (para demo)
python
QUEJAS_EJEMPLO = [
    "No hay agua desde el martes, las pipas no llegan",
    "Hay un bache enorme en la esquina de mi casa",
    "Me extorsionaron por teléfono, ya no puedo dormir",
    "La luz se va cada noche, es peligroso",
    "Están construyendo ilegalmente en el terreno baldío",
    "El alumbrado público no funciona en toda la calle",
    "Los pipas cobran 500 pesos por llenar el tinaco",
    "Hay mucho ruido de motos toda la noche",
    "No hay señal de teléfono en la colonia",
    "El camión de la basura no pasa desde hace 3 días",
    "Vecinos reportan robos a casa habitación",
    "El agua sale con lodo y basura",
    "No hay transporte público después de las 10pm",
    "Los perros callejeros son un problema",
    "La construcción ilegal está tapando el drenaje",
    "El bache causó un accidente ayer",
    "Las pipas del gobierno nunca llegaron",
    "Hay personas sospechosas merodeando",
    "El parque está lleno de basura",
    "Falta señal de internet en la zona"
]
4. ACTAS (para OCR)
python
acta = {
    'id_seccion': int,
    'votos_partido1': int,  # Nuestro partido
    'votos_partido2': int,  # Rival
    'votos_nulos': int,
    'total': int,
    'anomalia': bool,
    'foto_path': str
}
5. CONFIGURACIÓN
python
CONFIG = {
    'UMBRAL_INDECISION': 40,    # %
    'UMBRAL_COBERTURA': 30,     # %
    'UMBRAL_ANOMALIA': 5,       # %
    'CENTRO_MAPA': [19.2889, -99.1689],
    'ZOOM_MAPA': 12,
    'COLORES': {
        'a_favor': '#00cc44',
        'en_contra': '#ff3333',
        'indeciso': '#ffcc00'
    }
}
6. GENERACIÓN DE DATOS SINTÉTICOS
python
# data.py
import random
from datetime import datetime

def generar_secciones(n=10):
    # ... implementación
    
def simular_visita(secciones_df):
    # Seleccionar sección aleatoria (ponderada por cobertura)
    # Generar voto aleatorio (con sesgo a favor de cobertura)
    # Seleccionar queja aleatoria de QUEJAS_EJEMPLO
    # Clasificar con NLP
    # Actualizar datos
    return secciones_df_actualizado, visita_data

# ESTRUCTURA DE DATOS - PESTAÑA 2: REDES SOCIALES

## 1. POSTS DE REDES SOCIALES (Sintéticos)

> **ACTUALIZACIÓN**: la Pestaña 2 es **real-only**. Los posts llegan de Scrapeless
> (TikTok vía Scraping API; Instagram vía Scraping Browser + API interna
> `web_profile_info`; X vía actor AI `scraper.grok`) y se normalizan a las mismas
> columnas de este esquema con `normalizar_posts()` en `modules/scrapeless.py`.
> En posts de Instagram `vistas`/`guardados` se fijan en 0 (no disponibles en
> sesión anónima); en posts de X `likes`/`comentarios` se fijan en 0 (no
> expuestos por la API de Grok) y `vistas` vienen de `view_count`. El
> `engagement_rate` se calcula sobre 1,000 impresiones simuladas.

### DataFrame: `posts_sociales`
| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| id_post | int | Identificador único | 1001 |
| red_social | str | TikTok, Facebook, X, Instagram | 'TikTok' |
| usuario | str | Nombre de usuario | '@votante2027' |
| fecha | datetime | Fecha y hora del post | '2026-07-07 14:30:00' |
| texto | str | Contenido del post | 'El agua en Tlalpan es un problema grave' |
| hashtags | list | Lista de hashtags | ['#Tlalpan', '#Agua'] |
| likes | int | Número de likes | 150 |
| comentarios | int | Número de comentarios | 45 |
| compartidos | int | Número de shares/retweets | 30 |
| sentimiento | str | 'positivo', 'negativo', 'neutral' | 'negativo' |
| tema_electoral | str | Categoría política | 'Agua' |
| engagement | int | likes + comentarios + compartidos | 225 |
| engagement_rate | float | engagement / seguidores (simulado) | 2.5 |

## 2. TEMAS ELECTORALES PRE-DEFINIDOS
```python
TEMAS_ELECTORALES = {
    'Agua': ['agua', 'pipas', 'desabasto', 'huachicoleo', 'tinaco', 'pozo'],
    'Seguridad': ['seguridad', 'robo', 'extorsión', 'policía', 'cámaras', 'patrullas'],
    'Transporte': ['transporte', 'metrobús', 'bache', 'movilidad', 'tráfico', 'camión'],
    'Vivienda': ['vivienda', 'construcción', 'terreno', 'infonavit', 'renta'],
    'Empleo': ['empleo', 'trabajo', 'desempleo', 'chamba', 'salario'],
    'Educación': ['escuela', 'maestro', 'estudiante', 'colegio', 'universidad'],
    'Salud': ['salud', 'hospital', 'médico', 'clínica', 'enfermedad'],
    'Medio Ambiente': ['basura', 'árbol', 'parque', 'reciclaje', 'contaminación'],
    'Corrupción': ['corrupción', 'robo', 'gobierno', 'fraude', 'transparencia'],
    'Participación': ['voto', 'elección', 'ciudadano', 'participación', 'comunidad']
}
3. USUARIOS SIMULADOS
python
USUARIOS = [
    '@tlalpaneja_2027', '@votante_tlalpan', '@coapa_life', '@topilejo_activo',
    '@ciudadano_tlalpan', '@jovenes_coapa', '@mujeres_tlalpan', '@comunidad_topilejo',
    '@negocios_tlalpan', '@estudiantes_tlalpan', '@agua_tlalpan', '@seguridad_tlalpan'
]
4. GENERACIÓN DE DATOS SINTÉTICOS
python
# social_media.py
import random
from datetime import datetime, timedelta
import pandas as pd
from faker import Faker

def generar_posts(n=500) -> pd.DataFrame:
    """Genera n posts simulados de redes sociales"""
    posts = []
    fake = Faker('es_MX')
    
    for i in range(n):
        # Seleccionar red social (ponderada por popularidad)
        red = random.choices(
            ['TikTok', 'Facebook', 'X', 'Instagram'],
            weights=[0.25, 0.30, 0.20, 0.25]
        )[0]
        
        # Generar fecha en últimos 30 días
        fecha = datetime.now() - timedelta(days=random.randint(0, 30))
        
        # Seleccionar tema y generar texto
        tema = random.choice(list(TEMAS_ELECTORALES.keys()))
        texto = generar_texto_por_tema(tema)
        
        # Hashtags (2-5 aleatorios)
        hashtags = random.sample(
            ['#Tlalpan', '#Elecciones2027', '#Voto', '#CDMX', '#Participación'] + 
            [f'#{tema.replace(" ", "")}'] + 
            random.choices(['#Coapa', '#Topilejo', '#Justicia', '#Cambio'], k=3),
            k=random.randint(2, 5)
        )
        
        posts.append({
            'id_post': i + 1,
            'red_social': red,
            'usuario': random.choice(USUARIOS),
            'fecha': fecha,
            'texto': texto,
            'hashtags': hashtags,
            'likes': random.randint(0, 500),
            'comentarios': random.randint(0, 100),
            'compartidos': random.randint(0, 50),
            'sentimiento': clasificar_sentimiento(texto),  # Usar NLP
            'tema_electoral': tema
        })
    
    df = pd.DataFrame(posts)
    df['engagement'] = df['likes'] + df['comentarios'] + df['compartidos']
    df['engagement_rate'] = df['engagement'] / random.randint(100, 1000)
    return df

def generar_texto_por_tema(tema: str) -> str:
    """Genera texto relevante para cada tema electoral"""
    templates = {
        'Agua': [
            'El agua en Tlalpan es un problema grave, las pipas no llegan',
            'Necesitamos soluciones reales para el desabasto de agua',
            'El huachicoleo de agua está afectando a toda la comunidad',
            'Exigimos que el gobierno regule las pipas ilegales'
        ],
        # ... (más templates para cada tema)
    }
    return random.choice(templates.get(tema, ['Voto por el cambio en Tlalpan']))
5. MÉTRICAS PARA DASHBOARD
python
def calcular_metricas(df: pd.DataFrame) -> dict:
    """Calcula KPIs principales"""
    return {
        'total_posts': len(df),
        'total_likes': df['likes'].sum(),
        'total_comentarios': df['comentarios'].sum(),
        'total_compartidos': df['compartidos'].sum(),
        'engagement_total': (df['likes'] + df['comentarios'] + df['compartidos']).sum(),
        'engagement_promedio': df['engagement'].mean(),
        'top_temas': df['tema_electoral'].value_counts().head(10),
        'sentimiento_distribucion': df['sentimiento'].value_counts(),
        'redes_distribucion': df['red_social'].value_counts()
    }
text

---