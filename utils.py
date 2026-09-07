import json
import os
from datetime import datetime

import streamlit as st

from modules.auth import validar_credenciales
from modules.data import CONFIG
from modules.scrapeless import (
    ejecutar_plan,
    estimar_costo,
    obtener_api_key,
    obtener_balance,
)

def inyectar_estilos_custom():
    """
    Inyecta estilos CSS personalizados para forzar una estética mobile-first y premium.
    Ajusta tipografías (Outfit), botones interactivos grandes y táctiles, tarjetas con bordes
    redondeados y sombras elegantes, además de colores de fondo optimizados.
    """
    st.markdown("""
        <style>
        /* Importar fuente premium */
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
        
        /* Aplicar tipografía a toda la app */
        html, body, [class*="css"], .stMarkdown, .stText, p, span, li, button, select, input {
            font-family: 'Outfit', -apple-system, BlinkMacSystemFont, sans-serif !important;
        }
        
        /* Estilizar títulos principales */
        .main-title {
            font-size: 26px;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 2px;
            text-align: center;
        }
        .subtitle {
            font-size: 14px;
            color: #64748b;
            margin-bottom: 20px;
            text-align: center;
        }
        
        /* Botones grandes y touch-friendly en móvil */
        div.stButton > button {
            border-radius: 14px !important;
            padding: 14px 28px !important;
            font-weight: 600 !important;
            font-size: 16px !important;
            background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
            color: white !important;
            border: none !important;
            box-shadow: 0 4px 6px -1px rgba(16, 185, 129, 0.2), 0 2px 4px -1px rgba(16, 185, 129, 0.1) !important;
            transition: all 0.2s ease-in-out !important;
            width: 100% !important;
        }
        
        div.stButton > button:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 10px 15px -3px rgba(16, 185, 129, 0.3) !important;
            background: linear-gradient(135deg, #34d399 0%, #059669 100%) !important;
        }
        
        div.stButton > button:active {
            transform: translateY(0px) !important;
        }
        
        /* Tarjetas personalizadas para paneles de información */
        .info-card {
            background-color: #ffffff;
            border: 1px solid #f1f5f9;
            border-radius: 16px;
            padding: 16px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            margin-bottom: 16px;
        }
        
        /* Alertas personalizadas y más elegantes */
        .custom-alert {
            background: #fffbeb;
            border-left: 5px solid #f59e0b;
            color: #78350f;
            border-radius: 12px;
            padding: 14px;
            margin-bottom: 10px;
            font-size: 14px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
            line-height: 1.4;
        }
        
        .custom-alert-danger {
            background: #fef2f2;
            border-left: 5px solid #ef4444;
            color: #7f1d1d;
            border-radius: 12px;
            padding: 14px;
            margin-bottom: 10px;
            font-size: 14px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
            line-height: 1.4;
        }
        
        /* Estilos de Badges para la intención de voto */
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 6px 12px;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 600;
            text-transform: capitalize;
            gap: 6px;
        }
        .badge-favor {
            background-color: #d1fae5;
            color: #065f46;
            border: 1px solid #a7f3d0;
        }
        .badge-contra {
            background-color: #fee2e2;
            color: #991b1b;
            border: 1px solid #fecaca;
        }
        .badge-indeciso {
            background-color: #fef3c7;
            color: #92400e;
            border: 1px solid #fde68a;
        }
        
        /* Contenedores de KPIs */
        .kpi-container {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 14px;
            background-color: #f8fafc;
            border-radius: 12px;
            margin-bottom: 8px;
            border: 1px solid #f1f5f9;
        }
        .kpi-label {
            font-size: 14px;
            color: #475569;
            font-weight: 500;
        }
        .kpi-value {
            font-size: 15px;
            font-weight: 700;
            color: #0f172a;
        }
        
        /* Borde redondeado y sombreado para el mapa de Folium */
        .folium-map-container {
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 10px 25px -5px rgba(0,0,0,0.08);
            border: 1px solid #e2e8f0;
            margin-bottom: 20px;
        }
        
        /* Estilización de listados de visitas */
        .visita-item {
            border-bottom: 1px solid #f1f5f9;
            padding: 10px 0;
        }
        .visita-item:last-child {
            border-bottom: none;
        }
        </style>
    """, unsafe_allow_html=True)

