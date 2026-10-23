import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

# ==========================================
# 1. CONFIGURACIÓN Y CONSTANTES
# ==========================================
st.set_page_config(page_title="Rental Valdivia", page_icon="🚜", layout="wide")

st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { border-radius: 6px 6px 0px 0px; }
    </style>
""", unsafe_allow_html=True)

DB_NAME = "rental_valdivia.db"

PAUTAS_MECANICAS = {
    "Cortadora Orbital": ["Revisión de carbones", "Holgura en cabezal", "Estado de portadisco", "Engrase"],
    "Unidad Motriz": ["Cambio de aceite (15W-40)", "Filtro de aire", "Acoples y mangueras", "Prueba de presión"],
    "Placa Compactadora": ["Tensión de correa", "Nivel de aceite", "Gomas amortiguadoras", "Limpieza carburador"],
    "Maquinaria con Horómetro": ["Aceite y filtros", "Sistema hidráulico", "Engrase general", "Batería"]
}

# ==========================================
# 2. CAPA DE BASE DE DATOS (BACKEND)
# ==========================================
# Lección de código: Usar 'with' asegura que la DB se cierre sola, evitando fugas de memoria.
def inicializar_db():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS equipos (
                codigo TEXT PRIMARY KEY,
                nombre TEXT, categoria TEXT, ubicacion_nfc TEXT, tipo_medicion TEXT,
                uso_acumulado INTEGER, limite_mantencion INTEGER, horometro_actual INTEGER,
                estado_operativo TEXT, falla_activa INTEGER, ultima_observacion TEXT, fecha_actualizacion TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS historial (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_equipo TEXT, fecha TEXT, tipo_evento TEXT, responsable TEXT,
                uso_sumado INTEGER, costo_repuestos INTEGER, detalle TEXT
            )
        """)
        
        # Insertar datos de prueba solo si está vacía
        c.execute("SELECT COUNT(*) FROM equipos")
        if c.fetchone()[0] == 0:
            equipos_demo = [
                ("ORB-01", "Cortadora Orbital Tubos", "Cortadora Orbital", "Base", "DIAS", 14, 15, 0, "DISPONIBLE", 0, "Operativa.", "2026-10-15"),
                ("MOT-07", "Unidad Motriz Honda", "Unidad Motriz", "Filtro", "DIAS", 8, 20, 0, "EN_PANA", 1, "Pierde presión.", "2026-10-19")
            ]
            c.executemany("INSERT INTO equipos VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", equipos_demo)
            conn.commit()

def obtener_datos(tabla):
    """Función genérica para leer tablas usando Pandas."""
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql_query(f"SELECT * FROM {tabla}", conn)

def actualizar_estado_bd(codigo, estado, falla, nota, ahora, evento):
    """Actualiza la máquina y guarda el historial en una sola transacción."""
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE equipos SET estado_operativo=?, falla_activa=?, ultima_observacion=?, fecha_actualizacion=? WHERE codigo=?", 
                  (estado, falla, nota, ahora, codigo))
        c.execute("INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, detalle) VALUES (?,?,?,?,?)",
                  (codigo, ahora, evento, "Usuario App", nota))
        conn.commit()

# ==========================================
# 3. LÓGICA DE NEGOCIO
# ==========================================
def calcular_semaforo(fila):
    if fila["falla_activa"] == 1 or fila["estado_operativo"] == "EN_PANA":
        return "🔴 EN PANA"
    elif fila["uso_acumulado"] >= fila["limite_mantencion"]:
        return "🟡 PIDE MANTENCIÓN"
    elif fila["estado_operativo"] == "ARRENDADA":
        return "🔵 EN TERRENO"
    else:
        return "🟢 DISPONIBLE"

def revisar_alertas_flota(df):
    """Muestra un toast emergente si alguna máquina está cerca del límite."""
    for _, maq in df.iterrows():
        limite = maq["limite_mantencion"]
        uso = maq["uso_acumulado"]
        # Alerta si está al 90% o más de su uso permitido
        if uso > 0 and uso >= (limite * 0.9) and maq["estado_operativo"] != "EN_PANA":
            st.toast(f"⚠️ Alerta preventiva: {maq['codigo']} está muy cerca de su mantención.", icon="🔧")

