import streamlit as st
from transformers import pipeline

CATEGORIAS = ['AGUA', 'SEGURIDAD', 'BACHEO', 'ALUMBRADO', 'CONSTRUCCION_ILEGAL']

@st.cache_resource
def cargar_modelo():
    """
    Carga el modelo zero-shot de Hugging Face.
    Retorna None si ocurre algún error durante la carga (por ejemplo, falta de conexión a internet o memoria).
    """
    try:
        return pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
            device=-1  # CPU
        )
    except Exception as e:
        # Fallback silencioso en consola para evitar romper la UI del demo
        print(f"Advertencia: No se pudo cargar el modelo zero-shot de NLP ({e}). Se usará clasificación por reglas.")
        return None

def clasificar_queja(texto: str):
    """
    Clasifica una queja y determina el sentimiento.
    Usa zero-shot classification si el modelo está disponible; si no,
    recurre a un clasificador basado en palabras clave (reglas) para garantizar la disponibilidad.
    
    Retorna:
        categoria (str): Categoría predicha de la queja.
        sentimiento (str): Sentimiento detectado ('positivo', 'negativo', 'neutral').
    """
    categoria_predicha = None
    modelo = cargar_modelo()
    
    # 1. Clasificación Zero-Shot (si el modelo está cargado)
    if modelo is not None:
        try:
            resultado = modelo(texto, CATEGORIAS)
            categoria_predicha = resultado['labels'][0]
        except Exception as e:
            print(f"Error durante la inferencia NLP: {e}")
            
    # 2. Clasificación por Reglas (Fallback si falla el modelo de ML)
    if categoria_predicha is None:
        texto_lower = texto.lower()
        if any(p in texto_lower for p in ['agua', 'pipa', 'tinaco', 'lluvia', 'drenaje', 'lodo', 'cobran']):
            categoria_predicha = 'AGUA'
        elif any(p in texto_lower for p in ['bache', 'hoyo', 'calle', 'pavimento', 'accidente', 'carril']):
            categoria_predicha = 'BACHEO'
        elif any(p in texto_lower for p in ['luz', 'alumbrado', 'foco', 'oscuridad', 'obscuro', 'oscura', 'obscuridad']):
            categoria_predicha = 'ALUMBRADO'
        elif any(p in texto_lower for p in ['construcción', 'construccion', 'terreno', 'obra', 'edificio', 'ilegal', 'tapando']):
            categoria_predicha = 'CONSTRUCCION_ILEGAL'
        else:
            # Por defecto o si contiene palabras clave de seguridad
            categoria_predicha = 'SEGURIDAD'

    # 3. Sentimiento simple basado en palabras clave
    palabras_negativas = ['no', 'nunca', 'problema', 'falla', 'robo', 'extorsión', 'extorsion', 'peligro', 'accidente', 'ilegal', 'motos', 'amenaza', 'peor', 'malo']
    palabras_positivas = ['gracias', 'bien', 'mejor', 'funciona', 'ayuda', 'apoyo', 'excelente', 'rápido', 'rapido']
    
    texto_lower = texto.lower()
    if any(palabra in texto_lower for palabra in palabras_negativas):
        sentimiento = 'negativo'
    elif any(palabra in texto_lower for palabra in palabras_positivas):
        sentimiento = 'positivo'
    else:
        sentimiento = 'neutral'
        
    return categoria_predicha, sentimiento
