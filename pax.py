import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# ==========================================
# 1. CONFIGURACIÓN GENERAL DE LA APLICACIÓN
# ==========================================
st.set_page_config(
    page_title="Rental Valdivia - Control de Flota NFC",
    page_icon="🚜",
    layout="wide",
    initial_sidebar_state="expanded"
)

DB_NAME = "rental_valdivia.db"

# Pautas mecánicas específicas por categoría de máquina
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
def inicializar_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Tabla de Máquinas
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
    
    # Tabla de Historial (Recepciones y Mantenciones)
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
    
    # Cargar datos de demostración si la base está vacía
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

# Inicializar la base de datos al arrancar
inicializar_db()
df_equipos = obtener_equipos()
df_equipos["semaforo"] = df_equipos.apply(calcular_semaforo, axis=1)

# ==========================================
# 3. LECTURA AUTOMÁTICA DE CHIP NFC (URL)
# ==========================================
# Si el mecánico escanea el NFC (ej: http://.../app?equipo=MOT-04), la app lo detecta aquí
params = st.query_params
equipo_url = params.get("equipo", None)

# ==========================================
# 4. BARRA LATERAL Y NAVEGACIÓN
# ==========================================
st.sidebar.title("🚜 Rental Valdivia")
st.sidebar.caption("Sistema de Control NFC & Mantención Preventiva")

modo_vista = st.sidebar.radio(
    "Selecciona Módulo:",
    [
        "📱 1. Escáner NFC / Ficha Taller",
        "🚦 2. Semáforo de Patio (Flota)",
        "📊 3. Panel del Dueño (KPIs)",
        "➕ 4. Agregar Máquina / Tag NFC"
    ]
)

st.sidebar.divider()
st.sidebar.markdown("### 💡 Simulador de Chip NFC")
st.sidebar.caption("En la reunión, muestra cómo al tocar un chip NFC se abre directo la máquina:")
lista_codigos = df_equipos["codigo"].tolist()
indice_default = lista_codigos.index(equipo_url) if equipo_url in lista_codigos else 0
equipo_seleccionado = st.sidebar.selectbox(
    "Máquina escaneada:",
    lista_codigos,
    index=indice_default
)

