import streamlit as st
import sqlite3
import pandas as pd
import os
import random
from datetime import datetime

# Importación segura del SDK actual de Google Gemini (google-genai)
try:
    from google import genai
    GEMINI_INSTALLED = True
except ImportError:
    GEMINI_INSTALLED = False

# ==============================================================================
# 1. CONFIGURACIÓN GENERAL Y ESTILOS VISUALES (FLUJO LINEAL)
# ==============================================================================
st.set_page_config(
    page_title="Rental Valdivia - Control de Taller & NFC",
    page_icon="🚜",
    layout="wide",
    initial_sidebar_state="collapsed"  # Oculta la barra lateral para priorizar fluidez lineal
)

st.markdown("""
    <style>
    /* Tarjetas de métricas compactas y limpias */
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        border: 1px solid #e2e8f0;
        padding: 12px 15px;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    /* Estilo de pestañas operativas más visibles y lineales */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: #f1f5f9;
        padding: 6px;
        border-radius: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 600;
    }
    /* Reducir espacio superior excesivo para lectura directa de arriba hacia abajo */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

DB_NAME = "rental_valdivia.db"

# ==============================================================================
# 2. CATÁLOGO CONTEXTUALIZADO: PANAS COMUNES Y PAUTAS POR TIPO DE MÁQUINA
# ==============================================================================
PANAS_POR_CATEGORIA = {
    "Cortadora Orbital": [
        "Desgaste o rotura de carbones del motor eléctrico",
        "Falta de engrase / trabamiento en cabezal giratorio o husillo",
        "Juego excesivo o deformación en mordazas de sujeción",
        "Cable blindado cortado o enchufe industrial (Legrand/Mennekes) dañado",
        "Portadisco rodado o seguro de traba roto",
        "Recalentamiento de motor / inducido con olor a quemado"
    ],
    "Placa Compactadora": [
        "Correa centrífuga (embrague) cortada, quemada o destensada",
        "Fuga o bajo nivel de aceite en unidad vibradora (excitador)",
        "Silentblocks (gomas amortiguadoras) cortados o fatigados",
        "Carburador sucio / motor se ahoga o no mantiene ralentí",
        "Piola de aceleración o cuerda de partida retráctil cortada",
        "Fisura en base compactadora o pernos de soporte sueltos"
    ],
    "Unidad Motriz": [
        "Fuga o rotura en acoples rápidos hidráulicos (QDC)",
        "Pérdida de presión hidráulica al tomar temperatura de trabajo",
        "Manguera de alta presión reventada o con malla de acero expuesta",
        "Bajo nivel o contaminación de aceite de motor / hidráulico (agua en aceite)",
        "No enciende en frío (bujía empastada, bobina o filtro saturado)",
        "Válvula de alivio o retorno hidráulico obstruido"
    ],
    "Maquinaria con Horómetro": [
        "Fuga de aceite hidráulico en cilindros, sellos o banco de válvulas",
        "Falla eléctrica de arranque (batería descargada, alternador o motor de partida)",
        "Pérdida de potencia del motor diésel (filtros saturados o inyectores)",
        "Sobrecalentamiento de motor (radiador obstruido, termostato o bomba de agua)",
        "Desgaste / juego excesivo en pasadores, bujes o corona de giro",
        "Oruga destensada / cortada o neumático dañado"
    ],
    "Generador Eléctrico": [
        "Generador enciende pero no entrega voltaje (falla de AVR o carbones)",
        "Disparo constante de automático / disyuntor por sobrecarga o cortocircuito",
        "Fuga de combustible o aire en línea de petróleo (no parte)",
        "Falla en panel digital / horómetro o sensor de presión de aceite",
        "Batería sin carga o bornes sulfatados",
        "Ruido anormal en rodamiento de alternador"
    ],
    "Martillo Demoledor": [
        "Desgaste de carbones o falla en interruptor de gatillo",
        "Pérdida de percusión (desgaste de o-rings de pistón o falta de grasa especial)",
        "Portaherramienta / retenedor de punta o cincel quebrado",
        "Cable de alimentación cortado en prensaestopa",
        "Fuga de grasa por sellos del cabezal"
    ],
    "Motobomba / Bomba Sumergible": [
        "No levanta presión / no succiona (sello mecánico o rodete desgastado)",
        "Entrada de agua al estator eléctrico (falla de aislación / salta diferencial)",
        "Carcasa o difusor obstruido por lodo/piedras de faena",
        "Cuerda de partida o carburador con agua en cuba (motobomba combustión)",
        "Acoples Storz quebrados o sin goma de sello"
    ]
}

PAUTAS_MECANICAS = {
    "Cortadora Orbital": [
        "Revisión y limpieza de carbones del motor eléctrico",
        "Inspección de holgura en cabezal giratorio y mordazas de sujeción",
        "Verificación de estado de portadisco y seguro de traba",
        "Revisión de cableado blindado y enchufe industrial (Legrand/Mennekes)",
        "Engrase general de husillo y puntos móviles"
    ],
    "Placa Compactadora": [
        "Revisión de tensión y desgaste de correa centrífuga (embrague)",
        "Verificación de nivel de aceite en unidad vibradora (excitador)",
        "Inspección de silentblocks (gomas amortiguadoras) y chasis",
        "Limpieza de carburador y filtro de combustible",
        "Ajuste de piola de aceleración y parada de emergencia"
    ],
    "Unidad Motriz": [
        "Cambio de aceite de motor (15W-40) y revisión de fugas",
        "Verificación de nivel y estado de aceite hidráulico / retorno",
        "Limpieza o reemplazo de filtro de aire y revisión de bujía",
        "Inspección de acoples rápidos hidráulicos (QDC) y mangueras de alta presión",
        "Prueba de presión de trabajo y encendido en frío"
    ],
    "Maquinaria con Horómetro": [
        "Cambio de aceite de motor y filtro primario/secundario",
        "Revisión de sistema hidráulico, cilindros y sellos",
        "Inspección de filtros de aire (primario y seguridad) y separador de agua",
        "Engrase de pasadores, bujes y corona de giro",
        "Verificación de sistema eléctrico, alternador y batería"
    ],
    "Generador Eléctrico": [
        "Cambio de aceite de motor, filtro de aceite y filtro de combustible",
        "Medición de voltaje en vacío y con carga (verificación de AVR y frecuencia 50Hz)",
        "Revisión de nivel de refrigerante y tensión de correa de ventilador",
        "Inspección de batería, cargador de mantención y paradas de emergencia",
        "Limpieza de gabinete insonorizado y drenaje de decantador de agua"
    ],
    "Martillo Demoledor": [
        "Revisión de medida de carbones y limpieza de colector del inducido",
        "Reemplazo de grasa especial de percusión y revisión de sellos",
        "Inspección de portaherramienta, pasador de retención y buje guía",
        "Chequeo de continuidad y aislación de cable de poder e interruptor",
        "Apriete general de pernos de carcasa con torque y prueba de golpe"
    ],
    "Motobomba / Bomba Sumergible": [
        "Inspección de rodete (impulsor), voluta y holgura de desgaste",
        "Verificación de sello mecánico y nivel de aceite de cámara de sello",
        "Medición de aislación de bobinado (Megger) y estado de cable sumergible",
        "Revisión de acoples rápidos Storz, empaquetaduras y canastillo de succión",
        "Prueba hidráulica de caudal y presión en banco de prueba"
    ]
}

# ==============================================================================
# 3. MOTOR DE BASE DE DATOS SQLITE DE ALTO RENDIMIENTO (WAL + ÍNDICES)
# ==============================================================================
def get_connection():
    """Conexión optimizada para alta concurrencia y miles de registros."""
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-64000;")  # ~64MB de caché en RAM
    return conn

# ARREGLO v7: los INSERT de 'equipos' nombran sus columnas en lugar de usar VALUES(?)
# posicional. Motivo: en una base que venía de una versión anterior, el ALTER TABLE
# pone 'panas_reportadas' al FINAL, y los valores posicionales terminaban en la columna
# equivocada (la fecha guardada como pana y la pana como observación).
COLUMNAS_EQUIPOS = [
    "codigo", "nombre", "categoria", "ubicacion_nfc", "tipo_medicion",
    "uso_acumulado", "limite_mantencion", "horometro_actual", "estado_operativo",
    "falla_activa", "panas_reportadas", "ultima_observacion", "fecha_actualizacion"
]
PLACEHOLDERS_EQUIPOS = ",".join(["?"] * len(COLUMNAS_EQUIPOS))
NOMBRES_EQUIPOS = ",".join(COLUMNAS_EQUIPOS)
INSERT_EQUIPOS_SQL = "INSERT INTO equipos (" + NOMBRES_EQUIPOS + ") VALUES (" + PLACEHOLDERS_EQUIPOS + ")"
INSERT_EQUIPOS_IGNORAR_SQL = INSERT_EQUIPOS_SQL.replace("INSERT INTO", "INSERT OR IGNORE INTO")

def inicializar_db(forzar_reinicio=False):
    conn = get_connection()
    c = conn.cursor()
    
    if forzar_reinicio:
        c.execute("DROP TABLE IF EXISTS equipos")
        c.execute("DROP TABLE IF EXISTS historial")
        c.execute("DROP TABLE IF EXISTS presupuestos")
    
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
            panas_reportadas TEXT,
            ultima_observacion TEXT,
            fecha_actualizacion TEXT
        )
    """)

    # Migración automática segura si la base de datos venía de una versión anterior sin 'panas_reportadas'
    c.execute("PRAGMA table_info(equipos)")
    columnas_equipos = [col[1] for col in c.fetchall()]
    if "panas_reportadas" not in columnas_equipos:
        c.execute("ALTER TABLE equipos ADD COLUMN panas_reportadas TEXT DEFAULT ''")

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

    # NUEVA TABLA: Puesto de Solicitud de Presupuestos
    c.execute("""
        CREATE TABLE IF NOT EXISTS presupuestos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            folio TEXT,
            codigo_equipo TEXT,
            nombre_equipo TEXT,
            categoria TEXT,
            fecha_solicitud TEXT,
            solicitante TEXT,
            destinatario_tipo TEXT,
            destinatario_nombre TEXT,
            prioridad TEXT,
            panas_asociadas TEXT,
            detalle_trabajos TEXT,
            costo_repuestos INTEGER,
            costo_mano_obra INTEGER,
            costo_insumos INTEGER,
            monto_total INTEGER,
            estado_presupuesto TEXT,
            observaciones_resolucion TEXT
        )
    """)

    # Índices para velocidad instantánea con +3.000 máquinas
    c.execute("CREATE INDEX IF NOT EXISTS idx_equipos_cat_est ON equipos(categoria, estado_operativo);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_hist_codigo_fecha ON historial(codigo_equipo, fecha DESC);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_pres_codigo_est ON presupuestos(codigo_equipo, estado_presupuesto);")

    c.execute("SELECT COUNT(*) FROM equipos")
    if c.fetchone()[0] == 0:
        equipos_demo = [
            ("ORB-01", "Cortadora Orbital Tubos 6-12\"", "Cortadora Orbital", "Cara interna base mordaza", "DIAS", 14, 15, 0, "DISPONIBLE", 0, "", "Operativa. Próxima a revisión preventiva.", "2026-10-15 09:30"),
            ("ORB-02", "Cortadora Orbital Alta Carga", "Cortadora Orbital", "Chasis inferior protegido", "DIAS", 16, 15, 0, "DISPONIBLE", 0, "", "Superó límite de 15 días de uso acumulado.", "2026-10-18 17:15"),
            ("MOT-04", "Unidad Motriz Hidráulica 18 HP", "Unidad Motriz", "Ángulo interno jaula tubular", "DIAS", 22, 20, 0, "DISPONIBLE", 0, "", "Pide cambio de aceite y revisión de acoples.", "2026-10-17 18:00"),
            ("MOT-07", "Unidad Motriz Bencinera Honda", "Unidad Motriz", "Tras soporte filtro de aire", "DIAS", 8, 20, 0, "EN_PANA", 1, "Fuga o rotura en acoples rápidos hidráulicos (QDC) | Pérdida de presión hidráulica al tomar temperatura de trabajo", "Ingresó con pérdida de presión en manguera y acople dañado.", "2026-10-19 11:20"),
            ("PLC-12", "Placa Compactadora Reversible 160kg", "Placa Compactadora", "Base interior manillar", "DIAS", 5, 15, 0, "DISPONIBLE", 0, "", "Mantención recién hecha. Correa nueva.", "2026-10-16 12:00"),
            ("EXC-02", "Miniexcavadora Yanmar ViO35", "Maquinaria con Horómetro", "Marco interior cabina izq.", "HORAS", 245, 250, 1495, "DISPONIBLE", 0, "", "Quedan 5 hrs para pauta de 1.500 hrs.", "2026-10-18 16:40"),
            ("GEN-08", "Generador Insonorizado 40 kVA", "Generador Eléctrico", "Interior puerta panel control", "HORAS", 260, 250, 3080, "DISPONIBLE", 0, "", "Retornó de faena Camino a Niebla; requiere pauta preventiva.", "2026-10-20 08:30")
        ]
        c.executemany(INSERT_EQUIPOS_SQL, equipos_demo)
        
        historial_demo = [
            ("MOT-07", "2026-10-19 11:20", "RECEPCIÓN CON FALLA", "Bodega Patio", 4, 0, "Panas: Fuga en acoples QDC | Pérdida de presión. Se bloquea equipo para taller."),
            ("PLC-12", "2026-10-16 12:00", "MANTENCIÓN TALLER", "Mecánico Juan P.", 0, 28500, "Cambio de correa centrífuga y aceite de excitador."),
            ("MOT-04", "2026-10-17 18:00", "RECEPCIÓN NORMAL", "Bodega Patio", 6, 0, "Vuelve de faena en Paillaco sin daños visibles.")
        ]
        c.executemany("INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle) VALUES (?,?,?,?,?,?,?)", historial_demo)

        presupuestos_demo = [
            ("PRES-0001", "MOT-07", "Unidad Motriz Bencinera Honda", "Unidad Motriz", "2026-10-19 12:00", "Mecánico Jefe", "Por definir (Evaluación Interna)", "Pendiente asignar destinatario", "Alta (Equipo Bloqueado)", "Fuga o rotura en acoples rápidos hidráulicos (QDC) | Pérdida de presión hidráulica", "Reemplazo de juego de acoples rápidos Parker, manguera R2 1/2\" y cambio de aceite hidráulico ISO 68.", 65000, 35000, 18000, 118000, "PENDIENTE", "Esperando definir si se cobra a cliente o pasa por garantía interna.")
        ]
        c.executemany("""
            INSERT INTO presupuestos (
                folio, codigo_equipo, nombre_equipo, categoria, fecha_solicitud,
                solicitante, destinatario_tipo, destinatario_nombre, prioridad,
                panas_asociadas, detalle_trabajos, costo_repuestos, costo_mano_obra,
                costo_insumos, monto_total, estado_presupuesto, observaciones_resolucion
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, presupuestos_demo)
        conn.commit()
    conn.close()

def poblar_flota_masiva(cantidad_objetivo=3000):
    """Genera hasta 3.000 equipos realistas en una sola transacción ultrarrápida para pruebas de rendimiento."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM equipos")
    actuales = c.fetchone()[0]
    faltantes = max(0, cantidad_objetivo - actuales)
    if faltantes == 0:
        conn.close()
        return 0

    plantillas = [
        ("ORB", "Cortadora Orbital Industrial", "Cortadora Orbital", "Base mordaza protegida", "DIAS", 15),
        ("PLC", "Placa Compactadora Vibratoria", "Placa Compactadora", "Base interior manillar", "DIAS", 15),
        ("MOT", "Unidad Motriz Hidráulica", "Unidad Motriz", "Jaula tubular interna", "DIAS", 20),
        ("EXC", "Miniexcavadora / Retroexcavadora", "Maquinaria con Horómetro", "Marco cabina interior", "HORAS", 250),
        ("GEN", "Generador Insonorizado Faena", "Generador Eléctrico", "Puerta panel control", "HORAS", 250),
        ("DEM", "Martillo Demoledor Hexagonal", "Martillo Demoledor", "Carcasa superior", "DIAS", 12),
        ("BMB", "Bomba Sumergible Lodos", "Motobomba / Bomba Sumergible", "Placa cuello superior", "DIAS", 20),
    ]
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    nuevos = []
    for i in range(actuales + 1, cantidad_objetivo + 1):
        pref, nom_base, cat, ubic, t_med, lim = random.choice(plantillas)
        cod = f"{pref}-{i:04d}"
        uso = random.randint(0, int(lim * 1.3))
        horom = random.randint(100, 4500) if t_med == "HORAS" else 0
        r_est = random.random()
        if r_est < 0.12:
            est = "EN_PANA"
            falla = 1
            panas_disp = PANAS_POR_CATEGORIA.get(cat, [])
            pana_elegida = random.choice(panas_disp) if panas_disp else "Falla general en revisión"
            obs = f"Falla detectada: {pana_elegida}"
        elif r_est < 0.22:
            est = "EN_PRESUPUESTO"
            falla = 1
            panas_disp = PANAS_POR_CATEGORIA.get(cat, [])
            pana_elegida = random.choice(panas_disp) if panas_disp else "Daño en faena"
            obs = f"En espera de presupuesto. Pana: {pana_elegida}"
        else:
            est = "DISPONIBLE"
            falla = 0
            pana_elegida = ""
            obs = "Operativa en patio." if uso < lim else "Tope de uso alcanzado; requiere pauta preventiva."
        nuevos.append((cod, f"{nom_base} #{i}", cat, ubic, t_med, uso, lim, horom, est, falla, pana_elegida, obs, ahora))

    c.executemany(INSERT_EQUIPOS_IGNORAR_SQL, nuevos)
    conn.commit()
    conn.close()
    return len(nuevos)

