import streamlit as st
import pandas as pd
import folium
import random
from datetime import datetime
from streamlit_folium import folium_static

# Importaciones locales
from modules.data import CONFIG, generar_datos_iniciales, simular_visita
from modules.nlp import clasificar_queja
from utils import (
    inyectar_estilos_custom,
    mostrar_alertas,
    mostrar_boton_cerrar_sesion,
    verificar_autenticacion
)

# 1. Configuración de página optimizada para móvil (mobile-first)
st.set_page_config(
    page_title="Tlalpan Electoral 2027",
    page_icon="🗳️",
    layout="wide",
    initial_sidebar_state="collapsed"  # Mantiene limpia la UI en celulares
)

# 2. Inicialización del estado global de la aplicación (Streamlit session_state)
if 'secciones' not in st.session_state:
    st.session_state.secciones = generar_datos_iniciales()
if 'visitas' not in st.session_state:
    st.session_state.visitas = []
if 'alertas' not in st.session_state:
    st.session_state.alertas = []
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

def generar_alertas(df):
    """
    Evalúa las secciones electorales y genera alertas automáticas en st.session_state.alertas
    basándose en la cobertura y en la tendencia de intención de voto.
    """
    for _, row in df.iterrows():
        # Alerta: Cobertura menor al umbral
        if row['cobertura'] < CONFIG['UMBRAL_COBERTURA']:
            ya_existe = any(a['seccion'] == row['id'] and a['tipo'] == 'Baja Cobertura' for a in st.session_state.alertas)
            if not ya_existe:
                st.session_state.alertas.append({
                    'seccion': row['id'],
                    'tipo': 'Baja Cobertura',
                    'mensaje': f"La sección '{row['nombre']}' tiene cobertura crítica de {row['cobertura']:.1f}% (mínimo: {CONFIG['UMBRAL_COBERTURA']}%)."
                })
        
        # Alerta: Oposición mayoritaria detectada
        if row['intencion'] == 'en_contra':
            ya_existe = any(a['seccion'] == row['id'] and a['tipo'] == 'Zona Crítica' for a in st.session_state.alertas)
            if not ya_existe:
                st.session_state.alertas.append({
                    'seccion': row['id'],
                    'tipo': 'Zona Crítica',
                    'mensaje': f"La sección '{row['nombre']}' muestra intención de voto mayoritaria en contra de nuestra coalición."
                })

def mostrar_mapa(df):
    """
    Genera el mapa Folium centrado en Tlalpan, renderiza los CircleMarkers correspondientes
    a cada sección con tamaños proporcionales a su cobertura y colores según su intención,
    y lo dibuja de forma responsiva.
    """
    m = folium.Map(
        location=CONFIG['CENTRO_MAPA'],
        zoom_start=CONFIG['ZOOM_MAPA'],
        zoom_control=True,
        tiles="OpenStreetMap"
    )
    
    # Añadir marcadores por cada sección electoral
    for _, row in df.iterrows():
        color = CONFIG['COLORES'][row['intencion']]
        popup_html = f"""
        <div style="font-family: 'Outfit', sans-serif; font-size: 13px; width: 170px; line-height: 1.4;">
            <strong style="font-size: 14px; color: #0f172a;">{row['nombre']}</strong><br>
            <span style="color: #64748b;">ID Sección:</span> {row['id']}<br>
            <span style="color: #64748b;">Intención:</span> <b>{row['intencion'].replace('_', ' ').capitalize()}</b><br>
            <span style="color: #64748b;">Cobertura:</span> {row['cobertura']:.1f}%<br>
            <span style="color: #64748b;">Tipo Zona:</span> {row['tipo_zona'].capitalize()}
        </div>
        """
        folium.CircleMarker(
            location=[row['lat'], row['lon']],
            radius=8 + (row['cobertura'] / 10),
            popup=folium.Popup(popup_html, max_width=220),
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.7,
            weight=2
        ).add_to(m)
        
    # Renderizar el mapa de forma adaptable
    folium_static(m, width=None, height=400)

