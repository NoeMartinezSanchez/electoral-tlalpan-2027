import pytesseract
from PIL import Image
import re
import os

# Configuración automática del ejecutable de Tesseract en Windows
rutas_tesseract = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Users\mecat\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
]
for ruta in rutas_tesseract:
    if os.path.exists(ruta):
        pytesseract.pytesseract.tesseract_cmd = ruta
        break

def procesar_acta(imagen_path: str, id_seccion: int):
    """
    Procesa la imagen de un acta con OCR para extraer los votos.
    Si Tesseract no está instalado o configurado correctamente en el sistema,
    utiliza un simulador determinista basado en el ID de la sección para no interrumpir el flujo.
    
    Retorna:
        dict: Contiene 'votos_partido1', 'votos_partido2', 'votos_nulos', 'total', 'anomalia', 'simulado', 'texto_extraido'.
    """
    try:
        # Abrir la imagen
        img = Image.open(imagen_path)
        
        texto_ocr = ""
        tesseract_disponible = True
        
        try:
            texto_ocr = pytesseract.image_to_string(img, lang='spa')
        except Exception as e:
            print(f"OCR: Tesseract no disponible o falló ({e}). Usando simulación.")
            tesseract_disponible = False
            
        # Si Tesseract falló o no extrajo texto, aplicamos fallback determinista
        if not tesseract_disponible or not texto_ocr.strip():
            # Generamos valores deterministas basados en el id_seccion
            votos_p1 = int((id_seccion % 10) * 15 + 100)
            votos_p2 = int((id_seccion % 7) * 20 + 80)
            votos_nulos = int((id_seccion % 5) * 3 + 4)
            total = votos_p1 + votos_p2 + votos_nulos
            
            # Anomalía si el id_seccion es par (para demostrar alertas en la demo)
            anomalia = (id_seccion % 2 == 0)
            
            return {
                'votos_partido1': votos_p1,
                'votos_partido2': votos_p2,
                'votos_nulos': votos_nulos,
                'total': total,
                'anomalia': anomalia,
                'simulado': True,
                'texto_extraido': "[Simulación: Tesseract OCR no está configurado localmente]"
            }
            
        # Si Tesseract funcionó, extraer todos los números
        numeros = [int(n) for n in re.findall(r'\d+', texto_ocr)]
        if len(numeros) >= 3:
            votos_p1 = numeros[0]
            votos_p2 = numeros[1]
            votos_nulos = numeros[2]
            total = votos_p1 + votos_p2 + votos_nulos
            
            # Detectar anomalías (ej: si los nulos superan el 8% del total, o si el total es sospechosamente bajo/alto)
            anomalia = False
            if votos_nulos > (total * 0.08):
                anomalia = True
                
            return {
                'votos_partido1': votos_p1,
                'votos_partido2': votos_p2,
                'votos_nulos': votos_nulos,
                'total': total,
                'anomalia': anomalia,
                'simulado': False,
                'texto_extraido': texto_ocr[:300]
            }
        else:
            # Fallback determinista si no se encontraron suficientes números
            votos_p1 = int((id_seccion % 10) * 15 + 100)
            votos_p2 = int((id_seccion % 7) * 20 + 80)
            votos_nulos = int((id_seccion % 5) * 3 + 4)
            total = votos_p1 + votos_p2 + votos_nulos
            
            return {
                'votos_partido1': votos_p1,
                'votos_partido2': votos_p2,
                'votos_nulos': votos_nulos,
                'total': total,
                'anomalia': True, # Anomalía por error de lectura
                'simulado': True,
                'texto_extraido': f"[Texto OCR incompleto: '{texto_ocr[:100]}']"
            }
            
    except Exception as e:
        return {'error': f"Error al procesar el acta: {str(e)}"}
