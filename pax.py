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

# Diseño minimalista: solo ajustes suaves, eliminamos el fondo problemático de stMetric
st.markdown("""
    <style>
    /* Suaviza los bordes de las pestañas sin romper el modo oscuro/claro */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { border-radius: 6px 6px 0px 0px; }
    </style>
""", unsafe_allow_html=True)

DB_NAME = "rental_valdivia.db"

PAUTAS_MECANICAS = {
    "Cortadora Orbital": [
        "Revisión y limpieza de carbones",
        "Inspección de holgura en cabezal",
        "Verificación de estado de portadisco",
        "Engrase general de husillo"
    ],
    "Unidad Motriz": [
        "Cambio de aceite de motor (15W-40)",
        "Limpieza o reemplazo de filtro de aire",
        "Inspección de acoples y mangueras",
        "Prueba de presión de trabajo"
    ],
    "Placa Compactadora": [
        "Revisión de tensión de correa",
        "Verificación de nivel de aceite",
        "Inspección de gomas amortiguadoras",
        "Limpieza de carburador"
    ],
    "Maquinaria con Horómetro": [
        "Cambio de aceite y filtros",
        "Revisión de sistema hidráulico",
        "Engrase de pasadores y bujes",
        "Verificación de batería"
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
            ("ORB-01", "Cortadora Orbital Tubos", "Cortadora Orbital", "Base mordaza", "DIAS", 14, 15, 0, "DISPONIBLE", 0, "Operativa.", "2026-10-15 09:30"),
            ("MOT-07", "Unidad Motriz Honda", "Unidad Motriz", "Filtro de aire", "DIAS", 8, 20, 0, "EN_PANA", 1, "Pérdida de presión.", "2026-10-19 11:20"),
            ("EXC-02", "Miniexcavadora Yanmar", "Maquinaria con Horómetro", "Cabina izq.", "HORAS", 245, 250, 1495, "DISPONIBLE", 0, "Lista.", "2026-10-18 16:40")
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
        return "🔴 EN PANA"
    elif fila["uso_acumulado"] >= fila["limite_mantencion"]:
        return "🟡 PIDE MANTENCIÓN"
    elif fila["estado_operativo"] == "ARRENDADA":
        return "🔵 EN TERRENO"
    else:
        return "🟢 DISPONIBLE"

def obtener_gemini_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except:
        return os.environ.get("GEMINI_API_KEY", "")

inicializar_db()
df_equipos = obtener_equipos()
df_equipos["semaforo"] = df_equipos.apply(calcular_semaforo, axis=1)

# ==========================================
# 3. BARRA LATERAL (Navegación Limpia)
# ==========================================
params = st.query_params
equipo_url = params.get("equipo", None)

with st.sidebar:
    st.title("🚜 Rental Valdivia")
    st.caption("Control minimalista de flota")
    
    modo_vista = st.radio(
        "Menú Principal:",
        ["📱 Ficha de Equipo", "🚦 Estado de Flota", "📊 Panel de Control", "➕ Nuevo Equipo"]
    )
    
    st.divider()
    lista_codigos = df_equipos["codigo"].tolist()
    indice_default = lista_codigos.index(equipo_url) if equipo_url in lista_codigos else 0
    equipo_seleccionado = st.selectbox("Simular lectura NFC:", lista_codigos, index=indice_default)

    api_key_gemini = st.text_input("API Key (Opcional para IA):", value=obtener_gemini_key(), type="password")

# ==========================================
# MÓDULO 1: FICHA Y ACCIÓN RÁPIDA (Minimalista)
# ==========================================
if modo_vista == "📱 Ficha de Equipo":
    maq = df_equipos[df_equipos["codigo"] == equipo_seleccionado].iloc[0]
    unidad = "días" if maq["tipo_medicion"] == "DIAS" else "hrs"
    estado_actual = maq["semaforo"]
    
    st.title(f"{maq['nombre']}")
    st.caption(f"Código: {maq['codigo']} | Categoría: {maq['categoria']}")
    
    # KPIs visuales y limpios
    col1, col2, col3 = st.columns(3)
    col1.metric("Estado Actual", estado_actual.split(" ", 1)[1])
    col2.metric(f"Desgaste ({unidad})", f"{maq['uso_acumulado']} / {maq['limite_mantencion']}")
    if maq["tipo_medicion"] == "HORAS":
        col3.metric("Horómetro", f"{maq['horometro_actual']} hrs")
    else:
        col3.metric("Ubicación NFC", maq['ubicacion_nfc'])

    porcentaje = min(int((maq["uso_acumulado"] / maq["limite_mantencion"]) * 100), 100)
    st.progress(porcentaje / 100, text="Desgaste hacia mantención preventiva")
    st.divider()

    # --- SECCIÓN SIMPLE PARA CAMBIAR EL ESTADO ---
    st.subheader("⚡ Acción Rápida")
    st.markdown("Cambia el estado del equipo al instante sin papeleo.")
    
    c_form1, c_form2 = st.columns([2, 1])
    with c_form1:
        nuevo_estado_rapido = st.radio(
            "Selecciona el nuevo estado:",
            ["DISPONIBLE", "ARRENDADA", "EN_PANA"],
            horizontal=True,
            index=["DISPONIBLE", "ARRENDADA", "EN_PANA"].index(maq["estado_operativo"]) if maq["estado_operativo"] in ["DISPONIBLE", "ARRENDADA", "EN_PANA"] else 0
        )
        nota_rapida = st.text_input("Nota breve (Opcional):", placeholder="Ej: Entregada a cliente, llegó sucia, etc.")
    
    with c_form2:
        st.write("") # Espaciado
        st.write("")
        if st.button("Actualizar Estado", type="primary", use_container_width=True):
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
            falla = 1 if nuevo_estado_rapido == "EN_PANA" else 0
            nota_final = nota_rapida if nota_rapida else f"Cambiado a {nuevo_estado_rapido}"
            
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("UPDATE equipos SET estado_operativo=?, falla_activa=?, ultima_observacion=?, fecha_actualizacion=? WHERE codigo=?", 
                      (nuevo_estado_rapido, falla, nota_final, ahora, maq["codigo"]))
            c.execute("INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, detalle) VALUES (?,?,?,?,?)",
                      (maq["codigo"], ahora, "CAMBIO RÁPIDO", "Operador", nota_final))
            conn.commit()
            conn.close()
            st.success("¡Estado actualizado!")
            st.rerun()

    # --- OPCIONES AVANZADAS (Ocultas por defecto para mantener minimalismo) ---
    st.write("")
    with st.expander("🛠️ Registro Detallado (Taller, Recepción con Horómetro e IA)"):
        tab1, tab2 = st.tabs(["Recepción y Taller", "Asistente Mecánico IA"])
        
        with tab1:
            st.markdown("**Registrar uso y gastos**")
            uso_extra = st.number_input(f"Sumar uso ({unidad}):", min_value=0, value=0)
            costo_rep = st.number_input("Costo de mantención ($):", min_value=0, step=5000)
            resetear_uso = st.checkbox("Reiniciar desgaste a cero (Mantención realizada)")
            
            if st.button("Guardar Registro Avanzado"):
                ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                nuevo_uso = 0 if resetear_uso else int(maq["uso_acumulado"]) + uso_extra
                
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                c.execute("UPDATE equipos SET uso_acumulado=?, fecha_actualizacion=? WHERE codigo=?", 
                          (nuevo_uso, ahora, maq["codigo"]))
                c.execute("INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle) VALUES (?,?,?,?,?,?,?)",
                          (maq["codigo"], ahora, "MANTENCIÓN AVANZADA", "Taller", uso_extra, costo_rep, "Registro detallado"))
                conn.commit()
                conn.close()
                st.success("Guardado correctamente.")
                st.rerun()

        with tab2:
            st.markdown(f"**Consulta sobre {maq['categoria']}**")
            duda = st.text_area("Ej: ¿Cómo revisar los carbones?")
            if st.button("Preguntar a IA"):
                if not api_key_gemini:
                    st.error("Falta la API Key de Gemini (pégala en la barra lateral o configura el Secret).")
                elif not duda.strip():
                    st.warning("Escribe primero la pregunta.")
                else:
                    try:
                        from google import genai
                        cliente_ia = genai.Client(api_key=api_key_gemini)
                        prompt = f"Un mecánico pregunta sobre una {maq['categoria']}: {duda}. Responde breve, paso a paso."
                        response = cliente_ia.models.generate_content(model="gemini-flash-latest", contents=prompt)
                        st.info(response.text)
                    except Exception as e:
                        st.error("Error con la IA. Verifica tu API Key.")

# ==========================================
# MÓDULO 2: SEMÁFORO (Vista limpia)
# ==========================================
elif modo_vista == "🚦 Estado de Flota":
    st.title("Estado de la Flota")
    
    # Filtros simples
    filtro = st.radio("Filtro rápido:", ["Todos", "🟢 Disponibles", "🔴 En Pana / Taller", "🔵 En Terreno"], horizontal=True)
    
    if filtro != "Todos":
        emoji = filtro.split(" ")[0]
        df_mostrar = df_equipos[df_equipos["semaforo"].str.contains(emoji)]
    else:
        df_mostrar = df_equipos

    # Tabla sin fondo ni distracciones
    st.dataframe(
        df_mostrar[["codigo", "nombre", "semaforo", "categoria"]],
        use_container_width=True, 
        hide_index=True
    )

# ==========================================
# MÓDULO 3 y 4: Mantenidos y Simplificados
# ==========================================
elif modo_vista == "📊 Panel de Control":
    st.title("KPIs y Rentabilidad")
    df_hist = obtener_historial()
    gasto = df_hist["costo_repuestos"].sum() if "costo_repuestos" in df_hist.columns else 0
    
    st.metric("Gasto Total en Repuestos", f"${gasto:,.0f} CLP")
    st.dataframe(df_hist, use_container_width=True, hide_index=True)

elif modo_vista == "➕ Nuevo Equipo":
    st.title("Registrar Nueva Maquinaria")
    with st.form("nuevo_equipo", border=False):
        c1, c2 = st.columns(2)
        with c1:
            nuevo_cod = st.text_input("Código (Ej: EXC-05):").upper()
            nuevo_nom = st.text_input("Modelo:")
        with c2:
            nueva_cat = st.selectbox("Categoría:", list(PAUTAS_MECANICAS.keys()))
            nuevo_lim = st.number_input("Límite Uso Preventivo:", min_value=1, value=15)
            
        if st.form_submit_button("Guardar Equipo", type="primary"):
            if nuevo_cod and nuevo_nom:
                ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO equipos VALUES (?,?,?,?, 'DIAS', 0, ?, 0, 'DISPONIBLE', 0, 'Nuevo', ?)",
                              (nuevo_cod, nuevo_nom, nueva_cat, "Pendiente", nuevo_lim, ahora))
                    conn.commit()
                    st.success(f"Equipo {nuevo_cod} agregado.")
                except sqlite3.IntegrityError:
                    st.error("El código ya existe.")
                finally:
                    conn.close()