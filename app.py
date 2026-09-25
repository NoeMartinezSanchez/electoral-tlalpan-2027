import streamlit as st
import pandas as pd
import folium
import random
from datetime import datetime
from streamlit_folium import folium_static

# Importaciones locales
from modules.data import CONFIG, generar_datos_iniciales, simular_visita
from modules.datos_campo import (
    conexion_ok,
    error_conexion,
    estado_secciones,
    importar_secciones_ine,
    insertar_registro,
    obtener_registros,
    obtener_resumen,
    obtener_secciones,
    reconectar,
    secciones_para_app,
)
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
    st.session_state.secciones, st.session_state.origen_secciones = secciones_para_app()
if 'visitas' not in st.session_state:
    st.session_state.visitas = []
if 'alertas' not in st.session_state:
    st.session_state.alertas = []
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
if 'usuario_login' not in st.session_state:
    st.session_state.usuario_login = 'admin'

def generar_alertas(df, registros_df=None):
    """
    Evalúa las secciones electorales y genera alertas automáticas en
    st.session_state.alertas a partir de cobertura, intención y, con registros
    reales, indecisión (%) y concentración de quejas de agua.
    """
    for _, row in df.iterrows():
        seccion_id = int(row['id'])
        # Alerta: Cobertura menor al umbral
        if row['cobertura'] < CONFIG['UMBRAL_COBERTURA']:
            ya_existe = any(a['seccion'] == seccion_id and a['tipo'] == 'Baja Cobertura'
                            for a in st.session_state.alertas)
            if not ya_existe:
                st.session_state.alertas.append({
                    'seccion': seccion_id,
                    'tipo': 'Baja Cobertura',
                    'mensaje': f"La sección '{row['nombre']}' tiene cobertura crítica de "
                               f"{row['cobertura']:.1f}% (mínimo: {CONFIG['UMBRAL_COBERTURA']}%). "
                               f"Se recomienda desviar estructura a este punto."
                })

        # Alerta: Oposición mayoritaria detectada
        if row['intencion'] == 'en_contra':
            ya_existe = any(a['seccion'] == seccion_id and a['tipo'] == 'Zona Crítica'
                            for a in st.session_state.alertas)
            if not ya_existe:
                st.session_state.alertas.append({
                    'seccion': seccion_id,
                    'tipo': 'Zona Crítica',
                    'mensaje': f"La sección '{row['nombre']}' muestra intención de voto "
                               f"mayoritaria en contra de nuestra coalición."
                })

        # Alertas con registros reales de campo
        if registros_df is not None and not registros_df.empty:
            # Alta indecisión: % de indecisos entre las simpatías de la sección > 40
            sim_seccion = registros_df[(registros_df['seccion_id'] == seccion_id)
                                       & (registros_df['tipo'] == 'simpatia')]
            if not sim_seccion.empty and 'intencion' in sim_seccion:
                n_ind = int((sim_seccion['intencion'] == 'indeciso').sum())
                pct_ind = 100.0 * n_ind / len(sim_seccion)
                if pct_ind > CONFIG['UMBRAL_INDECISION']:
                    ya = any(a['seccion'] == seccion_id and a['tipo'] == 'Alta Indecisión'
                             for a in st.session_state.alertas)
                    if not ya:
                        st.session_state.alertas.append({
                            'seccion': seccion_id,
                            'tipo': 'Alta Indecisión',
                            'mensaje': f"La sección '{row['nombre']}' supera el "
                                       f"{CONFIG['UMBRAL_INDECISION']:.0f}% de indecisos "
                                       f"({pct_ind:.0f}%). Atender discurso local."
                        })
            # Quejas de agua concentradas (eje del documento estratégico)
            quejas_seccion = registros_df[registros_df['seccion_id'] == seccion_id]
            if 'queja_categoria' in registros_df.columns:
                quejas_agua = quejas_seccion[quejas_seccion['queja_categoria'] == 'AGUA']
            else:
                quejas_agua = quejas_seccion[quejas_seccion.get('tipo') == 'queja']
            if len(quejas_agua) >= 3:
                ya = any(a['seccion'] == seccion_id and a['tipo'] == 'Quejas de Agua'
                         for a in st.session_state.alertas)
                if not ya:
                    st.session_state.alertas.append({
                        'seccion': seccion_id,
                        'tipo': 'Quejas de Agua',
                        'mensaje': f"La sección '{row['nombre']}' concentra "
                                   f"{len(quejas_agua)} quejas de agua/desabasto. "
                                   f"Preparar respuesta de gobierno."
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

def _mostrar_formulario_registro():
    """
    Formulario de registro REAL de campo (brigadista→Mongo): sección, tipo
    (simpatía/visita/queja), intención y texto de queja. Clasifica con NLP e
    inserta en `registros_campo`. Cumple la nota INE: se registra como
    'simpatía', nunca como voto formal.
    """
    secciones_ids = st.session_state.secciones['id'].tolist()
    nombre_por_id = dict(zip(st.session_state.secciones['id'],
                             st.session_state.secciones['nombre']))
    if st.session_state.get('origen_secciones', 'demo') != 'ine':
        st.warning("🟡 Las secciones visibles siguen en modo demo. Para registrar "
                   "campo con geografía real, importa antes la cartografía IECM "
                   "('🔄 Importar secciones INE/IECM').")
    with st.form('form_registro_campo'):
        sec_sel = st.selectbox(
            "🗳️ Sección electoral:",
            options=secciones_ids,
            format_func=lambda x: f"{x} · {nombre_por_id.get(x, '')}")
        tipo = st.radio(
            "Tipo de registro:",
            options=['simpatia', 'visita', 'queja'],
            format_func=lambda t: {'simpatia': '🗳️ Simpatía',
                                   'visita': '🛡️ Visita',
                                   'queja': '⚠️ Queja/Incidencia'}[t],
            horizontal=True)
        intencion = None
        if tipo in ('simpatia', 'visita'):
            intencion = st.radio(
                "Intención (registro como simpatía, no voto formal):",
                options=['a_favor', 'indeciso', 'en_contra'],
                format_func=lambda v: {'a_favor': '💚 A favor',
                                       'indeciso': '💛 Indeciso',
                                       'en_contra': '❤️ En contra'}[v],
                horizontal=True)
        texto = st.text_area("📝 Queja / nota (obligatoria si el tipo es Queja):")
        enviado = st.form_submit_button("💾 Guardar registro", use_container_width=True)

    if enviado:
        if tipo == 'queja' and not texto.strip():
            st.error("❌ La queja no puede estar vacía.")
        else:
            categoria, sentimiento = (clasificar_queja(texto.strip())
                                      if texto.strip() else ('SIN_QUEJA', 'neutral'))
            doc = {
                'seccion_id': int(sec_sel),
                'tipo': tipo,
                'intencion': intencion,
                'queja_texto': texto.strip(),
                'queja_categoria': categoria,
                'queja_sentimiento': sentimiento,
                'brigadista': st.session_state.get('usuario_login', 'admin'),
                'fecha': datetime.now().isoformat(),
                'fuente': 'real',
            }
            resp = insertar_registro(doc)
            if resp['ok']:
                st.toast(f"Registro guardado · sección {sec_sel} ({tipo})", icon="✅")
                st.session_state['mensaje_campo'] = (
                    f"Registro de {tipo} en sección {sec_sel}. NLP: "
                    f"categoría {categoria} · sentimiento {sentimiento}.")
            else:
                st.session_state['mensaje_campo'] = f"No se pudo guardar: {resp['error']}"
            st.rerun()
    mensaje_campo = st.session_state.pop('mensaje_campo', None)
    if mensaje_campo:
        st.info(mensaje_campo)


def mostrar_panel_control(usar_real: bool):
    """
    Panel de acciones de campaña: registro real (Mongo) o demo (simulación),
    ficha de sección y bitácora de quejas.
    """
    st.markdown("<h3 style='font-size: 18px; margin-bottom: 12px; margin-top: 5px;'>🎯 Acciones de Campaña</h3>", unsafe_allow_html=True)

    st.radio(
        "Fuente de registros:",
        options=['auto', 'real', 'demo'],
        format_func=lambda m: {'auto': '⚙️ Auto (según conexión)',
                               'real': '🗳️ Real (Mongo)',
                               'demo': '🎲 Demo (simular)'}[m],
        horizontal=True,
        key='modo_campo',
        value='auto',
        help="Auto usa registro real si MongoDB está conectado; si no, cae a demo.",
    )
    usar_real = ((st.session_state.get('modo_campo', 'auto') == 'real')
                 or (st.session_state.get('modo_campo', 'auto') == 'auto'
                     and conexion_ok()))
    st.session_state['usar_real'] = usar_real

    # 1. Registro de visitas: modo real (formulario) o demo
    if usar_real:
        _mostrar_formulario_registro()
    else:
        if st.button("📱 Registrar Visita (Demo)", use_container_width=True):
            st.session_state['modo_campo'] = 'demo'
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
    
    # 3. Bitácora de quejas de la sección consultada (real o demo)
    if usar_real:
        df_quejas = obtener_registros(int(seccion_sel))
        quejas_seccion = []
        if not df_quejas.empty:
            for _, r in df_quejas.iterrows():
                try:
                    fecha_reg = datetime.fromisoformat(str(r.get('fecha', '')))
                except Exception:
                    fecha_reg = datetime.now()
                quejas_seccion.append({
                    'queja_sentimiento': r.get('queja_sentimiento') or 'neutral',
                    'queja_categoria': r.get('queja_categoria') or '',
                    'queja_texto': r.get('queja_texto') or '',
                    'fecha': fecha_reg,
                })
        texto_vacio = ("Aún no hay registros reales en esta sección. Usa el "
                       "formulario 'Guardar registro' para capturar visitas/quejas.")
    else:
        quejas_seccion = [v for v in st.session_state.visitas if v['seccion_id'] == seccion_sel]
        texto_vacio = ("Aún no se reportan quejas en esta sección. Presiona "
                       "'Registrar Visita (Demo)' para simular reportes.")

    st.markdown("<h4 style='font-size: 14px; font-weight: 600; margin-bottom: 8px;'>📋 Quejas Recientes</h4>", unsafe_allow_html=True)
    if not quejas_seccion:
        st.info(texto_vacio)
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
    # Determinar si se usa el registro real (Mongo) según conexión y preferencia
    modo_campo = st.session_state.get('modo_campo', 'auto')
    usar_real = (modo_campo == 'real') or (modo_campo == 'auto' and conexion_ok())
    st.session_state['usar_real'] = usar_real

    # Datos reales de campo: estado de secciones (cobertura/intención) con registros reales
    registros = obtener_registros() if usar_real else pd.DataFrame()
    if usar_real and not registros.empty:
        st.session_state.secciones = estado_secciones(
            st.session_state.secciones, registros)

    # Regenerar alertas en cada corrida para reflejar el estado actual
    st.session_state.alertas = []
    generar_alertas(st.session_state.secciones, registros)
        
    # Título del módulo
    st.markdown('<div class="main-title">🗳️ Inteligencia Electoral - Tlalpan 2027</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Monitoreo de Campo, Cobertura y Simulación de Visitas Territoriales</div>', unsafe_allow_html=True)

    # Origen de los datos (real INE/Mongo o demo)
    origen = st.session_state.get('origen_secciones', 'demo')
    if origen == 'ine':
        st.success(f"🗺️ Geografía electoral real (ITE/INE) · {len(st.session_state.secciones)} "
                   f"secciones · persistido en MongoDB.")
    else:
        col_av, col_btn = st.columns([2, 1])
        with col_av:
            estado_mongo = 'conectado' if conexion_ok() else f'sin conexión ({error_conexion()})'
            st.warning(f"🟡 Secciones en modo demo (sin cartografía INE cargada). "
                       f"MongoDB: {estado_mongo}.")
        with col_btn:
            if st.button("🔄 Importar secciones IECM/INE", use_container_width=True):
                res = importar_secciones_ine()
                if res['ok']:
                    st.toast(res['mensaje'], icon="✅")
                else:
                    st.error(res['mensaje'])
                st.session_state.secciones, st.session_state.origen_secciones = secciones_para_app()
                st.rerun()
            if st.button("🔁 Reintentar conexión Mongo", use_container_width=True):
                reconectar()
                st.rerun()
    
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

    # Resumen de actividad real cuando hay registros de campo
    if usar_real:
        resumen_campo = obtener_resumen()
        if resumen_campo:
            sim = resumen_campo.get('simpatias', {})
            st.caption(f"🗳️ Registros reales (Mongo): {resumen_campo.get('total', 0)} · "
                       f"simpatías 💚 {sim.get('a_favor', 0)} / 💛 {sim.get('indeciso', 0)} / "
                       f"❤️ {sim.get('en_contra', 0)} · quejas {resumen_campo.get('quejas', 0)} · "
                       f"secciones con actividad {resumen_campo.get('secciones_con_registro', 0)}")

    # Disposición responsiva en columnas.
    col_mapa, col_panel = st.columns([1.7, 1.3])
    
    with col_mapa:
        st.markdown("<h3 style='font-size: 18px; margin-bottom: 12px;'>🗺️ Mapa de Secciones</h3>", unsafe_allow_html=True)
        st.markdown('<div class="folium-map-container">', unsafe_allow_html=True)
        mostrar_mapa(st.session_state.secciones)
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col_panel:
        mostrar_panel_control(usar_real)
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
