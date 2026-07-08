import random
import pandas as pd
from datetime import datetime

CONFIG = {
    'UMBRAL_INDECISION': 40.0,    # %
    'UMBRAL_COBERTURA': 30.0,     # %
    'UMBRAL_ANOMALIA': 5.0,       # %
    'CENTRO_MAPA': [19.2889, -99.1689],
    'ZOOM_MAPA': 12,
    'COLORES': {
        'a_favor': '#00cc44',
        'en_contra': '#ff3333',
        'indeciso': '#ffcc00'
    }
}

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

def generar_datos_iniciales() -> pd.DataFrame:
    """
    Genera el DataFrame inicial con los datos de las 10 secciones de Tlalpan.
    """
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
    # Asegurar tipos correctos
    secciones['id'] = secciones['id'].astype(int)
    secciones['cobertura'] = secciones['cobertura'].astype(float)
    return secciones

def simular_visita(secciones_df: pd.DataFrame):
    """
    Simula una visita electoral.
    Selecciona una sección ponderada inversamente por su cobertura (prioriza secciones con baja cobertura).
    Genera un voto aleatorio con un sesgo que favorece 'a_favor' a mayor cobertura.
    Elige una queja aleatoria del catálogo QUEJAS_EJEMPLO.
    
    Retorna:
        seccion_id (int): ID de la sección visitada.
        nuevo_voto (str): El voto simulado ('a_favor', 'en_contra', 'indeciso').
        queja (str): El texto de la queja seleccionada.
    """
    # Ponderación inversa de cobertura: a menor cobertura, mayor probabilidad de visita.
    # Usamos (100.1 - cobertura) para evitar valores de peso cero o negativos si cobertura es 100.
    pesos_seleccion = 100.1 - secciones_df['cobertura']
    seccion_fila = secciones_df.sample(n=1, weights=pesos_seleccion).iloc[0]
    
    seccion_id = int(seccion_fila['id'])
    cobertura = float(seccion_fila['cobertura'])
    
    # Sesgo del voto: a mayor cobertura, mayor probabilidad de estar a favor.
    prob_favor = (cobertura / 100.0) * 0.7 + 0.1       # Rango: 0.1 a 0.8
    prob_contra = (1.0 - (cobertura / 100.0)) * 0.7 + 0.1 # Rango: 0.1 a 0.8
    prob_indeciso = 0.2
    
    suma_probs = prob_favor + prob_contra + prob_indeciso
    p_favor = prob_favor / suma_probs
    p_contra = prob_contra / suma_probs
    p_indeciso = prob_indeciso / suma_probs
    
    nuevo_voto = random.choices(
        ['a_favor', 'en_contra', 'indeciso'], 
        weights=[p_favor, p_contra, p_indeciso], 
        k=1
    )[0]
    
    queja = random.choice(QUEJAS_EJEMPLO)
    
    return seccion_id, nuevo_voto, queja
