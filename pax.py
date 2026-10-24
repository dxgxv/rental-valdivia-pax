import streamlit as st
import sqlite3
import pandas as pd
import os
from datetime import datetime

# Importación segura de Gemini para evitar que la app falle si no está instalada la librería
# LECCIÓN DE CÓDIGO: la librería 'google.generativeai' es la ANTIGUA y ya no está instalada.
# La actual se llama 'google-genai' y se importa como 'google.genai'.
try:
    from google import genai
    GEMINI_INSTALLED = True
except ImportError:
    GEMINI_INSTALLED = False

# ==========================================
# 1. CONFIGURACIÓN GENERAL DE LA APLICACIÓN
# ==========================================
st.set_page_config(
    page_title="Rental Valdivia - Control de Flota NFC",
    page_icon="🚜",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS para mejorar la interfaz visual tipo Dashboard Industrial
st.markdown("""
    <style>
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px 6px 0px 0px;
        padding: 10px 18px;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

DB_NAME = "rental_valdivia.db"

# Pautas mecánicas completas originales (Intocables)
PAUTAS_MECANICAS = {
    "Cortadora Orbital": [
        "Revisión y limpieza de carbones del motor eléctrico",
        "Inspección de holgura en cabezal giratorio y mordazas de sujeción",
        "Verificación de estado de portadisco y seguro de traba",
        "Revisión de cableado blindado y enchufe industrial (Legrand/Mennekes)",
        "Engrase general de husillo y puntos móviles"
    ],
    "Unidad Motriz": [
        "Cambio de aceite de motor (15W-40) y revisión de fugas",
        "Verificación de nivel y estado de aceite hidráulico / retorno",
        "Limpieza o reemplazo de filtro de aire y revisión de bujía",
        "Inspección de acoples rápidos hidráulicos (QDC) y mangueras de alta presión",
        "Prueba de presión de trabajo y encendido en frío"
    ],
    "Placa Compactadora": [
        "Revisión de tensión y desgaste de correa centrífuga (embrague)",
        "Verificación de nivel de aceite en unidad vibradora (excitador)",
        "Inspección de silentblocks (gomas amortiguadoras) y chasis",
        "Limpieza de carburador y filtro de combustible",
        "Ajuste de piola de aceleración y parada de emergencia"
    ],
    "Maquinaria con Horómetro": [
        "Cambio de aceite de motor y filtro primario/secundario",
        "Revisión de sistema hidráulico, cilindros y sellos",
        "Inspección de filtros de aire (primario y seguridad) y separador de agua",
        "Engrase de pasadores, bujes y corona de giro",
        "Verificación de sistema eléctrico, alternador y batería"
    ]
}

# ==========================================
# 2. BASE DE DATOS LOCAL (SQLite)
# ==========================================
def inicializar_db(forzar_reinicio=False):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    if forzar_reinicio:
        c.execute("DROP TABLE IF EXISTS equipos")
        c.execute("DROP TABLE IF EXISTS historial")
    
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
            ("ORB-02", "Cortadora Orbital Alta Carga", "Cortadora Orbital", "Chasis inferior protegido", "DIAS", 16, 15, 0, "DISPONIBLE", 0, "Superó límite de 15 días de arriendo.", "2026-10-18 17:15"),
            ("MOT-04", "Unidad Motriz Hidráulica 18 HP", "Unidad Motriz", "Ángulo interno jaula tubular", "DIAS", 22, 20, 0, "DISPONIBLE", 0, "Pide cambio de aceite y revisión de acoples.", "2026-10-17 18:00"),
            ("MOT-07", "Unidad Motriz Bencinera Honda", "Unidad Motriz", "Tras soporte filtro de aire", "DIAS", 8, 20, 0, "EN_PANA", 1, "Cliente reporta pérdida de presión en manguera.", "2026-10-19 11:20"),
            ("PLC-12", "Placa Compactadora Reversible 160kg", "Placa Compactadora", "Base interior manillar", "DIAS", 5, 15, 0, "DISPONIBLE", 0, "Mantención recién hecha. Correa nueva.", "2026-10-16 12:00"),
            ("EXC-02", "Miniexcavadora Yanmar ViO35", "Maquinaria con Horómetro", "Marco interior cabina izq.", "HORAS", 245, 250, 1495, "DISPONIBLE", 0, "Quedan 5 hrs para pauta de 1.500 hrs.", "2026-10-18 16:40"),
            ("GEN-08", "Generador Insonorizado 40 kVA", "Maquinaria con Horómetro", "Interior puerta panel control", "HORAS", 80, 250, 3080, "ARRENDADA", 0, "En faena forestal Camino a Niebla.", "2026-10-14 08:30")
        ]
        c.executemany("INSERT INTO equipos VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", equipos_demo)
        
        historial_demo = [
            ("MOT-07", "2026-10-19 11:20", "RECEPCIÓN CON FALLA", "Bodega Patio", 4, 0, "Llegó con fuga en acople rápido hembra. Se bloquea equipo."),
            ("PLC-12", "2026-10-16 12:00", "MANTENCIÓN TALLER", "Mecánico Juan P.", 0, 28500, "Cambio de correa centrífuga y aceite de excitador."),
            ("MOT-04", "2026-10-17 18:00", "RECEPCIÓN NORMAL", "Bodega Patio", 6, 0, "Vuelve de faena en Paillaco sin daños visibles.")
        ]
        c.executemany("INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle) VALUES (?,?,?,?,?,?,?)", historial_demo)
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

# Inicializar Base de Datos y cargar DataFrames
inicializar_db()
df_equipos = obtener_equipos()

# LECCIÓN DE CÓDIGO: si alguna celda llegó vacía (NULL) desde SQLite, Pandas la deja como NA
# y eso revienta los int() y las comparaciones del semáforo. Sanamos el DataFrame una sola vez.
if not df_equipos.empty:
    for col_num in ["uso_acumulado", "horometro_actual", "falla_activa"]:
        df_equipos[col_num] = pd.to_numeric(df_equipos[col_num], errors="coerce").fillna(0).astype(int)
    # El límite nunca puede ser 0 porque se usa para dividir el porcentaje de desgaste.
    df_equipos["limite_mantencion"] = pd.to_numeric(df_equipos["limite_mantencion"], errors="coerce").fillna(1).astype(int).clip(lower=1)
    for col_txt in ["ultima_observacion", "nombre", "categoria", "ubicacion_nfc", "estado_operativo", "tipo_medicion", "fecha_actualizacion"]:
        df_equipos[col_txt] = df_equipos[col_txt].fillna("").astype(str)

df_equipos["semaforo"] = df_equipos.apply(calcular_semaforo, axis=1)

def obtener_gemini_key():
    """Lee la clave desde .streamlit/secrets.toml (nube) o desde una variable de entorno (PC)."""
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.environ.get("GEMINI_API_KEY", "")

# ==========================================
# 3. LECTURA AUTOMÁTICA DE CHIP NFC (URL) Y ESTADO DE SESIÓN
# ==========================================
params = st.query_params
equipo_url = params.get("equipo", None)

lista_codigos = df_equipos["codigo"].tolist()

# Gestión de estado para poder saltar de un módulo a otro interactivamente
if "modulo_activo" not in st.session_state:
    st.session_state.modulo_activo = "📱 1. Escáner NFC / Ficha Taller"

if "equipo_activo" not in st.session_state:
    if equipo_url in lista_codigos:
        st.session_state.equipo_activo = equipo_url
    else:
        st.session_state.equipo_activo = lista_codigos[0] if lista_codigos else None

# Si el usuario entra con un parámetro URL nuevo, priorizarlo
if equipo_url in lista_codigos and st.session_state.get("ultimo_url") != equipo_url:
    st.session_state.equipo_activo = equipo_url
    st.session_state.ultimo_url = equipo_url
    st.session_state.modulo_activo = "📱 1. Escáner NFC / Ficha Taller"

# ==========================================
# 4. BARRA LATERAL Y NAVEGACIÓN
# ==========================================
st.sidebar.title("🚜 Rental Valdivia")
st.sidebar.caption("Sistema de Control NFC & Mantención Preventiva")

opciones_menu = [
    "📱 1. Escáner NFC / Ficha Taller",
    "🚦 2. Semáforo de Patio (Flota)",
    "📊 3. Panel del Dueño (KPIs)",
    "➕ 4. Agregar Máquina / Tag NFC"
]

modo_vista = st.sidebar.radio(
    "Selecciona Módulo:",
    opciones_menu,
    index=opciones_menu.index(st.session_state.modulo_activo)
)
st.session_state.modulo_activo = modo_vista

st.sidebar.divider()
st.sidebar.markdown("### 💡 Simulador de Chip NFC")

if lista_codigos:
    idx_actual = lista_codigos.index(st.session_state.equipo_activo) if st.session_state.equipo_activo in lista_codigos else 0
    equipo_seleccionado = st.sidebar.selectbox(
        "Máquina escaneada:",
        lista_codigos,
        index=idx_actual,
        help="Simula haber acercado el teléfono al Tag NFC de esta máquina."
    )
    st.session_state.equipo_activo = equipo_seleccionado
else:
    equipo_seleccionado = None

st.sidebar.divider()
st.sidebar.markdown("### 🤖 Configuración IA Taller")
api_key_gemini = st.sidebar.text_input(
    "API Key de Google Gemini:",
    value=obtener_gemini_key(),
    type="password",
    help="Pega tu clave de Google AI Studio para habilitar el asistente de diagnóstico mecánico. Si ya la tienes en secrets.toml, aparece cargada."
)
if not GEMINI_INSTALLED:
    st.sidebar.caption("⚠️ Librería `google-genai` no instalada. Ejecuta `pip install google-genai` para usar IA.")

with st.sidebar.expander("🛠️ Opciones de Prueba (Sandbox)"):
    st.caption("¿Estuviste haciendo pruebas y quieres volver a los 7 equipos originales de fábrica?")
    # LECCIÓN DE CÓDIGO: este botón BORRA la base de datos real (equipos e historial).
    # Se pide confirmación explícita para no perder los datos de la empresa con un clic.
    confirmar_reset = st.checkbox("Entiendo que se BORRARÁN todos los equipos e historiales.")
    if st.button("🔄 Restaurar Datos de Fábrica", disabled=not confirmar_reset, use_container_width=True):
        inicializar_db(forzar_reinicio=True)
        st.success("Base de datos restaurada al estado original.")
        st.rerun()

# ==========================================
# MÓDULO 1: ESCÁNER NFC Y OPERACIÓN EN PATIO
# ==========================================
if modo_vista == "📱 1. Escáner NFC / Ficha Taller":
    if not equipo_seleccionado:
        st.warning("No hay equipos registrados en el sistema.")
    else:
        maq = df_equipos[df_equipos["codigo"] == equipo_seleccionado].iloc[0]
        unidad = "días acumulados" if maq["tipo_medicion"] == "DIAS" else "horas desde última mant."
        
        st.title(f"🔧 {maq['codigo']} — {maq['nombre']}")
        st.caption(f"📍 **Ubicación física del Chip NFC:** {maq['ubicacion_nfc']}  |  **Categoría:** {maq['categoria']}  |  🔗 **URL Chip:** `?equipo={maq['codigo']}`")

        # Tarjeta principal de estado y métricas
        with st.container(border=True):
            estado_actual = maq["semaforo"]
            if "🔴" in estado_actual:
                st.error(f"### {estado_actual}\n**Motivo / Última nota:** {maq['ultima_observacion']} *(PROHIBIDO ENTREGAR A CLIENTE)*")
            elif "🟡" in estado_actual:
                st.warning(f"### {estado_actual}\n**Desgaste acumulado:** {maq['uso_acumulado']} de {maq['limite_mantencion']} {unidad}. Requiere paso por taller antes de volver a salir.")
            elif "🔵" in estado_actual:
                st.info(f"### {estado_actual}\n**Nota:** {maq['ultima_observacion']}")
            else:
                st.success(f"### {estado_actual}\n**Desgaste acumulado:** {maq['uso_acumulado']} de {maq['limite_mantencion']} {unidad}. Máquina autorizada para despacho.")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Uso Acumulado (Ciclo)", f"{maq['uso_acumulado']} {maq['tipo_medicion'].lower()}", f"Límite: {maq['limite_mantencion']}")
            porcentaje_desgaste = min(int((maq["uso_acumulado"] / maq["limite_mantencion"]) * 100), 100) if maq["limite_mantencion"] > 0 else 0
            col2.metric("Nivel de Desgaste Preventivo", f"{porcentaje_desgaste}%")
            col3.metric("Horómetro Motor", f"{maq['horometro_actual']} hrs" if maq["tipo_medicion"] == "HORAS" else "Sin Horómetro (Por Días)")
            col4.metric("Última Actualización", maq["fecha_actualizacion"])
            
            st.progress(porcentaje_desgaste / 100, text=f"Progreso hacia mantención preventiva ({porcentaje_desgaste}%)")

        st.write("") # Espaciador visual

        # LAS 5 PESTAÑAS OPERATIVAS COMPLETAS
        tab_recepcion, tab_taller, tab_despacho, tab_forzar, tab_hist = st.tabs([
            "📥 1. Recepción de Arriendo (Patio)",
            "🛠️ 2. Liberación de Taller + IA (Mecánico)",
            "🚚 3. Salida a Arriendo",
            "⚙️ 4. Cambiar Estado Manual",
            "📋 5. Historial del Equipo"
        ])

        # --- PESTAÑA 1: RECEPCIÓN ---
        with tab_recepcion:
            with st.container(border=True):
                st.subheader("Recepción rápida al bajar de la camioneta")
                with st.form("form_recepcion"):
                    c1, c2 = st.columns(2)
                    with c1:
                        responsable_rec = st.text_input("Nombre de quien recibe:", value="Encargado de Patio")
                        if maq["tipo_medicion"] == "DIAS":
                            uso_nuevo = st.number_input("¿Cuántos días estuvo arrendada en faena?", min_value=1, max_value=365, value=3)
                            nuevo_horometro = 0
                        else:
                            nuevo_horometro = st.number_input(
                                f"Ingresa Horómetro actual (Anterior: {maq['horometro_actual']} hrs):",
                                min_value=int(maq["horometro_actual"]),
                                value=int(maq["horometro_actual"]) + 15
                            )
                            uso_nuevo = nuevo_horometro - int(maq["horometro_actual"])
                        
                        llego_con_falla = st.checkbox("⚠️ ¿Llegó con falla mecánica, golpe o piezas faltantes?")
                    
                    with c2:
                        obs_recepcion = st.text_area("Observaciones de llegada (estado de cables, mangueras, disco, etc.):")
                        foto_evidencia = st.file_uploader("📸 Adjuntar foto de respaldo (si viene con daño del cliente):", type=["jpg", "png", "jpeg"])

                    guardar_rec = st.form_submit_button("💾 Guardar Recepción y Actualizar Semáforo", type="primary", use_container_width=True)
                    
                    if guardar_rec:
                        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                        nuevo_uso_acum = int(maq["uso_acumulado"]) + int(uso_nuevo)
                        nuevo_estado = "EN_PANA" if llego_con_falla else "DISPONIBLE"
                        falla_flag = 1 if llego_con_falla else int(maq["falla_activa"])
                        horometro_final = nuevo_horometro if maq["tipo_medicion"] == "HORAS" else int(maq["horometro_actual"])
                        
                        nota_final = obs_recepcion.strip() if obs_recepcion.strip() else f"Recepción normal (+{uso_nuevo} {maq['tipo_medicion'].lower()})."
                        if foto_evidencia is not None:
                            nota_final += f" [📸 Foto de daño guardada: {foto_evidencia.name}]"

                        conn = sqlite3.connect(DB_NAME)
                        c = conn.cursor()
                        c.execute("""
                            UPDATE equipos 
                            SET uso_acumulado=?, horometro_actual=?, estado_operativo=?, falla_activa=?, ultima_observacion=?, fecha_actualizacion=?
                            WHERE codigo=?
                        """, (nuevo_uso_acum, horometro_final, nuevo_estado, falla_flag, nota_final, ahora, maq["codigo"]))
                        
                        tipo_ev = "RECEPCIÓN CON FALLA" if llego_con_falla else "RECEPCIÓN NORMAL"
                        c.execute("""
                            INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle)
                            VALUES (?,?,?,?,?,?,?)
                        """, (maq["codigo"], ahora, tipo_ev, responsable_rec, uso_nuevo, 0, nota_final))
                        conn.commit()
                        conn.close()
                        st.success("✅ Recepción registrada correctamente.")
                        st.rerun()

        # --- PESTAÑA 2: TALLER + ASISTENTE IA GEMINI ---
        with tab_taller:
            col_pauta, col_ia = st.columns([1.3, 1])
            
            with col_pauta:
                with st.container(border=True):
                    st.subheader(f"Pauta de Mantención — {maq['categoria']}")
                    pauta_actual = PAUTAS_MECANICAS.get(maq["categoria"], PAUTAS_MECANICAS["Maquinaria con Horómetro"])
                    tareas_marcadas = []
                    for idx_t, tarea in enumerate(pauta_actual):
                        if st.checkbox(tarea, key=f"chk_{maq['codigo']}_{idx_t}"):
                            tareas_marcadas.append(tarea)
                    
                    st.divider()
                    c1, c2 = st.columns(2)
                    with c1:
                        mecanico = st.text_input("Mecánico responsable:", value="Taller Central")
                        costo_rep = st.number_input("Costo estimado en repuestos/insumos ($ CLP):", min_value=0, step=5000, value=15000)
                    with c2:
                        detalle_ot = st.text_area("Trabajos adicionales o repuestos cambiados:")

                    if st.button("✅ Liberar Máquina (Reiniciar Contador y Pasar a VERDE)", type="primary", use_container_width=True):
                        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                        texto_extra = detalle_ot.strip() if detalle_ot.strip() else "Sin observaciones adicionales."
                        resumen_tareas = f"Pauta completada ({len(tareas_marcadas)}/{len(pauta_actual)} ítems). {texto_extra}"
                        
                        conn = sqlite3.connect(DB_NAME)
                        c = conn.cursor()
                        c.execute("""
                            UPDATE equipos 
                            SET uso_acumulado=0, estado_operativo='DISPONIBLE', falla_activa=0, ultima_observacion=?, fecha_actualizacion=?
                            WHERE codigo=?
                        """, (f"Mantención OK por {mecanico}: {resumen_tareas}", ahora, maq["codigo"]))
                        
                        c.execute("""
                            INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle)
                            VALUES (?,?,?,?,?,?,?)
                        """, (maq["codigo"], ahora, "MANTENCIÓN TALLER", mecanico, 0, costo_rep, resumen_tareas))
                        conn.commit()
                        conn.close()
                        st.success("🟢 ¡Máquina liberada y lista para arriendo!")
                        st.rerun()

            with col_ia:
                with st.container(border=True):
                    st.subheader("🤖 Portal de Diagnóstico IA (Gemini)")
                    st.caption(f"Asistente mecánico contextualizado para: **{maq['nombre']}** ({maq['categoria']})")
                    st.markdown(f"**Último reporte en sistema:** *{maq['ultima_observacion']}*")
                    
                    consulta_mecanico = st.text_area(
                        "Escribe la falla, ruido o duda técnica:",
                        placeholder=f"Ej: La {maq['nombre']} pierde fuerza al calentar o tiene fuga en el sello. ¿Qué reviso primero y qué pruebas hago?",
                        height=110
                    )
                    
                    col_btn_ia1, col_btn_ia2 = st.columns(2)
                    preguntar_ia = col_btn_ia1.button("🔍 Diagnosticar Falla", type="secondary", use_container_width=True)
                    sugerir_pauta = col_btn_ia2.button("📋 Pedir Paso a Paso", use_container_width=True)
                    
                    if preguntar_ia or sugerir_pauta:
                        prompt_base = consulta_mecanico if consulta_mecanico.strip() else f"Analiza este síntoma reportado: {maq['ultima_observacion']}"
                        if sugerir_pauta and not consulta_mecanico.strip():
                            prompt_base = f"Dame el procedimiento técnico paso a paso para realizar la pauta de mantención preventiva de esta {maq['categoria']}: {', '.join(pauta_actual)}"
                            
                        if not GEMINI_INSTALLED:
                            st.error("No tienes instalada la librería `google-genai`. Instálala con `pip install google-genai`.")
                        elif not api_key_gemini:
                            st.warning("⚠️ Ingresa tu API Key de Google Gemini en la barra lateral izquierda para consultar al asistente en vivo.")
                            st.info(
                                f"💡 **Modo Simulación (Sin API Key activa):**\n\n"
                                f"Para **{maq['nombre']}**, ante el reporte *'{maq['ultima_observacion']}'*, se recomienda:\n"
                                f"1. Verificar presión y estanqueidad en frío antes de desarmar.\n"
                                f"2. Revisar puntos críticos de la pauta: *{pauta_actual[0]}* y *{pauta_actual[1]}*.\n"
                                f"3. Registrar costo de insumos reemplazados al liberar la Orden de Trabajo."
                            )
                        else:
                            with st.spinner("Consultando manuales y diagnosticando..."):
                                try:
                                    # LECCIÓN DE CÓDIGO: en el SDK nuevo se crea un Client con la clave
                                    # y se llama a models.generate_content (ya no existe GenerativeModel).
                                    # 'gemini-flash-latest' es el alias estable; las versiones numeradas
                                    # antiguas (1.5 / 2.5) devuelven 404 para cuentas nuevas.
                                    cliente_ia = genai.Client(api_key=api_key_gemini)
                                    prompt_completo = (
                                        f"Actúa como Jefe de Taller Mecánico experto en maquinaria de arriendo en Chile. "
                                        f"Un mecánico está frente a la máquina código {maq['codigo']}: '{maq['nombre']}' "
                                        f"(Categoría: {maq['categoria']}, Uso acumulado: {maq['uso_acumulado']}/{maq['limite_mantencion']} {maq['tipo_medicion']}, "
                                        f"Última nota: '{maq['ultima_observacion']}'). "
                                        f"Consulta del mecánico: '{prompt_base}'. "
                                        f"Responde de forma estructurada, breve, 100% técnica y orientada a taller (causas probables, herramientas/pruebas y solución)."
                                    )
                                    respuesta = cliente_ia.models.generate_content(
                                        model="gemini-flash-latest",
                                        contents=prompt_completo
                                    )
                                    st.success("Diagnóstico de Gemini:")
                                    st.markdown(respuesta.text)
                                except Exception as e:
                                    st.error(f"Error al conectar con la API de Gemini: {e}")

        # --- PESTAÑA 3: DESPACHO A ARRIENDO ---
        with tab_despacho:
            with st.container(border=True):
                st.subheader("Despacho a Cliente / Faena")
                if "🔴" in estado_actual or "🟡" in estado_actual:
                    st.error("⛔ **ALERTA DE CONTROL:** Esta máquina está en ROJO o AMARILLO. No debería salir a terreno sin autorización de taller.")
                    autorizacion_forzada = st.checkbox("Autorizo bajo responsabilidad de jefatura el despacho excepcional de este equipo.")
                else:
                    autorizacion_forzada = True
                
                c1, c2 = st.columns(2)
                with c1:
                    cliente_faena = st.text_input("Nombre del Cliente / Obra (Ej: Constructora Austral - Obra Niebla):")
                with c2:
                    despachador = st.text_input("Despachado por:", value="Mesón Arriendo")
                
                if st.button("🚚 Registrar Salida a Terreno (Pasar a AZUL)", type="primary", use_container_width=True):
                    if not autorizacion_forzada:
                        st.error("Debes marcar la casilla de autorización si deseas despachar un equipo en Rojo o Amarillo.")
                    elif not cliente_faena.strip():
                        st.warning("⚠️ Por favor ingresa el nombre del Cliente o Faena antes de despachar.")
                    else:
                        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                        conn = sqlite3.connect(DB_NAME)
                        c = conn.cursor()
                        c.execute("""
                            UPDATE equipos SET estado_operativo='ARRENDADA', ultima_observacion=?, fecha_actualizacion=? WHERE codigo=?
                        """, (f"En arriendo: {cliente_faena.strip()}", ahora, maq["codigo"]))
                        c.execute("""
                            INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle)
                            VALUES (?,?,?,?,?,?,?)
                        """, (maq["codigo"], ahora, "SALIDA A ARRIENDO", despachador, 0, 0, f"Entregada a cliente: {cliente_faena.strip()}"))
                        conn.commit()
                        conn.close()
                        st.success(f"🔵 Máquina {maq['codigo']} despachada a {cliente_faena}.")
                        st.rerun()

        # --- PESTAÑA 4: CAMBIAR ESTADO MANUALMENTE (CONTROL TOTAL) ---
        with tab_forzar:
            with st.container(border=True):
                st.subheader("⚙️ Control Manual de Estado y Parámetros")
                st.caption("Permite cambiar el estado del semáforo o ajustar el desgaste directamente para pruebas o corrección de errores de digitación.")
                
                with st.form("form_cambio_manual"):
                    cm1, cm2, cm3 = st.columns(3)
                    with cm1:
                        estado_elegido = st.selectbox(
                            "Nuevo Estado del Semáforo:",
                            [
                                "🟢 OPERATIVA (Disponible y limpia)",
                                "🟡 PIDE MANTENCIÓN (Tope de uso alcanzado)",
                                "🔴 EN PANA / BLOQUEADA (Con falla activa)",
                                "🔵 EN ARRIENDO (En terreno con cliente)"
                            ]
                        )
                    with cm2:
                        uso_manual = st.number_input(
                            f"Ajustar Uso Acumulado ({maq['tipo_medicion']}):",
                            min_value=0, max_value=5000, value=int(maq["uso_acumulado"])
                        )
                        horometro_manual = st.number_input(
                            "Ajustar Horómetro Total:",
                            min_value=0, max_value=50000, value=int(maq["horometro_actual"])
                        )
                    with cm3:
                        nota_manual = st.text_input("Nota / Motivo del cambio:", value=maq["ultima_observacion"])
                        registrar_en_hist = st.checkbox("Dejar constancia en el Historial", value=True)
                    
                    if st.form_submit_button("⚡ Aplicar Cambio Inmediato", type="primary", use_container_width=True):
                        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                        
                        if "🟢" in estado_elegido:
                            est_op = "DISPONIBLE"
                            falla_act = 0
                            # Si el usuario eligió Verde pero el uso superaba el límite, ajustarlo para que realmente quede verde
                            uso_final = 0 if uso_manual >= maq["limite_mantencion"] else uso_manual
                        elif "🟡" in estado_elegido:
                            est_op = "DISPONIBLE"
                            falla_act = 0
                            uso_final = max(uso_manual, int(maq["limite_mantencion"]))
                        elif "🔴" in estado_elegido:
                            est_op = "EN_PANA"
                            falla_act = 1
                            uso_final = uso_manual
                        else: # 🔵 EN ARRIENDO
                            est_op = "ARRENDADA"
                            falla_act = 0
                            uso_final = uso_manual

                        conn = sqlite3.connect(DB_NAME)
                        c = conn.cursor()
                        c.execute("""
                            UPDATE equipos 
                            SET uso_acumulado=?, horometro_actual=?, estado_operativo=?, falla_activa=?, ultima_observacion=?, fecha_actualizacion=?
                            WHERE codigo=?
                        """, (uso_final, horometro_manual, est_op, falla_act, nota_manual, ahora, maq["codigo"]))
                        
                        if registrar_en_hist:
                            c.execute("""
                                INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle)
                                VALUES (?,?,?,?,?,?,?)
                            """, (maq["codigo"], ahora, "AJUSTE MANUAL", "Admin Sistema", 0, 0, f"Cambio directo a {estado_elegido}. Nota: {nota_manual}"))
                            
                        conn.commit()
                        conn.close()
                        st.success("Estado actualizado correctamente.")
                        st.rerun()

        # --- PESTAÑA 5: HISTORIAL DEL EQUIPO ---
        with tab_hist:
            with st.container(border=True):
                st.subheader(f"Historial Clínico del Equipo {maq['codigo']}")
                df_h = obtener_historial()
                df_h_maq = df_h[df_h["codigo_equipo"] == maq["codigo"]]
                if df_h_maq.empty:
                    st.info("Este equipo aún no registra eventos en el historial.")
                else:
                    st.dataframe(df_h_maq, use_container_width=True, hide_index=True)

# ==========================================
# MÓDULO 2: SEMÁFORO DE PATIO (VISTA FLOTA INTERACTIVA)
# ==========================================
elif modo_vista == "🚦 2. Semáforo de Patio (Flota)":
    st.title("🚦 Semáforo de Patio en Tiempo Real")
    
    total_maq = len(df_equipos)
    verdes = len(df_equipos[df_equipos["semaforo"].str.contains("🟢")])
    amarillas = len(df_equipos[df_equipos["semaforo"].str.contains("🟡")])
    rojas = len(df_equipos[df_equipos["semaforo"].str.contains("🔴")])
    arrendadas = len(df_equipos[df_equipos["semaforo"].str.contains("🔵")])

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Equipos", total_maq)
    m2.metric("🟢 Listas para Arriendo", verdes)
    m3.metric("🟡 Piden Mantención", amarillas)
    m4.metric("🔴 En Pana / Bloqueadas", rojas)
    m5.metric("🔵 En Faena (Arrendadas)", arrendadas)
    st.divider()

    # Filtros de búsqueda
    f1, f2, f3 = st.columns(3)
    with f1:
        filtro_sem = st.multiselect("Filtrar por Estado del Semáforo:", df_equipos["semaforo"].unique(), default=df_equipos["semaforo"].unique())
    with f2:
        filtro_cat = st.multiselect("Filtrar por Categoría:", df_equipos["categoria"].unique(), default=df_equipos["categoria"].unique())
    with f3:
        busqueda = st.text_input("🔍 Buscar por código, nombre o nota:")

    df_filtrado = df_equipos[(df_equipos["semaforo"].isin(filtro_sem)) & (df_equipos["categoria"].isin(filtro_cat))]
    if busqueda:
        # LECCIÓN DE CÓDIGO: str.contains trata la texto como expresión regular por defecto,
        # así que buscar algo con paréntesis o corchete (ej. "Honda (4t)") revienta la app.
        df_filtrado = df_filtrado[
            df_filtrado["codigo"].str.contains(busqueda, case=False, regex=False) | 
            df_filtrado["nombre"].str.contains(busqueda, case=False, regex=False) |
            df_filtrado["ultima_observacion"].str.contains(busqueda, case=False, regex=False)
        ]

    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

    # BARRA DE ACCIÓN RÁPIDA EN PATIO (INTERACTIVIDAD DIRECTA)
    st.divider()
    with st.container(border=True):
        st.subheader("⚡ Acción Rápida desde Patio")
        st.caption("Selecciona cualquier máquina filtrada arriba para ir directo a su ficha o cambiar su estado en 1 clic sin salir del Semáforo.")
        
        codigos_filtrados = df_filtrado["codigo"].tolist()
        if codigos_filtrados:
            ac1, ac2, ac3 = st.columns([1.2, 1.5, 1.3])
            with ac1:
                maq_patio = st.selectbox("Equipo seleccionado en patio:", codigos_filtrados)
            with ac2:
                accion_rapida = st.selectbox(
                    "Acción rápida:",
                    [
                        "🔍 Abrir Ficha Técnica / Taller de este equipo",
                        "🟢 Marcar como OPERATIVA (Liberar rápido)",
                        "🔴 Marcar EN PANA (Bloquear por falla en patio)",
                        "🔵 Marcar EN ARRIENDO (Salida rápida)"
                    ]
                )
            with ac3:
                nota_rapida = st.text_input("Observación rápida (opcional):", placeholder="Ej: Revisado en patio OK")
            
            if st.button("🚀 Ejecutar Acción en Equipo", type="primary", use_container_width=True):
                if "🔍 Abrir Ficha" in accion_rapida:
                    st.session_state.equipo_activo = maq_patio
                    st.session_state.modulo_activo = "📱 1. Escáner NFC / Ficha Taller"
                    st.rerun()
                else:
                    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    if "🟢" in accion_rapida:
                        obs = nota_rapida.strip() if nota_rapida.strip() else "Liberada desde Semáforo de Patio."
                        c.execute("UPDATE equipos SET uso_acumulado=0, estado_operativo='DISPONIBLE', falla_activa=0, ultima_observacion=?, fecha_actualizacion=? WHERE codigo=?", (obs, ahora, maq_patio))
                        ev = "LIBERACIÓN PATIO"
                    elif "🔴" in accion_rapida:
                        obs = nota_rapida.strip() if nota_rapida.strip() else "Bloqueada por falla detectada en patio."
                        c.execute("UPDATE equipos SET estado_operativo='EN_PANA', falla_activa=1, ultima_observacion=?, fecha_actualizacion=? WHERE codigo=?", (obs, ahora, maq_patio))
                        ev = "BLOQUEO EN PATIO"
                    else:
                        obs = nota_rapida.strip() if nota_rapida.strip() else "En arriendo (registrado desde patio)."
                        c.execute("UPDATE equipos SET estado_operativo='ARRENDADA', ultima_observacion=?, fecha_actualizacion=? WHERE codigo=?", (obs, ahora, maq_patio))
                        ev = "SALIDA RÁPIDA"
                    
                    c.execute("INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle) VALUES (?,?,?,?,?,?,?)",
                              (maq_patio, ahora, ev, "Supervisor Patio", 0, 0, obs))
                    conn.commit()
                    conn.close()
                    st.success(f"Equipo {maq_patio} actualizado inmediatamente.")
                    st.rerun()

# ==========================================
# MÓDULO 3: PANEL DEL DUEÑO (KPIs Y COSTOS INTERACTIVO)
# ==========================================
elif modo_vista == "📊 3. Panel del Dueño (KPIs)":
    st.title("📊 Control Gerencial y Rentabilidad de Flota")
    df_hist = obtener_historial()
    
    total_equipos_kpi = len(df_equipos) if len(df_equipos) > 0 else 1
    rojas_kpi = len(df_equipos[df_equipos["semaforo"].str.contains("🔴")])
    disponibilidad = round(((total_equipos_kpi - rojas_kpi) / total_equipos_kpi) * 100, 1)
    gasto_total_repuestos = df_hist["costo_repuestos"].sum() if not df_hist.empty else 0
    total_panas = len(df_hist[df_hist["tipo_evento"] == "RECEPCIÓN CON FALLA"]) if not df_hist.empty else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Disponibilidad Mecánica de Flota", f"{disponibilidad}%", f"{total_equipos_kpi - rojas_kpi} de {total_equipos_kpi} operativas")
    k2.metric("Gasto Acumulado en Repuestos", f"${gasto_total_repuestos:,.0f} CLP".replace(",", "."))
    k3.metric("Equipos Recibidos con Falla", f"{total_panas} eventos")
    st.divider()

    # Gráficos interactivos para el dueño
    g_col1, g_col2 = st.columns(2)
    with g_col1:
        with st.container(border=True):
            st.subheader("💸 Gasto en Repuestos por Máquina ($ CLP)")
            if not df_hist.empty and df_hist["costo_repuestos"].sum() > 0:
                df_costos_maq = df_hist.groupby("codigo_equipo")["costo_repuestos"].sum().reset_index()
                df_costos_maq = df_costos_maq[df_costos_maq["costo_repuestos"] > 0]
                st.bar_chart(df_costos_maq.set_index("codigo_equipo"))
            else:
                st.info("Aún no hay gastos de repuestos registrados.")

    with g_col2:
        with st.container(border=True):
            st.subheader("📈 Porcentaje de Desgaste Actual por Equipo (%)")
            df_desgaste = df_equipos.copy()
            df_desgaste["pct_desgaste"] = ((df_desgaste["uso_acumulado"] / df_desgaste["limite_mantencion"]) * 100).round(1)
            st.bar_chart(df_desgaste.set_index("codigo")["pct_desgaste"])

    st.divider()
    with st.container(border=True):
        st.subheader("📋 Auditoría Interactiva de Eventos e Historial")
        f_hist1, f_hist2 = st.columns(2)
        with f_hist1:
            maq_filtro_h = st.multiselect("Filtrar por Máquina:", df_equipos["codigo"].unique(), default=df_equipos["codigo"].unique())
        with f_hist2:
            tipos_ev_disp = df_hist["tipo_evento"].unique().tolist() if not df_hist.empty else []
            ev_filtro_h = st.multiselect("Filtrar por Tipo de Evento:", tipos_ev_disp, default=tipos_ev_disp)
        
        df_hist_filtrado = df_hist[
            (df_hist["codigo_equipo"].isin(maq_filtro_h)) &
            (df_hist["tipo_evento"].isin(ev_filtro_h))
        ] if not df_hist.empty else df_hist

        st.dataframe(df_hist_filtrado, use_container_width=True, hide_index=True)

        csv = df_hist_filtrado.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Descargar Historial Filtrado (.CSV / Excel)",
            data=csv,
            file_name="historial_rental_valdivia.csv",
            mime="text/csv",
            type="primary"
        )

# ==========================================
# MÓDULO 4: AGREGAR NUEVA MÁQUINA Y LINK NFC
# ==========================================
elif modo_vista == "➕ 4. Agregar Máquina / Tag NFC":
    st.title("➕ Enrolar Nueva Máquina al Sistema NFC")
    with st.container(border=True):
        with st.form("nuevo_equipo"):
            c1, c2 = st.columns(2)
            with c1:
                nuevo_cod = st.text_input("Código Interno (ej. ORB-05):").upper().strip()
                nuevo_nom = st.text_input("Nombre / Modelo del Equipo (ej. Cortadora Orbital 14\"):").strip()
                nueva_cat = st.selectbox("Categoría de Pauta:", list(PAUTAS_MECANICAS.keys()))
                estado_inicial = st.selectbox("Estado Inicial:", ["DISPONIBLE", "ARRENDADA", "EN_PANA"])
            with c2:
                nuevo_tipo = st.selectbox("Método de Control de Desgaste:", ["DIAS", "HORAS"])
                nuevo_lim = st.number_input("Límite para Mantención Preventiva:", min_value=1, max_value=5000, value=15)
                horometro_ini = st.number_input("Horómetro Inicial (0 si se controla por Días):", min_value=0, max_value=50000, value=0)
                nueva_ubic = st.text_input("Dónde se instalará el Chip NFC (ej. Interior chasis):").strip()

            if st.form_submit_button("💾 Registrar Máquina y Generar Enlace NFC", type="primary", use_container_width=True):
                if not nuevo_cod or not nuevo_nom:
                    st.warning("⚠️ Debes completar al menos el Código Interno y el Nombre del Equipo.")
                else:
                    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                    ubic_final = nueva_ubic if nueva_ubic else "Chasis protegido"
                    falla_ini = 1 if estado_inicial == "EN_PANA" else 0
                    
                    conn = sqlite3.connect(DB_NAME)
                    c = conn.cursor()
                    try:
                        # Consulta SQL exacta de 12 columnas verificada (0 errores)
                        c.execute(
                            "INSERT INTO equipos VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (nuevo_cod, nuevo_nom, nueva_cat, ubic_final, nuevo_tipo, 0, nuevo_lim, horometro_ini, estado_inicial, falla_ini, "Recién enrolada en sistema.", ahora)
                        )
                        c.execute(
                            "INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle) VALUES (?,?,?,?,?,?,?)",
                            (nuevo_cod, ahora, "ENROLAMIENTO NFC", "Admin Sistema", 0, 0, f"Alta de equipo en categoría {nueva_cat}.")
                        )
                        conn.commit()
                        st.session_state.equipo_activo = nuevo_cod
                        st.success(f"✅ Máquina {nuevo_cod} ({nuevo_nom}) creada con éxito.")
                        st.info(f"📲 **Enlace listo para grabar en Tag NFC (NTAG213 / On-Metal):**\n\n`https://TU-APP.streamlit.app/?equipo={nuevo_cod}`")
                    except sqlite3.IntegrityError:
                        st.error(f"❌ El código de máquina '{nuevo_cod}' ya existe en la base de datos. Intenta con otro código.")
                    finally:
                        conn.close()