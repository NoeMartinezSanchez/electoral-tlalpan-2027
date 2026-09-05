import streamlit as st

# Credenciales de respaldo para el modo demo (se usan solo si no existe .streamlit/secrets.toml)
CREDENCIALES_DEMO = {
    'usuario': 'admin',
    'contrasena': 'tlalpan2027'
}

def obtener_credenciales():
    """
    Obtiene las credenciales de acceso desde .streamlit/secrets.toml.
    Si el archivo de secrets no existe o no tiene la sección [AUTH],
    regresa credenciales demo por defecto e imprime un aviso por consola.

    Retorna:
        dict: Diccionario con 'usuario' y 'contrasena'.
    """
    try:
        return {
            'usuario': st.secrets['AUTH']['USUARIO'],
            'contrasena': st.secrets['AUTH']['CONTRASENA']
        }
    except Exception as e:
        print(
            f"AUTH: No se encontró la configuración de secrets ({e}). "
            f"Usando credenciales demo: {CREDENCIALES_DEMO['usuario']} / {CREDENCIALES_DEMO['contrasena']}"
        )
        return CREDENCIALES_DEMO

def validar_credenciales(usuario: str, contrasena: str) -> bool:
    """
    Valida las credenciales ingresadas contra la configuración activa.

    Retorna:
        True si el usuario y la contraseña coinciden, False en caso contrario.
    """
    credenciales = obtener_credenciales()
    return (usuario == credenciales['usuario'] and
            contrasena == credenciales['contrasena'])