# ==========================================
# MÓDULO 1: ESCÁNER NFC Y OPERACIÓN EN PATIO
# ==========================================
if modo_vista == "📱 1. Escáner NFC / Ficha Taller":
    maq = df_equipos[df_equipos["codigo"] == equipo_seleccionado].iloc[0]
    unidad = "días acumulados" if maq["tipo_medicion"] == "DIAS" else "horas desde última mant."
    
    st.title(f"🔧 {maq['codigo']} — {maq['nombre']}")
    st.caption(f"📍 **Ubicación física del Chip NFC:** {maq['ubicacion_nfc']}  |  **Categoría:** {maq['categoria']}")

    # Cartel gigante del Semáforo
    estado_actual = maq["semaforo"]
    if "🔴" in estado_actual:
        st.error(f"### {estado_actual}\n**Motivo / Última nota:** {maq['ultima_observacion']} *(PROHIBIDO ENTREGAR A CLIENTE)*")
    elif "🟡" in estado_actual:
        st.warning(f"### {estado_actual}\n**Desgaste acumulado:** {maq['uso_acumulado']} de {maq['limite_mantencion']} {unidad}. Requiere paso por taller antes de volver a salir.")
    elif "🔵" in estado_actual:
        st.info(f"### {estado_actual}\n**Nota:** {maq['ultima_observacion']}")
    else:
        st.success(f"### {estado_actual}\n**Desgaste acumulado:** {maq['uso_acumulado']} de {maq['limite_mantencion']} {unidad}. Máquina autorizada para despacho.")

    # Métricas rápidas de la ficha
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Uso Acumulado (Ciclo)", f"{maq['uso_acumulado']} {maq['tipo_medicion'].lower()}", f"Límite: {maq['limite_mantencion']}")
    porcentaje_desgaste = min(int((maq["uso_acumulado"] / maq["limite_mantencion"]) * 100), 100)
    col2.metric("Nivel de Desgaste Preventivo", f"{porcentaje_desgaste}%")
    col3.metric("Horómetro Motor", f"{maq['horometro_actual']} hrs" if maq["tipo_medicion"] == "HORAS" else "Sin Horómetro (Por Días)")
    col4.metric("Última Actualización", maq["fecha_actualizacion"])
    
    st.progress(porcentaje_desgaste / 100)
    st.divider()

    # Pestañas operativas de 15 segundos
    tab_recepcion, tab_taller, tab_despacho, tab_hist = st.tabs([
        "📥 1. Recepción de Arriendo (Patio)",
        "🛠️ 2. Liberación de Taller (Mecánico)",
        "🚚 3. Salida a Arriendo",
        "📋 Historial del Equipo"
    ])

    # --- PESTAÑA 1: RECEPCIÓN EN PATIO ---
    with tab_recepcion:
        st.subheader("Recepción rápida al bajar de la camioneta")
        with st.form("form_recepcion"):
            c1, c2 = st.columns(2)
            with c1:
                responsable_rec = st.text_input("Nombre de quien recibe:", value="Encargado de Patio")
                if maq["tipo_medicion"] == "DIAS":
                    uso_nuevo = st.number_input("¿Cuántos días estuvo arrendada en faena?", min_value=1, max_value=90, value=3)
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

            guardar_rec = st.form_submit_button("💾 Guardar Recepción y Actualizar Semáforo", use_container_width=True)
            
            if guardar_rec:
                ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                nuevo_uso_acum = int(maq["uso_acumulado"]) + int(uso_nuevo)
                nuevo_estado = "EN_PANA" if llego_con_falla else "DISPONIBLE"
                falla_flag = 1 if llego_con_falla else int(maq["falla_activa"])
                horometro_final = nuevo_horometro if maq["tipo_medicion"] == "HORAS" else 0
                
                nota_final = obs_recepcion if obs_recepcion else f"Recepción normal (+{uso_nuevo} {maq['tipo_medicion'].lower()})."
                if foto_evidencia:
                    nota_final += " [📸 Foto de daño guardada]"

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

    # --- PESTAÑA 2: MANTENCIÓN EN TALLER ---
    with tab_taller:
        st.subheader(f"Pauta de Mantención — {maq['categoria']}")
        st.write("Marca las tareas realizadas para reiniciar el contador preventivo y pasar la máquina a **🟢 VERDE**:")
        
        pauta_actual = PAUTAS_MECANICAS.get(maq["categoria"], PAUTAS_MECANICAS["Maquinaria con Horómetro"])
        tareas_marcadas = []
        for tarea in pauta_actual:
            if st.checkbox(tarea, key=f"chk_{tarea}"):
                tareas_marcadas.append(tarea)
        
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            mecanico = st.text_input("Mecánico responsable:", value="Taller Central")
            costo_rep = st.number_input("Costo estimado en repuestos/insumos ($ CLP):", min_value=0, step=5000, value=15000)
        with c2:
            detalle_ot = st.text_area("Trabajos adicionales o repuestos cambiados (ej. Bujía NGK, Aceite 15W-40, Carbones):")

        if st.button("✅ Liberar Máquina (Reiniciar Contador y Pasar a VERDE)", type="primary", use_container_width=True):
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
            resumen_tareas = f"Pauta completada ({len(tareas_marcadas)}/{len(pauta_actual)} ítems). {detalle_ot}"
            
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

    # --- PESTAÑA 3: SALIDA A ARRIENDO ---
    with tab_despacho:
        st.subheader("Despacho a Cliente / Faena")
        if "🔴" in estado_actual or "🟡" in estado_actual:
            st.error("⛔ **ALERTA DE CONTROL:** Esta máquina está en ROJO o AMARILLO. No debería salir a terreno sin autorización de taller.")
        
        cliente_faena = st.text_input("Nombre del Cliente / Obra (ej. Constructora Austral - Faena Niebla):")
        despachador = st.text_input("Despachado por:", value="Mesón Arriendo")
        if st.button("🚚 Registrar Salida a Terreno", use_container_width=True):
            ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("""
                UPDATE equipos SET estado_operativo='ARRENDADA', ultima_observacion=?, fecha_actualizacion=? WHERE codigo=?
            """, (f"En arriendo: {cliente_faena}", ahora, maq["codigo"]))
            c.execute("""
                INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle)
                VALUES (?,?,?,?,?,?,?)
            """, (maq["codigo"], ahora, "SALIDA A ARRIENDO", despachador, 0, 0, f"Entregada a cliente: {cliente_faena}"))
            conn.commit()
            conn.close()
            st.rerun()

    # --- PESTAÑA 4: HISTORIAL DEL EQUIPO ---
    with tab_hist:
        df_h = obtener_historial()
        df_h_maq = df_h[df_h["codigo_equipo"] == maq["codigo"]]
        st.dataframe(df_h_maq, use_container_width=True, hide_index=True)