def obtener_equipos():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM equipos", conn)
    conn.close()
    return df

def obtener_historial(limite=2000):
    conn = get_connection()
    df = pd.read_sql_query(f"SELECT * FROM historial ORDER BY id DESC LIMIT {int(limite)}", conn)
    conn.close()
    return df

def obtener_presupuestos():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM presupuestos ORDER BY id DESC", conn)
    conn.close()
    return df

def calcular_semaforo_vectorizado(df):
    """Cálculo vectorizado instantáneo para miles de equipos."""
    cond_pana = (df["falla_activa"] == 1) | (df["estado_operativo"] == "EN_PANA")
    cond_pres = (df["estado_operativo"] == "EN_PRESUPUESTO")
    cond_mant = (df["uso_acumulado"] >= df["limite_mantencion"])
    
    sem = pd.Series("🟢 OPERATIVA (LISTA)", index=df.index)
    sem = sem.mask(cond_mant, "🟡 PIDE MANTENCIÓN")
    sem = sem.mask(cond_pana, "🔴 EN PANA (TALLER)")
    sem = sem.mask(cond_pres, "🟣 ESPERANDO PRESUPUESTO")
    return sem

def obtener_gemini_key():
    try:
        return st.secrets["GEMINI_API_KEY"]
    except Exception:
        return os.environ.get("GEMINI_API_KEY", "")

# Inicializar Base de Datos y sanear tipos
inicializar_db()
df_equipos = obtener_equipos()

