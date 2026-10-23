import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

# ==========================================
# 1. CONFIGURACIÓN GENERAL Y DISEÑO
# ==========================================
st.set_page_config(
    page_title="Rental Valdivia - Control Flota",
    page_icon="🚜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo CSS personalizado para mejorar el look
st.markdown("""
    <style>
    .stMetric { background-color: #f0f2f6; padding: 15px; border-radius: 10px; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { border-radius: 5px 5px 0px 0px; padding: 10px 20px; }
    </style>
""", unsafe_allow_html=True)

DB_NAME = "rental_valdivia.db"

PAUTAS_MECANICAS = {
    "Cortadora Orbital": [
        "Revisión y limpieza de carbones del motor eléctrico",
        "Inspección de holgura en cabezal giratorio y mordazas",
        "Verificación de estado de portadisco y seguro",
        "Revisión de cableado blindado y enchufe industrial",
        "Engrase general de husillo y puntos móviles"
    ],
    "Unidad Motriz": [
        "Cambio de aceite de motor (15W-40) y revisión de fugas",
        "Verificación de nivel de aceite hidráulico",
        "Limpieza o reemplazo de filtro de aire y bujía",
        "Inspección de acoples rápidos (QDC) y mangueras",
        "Prueba de presión de trabajo y encendido"
    ],
    "Placa Compactadora": [
        "Revisión de tensión de correa centrífuga (embrague)",
        "Verificación de nivel de aceite en unidad vibradora",
        "Inspección de silentblocks (gomas amortiguadoras)",
        "Limpieza de carburador y filtro de combustible",
        "Ajuste de piola de aceleración"
    ],
    "Maquinaria con Horómetro": [
        "Cambio de aceite de motor y filtros",
        "Revisión de sistema hidráulico, cilindros y sellos",
        "Inspección de filtros de aire (primario y seguridad)",
        "Engrase de pasadores, bujes y corona de giro",
        "Verificación de sistema eléctrico y batería"
    ]
}

# ==========================================
# 2. BASE DE DATOS LOCAL (SQLite)
# ==========================================
def inicializar_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS equipos (
            codigo TEXT PRIMARY KEY,
            nombre TEXT,
            categoria TEXT,
            ubicacion_nfc TEXT,
            tipo_medicion TEXT,
            uso_acumulado INTEGER,
            limite_mantencion INTEGER,
            horometro_actual INTEGER,
            estado_operativo TEXT,
            falla_activa INTEGER,
            ultima_observacion TEXT,
            fecha_actualizacion TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_equipo TEXT,
            fecha TEXT,
            tipo_evento TEXT,
            responsable TEXT,
            uso_sumado INTEGER,
            costo_repuestos INTEGER,
            detalle TEXT
        )
    """)
    
    c.execute("SELECT COUNT(*) FROM equipos")
    if c.fetchone()[0] == 0:
        equipos_demo = [
            ("ORB-01", "Cortadora Orbital Tubos 6-12\"", "Cortadora Orbital", "Cara interna base mordaza", "DIAS", 14, 15, 0, "DISPONIBLE", 0, "Operativa. Próxima a revisión de carbones.", "2026-10-15 09:30"),
            ("MOT-07", "Unidad Motriz Bencinera Honda", "Unidad Motriz", "Tras soporte filtro de aire", "DIAS", 8, 20, 0, "EN_PANA", 1, "Cliente reporta pérdida de presión en manguera.", "2026-10-19 11:20"),
            ("EXC-02", "Miniexcavadora Yanmar ViO35", "Maquinaria con Horómetro", "Marco interior cabina izq.", "HORAS", 245, 250, 1495, "DISPONIBLE", 0, "Quedan 5 hrs para pauta.", "2026-10-18 16:40"),
            ("GEN-08", "Generador Insonorizado 40 kVA", "Maquinaria con Horómetro", "Interior puerta panel control", "HORAS", 80, 250, 3080, "ARRENDADA", 0, "En faena forestal Camino a Niebla.", "2026-10-14 08:30")
        ]
        c.executemany("INSERT INTO equipos VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", equipos_demo)
        conn.commit()
    conn.close()

def obtener_equipos():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM equipos", conn)
    conn.close()
    return df

def obtener_historial():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM historial ORDER BY id DESC", conn)
    conn.close()
    return df

def calcular_semaforo(fila):
    if fila["falla_activa"] == 1 or fila["estado_operativo"] == "EN_PANA":
        return "🔴 EN PANA (BLOQUEADA)"
    elif fila["uso_acumulado"] >= fila["limite_mantencion"]:
        return "🟡 PIDE MANTENCIÓN"
    elif fila["estado_operativo"] == "ARRENDADA":
        return "🔵 EN ARRIENDO (TERRENO)"
    else:
        return "🟢 OPERATIVA (LISTA)"

def obtener_gemini_key():
    """Obtiene la API key de Gemini desde secrets de Streamlit o variable de entorno."""
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.environ.get("GEMINI_API_KEY", "")

inicializar_db()
df_equipos = obtener_equipos()
df_equipos["semaforo"] = df_equipos.apply(calcular_semaforo, axis=1)

# ==========================================
# 3. LECTURA URL & BARRA LATERAL
# ==========================================
params = st.query_params
equipo_url = params.get("equipo", None)

with st.sidebar:
    try:
        st.image("https://cdn-icons-png.flaticon.com/512/2883/2883907.png", width=80) # Icono decorativo
    except Exception:
        pass # Si no hay internet, la app sigue funcionando sin el icono
    st.title("🚜 Rental Valdivia")
    st.caption("Control NFC & Mantención")
    st.divider()
    
    modo_vista = st.radio(
        "Navegación:",
        [
            "📱 1. Escáner NFC / Ficha",
            "🚦 2. Semáforo de Flota",
            "📊 3. Panel Gerencial",
            "➕ 4. Enrolar Máquina"
        ]
    )
    
    st.divider()
    st.markdown("### 🔧 Simulador de Escáner")
    lista_codigos = df_equipos["codigo"].tolist()
    indice_default = lista_codigos.index(equipo_url) if equipo_url in lista_codigos else 0
    equipo_seleccionado = st.selectbox("Simular lectura NFC:", lista_codigos, index=indice_default)

    st.divider()
    st.markdown("### 🤖 Asistente Mecánico (IA)")
    api_key_gemini = st.text_input("API Key de Google Gemini:", value=obtener_gemini_key(), type="password", help="Se completa automática si está en los Secrets; si no, pégala manualmente.")

# ==========================================
# MÓDULO 1: ESCÁNER NFC Y OPERACIÓN EN PATIO
# ==========================================
if modo_vista == "📱 1. Escáner NFC / Ficha":
    maq = df_equipos[df_equipos["codigo"] == equipo_seleccionado].iloc[0]
    unidad = "días" if maq["tipo_medicion"] == "DIAS" else "hrs desde última mant."
    
    st.title(f"Ficha Técnica: {maq['codigo']}")
    st.subheader(f"{maq['nombre']}")
    
    estado_actual = maq["semaforo"]
    
    # Tarjeta de Estado
    with st.container(border=True):
        if "🔴" in estado_actual:
            st.error(f"### {estado_actual}\n**Motivo:** {maq['ultima_observacion']}")
        elif "🟡" in estado_actual:
            st.warning(f"### {estado_actual}\n**Desgaste:** {maq['uso_acumulado']} / {maq['limite_mantencion']} {unidad}. Requiere taller.")
        elif "🔵" in estado_actual:
            st.info(f"### {estado_actual}\n**Nota:** {maq['ultima_observacion']}")
        else:
            st.success(f"### {estado_actual}\n**Desgaste:** {maq['uso_acumulado']} / {maq['limite_mantencion']} {unidad}. Lista para despacho.")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Uso Ciclo Actual", f"{maq['uso_acumulado']} {maq['tipo_medicion'].lower()}")
        porcentaje = min(int((maq["uso_acumulado"] / maq["limite_mantencion"]) * 100), 100)
        col2.metric("Desgaste Preventivo", f"{porcentaje}%")
        col3.metric("Horómetro Total", f"{maq['horometro_actual']} hrs" if maq["tipo_medicion"] == "HORAS" else "N/A")
        col4.metric("Ubicación Chip NFC", maq['ubicacion_nfc'])
        
        st.progress(porcentaje / 100, text="Nivel de desgaste hacia la próxima mantención preventiva")

    # PESTAÑAS OPERATIVAS
    tab_recepcion, tab_taller, tab_despacho, tab_admin, tab_hist = st.tabs([
        "📥 Recepción", "🛠️ Taller e IA", "🚚 Despacho", "⚙️ Forzar Estado", "📋 Historial"
    ])

    # 1. RECEPCIÓN
    with tab_recepcion:
        with st.form("form_recepcion", border=True):
            st.markdown("#### Registro de llegada desde Faena")
            c1, c2 = st.columns(2)
            with c1:
                responsable_rec = st.text_input("Recepcionado por:", value="Encargado de Patio")
                if maq["tipo_medicion"] == "DIAS":
                    uso_nuevo = st.number_input("Días en terreno:", min_value=1, value=3)
                    nuevo_horometro = 0
                else:
                    nuevo_horometro = st.number_input(
                        f"Horómetro actual (Anterior: {maq['horometro_actual']}):",
                        min_value=int(maq["horometro_actual"]), value=int(maq["horometro_actual"]) + 15
                    )
                    uso_nuevo = nuevo_horometro - int(maq["horometro_actual"])
                
                llego_con_falla = st.checkbox("⚠️ Llegó en Pana / Con Daños")
            with c2:
                obs_recepcion = st.text_area("Observaciones visuales:")
            
            if st.form_submit_button("💾 Guardar Recepción", type="primary", use_container_width=True):
                ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                nuevo_uso_acum = int(maq["uso_acumulado"]) + int(uso_nuevo)
                nuevo_estado = "EN_PANA" if llego_con_falla else "DISPONIBLE"
                falla_flag = 1 if llego_con_falla else int(maq["falla_activa"])
                horometro_final = nuevo_horometro if maq["tipo_medicion"] == "HORAS" else maq["horometro_actual"]
                nota_final = obs_recepcion if obs_recepcion else "Recepción normal."
                
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("UPDATE equipos SET uso_acumulado=?, horometro_actual=?, estado_operativo=?, falla_activa=?, ultima_observacion=?, fecha_actualizacion=? WHERE codigo=?", 
                          (nuevo_uso_acum, horometro_final, nuevo_estado, falla_flag, nota_final, ahora, maq["codigo"]))
                c.execute("INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle) VALUES (?,?,?,?,?,?,?)",
                          (maq["codigo"], ahora, "RECEPCIÓN", responsable_rec, uso_nuevo, 0, nota_final))
                conn.commit()
                conn.close()
                st.rerun()

    # 2. TALLER E IA MECÁNICA
    with tab_taller:
        col_pauta, col_ia = st.columns([1.5, 1])
        
        with col_pauta:
            st.markdown("#### Pauta de Mantención")
            pauta_actual = PAUTAS_MECANICAS.get(maq["categoria"], PAUTAS_MECANICAS["Maquinaria con Horómetro"])
            tareas_marcadas = [tarea for tarea in pauta_actual if st.checkbox(tarea, key=f"chk_{tarea}")]
            
            with st.expander("Finalizar y Liberar Máquina", expanded=True):
                mecanico = st.text_input("Mecánico responsable:", value="Taller Central")
                costo_rep = st.number_input("Costo de Repuestos ($ CLP):", min_value=0, step=1000)
                detalle_ot = st.text_area("Detalle de trabajos y repuestos:")
                
                if st.button("✅ Liberar a Patio (Pasar a VERDE)", use_container_width=True):
                    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    c.execute("UPDATE equipos SET uso_acumulado=0, estado_operativo='DISPONIBLE', falla_activa=0, ultima_observacion=?, fecha_actualizacion=? WHERE codigo=?", 
                              (f"Mantención OK: {detalle_ot}", ahora, maq["codigo"]))
                    c.execute("INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle) VALUES (?,?,?,?,?,?,?)",
                              (maq["codigo"], ahora, "MANTENCIÓN TALLER", mecanico, 0, costo_rep, detalle_ot))
                    conn.commit()
                    conn.close()
                    st.rerun()

        with col_ia:
            with st.container(border=True):
                st.markdown("#### 🤖 Consulta al Manual (IA)")
                st.caption(f"Pregunta sobre {maq['categoria']}.")
                duda = st.text_area("Ej: ¿Cómo calibrar el carburador?", height=100)
                
                if st.button("Consultar a Gemini", use_container_width=True):
                    if not api_key_gemini:
                        st.error("Por favor, ingresa tu API Key en la barra lateral.")
                    elif duda:
                        with st.spinner("Consultando manuales..."):
                            try:
                                from google import genai
                                cliente_ia = genai.Client(api_key=api_key_gemini)
                                prompt = f"Eres un mecánico experto en maquinaria pesada y ligera. Un colega te pregunta sobre una {maq['categoria']} (Modelo: {maq['nombre']}): {duda}. Responde de forma técnica, directa, paso a paso y en español chileno."
                                response = cliente_ia.models.generate_content(model="gemini-flash-latest", contents=prompt)
                                st.info(response.text)
                            except Exception as e:
                                st.error(f"Error de conexión con la IA: {e}")

    # 3. DESPACHO
    with tab_despacho:
        with st.container(border=True):
            st.markdown("#### Autorización de Salida")
            if "🔴" in estado_actual or "🟡" in estado_actual:
                st.error("⛔ ALERTA: Esta máquina requiere taller. Despachar bajo su propio riesgo.")
            cliente = st.text_input("Cliente / Obra destino:")
            
            if st.button("🚚 Registrar Salida (Pasar a AZUL)", use_container_width=True):
                if cliente:
                    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    c.execute("UPDATE equipos SET estado_operativo='ARRENDADA', ultima_observacion=?, fecha_actualizacion=? WHERE codigo=?", 
                              (f"Arrendada a: {cliente}", ahora, maq["codigo"]))
                    c.execute("INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle) VALUES (?,?,?,?,?,?,?)",
                              (maq["codigo"], ahora, "SALIDA", "Mesón", 0, 0, f"A cliente: {cliente}"))
                    conn.commit()
                    conn.close()
                    st.rerun()
                else:
                    st.warning("Falta indicar el cliente.")

    # 4. FORZAR ESTADO (ADMIN)
    with tab_admin:
        with st.container(border=True):
            st.markdown("#### ⚙️ Corrección Manual de Estado")
            st.caption("Usa esto solo si hubo un error de digitación. No suma historial de horas ni costos.")
            nuevo_estado_manual = st.selectbox("Selecciona el estado real del equipo:", ["DISPONIBLE", "EN_PANA", "ARRENDADA"])
            quitar_falla = st.checkbox("Remover bandera de falla/daño (Dejar máquina limpia)")
            
            if st.button("Aplicar Cambio Forzado"):
                falla_val = 0 if quitar_falla else maq["falla_activa"]
                if nuevo_estado_manual == "EN_PANA": falla_val = 1
                
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("UPDATE equipos SET estado_operativo=?, falla_activa=? WHERE codigo=?", (nuevo_estado_manual, falla_val, maq["codigo"]))
                conn.commit()
                conn.close()
                st.success("Estado corregido. Actualizando...")
                st.rerun()

    # 5. HISTORIAL
    with tab_hist:
        df_h = obtener_historial()
        st.dataframe(df_h[df_h["codigo_equipo"] == maq["codigo"]], use_container_width=True, hide_index=True)


# ==========================================
# MÓDULO 2: SEMÁFORO DE PATIO (VISTA FLOTA)
# ==========================================
elif modo_vista == "🚦 2. Semáforo de Flota":
    st.title("🚦 Vista de Patio y Semáforo")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🟢 Operativas", len(df_equipos[df_equipos["semaforo"].str.contains("🟢")]))
    c2.metric("🟡 Prevención", len(df_equipos[df_equipos["semaforo"].str.contains("🟡")]))
    c3.metric("🔴 En Pana", len(df_equipos[df_equipos["semaforo"].str.contains("🔴")]))
    c4.metric("🔵 En Terreno", len(df_equipos[df_equipos["semaforo"].str.contains("🔵")]))
    
    st.divider()
    f1, f2 = st.columns([1, 2])
    with f1:
        filtro_sem = st.multiselect("Filtrar Estado:", df_equipos["semaforo"].unique(), default=df_equipos["semaforo"].unique())
    with f2:
        busqueda = st.text_input("🔍 Buscar por Código o Nombre:")

    df_filt = df_equipos[df_equipos["semaforo"].isin(filtro_sem)]
    if busqueda:
        df_filt = df_filt[df_filt["codigo"].str.contains(busqueda, case=False) | df_filt["nombre"].str.contains(busqueda, case=False)]

    # Mostrar tabla con formato pulido
    st.dataframe(
        df_filt[["codigo", "nombre", "semaforo", "categoria", "uso_acumulado"]],
        use_container_width=True, hide_index=True
    )

# ==========================================
# MÓDULO 3: PANEL DEL DUEÑO (KPIs Y COSTOS)
# ==========================================
elif modo_vista == "📊 3. Panel Gerencial":
    st.title("📊 Rentabilidad y KPIs de Flota")
    df_hist = obtener_historial()
    
    try:
        disp = round(((len(df_equipos) - len(df_equipos[df_equipos["semaforo"].str.contains("🔴")])) / len(df_equipos)) * 100, 1)
    except:
        disp = 100
        
    gasto = df_hist["costo_repuestos"].sum()
    
    c1, c2 = st.columns(2)
    with c1:
        st.metric("🔧 Disponibilidad Mecánica (Target: >90%)", f"{disp}%")
        st.metric("💸 Gasto Acumulado Repuestos", f"${gasto:,.0f} CLP")
    
    with c2:
        if not df_hist.empty:
            costos_por_tipo = df_hist.groupby("tipo_evento")["costo_repuestos"].sum().reset_index()
            st.bar_chart(costos_por_tipo.set_index("tipo_evento"))
            
    st.download_button("📥 Exportar Todo el Historial (CSV)", data=df_hist.to_csv(index=False).encode("utf-8"), file_name="kpi_rental.csv")

# ==========================================
# MÓDULO 4: AGREGAR NUEVA MÁQUINA
# ==========================================
elif modo_vista == "➕ 4. Enrolar Máquina":
    st.title("➕ Enrolar Equipo y Generar NFC")
    with st.container(border=True):
        with st.form("nuevo_equipo"):
            c1, c2 = st.columns(2)
            with c1:
                nuevo_cod = st.text_input("Código Interno (Ej: ORB-05):").upper().strip()
                nuevo_nom = st.text_input("Modelo/Descripción:")
                nueva_cat = st.selectbox("Pauta Técnica:", list(PAUTAS_MECANICAS.keys()))
            with c2:
                nuevo_tipo = st.selectbox("Control por:", ["DIAS", "HORAS"])
                nuevo_lim = st.number_input("Límite Preventivo:", min_value=1, value=15)
                nueva_ubic = st.text_input("Ubicación física del Tag NFC:")
                
            if st.form_submit_button("Crear y Generar Link NFC", type="primary"):
                if nuevo_cod and nuevo_nom:
                    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO equipos VALUES (?,?,?,?,?,0,?,0,'DISPONIBLE',0,'Recién enrolada.',?)",
                                  (nuevo_cod, nuevo_nom, nueva_cat, nueva_ubic, nuevo_tipo, nuevo_lim, ahora))
                        conn.commit()
                        st.success(f"✅ Equipo {nuevo_cod} enrolado correctamente.")
                        st.code(f"https://TU-APP.streamlit.app/?equipo={nuevo_cod}", language="markdown")
                    except sqlite3.IntegrityError:
                        st.error("❌ Código ya existe.")
                    finally:
                        conn.close()