# ==========================================
# MÓDULO 2: SEMÁFORO DE PATIO (VISTA FLOTA)
# ==========================================
elif modo_vista == "🚦 2. Semáforo de Patio (Flota)":
    st.title("🚦 Semáforo de Patio en Tiempo Real")
    st.write("Vista rápida para que mesón de ventas y jefe de taller sepan qué máquina se puede entregar y cuál debe entrar a banco de pruebas.")

    # Contadores rápidos
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

    # Filtros pensados para buscar entre 3.000 máquinas
    f1, f2, f3 = st.columns(3)
    with f1:
        filtro_sem = st.multiselect("Filtrar por Estado del Semáforo:", df_equipos["semaforo"].unique(), default=df_equipos["semaforo"].unique())
    with f2:
        filtro_cat = st.multiselect("Filtrar por Categoría:", df_equipos["categoria"].unique(), default=df_equipos["categoria"].unique())
    with f3:
        busqueda = st.text_input("🔍 Buscar por código o nombre (ej. ORB-01, Motriz):")

    df_filtrado = df_equipos[
        (df_equipos["semaforo"].isin(filtro_sem)) &
        (df_equipos["categoria"].isin(filtro_cat))
    ]
    if busqueda:
        df_filtrado = df_filtrado[
            df_filtrado["codigo"].str.contains(busqueda, case=False) |
            df_filtrado["nombre"].str.contains(busqueda, case=False)
        ]

    st.dataframe(
        df_filtrado[["codigo", "semaforo", "nombre", "categoria", "uso_acumulado", "limite_mantencion", "tipo_medicion", "ubicacion_nfc", "ultima_observacion"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "codigo": "Código",
            "semaforo": "Estado Semáforo",
            "nombre": "Equipo",
            "categoria": "Familia",
            "uso_acumulado": "Uso Acumulado",
            "limite_mantencion": "Límite Pauta",
            "tipo_medicion": "Control por",
            "ubicacion_nfc": "Ubicación Chip NFC",
            "ultima_observacion": "Último Reporte"
        }
    )

# ==========================================
# MÓDULO 3: PANEL DEL DUEÑO (KPIs Y COSTOS)
# ==========================================
elif modo_vista == "📊 3. Panel del Dueño (KPIs)":
    st.title("📊 Control Gerencial y Rentabilidad de Flota")
    st.write("Indicadores clave para toma de decisiones, control de gastos en repuestos y detección de equipos críticos.")

    df_hist = obtener_historial()
    disponibilidad = round(((len(df_equipos) - len(df_equipos[df_equipos["semaforo"].str.contains("🔴")])) / len(df_equipos)) * 100, 1)
    gasto_total_repuestos = df_hist["costo_repuestos"].sum()
    total_panas = len(df_hist[df_hist["tipo_evento"] == "RECEPCIÓN CON FALLA"])

    k1, k2, k3 = st.columns(3)
    k1.metric("Disponibilidad Mecánica de Flota", f"{disponibilidad}%", "Meta ideal: mayor a 90%")
    k2.metric("Gasto Acumulado en Repuestos (Taller)", f"${gasto_total_repuestos:,.0f} CLP".replace(",", "."))
    k3.metric("Equipos Recibidos con Falla / Daño", f"{total_panas} eventos")

    st.divider()
    col_g1, col_g2 = st.columns(2)

    with col_g1:
        st.subheader("🔧 Gasto en Mantención por Máquina ($ CLP)")
        gasto_por_maq = df_hist.groupby("codigo_equipo")["costo_repuestos"].sum().reset_index()
        st.bar_chart(gasto_por_maq.set_index("codigo_equipo"))

    with col_g2:
        st.subheader("📈 Nivel de Desgaste Acumulado vs. Límite")
        df_chart = df_equipos[["codigo", "uso_acumulado", "limite_mantencion"]].set_index("codigo")
        st.bar_chart(df_chart)

    st.subheader("📥 Descargar Reporte Completo para Excel")
    csv = df_hist.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📊 Descargar Historial de Mantenciones y Recepciones (.CSV / Excel)",
        data=csv,
        file_name="historial_mantencion_rental_valdivia.csv",
        mime="text/csv"
    )

# ==========================================
# MÓDULO 4: AGREGAR NUEVA MÁQUINA Y LINK NFC
# ==========================================
elif modo_vista == "➕ 4. Agregar Máquina / Tag NFC":
    st.title("➕ Enrolar Nueva Máquina al Sistema NFC")
    with st.form("nuevo_equipo"):
        c1, c2 = st.columns(2)
        with c1:
            nuevo_cod = st.text_input("Código Interno (ej. ORB-05, MOT-12):").upper().strip()
            nuevo_nom = st.text_input("Nombre / Modelo del Equipo:")
            nueva_cat = st.selectbox("Categoría de Pauta:", list(PAUTAS_MECANICAS.keys()))
        with c2:
            nuevo_tipo = st.selectbox("Método de Control de Desgaste:", ["DIAS", "HORAS"])
            nuevo_lim = st.number_input("Límite para Mantención Preventiva (Días o Horas):", min_value=5, max_value=1000, value=15)
            nueva_ubic = st.text_input("Dónde se instalará el Chip NFC (ej. Interior jaula motor):")

        if st.form_submit_button("Registrar Máquina y Generar Enlace NFC"):
            if nuevo_cod and nuevo_nom:
                ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
                conn = sqlite3.connect(DB_NAME)
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO equipos VALUES (?,?,?,?,?,?,?,0,'DISPONIBLE',0,'Recién enrolada en sistema.',?)",
                              (nuevo_cod, nuevo_nom, nueva_cat, nueva_ubic, nuevo_tipo, 0, nuevo_lim, ahora))
                    conn.commit()
                    st.success(f"✅ Máquina {nuevo_cod} creada con éxito.")
                    st.info(f"📲 **Enlace para grabar en el Chip NFC con la app 'NFC Tools':**\n`http://TU-IP-O-DOMINIO:8501/?equipo={nuevo_cod}`")
                except sqlite3.IntegrityError:
                    st.error("❌ Ese código de máquina ya existe.")
                finally:
                    conn.close()