if not df_equipos.empty:
    for col_num in ["uso_acumulado", "horometro_actual", "falla_activa"]:
        df_equipos[col_num] = pd.to_numeric(df_equipos[col_num], errors="coerce").fillna(0).astype(int)
    df_equipos["limite_mantencion"] = pd.to_numeric(df_equipos["limite_mantencion"], errors="coerce").fillna(1).astype(int).clip(lower=1)
    for col_txt in ["ultima_observacion", "panas_reportadas", "nombre", "categoria", "ubicacion_nfc", "estado_operativo", "tipo_medicion", "fecha_actualizacion"]:
        if col_txt not in df_equipos.columns:
            df_equipos[col_txt] = ""
        df_equipos[col_txt] = df_equipos[col_txt].fillna("").astype(str)
    df_equipos["semaforo"] = calcular_semaforo_vectorizado(df_equipos)

# ==============================================================================
# 4. GESTIÓN DE ESTADO Y LECTURA DE TAG NFC POR URL
# ==============================================================================
params = st.query_params
equipo_url = params.get("equipo", None)
lista_codigos = df_equipos["codigo"].tolist()

opciones_menu = [
    "🔧 1. Estación de Trabajo (Recepción / Taller / NFC)",
    "💰 2. Puesto de Presupuestos",
    "🚦 3. Semáforo de Patio (Flota)",
    "📊 4. Panel Gerencial (KPIs)",
    "➕ 5. Enrolar Máquina / Tag NFC"
]

if "modulo_activo" not in st.session_state or st.session_state.modulo_activo not in opciones_menu:
    st.session_state.modulo_activo = opciones_menu[0]

if "equipo_activo" not in st.session_state:
    if equipo_url in lista_codigos:
        st.session_state.equipo_activo = equipo_url
    else:
        st.session_state.equipo_activo = lista_codigos[0] if lista_codigos else None

if equipo_url in lista_codigos and st.session_state.get("ultimo_url") != equipo_url:
    st.session_state.equipo_activo = equipo_url
    st.session_state.ultimo_url = equipo_url
    st.session_state.modulo_activo = opciones_menu[0]

# ==============================================================================
# 5. BARRA LATERAL (SOLO CONFIGURACIÓN TÉCNICA SECUNDARIA)
# ==============================================================================
with st.sidebar:
    st.title("⚙️ Configuración Técnica")
    st.caption("Las operaciones diarias y la búsqueda de máquinas están ahora en la pantalla principal de forma lineal.")
    st.divider()
    api_key_gemini = st.text_input(
        "🔑 API Key de Google Gemini:",
        value=obtener_gemini_key(),
        type="password",
        help="Para activar el diagnóstico asistido por IA en Taller."
    )
    st.divider()
    st.markdown("### 🚀 Rendimiento y Escala (~3.000 Equipos)")
    st.caption(f"Equipos actuales en base de datos: **{len(df_equipos):,}**")
    if st.button("⚡ Simular Flota de 3.000 Equipos", use_container_width=True):
        creados = poblar_flota_masiva(3000)
        st.success(f"Se agregaron {creados:,} máquinas de prueba. Total: 3.000 equipos.")
        st.rerun()

    st.divider()
    st.markdown("### 🛠️ Restaurar Fábrica")
    confirmar_reset = st.checkbox("Confirmar borrado de datos de prueba")
    if st.button("🔄 Volver a 7 Equipos Demo", disabled=not confirmar_reset, use_container_width=True):
        inicializar_db(forzar_reinicio=True)
        st.success("Base de datos reiniciada.")
        st.rerun()

# ==============================================================================
# 6. ENCABEZADO Y NAVEGACIÓN PRINCIPAL LINEAL (ARRIBA HACIA ABAJO)
# ==============================================================================
col_titulo, col_resumen_top = st.columns([2.2, 1.8])
with col_titulo:
    st.markdown("## 🚜 Rental Valdivia — Control Mecánico, Panas y Presupuestos")
with col_resumen_top:
    if not df_equipos.empty:
        v_cnt = int((df_equipos["semaforo"].str.contains("🟢")).sum())
        a_cnt = int((df_equipos["semaforo"].str.contains("🟡")).sum())
        r_cnt = int((df_equipos["semaforo"].str.contains("🔴")).sum())
        p_cnt = int((df_equipos["semaforo"].str.contains("🟣")).sum())
        st.caption(
            f"**Estado Rápido Flota ({len(df_equipos):,} eq.):** "
            f"🟢 **{v_cnt}** Operativas  |  🟡 **{a_cnt}** Piden Mant.  |  "
            f"🔴 **{r_cnt}** En Pana  |  🟣 **{p_cnt}** En Presupuesto"
        )

modo_vista = st.radio(
    "Navegación Principal:",
    opciones_menu,
    index=opciones_menu.index(st.session_state.modulo_activo),
    horizontal=True,
    label_visibility="collapsed"
)
st.session_state.modulo_activo = modo_vista
st.divider()