# ==========================================
# 4. COMPONENTES VISUALES (FRONTEND)
# ==========================================
def mostrar_ficha(df_equipos):
    codigo_seleccionado = st.session_state.equipo_seleccionado
    
    if not codigo_seleccionado or codigo_seleccionado not in df_equipos['codigo'].values:
        st.info("Selecciona un equipo en la barra lateral.")
        return
        
    maq = df_equipos[df_equipos["codigo"] == codigo_seleccionado].iloc[0]
    
    st.title(f"{maq['nombre']}")
    st.caption(f"Código: {maq['codigo']} | Categoría: {maq['categoria']}")
    
    # Métricas
    c1, c2, c3 = st.columns(3)
    c1.metric("Estado", maq["semaforo"].split(" ", 1)[1])
    c2.metric("Desgaste", f"{maq['uso_acumulado']} / {maq['limite_mantencion']}")
    c3.metric("Ubicación Tag", maq['ubicacion_nfc'])
    
    progreso = min(int((maq["uso_acumulado"] / maq["limite_mantencion"]) * 100), 100)
    st.progress(progreso / 100, text=f"Desgaste: {progreso}%")
    st.divider()
    
    # Formulario rápido de estado
    st.subheader("⚡ Acción Rápida")
    c_f1, c_f2 = st.columns([2, 1])
    with c_f1:
        nuevo_estado = st.radio("Cambiar estado a:", ["DISPONIBLE", "ARRENDADA", "EN_PANA"], horizontal=True)
        nota = st.text_input("Nota breve:")
    with c_f2:
        st.write("") 
        st.write("")
        if st.button("Actualizar", type="primary", use_container_width=True):
            falla = 1 if nuevo_estado == "EN_PANA" else 0
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
            actualizar_estado_bd(maq["codigo"], nuevo_estado, falla, nota, ahora, "CAMBIO RÁPIDO")
            st.success("Estado actualizado")
            st.rerun()

def mostrar_semaforo(df_equipos):
    st.title("🚦 Estado de la Flota")
    filtro = st.radio("Filtro:", ["Todos", "🟢 Disponibles", "🔴 En Pana", "🔵 En Terreno"], horizontal=True)
    
    if filtro != "Todos":
        emoji = filtro.split(" ")[0]
        df_mostrar = df_equipos[df_equipos["semaforo"].str.contains(emoji)]
    else:
        df_mostrar = df_equipos
        
    st.dataframe(df_mostrar[["codigo", "nombre", "semaforo", "categoria"]], use_container_width=True, hide_index=True)

# ==========================================
# 5. CONTROLADOR PRINCIPAL (APP)
# ==========================================
def main():
    inicializar_db()
    df_equipos = obtener_datos("equipos")
    df_equipos["semaforo"] = df_equipos.apply(calcular_semaforo, axis=1)
    
    revisar_alertas_flota(df_equipos) # Activa notificaciones proactivas
    
    # --- Gestión de Memoria (Session State) ---
    if "vista_actual" not in st.session_state:
        st.session_state.vista_actual = "📱 Ficha"
    if "equipo_seleccionado" not in st.session_state:
        st.session_state.equipo_seleccionado = df_equipos["codigo"].iloc[0] if not df_equipos.empty else None

    # --- Barra Lateral ---
    with st.sidebar:
        st.title("🚜 Rental Valdivia")
        
        # Guardamos la vista seleccionada en la memoria
        st.session_state.vista_actual = st.radio(
            "Navegación:", 
            ["📱 Ficha", "🚦 Flota", "📊 Historial"],
            index=["📱 Ficha", "🚦 Flota", "📊 Historial"].index(st.session_state.vista_actual)
        )
        
        st.divider()
        lista_cod = df_equipos["codigo"].tolist()
        if lista_cod:
            idx_default = lista_cod.index(st.session_state.equipo_seleccionado) if st.session_state.equipo_seleccionado in lista_cod else 0

            # Guardamos el equipo seleccionado en la memoria
            st.session_state.equipo_seleccionado = st.selectbox("Simular NFC:", lista_cod, index=idx_default)
        else:
            st.session_state.equipo_seleccionado = None
            st.caption("No hay equipos registrados.")

    # --- Enrutador de Pantallas ---
    if st.session_state.vista_actual == "📱 Ficha":
        mostrar_ficha(df_equipos)
    elif st.session_state.vista_actual == "🚦 Flota":
        mostrar_semaforo(df_equipos)
    elif st.session_state.vista_actual == "📊 Historial":
        st.title("Historial de Movimientos")
        st.dataframe(obtener_datos("historial"), use_container_width=True, hide_index=True)

# Esto le dice a Python que inicie el programa ejecutando la función main()
if __name__ == "__main__":
    main()