def mostrar_alertas(alertas):
    """
    Muestra alertas en formato mobile-friendly con diseño estilizado de tarjetas.
    Filtra y muestra solo las últimas 4 alertas para optimizar el espacio en pantallas pequeñas.
    """
    if alertas:
        st.markdown("<h3 style='font-size: 18px; margin-top: 15px; margin-bottom: 10px;'>⚠️ Centro de Alertas</h3>", unsafe_allow_html=True)
        # Mostrar solo las últimas 4 alertas para evitar el scroll infinito en móviles
        for alerta in alertas[-4:]:
            tipo = alerta.get('tipo', 'Alerta')
            mensaje = alerta.get('mensaje', '')
            seccion = alerta.get('seccion', '')
            
            # Determinar tipo de tarjeta según el mensaje
            es_critica = any(palabra in mensaje.lower() for palabra in ['anomalia', 'anomalía', 'diferencia', 'nulo'])
            
            if es_critica:
                st.markdown(f"""
                    <div class="custom-alert-danger">
                        <strong>🚨 {tipo} (Sección {seccion}):</strong><br>{mensaje}
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div class="custom-alert">
                        <strong>⚠️ {tipo} (Sección {seccion}):</strong><br>{mensaje}
                    </div>
                """, unsafe_allow_html=True)

def mostrar_login():
    """
    Renderiza el formulario de inicio de sesión (mobile-first) usando las
    clases CSS existentes. Valida las credenciales y actualiza
    st.session_state.autenticado en caso de éxito.
    """
    st.markdown('<div class="main-title">🗳️ Tlalpan Electoral 2027</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Acceso restringido · Ingresa tus credenciales</div>', unsafe_allow_html=True)

    st.markdown('<div class="info-card">', unsafe_allow_html=True)
    usuario = st.text_input("👤 Usuario", placeholder="Escribe tu usuario")
    contrasena = st.text_input("🔑 Contraseña", type="password", placeholder="Escribe tu contraseña")
    if st.button("🔐 Iniciar Sesión", use_container_width=True):
        if validar_credenciales(usuario, contrasena):
            st.session_state.autenticado = True
            st.rerun()
        else:
            st.error("❌ Credenciales incorrectas. Intenta nuevamente.")
    st.markdown('</div>', unsafe_allow_html=True)

def verificar_autenticacion() -> bool:
    """
    Verifica si el usuario tiene una sesión activa.
    Si no está autenticado, renderiza el formulario de login y retorna False
    para que el resto de la app no se renderice.

    Retorna:
        True si la sesión está activa, False si se muestra el login.
    """
    if 'autenticado' not in st.session_state:
        st.session_state.autenticado = False
    if not st.session_state.autenticado:
        mostrar_login()
        return False
    return True

def mostrar_boton_cerrar_sesion():
    """
    Muestra el botón para cerrar la sesión activa en el encabezado de la app.
    Al pulsarlo resetea st.session_state.autenticado y recarga la página.
    """
    col_boton, col_vacio = st.columns([1, 3])
    with col_boton:
        if st.button("🔒 Cerrar sesión", use_container_width=True):
            st.session_state.autenticado = False
            st.rerun()

# ---------------------------------------------------------------------------
# Extracción real de datos con la Scraping API de Scrapeless
# ---------------------------------------------------------------------------

def _inicializar_config_extraccion():
    """Inicializa las claves no-widget de session_state para la configuración de extracción."""
    valores_por_defecto = {
        'scrapeless_balance': None,
        'posts_origen': 'real',
        'estado_extraccion': None,
        'ultima_extraccion': None,
    }
    for clave, valor in valores_por_defecto.items():
        if clave not in st.session_state:
            st.session_state[clave] = valor

def _armar_plan() -> list:
    """Construye el plan de extracción a partir de los widgets de configuración."""
    ambito = st.session_state.get('ambito_extraccion', 'perfil')
    return [
        {
            'red': 'TikTok',
            'ambito': ambito,
            'activo': bool(st.session_state.get('cfg_tt_activa')),
            'consulta': st.session_state.get('cfg_tt_keyword', '').strip(),
            'limite': int(st.session_state.get('cfg_tt_limite', 35)),
        },
        {
            'red': 'Instagram',
            'ambito': ambito,
            'activo': False,
            'consulta': st.session_state.get('cfg_ig_keyword', '').strip(),
            'limite': int(st.session_state.get('cfg_ig_limite', 35)),
        },
    ]