# ==============================================================================
# MÓDULO 1: ESTACIÓN DE TRABAJO LINEAL (RECEPCIÓN + TALLER + PRESUPUESTO)
# ==============================================================================
if modo_vista == "🔧 1. Estación de Trabajo (Recepción / Taller / NFC)":
    if df_equipos.empty:
        st.warning("No hay máquinas registradas. Ve a la pestaña '➕ 5. Enrolar Máquina' para agregar la primera.")
    else:
        # ----------------------------------------------------------------------
        # PASO 1 LINEAL: BARRA DE BÚSQUEDA Y SELECCIÓN DE MÁQUINA EN PANTALLA
        # ----------------------------------------------------------------------
        with st.container(border=True):
            st.markdown("#### 🔍 Paso 1: Selecciona o Escanea la Máquina")
            b_col1, b_col2, b_col3 = st.columns([1.1, 1.3, 2.2])
            
            with b_col1:
                categorias_disp = ["Todas las categorías"] + sorted(df_equipos["categoria"].unique().tolist())
                cat_filtro_top = st.selectbox("1️⃣ Filtrar Tipo de Máquina:", categorias_disp)
            
            with b_col2:
                texto_buscar_top = st.text_input("2️⃣ Buscar código o nombre:", placeholder="Ej: ORB-01, Honda, Placa...")
            
            df_selector = df_equipos
            if cat_filtro_top != "Todas las categorías":
                df_selector = df_selector[df_selector["categoria"] == cat_filtro_top]
            if texto_buscar_top.strip():
                q = texto_buscar_top.strip()
                df_selector = df_selector[
                    df_selector["codigo"].str.contains(q, case=False, regex=False) |
                    df_selector["nombre"].str.contains(q, case=False, regex=False)
                ]
            
            if df_selector.empty:
                st.warning("Ninguna máquina coincide con ese filtro. Mostrando lista completa.")
                df_selector = df_equipos

            codigos_disp = df_selector["codigo"].tolist()
            mapa_etiquetas = dict(zip(
                df_selector["codigo"],
                df_selector["codigo"] + " — " + df_selector["nombre"] + " [" + df_selector["categoria"] + "] (" + df_selector["semaforo"] + ")"
            ))

            idx_sel = codigos_disp.index(st.session_state.equipo_activo) if st.session_state.equipo_activo in codigos_disp else 0
            
            with b_col3:
                equipo_seleccionado = st.selectbox(
                    "3️⃣ Máquina Activa (o escaneada vía Tag NFC):",
                    options=codigos_disp,
                    index=idx_sel,
                    format_func=lambda c: mapa_etiquetas.get(c, c)
                )
                st.session_state.equipo_activo = equipo_seleccionado

        # Cargar datos de la máquina seleccionada
        maq = df_equipos[df_equipos["codigo"] == equipo_seleccionado].iloc[0]
        cat_maq = maq["categoria"]
        unidad_uso = "días" if maq["tipo_medicion"] == "DIAS" else "horas"
        porcentaje_desgaste = min(int((maq["uso_acumulado"] / maq["limite_mantencion"]) * 100), 100) if maq["limite_mantencion"] > 0 else 0

        # ----------------------------------------------------------------------
        # PASO 2 LINEAL: FICHA RESUMEN DEL EQUIPO SELECCIONADO
        # ----------------------------------------------------------------------
        with st.container(border=True):
            c_head1, c_head2 = st.columns([2.2, 1.8])
            with c_head1:
                st.markdown(f"### 🔧 {maq['codigo']} — {maq['nombre']}")
                st.caption(
                    f"🏷️ **Categoría:** `{cat_maq}`  |  "
                    f"📍 **Chip NFC:** {maq['ubicacion_nfc']}  |  "
                    f"🔗 **Link NFC:** `?equipo={maq['codigo']}`"
                )
            with c_head2:
                estado_actual = maq["semaforo"]
                if "🔴" in estado_actual:
                    st.error(f"**{estado_actual}**\n\n*{maq['ultima_observacion']}*")
                elif "🟣" in estado_actual:
                    st.warning(f"**{estado_actual}**\n\n*{maq['ultima_observacion']}*")
                elif "🟡" in estado_actual:
                    st.warning(f"**{estado_actual}** — Acumula {maq['uso_acumulado']}/{maq['limite_mantencion']} {unidad_uso}.")
                else:
                    st.success(f"**{estado_actual}** — Acumula {maq['uso_acumulado']}/{maq['limite_mantencion']} {unidad_uso}.")

            if maq["panas_reportadas"].strip():
                st.markdown(f"⚠️ **Panas activas registradas en esta máquina:** `{maq['panas_reportadas']}`")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Uso Acumulado Ciclo", f"{maq['uso_acumulado']} {unidad_uso}", f"Tope Mant.: {maq['limite_mantencion']} {unidad_uso}")
            m2.metric("Desgaste Preventivo", f"{porcentaje_desgaste}%")
            m3.metric("Horómetro Motor", f"{maq['horometro_actual']} hrs" if maq["tipo_medicion"] == "HORAS" else "Control por Días")
            m4.metric("Último Movimiento", maq["fecha_actualizacion"])
            st.progress(porcentaje_desgaste / 100, text=f"Nivel de desgaste acumulado hacia pauta preventiva ({porcentaje_desgaste}%)")

        # ----------------------------------------------------------------------
        # PASO 3 LINEAL: OPERACIÓN EN PATIO / TALLER / PRESUPUESTOS (SIN SALIDAS)
        # ----------------------------------------------------------------------
        st.markdown("#### 🛠️ Paso 2: Ejecuta la Operación sobre esta Máquina")
        tab_rec, tab_taller, tab_pres, tab_manual, tab_hist = st.tabs([
            "📥 1. Recepción e Ingreso de Panas",
            "🔧 2. Taller Mecánico y Pauta + IA",
            "💰 3. Solicitar Presupuesto",
            "⚙️ 4. Forzar Estado / Ajuste",
            "📋 5. Historial del Equipo"
        ])

        # ======================================================================
        # PESTAÑA 1: RECEPCIÓN E INGRESO CONTEXTUALIZADO DE PANAS
        # ======================================================================
        with tab_rec:
            with st.container(border=True):
                st.subheader(f"📥 Recepción en Patio — {maq['codigo']} ({cat_maq})")
                st.caption("Registra el ingreso de la máquina y marca sus panas específicas según su tipo de maquinaria (las salidas/despachos se gestionan en el sistema externo).")

                rc1, rc2 = st.columns(2)
                with rc1:
                    responsable_rec = st.text_input("Recibido por:", value="Encargado de Patio", key=f"rec_resp_{maq['codigo']}")
                    if maq["tipo_medicion"] == "DIAS":
                        uso_nuevo = st.number_input("Días de uso a sumar en este ingreso:", min_value=0, max_value=365, value=3, key=f"rec_dias_{maq['codigo']}")
                        nuevo_horometro = int(maq["horometro_actual"])
                    else:
                        nuevo_horometro = st.number_input(
                            f"Horómetro actual de llegada (Anterior: {maq['horometro_actual']} hrs):",
                            min_value=int(maq["horometro_actual"]),
                            value=int(maq["horometro_actual"]) + 12,
                            key=f"rec_hor_{maq['codigo']}"
                        )
                        uso_nuevo = nuevo_horometro - int(maq["horometro_actual"])

                with rc2:
                    estado_llegada = st.radio(
                        "¿En qué condición ingresa el equipo?",
                        [
                            "✅ Ingresa Operativa (Sin fallas reportadas)",
                            "🔴 Ingresa EN PANA (Bloquear y enviar a Taller)",
                            "🟣 Ingresa con Daño / Falla que Requiere Presupuesto"
                        ],
                        key=f"rec_cond_{maq['codigo']}"
                    )
                    foto_evidencia = st.file_uploader(
                        "📸 Adjuntar foto de evidencia (opcional):",
                        type=["jpg", "png", "jpeg"],
                        key=f"rec_foto_{maq['codigo']}"
                    )

                st.divider()
                # SELECTOR CONTEXTUALIZADO DE PANAS SEGÚN CATEGORÍA DE LA MÁQUINA
                st.markdown(f"##### 🔎 Causas de Pana Más Comunes para: **{cat_maq}**")
                st.caption("Al cambiar de máquina (ej. de Cortadora Orbital a Placa Compactadora), esta lista cambia automáticamente con las panas propias de esa familia.")
                
                lista_panas_cat = PANAS_POR_CATEGORIA.get(cat_maq, PANAS_POR_CATEGORIA["Maquinaria con Horómetro"])
                panas_seleccionadas_rec = []
                
                col_p1, col_p2 = st.columns(2)
                for idx_p, pana_item in enumerate(lista_panas_cat):
                    col_destino = col_p1 if idx_p % 2 == 0 else col_p2
                    # Key única con código y categoría para que NUNCA se queden pegadas las opciones de otra máquina
                    if col_destino.checkbox(pana_item, key=f"pana_rec_{maq['codigo']}_{cat_maq}_{idx_p}"):
                        panas_seleccionadas_rec.append(pana_item)

                # RECUADRO EXTRA OBLIGATORIO PARA OTRA PANA CUALQUIERA
                otra_pana_rec = st.text_input(
                    "➕ Otra pana cualquiera (escribe aquí si presenta otra falla distinta a las de la lista):",
                    placeholder=f"Ej: Golpe en chasis, pieza faltante o ruido específico en {maq['nombre']}...",
                    key=f"otra_pana_rec_{maq['codigo']}"
                )

                obs_adicional_rec = st.text_area(
                    "Observaciones generales de recepción:",
                    placeholder="Detalles de cómo llegó del terreno, accesorios, estado de limpieza, etc.",
                    height=75,
                    key=f"obs_rec_{maq['codigo']}"
                )

                if st.button("💾 Registrar Recepción y Actualizar Estado", type="primary", use_container_width=True, key=f"btn_save_rec_{maq['codigo']}"):
                    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                    nuevo_uso_acum = int(maq["uso_acumulado"]) + int(uso_nuevo)
                    
                    todas_las_panas = list(panas_seleccionadas_rec)
                    if otra_pana_rec.strip():
                        todas_las_panas.append(f"Otra pana: {otra_pana_rec.strip()}")
                    panas_str = " | ".join(todas_las_panas)

                    tiene_falla = ("🔴" in estado_llegada) or ("🟣" in estado_llegada) or (len(todas_las_panas) > 0)
                    
                    if "🟣" in estado_llegada:
                        nuevo_estado_op = "EN_PRESUPUESTO"
                        falla_flag = 1
                        tipo_ev = "RECEPCIÓN PARA PRESUPUESTO"
                    elif tiene_falla:
                        nuevo_estado_op = "EN_PANA"
                        falla_flag = 1
                        tipo_ev = "RECEPCIÓN CON FALLA"
                    else:
                        nuevo_estado_op = "DISPONIBLE"
                        falla_flag = 0
                        tipo_ev = "RECEPCIÓN NORMAL"

                    partes_nota = []
                    if panas_str:
                        partes_nota.append(f"Panas: {panas_str}")
                    if obs_adicional_rec.strip():
                        partes_nota.append(obs_adicional_rec.strip())
                    if not partes_nota:
                        partes_nota.append(f"Recepción normal (+{uso_nuevo} {unidad_uso}).")
                    if foto_evidencia is not None:
                        partes_nota.append(f"[📸 Foto: {foto_evidencia.name}]")
                    
                    nota_final = " — ".join(partes_nota)

                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("""
                        UPDATE equipos
                        SET uso_acumulado=?, horometro_actual=?, estado_operativo=?, falla_activa=?,
                            panas_reportadas=?, ultima_observacion=?, fecha_actualizacion=?
                        WHERE codigo=?
                    """, (nuevo_uso_acum, nuevo_horometro, nuevo_estado_op, falla_flag, panas_str, nota_final, ahora, maq["codigo"]))

                    c.execute("""
                        INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle)
                        VALUES (?,?,?,?,?,?,?)
                    """, (maq["codigo"], ahora, tipo_ev, responsable_rec, uso_nuevo, 0, nota_final))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Recepción de {maq['codigo']} guardada exitosamente.")
                    st.rerun()

        # ======================================================================
        # PESTAÑA 2: TALLER MECÁNICO + DIAGNÓSTICO DE PANAS + PAUTA + IA
        # ======================================================================
        with tab_taller:
            col_taller_izq, col_taller_der = st.columns([1.35, 1])

            with col_taller_izq:
                with st.container(border=True):
                    st.subheader(f"🔧 Diagnóstico y Pauta de Taller — {cat_maq}")

                    # ARREGLO v7: Streamlit conserva el valor con el que creó cada control,
                    # así que al guardar una Recepción el panel de Taller y el multiselect de
                    # Presupuesto seguían mostrando las panas antiguas (o ninguna) y las
                    # borraban al guardar. Se vuelcan desde la base solo cuando cambiaron,
                    # para no pisar lo que el mecánico está marcando en pantalla.
                    firma_panas_actual = f"{cat_maq}||{maq['panas_reportadas']}"
                    if st.session_state.get(f"firma_panas_{maq['codigo']}") != firma_panas_actual:
                        st.session_state[f"firma_panas_{maq['codigo']}"] = firma_panas_actual
                        panas_guardadas = [p.strip() for p in maq["panas_reportadas"].split("|") if p.strip()]
                        otras_guardadas = [p.replace("Otra pana:", "").strip() for p in panas_guardadas if p.startswith("Otra pana:")]
                        for idx_fs, pana_fs in enumerate(PANAS_POR_CATEGORIA.get(cat_maq, [])):
                            st.session_state[f"tal_pana_{maq['codigo']}_{cat_maq}_{idx_fs}"] = pana_fs in panas_guardadas
                        st.session_state[f"tal_otra_pana_{maq['codigo']}"] = ", ".join(otras_guardadas)
                        st.session_state[f"pres_multi_panas_{maq['codigo']}"] = panas_guardadas

                    # Si el mecánico detecta panas adicionales al desarmar en taller:
                    with st.expander("🔍 Diagnosticar / Modificar Panas Detectadas en Taller", expanded=bool(maq["panas_reportadas"].strip())):
                        st.caption(f"Causas frecuentes específicas para **{cat_maq}**:")
                        panas_actuales_lista = [p.strip() for p in maq["panas_reportadas"].split("|") if p.strip()]
                        panas_taller_marcadas = []
                        for idx_pt, pana_t in enumerate(PANAS_POR_CATEGORIA.get(cat_maq, [])):
                            estaba_marcada = pana_t in panas_actuales_lista
                            if st.checkbox(pana_t, value=estaba_marcada, key=f"tal_pana_{maq['codigo']}_{cat_maq}_{idx_pt}"):
                                panas_taller_marcadas.append(pana_t)
                        
                        # Extraer si había una "Otra pana:" previa
                        otras_previas = [p.replace("Otra pana:", "").strip() for p in panas_actuales_lista if p.startswith("Otra pana:")]
                        valor_otra_previa = ", ".join(otras_previas)
                        otra_pana_taller = st.text_input(
                            "➕ Otra pana detectada en desarme (escribir):",
                            value=valor_otra_previa,
                            key=f"tal_otra_pana_{maq['codigo']}"
                        )
                        
                        if st.button("📌 Actualizar Diagnóstico de Panas (Sin liberar aún)", use_container_width=True, key=f"btn_upd_pana_{maq['codigo']}"):
                            ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                            nuevas_p = list(panas_taller_marcadas)
                            if otra_pana_taller.strip():
                                nuevas_p.append(f"Otra pana: {otra_pana_taller.strip()}")
                            str_panas_tal = " | ".join(nuevas_p)
                            obs_tal = f"Diagnóstico Taller: {str_panas_tal}" if str_panas_tal else "En revisión de taller."
                            conn = get_connection()
                            c = conn.cursor()
                            c.execute("""
                                UPDATE equipos SET estado_operativo='EN_PANA', falla_activa=1, panas_reportadas=?, ultima_observacion=?, fecha_actualizacion=?
                                WHERE codigo=?
                            """, (str_panas_tal, obs_tal, ahora, maq["codigo"]))
                            conn.commit()
                            conn.close()
                            st.success("Diagnóstico de panas actualizado en la ficha.")
                            st.rerun()

                    st.markdown(f"##### ✅ Checklist de Mantención Preventiva ({cat_maq})")
                    pauta_actual = PAUTAS_MECANICAS.get(cat_maq, PAUTAS_MECANICAS["Maquinaria con Horómetro"])
                    tareas_marcadas = []
                    for idx_t, tarea in enumerate(pauta_actual):
                        if st.checkbox(tarea, key=f"chk_pauta_{maq['codigo']}_{cat_maq}_{idx_t}"):
                            tareas_marcadas.append(tarea)

                    st.divider()
                    tc1, tc2 = st.columns(2)
                    with tc1:
                        mecanico = st.text_input("Mecánico ejecutante:", value="Taller Central", key=f"mec_nom_{maq['codigo']}")
                        costo_rep = st.number_input("Costo en repuestos/insumos ($ CLP):", min_value=0, step=5000, value=15000, key=f"mec_cost_{maq['codigo']}")
                    with tc2:
                        detalle_ot = st.text_area(
                            "Repuestos reemplazados / Trabajo realizado:",
                            placeholder="Ej: Cambio de carbones, engrase de cabezal y prueba eléctrica OK.",
                            key=f"mec_det_{maq['codigo']}"
                        )

                    if st.button("🟢 Liberar Máquina de Taller (Limpiar Panas, Reiniciar Ciclo y Pasar a VERDE)", type="primary", use_container_width=True, key=f"btn_lib_{maq['codigo']}"):
                        ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                        texto_extra = detalle_ot.strip() if detalle_ot.strip() else "Pauta preventiva estándar realizada."
                        resumen_tareas = f"Pauta completada ({len(tareas_marcadas)}/{len(pauta_actual)} ítems). {texto_extra}"

                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("""
                            UPDATE equipos 
                            SET uso_acumulado=0, estado_operativo='DISPONIBLE', falla_activa=0,
                                panas_reportadas='', ultima_observacion=?, fecha_actualizacion=?
                            WHERE codigo=?
                        """, (f"Liberada por {mecanico}: {resumen_tareas}", ahora, maq["codigo"]))

                        c.execute("""
                            INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle)
                            VALUES (?,?,?,?,?,?,?)
                        """, (maq["codigo"], ahora, "MANTENCIÓN TALLER", mecanico, 0, costo_rep, resumen_tareas))
                        conn.commit()
                        conn.close()
                        st.success(f"🟢 ¡Máquina {maq['codigo']} liberada y operativa!")
                        st.rerun()

            with col_taller_der:
                with st.container(border=True):
                    st.subheader("🤖 Asistente Técnico IA (Gemini)")
                    st.caption(f"Contextualizado para: **{maq['nombre']}** (`{cat_maq}`)")
                    if maq["panas_reportadas"]:
                        st.info(f"**Panas activas:** {maq['panas_reportadas']}")
                    else:
                        st.markdown(f"**Última nota:** *{maq['ultima_observacion']}*")

                    consulta_mecanico = st.text_area(
                        "Consulta técnica o síntoma en banco de prueba:",
                        placeholder=f"Ej: ¿Cómo diagnosticar paso a paso esta falla en {maq['nombre']} y qué tolerancias revisar?",
                        height=100,
                        key=f"ia_q_{maq['codigo']}"
                    )

                    b_ia1, b_ia2 = st.columns(2)
                    preguntar_ia = b_ia1.button("🔍 Diagnosticar Pana", type="secondary", use_container_width=True, key=f"btn_ia1_{maq['codigo']}")
                    sugerir_pauta = b_ia2.button("📋 Paso a Paso Pauta", use_container_width=True, key=f"btn_ia2_{maq['codigo']}")

                    if preguntar_ia or sugerir_pauta:
                        contexto_falla = maq["panas_reportadas"] if maq["panas_reportadas"] else maq["ultima_observacion"]
                        prompt_base = consulta_mecanico.strip() if consulta_mecanico.strip() else f"Analiza las siguientes panas reportadas: {contexto_falla}"
                        if sugerir_pauta and not consulta_mecanico.strip():
                            prompt_base = f"Dame el procedimiento técnico resumido para ejecutar esta pauta en {cat_maq}: {', '.join(pauta_actual)}"

                        if not GEMINI_INSTALLED or not api_key_gemini:
                            st.info(
                                f"💡 **Guía Rápida de Taller para {maq['nombre']} ({cat_maq}):**\n\n"
                                f"- **Síntoma / Pana:** *{contexto_falla}*\n"
                                f"- **Puntos clave a verificar:**\n"
                                f"  1. *{pauta_actual[0]}*\n"
                                f"  2. *{pauta_actual[1]}*\n"
                                f"  3. Si requiere repuestos mayores, genera la solicitud en la pestaña **💰 3. Solicitar Presupuesto**.\n\n"
                                f"*(Configura tu API Key de Gemini en el botón superior izquierdo `>` para diagnósticos generativos en vivo).* "
                            )
                        else:
                            with st.spinner("Generando diagnóstico mecánico..."):
                                try:
                                    cliente_ia = genai.Client(api_key=api_key_gemini)
                                    prompt_completo = (
                                        f"Actúa como Jefe de Taller Mecánico experto en maquinaria de arriendo en Chile. "
                                        f"Equipo: {maq['codigo']} - {maq['nombre']} (Categoría: {cat_maq}, "
                                        f"Uso: {maq['uso_acumulado']}/{maq['limite_mantencion']} {maq['tipo_medicion']}, "
                                        f"Panas registradas: '{maq['panas_reportadas']}', Nota: '{maq['ultima_observacion']}'). "
                                        f"Consulta: '{prompt_base}'. "
                                        f"Responde de forma breve, directa y estructurada: 1) Causa raíz probable, 2) Pruebas en banco, 3) Repuestos habituales."
                                    )
                                    respuesta = cliente_ia.models.generate_content(
                                        model="gemini-flash-latest",
                                        contents=prompt_completo
                                    )
                                    st.success("Diagnóstico Técnico:")
                                    st.markdown(respuesta.text)
                                except Exception as e:
                                    st.error(f"Error al consultar Gemini: {e}")

        # ======================================================================
        # PESTAÑA 3: NUEVO PUESTO DE SOLICITUD DE PRESUPUESTOS (EN LA FICHA)
        # ======================================================================
        with tab_pres:
            with st.container(border=True):
                st.subheader(f"💰 Solicitud de Presupuesto — {maq['codigo']} ({maq['nombre']})")
                st.caption(
                    "Crea un presupuesto técnico detallado para esta máquina. Como el destinatario final puede variar "
                    "(evaluación interna, cobro a cliente por daño, aprobación del dueño o cotización a proveedor), "
                    "puedes dejarlo como 'Por definir' o asignarlo cuando lo decidas."
                )

                pc1, pc2, pc3 = st.columns(3)
                with pc1:
                    solicitante_pres = st.text_input("Solicitado por (Mecánico / Encargado):", value="Jefe de Taller", key=f"pres_sol_{maq['codigo']}")
                    prioridad_pres = st.selectbox(
                        "Prioridad de la Solicitud:",
                        ["Alta (Equipo Bloqueado en Taller)", "Media (Reparación Programable)", "Baja (Mejora / Preventivo)"],
                        key=f"pres_prio_{maq['codigo']}"
                    )
                with pc2:
                    destinatario_tipo = st.selectbox(
                        "Destinatario / Uso del Presupuesto:",
                        [
                            "Por definir (Dejar guardado en bandeja)",
                            "Aprobación Interna (Dueño / Gerencia)",
                            "Cobro a Cliente (Daño o mal uso en faena)",
                            "Solicitud de Cotización a Proveedor / Maestranza"
                        ],
                        key=f"pres_dest_t_{maq['codigo']}"
                    )
                    destinatario_nombre = st.text_input(
                        "Referencia / Nombre (Opcional):",
                        placeholder="Ej: Pendiente definir / Cliente X / Repuestos Austral...",
                        value="Pendiente por definir",
                        key=f"pres_dest_n_{maq['codigo']}"
                    )
                with pc3:
                    marcar_espera_pres = st.checkbox(
                        "🟣 Dejar máquina en estado 'ESPERANDO PRESUPUESTO'",
                        value=True,
                        help="Cambia el semáforo de la máquina a morado para saber en patio que está detenida esperando resolución de presupuesto.",
                        key=f"pres_chk_est_{maq['codigo']}"
                    )

                st.divider()
                st.markdown("##### 🔧 Panas y Trabajos Incluidos en el Presupuesto")
                
                # Pre-cargar las panas activas de la máquina + permitir marcar de la categoría
                lista_panas_pres = PANAS_POR_CATEGORIA.get(cat_maq, [])
                panas_activas_maq = [p.strip() for p in maq["panas_reportadas"].split("|") if p.strip()]
                
                panas_elegidas_pres = st.multiselect(
                    f"Panas asociadas de {cat_maq} (se cargan automáticamente las reportadas):",
                    options=list(dict.fromkeys(lista_panas_pres + panas_activas_maq)),
                    default=panas_activas_maq,
                    key=f"pres_multi_panas_{maq['codigo']}"
                )
                
                otra_pana_pres = st.text_input(
                    "➕ Agregar otra pana o motivo específico al presupuesto:",
                    placeholder="Escribe cualquier falla adicional no listada...",
                    key=f"pres_otra_p_{maq['codigo']}"
                )

                detalle_repuestos_pres = st.text_area(
                    "Listado detallado de repuestos, piezas y mano de obra requerida:",
                    placeholder="Ej:\n- 1x Juego de carbones originales ($14.000)\n- 2x Rodamientos 6203 ZZ ($12.000)\n- 2 hrs Mano de obra electromecánica ($30.000)",
                    height=100,
                    key=f"pres_det_rep_{maq['codigo']}"
                )

                # Cálculo automático en vivo de montos
                cost1, cost2, cost3, cost4 = st.columns(4)
                with cost1:
                    c_rep = st.number_input("Costo Repuestos ($ CLP):", min_value=0, step=5000, value=35000, key=f"pres_c_rep_{maq['codigo']}")
                with cost2:
                    c_mo = st.number_input("Mano de Obra ($ CLP):", min_value=0, step=5000, value=25000, key=f"pres_c_mo_{maq['codigo']}")
                with cost3:
                    c_ins = st.number_input("Insumos / Externos ($ CLP):", min_value=0, step=2000, value=5000, key=f"pres_c_ins_{maq['codigo']}")
                total_pres_calc = int(c_rep + c_mo + c_ins)
                with cost4:
                    st.metric("💰 Total Presupuesto (Neto)", f"${total_pres_calc:,.0f} CLP".replace(",", "."))

                if st.button("📨 Generar y Guardar Solicitud de Presupuesto", type="primary", use_container_width=True, key=f"btn_crear_pres_{maq['codigo']}"):
                    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                    todas_panas_p = list(panas_elegidas_pres)
                    if otra_pana_pres.strip():
                        todas_panas_p.append(f"Otra: {otra_pana_pres.strip()}")
                    panas_pres_str = " | ".join(todas_panas_p) if todas_panas_p else "Evaluación general en taller"
                    det_final_pres = detalle_repuestos_pres.strip() if detalle_repuestos_pres.strip() else "Pendiente desglose fino de repuestos."

                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("SELECT COUNT(*) FROM presupuestos")
                    corr = c.fetchone()[0] + 1
                    folio_nuevo = f"PRES-{corr:04d}"

                    c.execute("""
                        INSERT INTO presupuestos (
                            folio, codigo_equipo, nombre_equipo, categoria, fecha_solicitud,
                            solicitante, destinatario_tipo, destinatario_nombre, prioridad,
                            panas_asociadas, detalle_trabajos, costo_repuestos, costo_mano_obra,
                            costo_insumos, monto_total, estado_presupuesto, observaciones_resolucion
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        folio_nuevo, maq["codigo"], maq["nombre"], cat_maq, ahora,
                        solicitante_pres, destinatario_tipo, destinatario_nombre, prioridad_pres,
                        panas_pres_str, det_final_pres, c_rep, c_mo, c_ins, total_pres_calc,
                        "PENDIENTE", "En bandeja de presupuestos por definir/aprobar."
                    ))

                    if marcar_espera_pres:
                        c.execute("""
                            UPDATE equipos
                            SET estado_operativo='EN_PRESUPUESTO', falla_activa=1,
                                panas_reportadas=?, ultima_observacion=?, fecha_actualizacion=?
                            WHERE codigo=?
                        """, (
                            panas_pres_str,
                            f"Presupuesto {folio_nuevo} (${total_pres_calc:,.0f} CLP) — {destinatario_tipo}".replace(",", "."),
                            ahora, maq["codigo"]
                        ))

                    c.execute("""
                        INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle)
                        VALUES (?,?,?,?,?,?,?)
                    """, (
                        maq["codigo"], ahora, "SOLICITUD PRESUPUESTO", solicitante_pres, 0, 0,
                        f"Folio {folio_nuevo} por ${total_pres_calc:,.0f} CLP ({destinatario_tipo}). Panas: {panas_pres_str}".replace(",", ".")
                    ))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Presupuesto **{folio_nuevo}** generado correctamente. Puedes gestionarlo aquí o en el módulo superior '💰 2. Puesto de Presupuestos'.")
                    st.rerun()

                # Mostrar presupuestos anteriores de esta máquina
                df_pres_maq = obtener_presupuestos()
                df_pres_maq = df_pres_maq[df_pres_maq["codigo_equipo"] == maq["codigo"]] if not df_pres_maq.empty else pd.DataFrame()
                if not df_pres_maq.empty:
                    st.divider()
                    st.markdown(f"##### 📂 Presupuestos Asociados a {maq['codigo']}")
                    st.dataframe(
                        df_pres_maq[["folio", "fecha_solicitud", "estado_presupuesto", "destinatario_tipo", "monto_total", "panas_asociadas", "detalle_trabajos"]],
                        use_container_width=True,
                        hide_index=True
                    )

        # ======================================================================
        # PESTAÑA 4: CAMBIAR ESTADO MANUALMENTE
        # ======================================================================
        with tab_manual:
            with st.container(border=True):
                st.subheader("⚙️ Control Manual de Estado y Parámetros")
                st.caption("Corrige errores de digitación o fuerza el estado de la máquina directamente.")
                cm1, cm2, cm3 = st.columns(3)
                with cm1:
                    estado_elegido = st.selectbox(
                        "Nuevo Estado del Semáforo:",
                        [
                            "🟢 OPERATIVA (Disponible en patio)",
                            "🟡 PIDE MANTENCIÓN (Tope preventivo alcanzado)",
                            "🔴 EN PANA / TALLER (Con falla activa)",
                            "🟣 ESPERANDO PRESUPUESTO (Detenida por cotización)"
                        ],
                        key=f"man_est_{maq['codigo']}"
                    )
                with cm2:
                    uso_manual = st.number_input(
                        f"Ajustar Uso Acumulado ({maq['tipo_medicion']}):",
                        min_value=0, max_value=10000, value=int(maq["uso_acumulado"]),
                        key=f"man_uso_{maq['codigo']}"
                    )
                    horometro_manual = st.number_input(
                        "Ajustar Horómetro Total:",
                        min_value=0, max_value=100000, value=int(maq["horometro_actual"]),
                        key=f"man_hor_{maq['codigo']}"
                    )
                with cm3:
                    nota_manual = st.text_input("Nota / Motivo del ajuste:", value=maq["ultima_observacion"], key=f"man_nota_{maq['codigo']}")
                    limpiar_panas_man = st.checkbox("Limpiar panas reportadas", value=("🟢" in estado_elegido), key=f"man_clr_{maq['codigo']}")

                if st.button("⚡ Aplicar Ajuste Manual", type="primary", use_container_width=True, key=f"btn_man_{maq['codigo']}"):
                    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                    if "🟢" in estado_elegido:
                        est_op, falla_act = "DISPONIBLE", 0
                        uso_final = 0 if uso_manual >= maq["limite_mantencion"] else uso_manual
                    elif "🟡" in estado_elegido:
                        est_op, falla_act = "DISPONIBLE", 0
                        uso_final = max(uso_manual, int(maq["limite_mantencion"]))
                    elif "🟣" in estado_elegido:
                        est_op, falla_act = "EN_PRESUPUESTO", 1
                        uso_final = uso_manual
                    else:
                        est_op, falla_act = "EN_PANA", 1
                        uso_final = uso_manual

                    panas_final = "" if limpiar_panas_man else maq["panas_reportadas"]

                    conn = get_connection()
                    c = conn.cursor()
                    c.execute("""
                        UPDATE equipos
                        SET uso_acumulado=?, horometro_actual=?, estado_operativo=?, falla_activa=?,
                            panas_reportadas=?, ultima_observacion=?, fecha_actualizacion=?
                        WHERE codigo=?
                    """, (uso_final, horometro_manual, est_op, falla_act, panas_final, nota_manual, ahora, maq["codigo"]))
                    c.execute("""
                        INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle)
                        VALUES (?,?,?,?,?,?,?)
                    """, (maq["codigo"], ahora, "AJUSTE MANUAL", "Admin Taller", 0, 0, f"Cambio directo a {estado_elegido}. Nota: {nota_manual}"))
                    conn.commit()
                    conn.close()
                    st.success("Estado actualizado.")
                    st.rerun()

        # ======================================================================
        # PESTAÑA 5: HISTORIAL CLÍNICO DEL EQUIPO
        # ======================================================================
        with tab_hist:
            with st.container(border=True):
                st.subheader(f"📋 Historial Clínico — {maq['codigo']}")
                conn = get_connection()
                df_h_maq = pd.read_sql_query(
                    "SELECT * FROM historial WHERE codigo_equipo = ? ORDER BY id DESC",
                    conn, params=(maq["codigo"],)
                )
                conn.close()
                if df_h_maq.empty:
                    st.info("Este equipo aún no registra eventos en el historial.")
                else:
                    st.dataframe(df_h_maq, use_container_width=True, hide_index=True)

# ==============================================================================
# MÓDULO 2: PUESTO CENTRAL DE PRESUPUESTOS (BANDEJA DE GESTIÓN Y RESOLUCIÓN)
# ==============================================================================
elif modo_vista == "💰 2. Puesto de Presupuestos":
    st.subheader("💰 Puesto Central de Solicitudes de Presupuesto")
    st.caption(
        "Aquí se concentran todos los presupuestos levantados en Taller o Recepción. "
        "Puedes revisar el detalle, definir a quién se le enviará o cobrará, cambiar su estado (Aprobado / Rechazado / En Revisión) "
        "y generar una ficha lista para imprimir o enviar por WhatsApp/Correo."
    )

    df_pres = obtener_presupuestos()

    if df_pres.empty:
        st.info("No hay presupuestos registrados todavía. Puedes crear uno desde la Estación de Trabajo de cualquier máquina.")
    else:
        # Métricas rápidas de presupuestos
        pendientes_df = df_pres[df_pres["estado_presupuesto"] == "PENDIENTE"]
        aprobados_df = df_pres[df_pres["estado_presupuesto"] == "APROBADO"]
        monto_pendiente = pendientes_df["monto_total"].sum() if not pendientes_df.empty else 0
        monto_aprobado = aprobados_df["monto_total"].sum() if not aprobados_df.empty else 0

        kp1, kp2, kp3, kp4 = st.columns(4)
        kp1.metric("Total Solicitudes", len(df_pres))
        kp2.metric("⏳ Pendientes de Definir/Aprobar", len(pendientes_df))
        kp3.metric("💰 Monto en Presupuestos Pendientes", f"${monto_pendiente:,.0f} CLP".replace(",", "."))
        kp4.metric("✅ Monto Presupuestos Aprobados", f"${monto_aprobado:,.0f} CLP".replace(",", "."))

        # Filtros lineales
        with st.container(border=True):
            fp1, fp2, fp3 = st.columns(3)
            with fp1:
                f_est_p = st.multiselect(
                    "Filtrar por Estado:",
                    options=df_pres["estado_presupuesto"].unique().tolist(),
                    default=df_pres["estado_presupuesto"].unique().tolist()
                )
            with fp2:
                f_dest_p = st.multiselect(
                    "Filtrar por Tipo de Destinatario:",
                    options=df_pres["destinatario_tipo"].unique().tolist(),
                    default=df_pres["destinatario_tipo"].unique().tolist()
                )
            with fp3:
                f_txt_p = st.text_input("🔍 Buscar por folio, máquina o pana:")

            df_p_filt = df_pres[
                df_pres["estado_presupuesto"].isin(f_est_p) &
                df_pres["destinatario_tipo"].isin(f_dest_p)
            ]
            if f_txt_p.strip():
                q_p = f_txt_p.strip()
                df_p_filt = df_p_filt[
                    df_p_filt["folio"].str.contains(q_p, case=False, regex=False) |
                    df_p_filt["codigo_equipo"].str.contains(q_p, case=False, regex=False) |
                    df_p_filt["panas_asociadas"].str.contains(q_p, case=False, regex=False)
                ]

            st.dataframe(df_p_filt, use_container_width=True, hide_index=True)

        # Panel para gestionar / editar destinatario / aprobar un presupuesto específico
        if not df_p_filt.empty:
            with st.container(border=True):
                st.markdown("#### ⚡ Gestionar / Definir Destinatario o Resolver Presupuesto")
                folios_disp = df_p_filt["folio"].tolist()
                col_g1, col_g2 = st.columns([1.3, 1.7])

                with col_g1:
                    folio_sel = st.selectbox("Selecciona Folio de Presupuesto:", folios_disp)
                    fila_p = df_p_filt[df_p_filt["folio"] == folio_sel].iloc[0]

                    nuevo_est_p = st.selectbox(
                        "Estado del Presupuesto:",
                        ["PENDIENTE", "EN REVISIÓN", "APROBADO", "RECHAZADO / DADO DE BAJA"],
                        index=["PENDIENTE", "EN REVISIÓN", "APROBADO", "RECHAZADO / DADO DE BAJA"].index(fila_p["estado_presupuesto"])
                        if fila_p["estado_presupuesto"] in ["PENDIENTE", "EN REVISIÓN", "APROBADO", "RECHAZADO / DADO DE BAJA"] else 0
                    )
                    nuevo_dest_t = st.selectbox(
                        "Asignar / Cambiar Tipo de Destinatario:",
                        [
                            "Por definir (Dejar guardado en bandeja)",
                            "Aprobación Interna (Dueño / Gerencia)",
                            "Cobro a Cliente (Daño o mal uso en faena)",
                            "Solicitud de Cotización a Proveedor / Maestranza"
                        ]
                    )
                    nuevo_dest_n = st.text_input("Nombre del Destinatario / Cliente / Proveedor:", value=fila_p["destinatario_nombre"])
                    obs_res = st.text_input("Nota de resolución / orden:", value=fila_p["observaciones_resolucion"])

                    c_btn_p1, c_btn_p2 = st.columns(2)
                    if c_btn_p1.button("💾 Guardar Cambios", type="primary", use_container_width=True):
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("""
                            UPDATE presupuestos
                            SET estado_presupuesto=?, destinatario_tipo=?, destinatario_nombre=?, observaciones_resolucion=?
                            WHERE folio=?
                        """, (nuevo_est_p, nuevo_dest_t, nuevo_dest_n, obs_res, folio_sel))
                        conn.commit()
                        conn.close()
                        st.success(f"Presupuesto {folio_sel} actualizado.")
                        st.rerun()

                    if c_btn_p2.button("🔧 Ir a Ficha de esta Máquina", use_container_width=True):
                        st.session_state.equipo_activo = fila_p["codigo_equipo"]
                        st.session_state.modulo_activo = opciones_menu[0]
                        st.rerun()

                with col_g2:
                    st.markdown("##### 📄 Resumen Formal Copiable (WhatsApp / Correo / PDF)")
                    texto_cotizacion = (
                        f"=== SOLICITUD DE PRESUPUESTO {fila_p['folio']} - RENTAL VALDIVIA ===\n"
                        f"Fecha: {fila_p['fecha_solicitud']}\n"
                        f"Equipo: {fila_p['codigo_equipo']} — {fila_p['nombre_equipo']} ({fila_p['categoria']})\n"
                        f"Destinatario / Uso: {fila_p['destinatario_tipo']} ({fila_p['destinatario_nombre']})\n"
                        f"Prioridad: {fila_p['prioridad']} | Estado: {fila_p['estado_presupuesto']}\n"
                        f"------------------------------------------------------------\n"
                        f"PANAS DETECTADAS:\n{fila_p['panas_asociadas']}\n\n"
                        f"DETALLE DE TRABAJOS Y REPUESTOS:\n{fila_p['detalle_trabajos']}\n"
                        f"------------------------------------------------------------\n"
                        f"- Repuestos:    ${fila_p['costo_repuestos']:,.0f} CLP\n"
                        f"- Mano de Obra: ${fila_p['costo_mano_obra']:,.0f} CLP\n"
                        f"- Insumos/Ext.: ${fila_p['costo_insumos']:,.0f} CLP\n"
                        f"TOTAL NETO:     ${fila_p['monto_total']:,.0f} CLP\n"
                        f"============================================================"
                    ).replace(",", ".")
                    st.code(texto_cotizacion, language="text")

# ==============================================================================
# MÓDULO 3: SEMÁFORO DE PATIO (ENFOCADO EN PATIO, TALLER Y PRESUPUESTOS)
# ==============================================================================
elif modo_vista == "🚦 3. Semáforo de Patio (Flota)":
    st.subheader("🚦 Semáforo de Patio y Taller en Tiempo Real")

    total_maq = len(df_equipos)
    verdes = int((df_equipos["semaforo"].str.contains("🟢")).sum())
    amarillas = int((df_equipos["semaforo"].str.contains("🟡")).sum())
    rojas = int((df_equipos["semaforo"].str.contains("🔴")).sum())
    moradas = int((df_equipos["semaforo"].str.contains("🟣")).sum())

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total Flota", f"{total_maq:,}")
    m2.metric("🟢 Operativas (Listas)", f"{verdes:,}")
    m3.metric("🟡 Piden Mantención", f"{amarillas:,}")
    m4.metric("🔴 En Pana (Taller)", f"{rojas:,}")
    m5.metric("🟣 En Presupuesto", f"{moradas:,}")

    with st.container(border=True):
        f1, f2, f3 = st.columns(3)
        with f1:
            filtro_sem = st.multiselect("Estado del Semáforo:", df_equipos["semaforo"].unique(), default=df_equipos["semaforo"].unique())
        with f2:
            filtro_cat = st.multiselect("Categoría de Máquina:", df_equipos["categoria"].unique(), default=df_equipos["categoria"].unique())
        with f3:
            busqueda = st.text_input("🔍 Buscar por código, nombre, pana u observación:")

        df_filtrado = df_equipos[(df_equipos["semaforo"].isin(filtro_sem)) & (df_equipos["categoria"].isin(filtro_cat))]
        if busqueda.strip():
            q = busqueda.strip()
            df_filtrado = df_filtrado[
                df_filtrado["codigo"].str.contains(q, case=False, regex=False) |
                df_filtrado["nombre"].str.contains(q, case=False, regex=False) |
                df_filtrado["panas_reportadas"].str.contains(q, case=False, regex=False) |
                df_filtrado["ultima_observacion"].str.contains(q, case=False, regex=False)
            ]

        st.dataframe(
            df_filtrado[["codigo", "nombre", "categoria", "semaforo", "uso_acumulado", "limite_mantencion", "panas_reportadas", "ultima_observacion", "fecha_actualizacion"]],
            use_container_width=True,
            hide_index=True
        )

    # Barra de acción rápida desde patio (sin salidas, 100% enfocada en taller y presupuestos)
    with st.container(border=True):
        st.markdown("#### ⚡ Acción Rápida sobre Equipo Filtrado")
        codigos_filtrados = df_filtrado["codigo"].tolist()
        if codigos_filtrados:
            ac1, ac2, ac3 = st.columns([1.2, 1.5, 1.3])
            with ac1:
                maq_patio = st.selectbox("Equipo:", codigos_filtrados[:500])  # Limitado a 500 en el dropdown para fluidez UI instantánea
            with ac2:
                accion_rapida = st.selectbox(
                    "Acción a realizar:",
                    [
                        "🔧 Abrir Estación de Trabajo / Taller de esta máquina",
                        "🟢 Liberar Rápido (Pasar a OPERATIVA y reiniciar ciclo)",
                        "🔴 Bloquear por Pana en Patio (Enviar a Taller)",
                        "🟣 Enviar a Espera de Presupuesto"
                    ]
                )
            with ac3:
                nota_rapida = st.text_input("Observación rápida:", placeholder="Ej: Revisado en patio")

            if st.button("🚀 Ejecutar Acción", type="primary", use_container_width=True):
                if "🔧 Abrir Estación" in accion_rapida:
                    st.session_state.equipo_activo = maq_patio
                    st.session_state.modulo_activo = opciones_menu[0]
                    st.rerun()
                else:
                    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                    conn = get_connection()
                    c = conn.cursor()
                    if "🟢" in accion_rapida:
                        obs = nota_rapida.strip() if nota_rapida.strip() else "Liberada desde Semáforo de Patio."
                        c.execute("UPDATE equipos SET uso_acumulado=0, estado_operativo='DISPONIBLE', falla_activa=0, panas_reportadas='', ultima_observacion=?, fecha_actualizacion=? WHERE codigo=?", (obs, ahora, maq_patio))
                        ev = "LIBERACIÓN PATIO"
                    elif "🟣" in accion_rapida:
                        obs = nota_rapida.strip() if nota_rapida.strip() else "Enviada a evaluación de presupuesto desde patio."
                        c.execute("UPDATE equipos SET estado_operativo='EN_PRESUPUESTO', falla_activa=1, ultima_observacion=?, fecha_actualizacion=? WHERE codigo=?", (obs, ahora, maq_patio))
                        ev = "ENVIADA A PRESUPUESTO"
                    else:
                        obs = nota_rapida.strip() if nota_rapida.strip() else "Bloqueada por falla detectada en patio."
                        c.execute("UPDATE equipos SET estado_operativo='EN_PANA', falla_activa=1, ultima_observacion=?, fecha_actualizacion=? WHERE codigo=?", (obs, ahora, maq_patio))
                        ev = "BLOQUEO EN PATIO"

                    c.execute(
                        "INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle) VALUES (?,?,?,?,?,?,?)",
                        (maq_patio, ahora, ev, "Supervisor Patio", 0, 0, obs)
                    )
                    conn.commit()
                    conn.close()
                    st.success(f"Equipo {maq_patio} actualizado.")
                    st.rerun()

# ==============================================================================
# MÓDULO 4: PANEL GERENCIAL (KPIs, COSTOS Y AUDITORÍA)
# ==============================================================================
elif modo_vista == "📊 4. Panel Gerencial (KPIs)":
    st.subheader("📊 Indicadores de Disponibilidad Mecánica, Panas y Presupuestos")
    df_hist = obtener_historial(limite=5000)
    df_pres_kpi = obtener_presupuestos()

    total_equipos_kpi = max(len(df_equipos), 1)
    indisponibles_kpi = int((df_equipos["semaforo"].str.contains("🔴|🟣")).sum())
    disponibilidad = round(((total_equipos_kpi - indisponibles_kpi) / total_equipos_kpi) * 100, 1)
    gasto_total_repuestos = int(df_hist["costo_repuestos"].sum()) if not df_hist.empty else 0
    monto_presupuestado = int(df_pres_kpi["monto_total"].sum()) if not df_pres_kpi.empty else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Disponibilidad Mecánica", f"{disponibilidad}%", f"{total_equipos_kpi - indisponibles_kpi:,} de {total_equipos_kpi:,} disponibles")
    k2.metric("Gasto Ejecutado en Taller", f"${gasto_total_repuestos:,.0f} CLP".replace(",", "."))
    k3.metric("Total en Presupuestos Emitidos", f"${monto_presupuestado:,.0f} CLP".replace(",", "."))
    k4.metric("Máquinas Detenidas (Pana/Presup.)", f"{indisponibles_kpi:,} equipos")

    g_col1, g_col2 = st.columns(2)
    with g_col1:
        with st.container(border=True):
            st.markdown("##### 💸 Gasto en Repuestos por Máquina ($ CLP)")
            if not df_hist.empty and df_hist["costo_repuestos"].sum() > 0:
                df_costos_maq = df_hist.groupby("codigo_equipo")["costo_repuestos"].sum().reset_index()
                df_costos_maq = df_costos_maq[df_costos_maq["costo_repuestos"] > 0].sort_values("costo_repuestos", ascending=False).head(25)
                st.bar_chart(df_costos_maq.set_index("codigo_equipo"))
            else:
                st.info("Sin gastos de repuestos registrados aún.")

    with g_col2:
        with st.container(border=True):
            st.markdown("##### 🔧 Cantidad de Equipos en Pana por Categoría")
            df_panas_cat = df_equipos[df_equipos["falla_activa"] == 1].groupby("categoria").size().reset_index(name="equipos_con_falla")
            if not df_panas_cat.empty:
                st.bar_chart(df_panas_cat.set_index("categoria"))
            else:
                st.info("No hay equipos con falla activa en este momento.")

    with st.container(border=True):
        st.markdown("##### 📋 Auditoría y Descarga de Historial Clínico")
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
        csv = df_hist.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Descargar Historial Completo (.CSV / Excel)",
            data=csv,
            file_name="historial_taller_rental_valdivia.csv",
            mime="text/csv",
            type="primary"
        )

# ==============================================================================
# MÓDULO 5: ENROLAR NUEVA MÁQUINA Y GENERAR LINK NFC
# ==============================================================================
elif modo_vista == "➕ 5. Enrolar Máquina / Tag NFC":
    st.subheader("➕ Enrolar Nueva Máquina al Sistema NFC")
    with st.container(border=True):
        with st.form("nuevo_equipo"):
            c1, c2 = st.columns(2)
            with c1:
                nuevo_cod = st.text_input("Código Interno (ej. ORB-05):").upper().strip()
                nuevo_nom = st.text_input("Nombre / Modelo del Equipo (ej. Cortadora Orbital 14\"):").strip()
                nueva_cat = st.selectbox("Categoría de Maquinaria (define sus Panas y Pautas):", list(PANAS_POR_CATEGORIA.keys()))
                estado_inicial = st.selectbox("Estado Inicial:", ["DISPONIBLE", "EN_PANA", "EN_PRESUPUESTO"])
            with c2:
                nuevo_tipo = st.selectbox("Método de Control de Desgaste:", ["DIAS", "HORAS"])
                nuevo_lim = st.number_input("Límite para Mantención Preventiva:", min_value=1, max_value=5000, value=15)
                horometro_ini = st.number_input("Horómetro Inicial (0 si se controla por Días):", min_value=0, max_value=100000, value=0)
                nueva_ubic = st.text_input("Ubicación física del Chip NFC (ej. Interior chasis):").strip()

            if st.form_submit_button("💾 Registrar Máquina y Generar Enlace NFC", type="primary", use_container_width=True):
                if not nuevo_cod or not nuevo_nom:
                    st.warning("⚠️ Completa al menos el Código Interno y el Nombre del Equipo.")
                else:
                    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                    ubic_final = nueva_ubic if nueva_ubic else "Chasis protegido"
                    falla_ini = 1 if estado_inicial in ["EN_PANA", "EN_PRESUPUESTO"] else 0

                    conn = get_connection()
                    c = conn.cursor()
                    try:
                        c.execute(
                            INSERT_EQUIPOS_SQL,
                            (nuevo_cod, nuevo_nom, nueva_cat, ubic_final, nuevo_tipo, 0, nuevo_lim, horometro_ini, estado_inicial, falla_ini, "", "Recién enrolada en sistema.", ahora)
                        )
                        c.execute(
                            "INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle) VALUES (?,?,?,?,?,?,?)",
                            (nuevo_cod, ahora, "ENROLAMIENTO NFC", "Admin Sistema", 0, 0, f"Alta de equipo en categoría {nueva_cat}.")
                        )
                        conn.commit()
                        st.session_state.equipo_activo = nuevo_cod
                        st.success(f"✅ Máquina {nuevo_cod} ({nuevo_nom}) registrada con éxito.")
                        st.info(f"📲 **Enlace para grabar en Tag NFC (NTAG213 / On-Metal):**\n\n`https://TU-APP.streamlit.app/?equipo={nuevo_cod}`")
                    except sqlite3.IntegrityError:
                        st.error(f"❌ El código '{nuevo_cod}' ya existe en la base de datos.")
                    finally:
                        conn.close()