def mostrar_panel_control():
    """
    Crea el panel de control interactivo para registrar visitas,
    seleccionar secciones y consultar su historial de quejas.
    """
    st.markdown("<h3 style='font-size: 18px; margin-bottom: 12px; margin-top: 5px;'>🎯 Acciones de Campaña</h3>", unsafe_allow_html=True)
    
    # 1. Registro de visitas
    if st.button("📱 Registrar Nueva Visita", use_container_width=True):
        # Simular los datos del evento de visita
        seccion_id, nuevo_voto, queja_texto = simular_visita(st.session_state.secciones)
        
        # Obtener los datos actuales de la sección elegida
        fila_actual = st.session_state.secciones[st.session_state.secciones['id'] == seccion_id]
        nombre_sec = fila_actual['nombre'].values[0]
        cobertura_act = fila_actual['cobertura'].values[0]
        
        # Incrementar cobertura sutilmente (simulando avance) y actualizar base
        incremento = random.uniform(3.0, 7.5)
        nueva_cobertura = min(100.0, round(cobertura_act + incremento, 1))
        
        # Guardar en base de datos local
        st.session_state.secciones.loc[st.session_state.secciones['id'] == seccion_id, 'intencion'] = nuevo_voto
        st.session_state.secciones.loc[st.session_state.secciones['id'] == seccion_id, 'cobertura'] = nueva_cobertura
        
        # Clasificación NLP de la queja vecinal
        categoria, sentimiento = clasificar_queja(queja_texto)
        
        # Añadir al historial de visitas de la sesión
        st.session_state.visitas.append({
            'seccion_id': seccion_id,
            'seccion_nombre': nombre_sec,
            'fecha': datetime.now(),
            'voto': nuevo_voto,
            'queja_texto': queja_texto,
            'queja_categoria': categoria,
            'queja_sentimiento': sentimiento
        })
        
        # Actualizar el gestor de alertas
        generar_alertas(st.session_state.secciones)
        
        # Mostrar feedback amigable mediante toast de Streamlit
        st.toast(f"Visita completada: Sección {seccion_id} ({nombre_sec}) | Voto: {nuevo_voto}", icon="✅")
        
        # Rerun para refrescar componentes
        st.rerun()

    st.markdown("<hr style='margin: 16px 0; border: 0; border-top: 1px solid #e2e8f0;'>", unsafe_allow_html=True)
    
    # 2. Selector de secciones para consulta detallada
    secciones_ids = st.session_state.secciones['id'].tolist()
    if 'seccion_consultada' not in st.session_state:
        st.session_state.seccion_consultada = secciones_ids[0]
        
    seccion_sel = st.selectbox(
        "🔍 Consultar Ficha de Sección:",
        options=secciones_ids,
        format_func=lambda x: f"Sección {x} - {st.session_state.secciones[st.session_state.secciones['id'] == x]['nombre'].values[0]}",
        index=secciones_ids.index(st.session_state.seccion_consultada)
    )
    st.session_state.seccion_consultada = seccion_sel
    
    # Cargar información de la sección a detallar
    info = st.session_state.secciones[st.session_state.secciones['id'] == seccion_sel].iloc[0]
    
    # Renderizar tarjeta informativa
    voto_estilo = {
        'a_favor': ('badge-favor', 'A Favor 💚'),
        'en_contra': ('badge-contra', 'En Contra ❤️'),
        'indeciso': ('badge-indeciso', 'Indeciso 💛')
    }[info['intencion']]
    
    st.markdown(f"""
        <div class="info-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <strong style="font-size: 16px;">{info['nombre']}</strong>
                <span class="badge {voto_estilo[0]}">{voto_estilo[1]}</span>
            </div>
            <div style="margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; font-size: 13px; color: #475569; margin-bottom: 4px;">
                    <span>Cobertura territorial</span>
                    <strong>{info['cobertura']:.1f}%</strong>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Progreso de la sección
    st.progress(float(info['cobertura'] / 100.0))
    
    # Características secundarias
    st.markdown(f"""
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 10px; margin-bottom: 15px;">
            <div style="background-color: #f8fafc; padding: 10px; border-radius: 12px; border: 1px solid #f1f5f9; text-align: center;">
                <div style="font-size: 11px; color: #64748b; margin-bottom: 2px;">Zona</div>
                <div style="font-size: 13px; font-weight: 600; text-transform: uppercase;">{info['tipo_zona']}</div>
            </div>
            <div style="background-color: #f8fafc; padding: 10px; border-radius: 12px; border: 1px solid #f1f5f9; text-align: center;">
                <div style="font-size: 11px; color: #64748b; margin-bottom: 2px;">Coordenadas</div>
                <div style="font-size: 12px; font-weight: 600;">{info['lat']:.4f}, {info['lon']:.4f}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # 3. Bitácora de quejas de la sección consultada
    quejas_seccion = [v for v in st.session_state.visitas if v['seccion_id'] == seccion_sel]
    
    st.markdown("<h4 style='font-size: 14px; font-weight: 600; margin-bottom: 8px;'>📋 Quejas Recientes</h4>", unsafe_allow_html=True)
    if not quejas_seccion:
        st.info("Aún no se reportan quejas en esta sección. Presiona 'Registrar Nueva Visita' para simular reportes.")
    else:
        for q in reversed(quejas_seccion[-3:]): # Mostrar últimas 3
            sentimiento_badge = {
                'positivo': ('#059669', '🟢 positivo'),
                'negativo': ('#dc2626', '🔴 negativo'),
                'neutral': ('#64748b', '⚪ neutral')
            }[q['queja_sentimiento']]
            
            fecha_str = q['fecha'].strftime("%H:%M:%S")
            st.markdown(f"""
                <div style="background-color: #f8fafc; border-left: 4px solid {sentimiento_badge[0]}; padding: 10px; border-radius: 8px; margin-bottom: 8px; font-size: 13px;">
                    <div style="display: flex; justify-content: space-between; font-weight: 600; font-size: 10px; color: #64748b; margin-bottom: 3px;">
                        <span>Categoría: {q['queja_categoria']}</span>
                        <span>{fecha_str}</span>
                    </div>
                    <div style="color: #1e293b; font-style: italic; margin-bottom: 4px;">"{q['queja_texto']}"</div>
                    <div style="font-size: 10px; color: #64748b;">
                        Sentimiento: <strong>{sentimiento_badge[1]}</strong>
                    </div>
                </div>
            """, unsafe_allow_html=True)

def mostrar_dashboard_electoral():
    """
    Renderiza el contenido completo del Módulo de Inteligencia Electoral (Pestaña 1).
    """
    # Inicializar alertas si el sistema se está arrancando
    if not st.session_state.alertas:
        generar_alertas(st.session_state.secciones)
        
    # Título del módulo
    st.markdown('<div class="main-title">🗳️ Inteligencia Electoral - Tlalpan 2027</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Monitoreo de Campo, Cobertura y Simulación de Visitas Territoriales</div>', unsafe_allow_html=True)
    
    # Indicadores Clave de Desempeño (KPIs)
    total_sec = len(st.session_state.secciones)
    favor_sec = len(st.session_state.secciones[st.session_state.secciones['intencion'] == 'a_favor'])
    contra_sec = len(st.session_state.secciones[st.session_state.secciones['intencion'] == 'en_contra'])
    indeciso_sec = len(st.session_state.secciones[st.session_state.secciones['intencion'] == 'indeciso'])
    
    # Fila de KPIs adaptables
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="kpi-container"><span class="kpi-label">📍 Secciones</span><span class="kpi-value">{total_sec}</span></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="kpi-container"><span class="kpi-label" style="color:#059669;">💚 Favor</span><span class="kpi-value" style="color:#059669;">{favor_sec}</span></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="kpi-container"><span class="kpi-label" style="color:#d97706;">💛 Indeciso</span><span class="kpi-value" style="color:#d97706;">{indeciso_sec}</span></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="kpi-container"><span class="kpi-label" style="color:#dc2626;">❤️ Contra</span><span class="kpi-value" style="color:#dc2626;">{contra_sec}</span></div>', unsafe_allow_html=True)

    # Disposición responsiva en columnas.
    col_mapa, col_panel = st.columns([1.7, 1.3])
    
    with col_mapa:
        st.markdown("<h3 style='font-size: 18px; margin-bottom: 12px;'>🗺️ Mapa de Secciones</h3>", unsafe_allow_html=True)
        st.markdown('<div class="folium-map-container">', unsafe_allow_html=True)
        mostrar_mapa(st.session_state.secciones)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_panel:
        mostrar_panel_control()
        mostrar_alertas(st.session_state.alertas)

def main():
    # Inyectar estilos CSS comunes para diseño mobile-first y premium
    inyectar_estilos_custom()
    
    # Gate de autenticación: si no hay sesión activa, solo se muestra el login
    if not verificar_autenticacion():
        st.stop()
    
    # Botón de cierre de sesión en el encabezado de la app
    mostrar_boton_cerrar_sesion()
    
    # Crear la navegación por Pestañas (independientes)
    tab1, tab2 = st.tabs(["🗳️ Inteligencia Electoral", "📊 Redes Sociales"])
    
    with tab1:
        mostrar_dashboard_electoral()
        
    with tab2:
        from modules.social_media import mostrar_dashboard_redes_sociales
        mostrar_dashboard_redes_sociales()

if __name__ == '__main__':
    main()