def _guardar_resultados(df, items, usuario):
    """
    Guarda los resultados de una extracción real en disco:
    - `datos_extraidos/posts_<usuario>_<ts>.csv`   -> DataFrame normalizado.
    - `datos_extraidos/raw_<usuario>_<ts>.json`    -> items crudos de Scrapeless.

    Retorna:
        dict con rutas y bytes para descarga ('csv_path', 'json_path', 'csv_bytes', 'json_bytes').
    """
    carpeta = 'datos_extraidos'
    os.makedirs(carpeta, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    usuario_limpio = usuario.replace(' ', '_')
    csv_path = os.path.join(carpeta, f'posts_{usuario_limpio}_{ts}.csv')
    json_path = os.path.join(carpeta, f'raw_{usuario_limpio}_{ts}.json')
    df.to_csv(csv_path, index=False)
    contenedor = {
        'red_social': 'TikTok',
        'ambito': 'perfil',
        'usuario': usuario_limpio,
        'cantidad_items': len(items),
        'generado': datetime.now().isoformat(),
        'items': items,
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(contenedor, f, ensure_ascii=False, indent=2)
    print(f'SCRAPELESS: resultados guardados en {csv_path} y {json_path}')
    return {
        'csv_path': csv_path,
        'json_path': json_path,
        'csv_bytes': df.to_csv(index=False).encode('utf-8'),
        'json_bytes': json.dumps(contenedor, ensure_ascii=False, indent=2).encode('utf-8'),
    }

def _verificar_saldo():
    """Consulta el saldo del usuario en Scrapeless y guarda el resultado."""
    api_key = obtener_api_key()
    balance = obtener_balance(api_key) if api_key else None
    st.session_state.scrapeless_balance = balance
    if balance is None:
        st.error("⚠️ No se pudo consultar el saldo: revisa tu API Key de Scrapeless o tu conexión.")
    else:
        estado_plan = 'activo' if balance['plan'].get('status') else 'sin suscripción activa'
        st.success(f"💳 Saldo disponible: {balance['creditos']:.4f} créditos "
                   f"(+{balance['excesos']:.4f} exceso). Plan: {estado_plan}.")

def _ejecutar_extraccion():
    """Ejecuta una extracción real de un perfil de TikTok y guarda los resultados."""
    api_key = obtener_api_key()
    balance = obtener_balance(api_key) if api_key else None
    st.session_state.scrapeless_balance = balance
    plan = _armar_plan()

    if st.session_state.get('ambito_extraccion') == 'keyword':
        st.session_state['estado_extraccion'] = ('aviso',
            "🔑 La búsqueda por palabra clave/hashtag ya no está soportada por Scrapeless. "
            "Usa el ámbito 'Perfil definido' con un @usuario de TikTok.")
        return
    if not any(cfg['activo'] and cfg['consulta'] for cfg in plan):
        st.session_state['estado_extraccion'] = ('aviso',
            "⚠️ Activa al menos una red e ingresa un @usuario de TikTok.")
        return
    if not api_key or balance is None or balance['creditos'] <= 0:
        st.session_state['estado_extraccion'] = ('aviso',
            "⚠️ Sin API Key configurada o sin saldo disponible. Revisa los Secrets "
            "([SCRAPELESS] API_KEY) y el saldo en Scrapeless.")
        st.rerun()
        return

    usuarios = ', '.join(cfg['consulta'].lstrip('@') for cfg in plan if cfg['activo'] and cfg['consulta'])
    with st.spinner(f"Descargando publicaciones reales de @{usuarios} desde Scrapeless..."):
        resultado = ejecutar_plan(plan, api_key=api_key)
    if resultado['df'] is not None:
        st.session_state.posts_sociales = resultado['df']
        st.session_state.posts_origen = 'real'
        st.session_state.fecha_extraccion = datetime.now()
        guardado = _guardar_resultados(
            resultado['df'], resultado.get('items', []), usuarios)
        st.session_state.ultima_extraccion = {
            'usuario': usuarios,
            'n_items': len(resultado['df']),
            'csv_bytes': guardado['csv_bytes'],
            'json_bytes': guardado['json_bytes'],
            'csv_path': guardado['csv_path'],
            'json_path': guardado['json_path'],
        }
        st.session_state['estado_extraccion'] = (
            'ok', f"✅ {len(resultado['df'])} posts reales descargados de {usuarios}.")
        st.toast(f"✅ {len(resultado['df'])} posts reales descargados", icon="✅")
    else:
        st.session_state['estado_extraccion'] = (
            'error', f"Fallo en la extracción: {resultado['error']}")
    st.rerun()

def _render_estado_extraccion():
    """Renderiza el estado de la última extracción guardado en session_state."""
    estado = st.session_state.get('estado_extraccion')
    if not estado:
        return
    tipo, texto = estado
    if tipo == 'ok':
        st.success(texto)
    elif tipo == 'error':
        st.error(texto)
    else:
        st.warning(texto)

def _render_resultado_extraccion():
    """
    Muestra la estructura de la última extracción (columnas y primer item crudo)
    con botones para descargar JSON y CSV.
    """
    ultima = st.session_state.get('ultima_extraccion')
    if not ultima:
        return
    with st.expander(f"🔎 Ver estructura del resultado de @{ultima['usuario']} "
                     f"({ultima['n_items']} posts)"):
        st.markdown("**Tabla normalizada (dashboard):**")
        st.write(st.session_state.posts_sociales.head(5))
        st.markdown(f"Archivos guardados:\n- `{ultima['csv_path']}`\n- `{ultima['json_path']}`")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button("📥 Descargar CSV", data=ultima['csv_bytes'],
                               file_name=f"posts_{ultima['usuario'].replace(' ', '_')}.csv",
                               mime='text/csv', use_container_width=True,
                               key="btn_descargar_csv_extraccion")
        with col_d2:
            st.download_button("📥 Descargar JSON (crudo)", data=ultima['json_bytes'],
                               file_name=f"raw_{ultima['usuario'].replace(' ', '_')}.json",
                               mime='application/json', use_container_width=True,
                               key="btn_descargar_json_extraccion")

def _mostrar_config_real():
    """Panel de configuración para el modo Real (Scrapeless)."""
    _render_estado_extraccion()
    col_sal, col_ver = st.columns([3, 1])
    with col_sal:
        balance = st.session_state.get('scrapeless_balance')
        if balance is None:
            st.markdown("💳 **Saldo:** no verificado")
        else:
            st.markdown(f"💳 **Saldo: {balance['creditos']:.4f}** créditos")
    with col_ver:
        if st.button("💳 Verificar saldo", use_container_width=True):
            _verificar_saldo()

    st.radio(
        "Ámbito de extracción:",
        options=['perfil', 'keyword'],
        format_func=lambda o: "👤 Perfil definido (TikTok) · activo"
                              if o == 'perfil' else "🔑 Palabra clave (no disponible)",
        horizontal=True,
        key='ambito_extraccion',
    )
    if st.session_state.get('ambito_extraccion') == 'keyword':
        st.warning("🔑 La búsqueda por palabra clave/hashtag ya no está soportada por "
                   "Scrapeless (actor deprecado) e Instagram no tiene actor público. "
                   "Cambia a 'Perfil definido' con un @usuario de TikTok.")

    st.markdown("### 📝 Configuración por red social")
    col_tt, col_ig = st.columns(2)
    with col_tt:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown("**🎵 TikTok (disponible)**")
        ambito = st.session_state.get('ambito_extraccion', 'perfil')
        if ambito == 'perfil':
            st.checkbox("Habilitar", key='cfg_tt_activa')
            st.text_input("Usuario de TikTok (@cuenta)", key='cfg_tt_keyword',
                          placeholder="ej. @gobiernocdmx o alcaldia_tlalpan")
            st.slider("Nº de publicaciones", 5, 200, 35, 5, key='cfg_tt_limite')
        else:
            st.info("La búsqueda por palabra clave en TikTok no está soportada por Scrapeless.")
        st.markdown('</div>', unsafe_allow_html=True)
    with col_ig:
        st.markdown('<div class="info-card">', unsafe_allow_html=True)
        st.markdown("**📸 Instagram (no disponible)**")
        st.checkbox("Habilitar", key='cfg_ig_activa', value=False, disabled=True,
                    help="Scrapeless no expone actor público para Instagram.")
        st.caption("Instagram se deshabilitará hasta que Scrapeless publique su actor.")
        st.markdown('</div>', unsafe_allow_html=True)

    balance_actual = st.session_state.get('scrapeless_balance')
    credito_actual = balance_actual['creditos'] if balance_actual else None
    est = estimar_costo(_armar_plan(), credito_actual)
    st.markdown(f"🔎 **Estimación:** {est['peticiones']} petición(es) ≈ "
                f"**${est['costo_usd']:.2f} USD**")
    if est['alcanza'] is False:
        st.warning("⚠️ El costo estimado supera el saldo disponible. Ajusta las cantidades.")

    if st.button("🚀 Ejecutar extracción", use_container_width=True):
        _ejecutar_extraccion()

    _render_resultado_extraccion()

    st.caption("Extracción real soportada: perfil de TikTok (`scraper.tiktok.user.detail` + "
               "`scraper.tiktok.user.work`). La búsqueda por palabra clave de TikTok y el "
               "actor de Instagram no están publicados por Scrapeless; por eso se ocultan.")

def mostrar_configuracion_extraccion():
    """
    Panel de extracción real de la Pestaña 2 con la Scraping API de Scrapeless
    (perfil de TikTok, por @usuario, con engagement real). Solo hay datos reales.
    """
    _inicializar_config_extraccion()
    st.markdown("<h4 style='font-size: 15px; font-weight: 600; margin-top: 8px;'>"
                "🚀 Extracción Real de Datos (Scrapeless)</h4>", unsafe_allow_html=True)
    st.caption("Descarga las publicaciones recientes de un perfil público de TikTok (@usuario) "
               "con su engagement. La API Key se lee de los Secrets (`.streamlit/secrets.toml`).")
    _mostrar_config_real()
