import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILO SERIO (CSS)
# ==========================================
# Configuramos la página. Aunque usamos layout="wide", limitaremos el ancho con CSS para mayor seriedad.
st.set_page_config(page_title="Sistema de Gestión de Flota", page_icon="⚙️", layout="wide")

# Inyectamos CSS para cambiar la fuente a 'Inter', reducir tamaños exagerados y centrar el contenido.
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    /* Limita el ancho máximo de la página para que se vea como un panel corporativo serio */
    .block-container {
        max-width: 1100px;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    /* Títulos más sobrios y profesionales */
    h1 { font-size: 1.8rem !important; font-weight: 700 !important; letter-spacing: -0.5px; }
    h2 { font-size: 1.35rem !important; font-weight: 600 !important; }
    h3 { font-size: 1.1rem !important; font-weight: 600 !important; }
    </style>
""", unsafe_allow_html=True)

DB_NAME = "rental_valdivia.db"

# ==========================================
# 2. CAPA DE BASE DE DATOS (BACKEND)
# ==========================================
def inicializar_db():
    """Crea las tablas necesarias si no existen en el archivo SQLite."""
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
        
        c.execute("SELECT COUNT(*) FROM equipos")
        if c.fetchone()[0] == 0:
            equipos_demo = [
                ("ORB-01", "Cortadora Orbital Tubos", "Cortadora Orbital", "Base mordaza", "DIAS", 14, 15, 0, "DISPONIBLE", 0, "Operativa.", "2026-10-15 09:30"),
                ("MOT-07", "Unidad Motriz Honda", "Unidad Motriz", "Filtro de aire", "DIAS", 8, 20, 0, "EN_PANA", 1, "Pierde presión.", "2026-10-19 11:20"),
                ("EXC-02", "Miniexcavadora Yanmar", "Maquinaria con Horómetro", "Cabina izq.", "HORAS", 245, 250, 1495, "ARRENDADA", 0, "En faena.", "2026-10-18 16:40")
            ]
            c.executemany("INSERT INTO equipos VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", equipos_demo)
            conn.commit()

def obtener_datos(tabla):
    """Extrae todos los registros de una tabla y los devuelve como un DataFrame de Pandas."""
    with sqlite3.connect(DB_NAME) as conn:
        return pd.read_sql_query(f"SELECT * FROM {tabla}", conn)

def actualizar_equipo_tabla(codigo, nuevo_estado, nueva_nota):
    """Guarda los cambios hechos desde la tabla interactiva de acción rápida."""
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    falla = 1 if nuevo_estado == "EN_PANA" else 0
    # LECCIÓN DE CÓDIGO: SQLite no sabe guardar el tipo NA de Pandas; lo convertimos a texto.
    if nueva_nota is None or bool(pd.isna(nueva_nota)):
        nueva_nota = ""
    nueva_nota = str(nueva_nota)
    nuevo_estado = str(nuevo_estado) if not (nuevo_estado is None or bool(pd.isna(nuevo_estado))) else "DISPONIBLE"
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE equipos 
            SET estado_operativo=?, falla_activa=?, ultima_observacion=?, fecha_actualizacion=? 
            WHERE codigo=?
        """, (nuevo_estado, falla, nueva_nota, ahora, codigo))
        
        c.execute("""
            INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle) 
            VALUES (?,?,?,?,?,?,?)
        """, (codigo, ahora, "CAMBIO EN TABLA", "Operador", 0, 0, f"Estado: {nuevo_estado} | Nota: {nueva_nota}"))
        conn.commit()

def reiniciar_desgaste_bd(codigo, responsable, costo, nota):
    """Reinicia el contador de uso_acumulado a 0 y deja la máquina disponible."""
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M")
    detalle_final = f"Mantención realizada. {nota}" if nota else "Mantención preventiva completada."
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE equipos 
            SET uso_acumulado=0, estado_operativo='DISPONIBLE', falla_activa=0, ultima_observacion=?, fecha_actualizacion=? 
            WHERE codigo=?
        """, (detalle_final, ahora, codigo))
        
        c.execute("""
            INSERT INTO historial (codigo_equipo, fecha, tipo_evento, responsable, uso_sumado, costo_repuestos, detalle) 
            VALUES (?,?,?,?,?,?,?)
        """, (codigo, ahora, "RESETEO MANTENCIÓN", responsable, 0, costo, detalle_final))
        conn.commit()

# ==========================================
# 3. LÓGICA DE COLORES Y ESTILOS VISUALES
# ==========================================
def colorear_estado(val):
    """
    Lección de código: Esta función evalúa el texto de la celda y devuelve 
    código CSS con colores de fondo suaves y texto contrastado.
    """
    if val == "DISPONIBLE" or "🟢" in str(val):
        return 'background-color: #dcfce7; color: #166534; font-weight: 600;' # Verde corporativo
    elif val == "EN_PANA" or "🔴" in str(val):
        return 'background-color: #fee2e2; color: #991b1b; font-weight: 600;' # Rojo alerta
    elif val == "ARRENDADA" or "🔵" in str(val):
        return 'background-color: #dbeafe; color: #1e40af; font-weight: 600;' # Azul terreno
    elif "🟡" in str(val):
        return 'background-color: #fef9c3; color: #854d0e; font-weight: 600;' # Amarillo prevención
    return ''

def calcular_semaforo(fila):
    if fila["falla_activa"] == 1 or fila["estado_operativo"] == "EN_PANA":
        return "🔴 EN PANA"
    elif fila["uso_acumulado"] >= fila["limite_mantencion"]:
        return "🟡 PIDE MANTENCIÓN"
    elif fila["estado_operativo"] == "ARRENDADA":
        return "🔵 EN TERRENO"
    else:
        return "🟢 DISPONIBLE"

# ==========================================
# 4. PANTALLAS DE LA APLICACIÓN (FRONTEND)
# ==========================================
def mostrar_ficha_y_acciones(df_equipos):
    st.title("Control Operativo de Maquinaria")
    st.caption("Panel de administración rápida de estados y registro de mantenciones.")
    
    # --- SECCIÓN 1: TABLA INTERACTIVA DE ACCIÓN RÁPIDA ---
    st.subheader("1. Tabla de Acción Rápida (Cambio de Estado)")
    st.markdown("Haz doble clic en la columna **Estado Operativo** o **Observación** para desplegar las opciones y modificar directamente.")
    
    # Preparamos los datos que se verán en la tabla
    columnas_tabla = ["codigo", "nombre", "estado_operativo", "uso_acumulado", "limite_mantencion", "ultima_observacion"]
    df_para_editar = df_equipos[columnas_tabla].copy()
    
    # Aplicamos la función de colores a la columna 'estado_operativo' usando Pandas Styler
    df_estilizado = df_para_editar.style.map(colorear_estado, subset=["estado_operativo"])
    
    # Mostramos la tabla editable con desplazamiento (scroll) y menús desplegables
    df_editado = st.data_editor(
        df_estilizado,
        column_config={
            "codigo": st.column_config.TextColumn("Código", disabled=True),
            "nombre": st.column_config.TextColumn("Equipo", disabled=True),
            "estado_operativo": st.column_config.SelectboxColumn(
                "Estado Operativo (Editable)",
                help="Selecciona el estado actual de la máquina",
                options=["DISPONIBLE", "ARRENDADA", "EN_PANA"],
                required=True
            ),
            "uso_acumulado": st.column_config.NumberColumn("Uso Actual", disabled=True),
            "limite_mantencion": st.column_config.NumberColumn("Límite", disabled=True),
            "ultima_observacion": st.column_config.TextColumn("Observación / Nota (Editable)")
        },
        use_container_width=True,
        hide_index=True,
        height=220, # Altura fija que permite desplazar (scroll) si hay muchas máquinas
        key="editor_estados"
    )
    
    # Botón para guardar los cambios hechos en la tabla
    if st.button("💾 Guardar Cambios de la Tabla", type="primary"):
        cambios_realizados = 0
        # Comparamos la tabla original con la editada fila por fila
        for index, row in df_editado.iterrows():
            orig_row = df_para_editar.loc[index]
            # LECCIÓN DE CÓDIGO: None/NaN no es igual a None/NaN (NaN != NaN siempre).
            # Normalizamos ambos valores a texto para comparar sin falsos cambios.
            def normalizar(v):
                return "" if v is None or bool(pd.isna(v)) else str(v)
            if normalizar(row["estado_operativo"]) != normalizar(orig_row["estado_operativo"]) or normalizar(row["ultima_observacion"]) != normalizar(orig_row["ultima_observacion"]):
                actualizar_equipo_tabla(row["codigo"], row["estado_operativo"], row["ultima_observacion"])
                cambios_realizados += 1
                
        if cambios_realizados > 0:
            st.success(f"Se actualizaron {cambios_realizados} equipo(s) correctamente.")
            st.rerun()
        else:
            st.info("No se detectaron cambios en la tabla para guardar.")

    st.divider()

    # --- SECCIÓN 2: DETALLE DE MÁQUINA Y BORRADO DE DESGASTE ---
    codigo_sel = st.session_state.equipo_seleccionado
    if not codigo_sel or codigo_sel not in df_equipos["codigo"].values:
        st.info("Selecciona un equipo válido en la barra lateral.")
        return
    maq = df_equipos[df_equipos["codigo"] == codigo_sel].iloc[0]
    unidad = "días" if maq["tipo_medicion"] == "DIAS" else "horas"

    st.subheader(f"2. Ficha de Mantención: {maq['nombre']} ({maq['codigo']})")
    
    # Tarjetas de métricas sobrias
    col1, col2, col3, col4 = st.columns(4)
    limite = int(maq["limite_mantencion"] or 0)
    uso = int(maq["uso_acumulado"] or 0)
    col1.metric("Diagnóstico General", maq["semaforo"])
    col2.metric(f"Desgaste Acumulado", f"{uso} / {limite} {unidad}")
    porcentaje = min(int((uso / limite) * 100), 100) if limite > 0 else 0
    col3.metric("Porcentaje de Uso", f"{porcentaje}%")
    col4.metric("Última Actualización", maq["fecha_actualizacion"])

    st.progress(porcentaje / 100)

    # Panel de Doble Confirmación para Borrar el Desgaste
    with st.container(border=True):
        st.markdown("#### 🔧 Cierre de Mantención y Reinicio de Desgaste")
        st.caption("Utiliza esta sección únicamente cuando el equipo haya pasado por taller y su contador deba volver a cero.")
        
        c_m1, c_m2, c_m3 = st.columns(3)
        with c_m1:
            responsable = st.text_input("Técnico Responsable:", value="Taller Central")
        with c_m2:
            costo = st.number_input("Costo de Repuestos ($ CLP):", min_value=0, step=5000)
        with c_m3:
            nota_mant = st.text_input("Detalle del trabajo realizado:")

        st.write("") # Espacio visual
        
        # LECCIÓN DE CÓDIGO: Doble confirmación. 
        # Guardamos el valor True/False del checkbox en la variable 'confirmar_borrado'.
        confirmar_borrado = st.checkbox(
            f"⚠️ Confirmo que se realizó la mantención a la máquina {maq['codigo']} y deseo reiniciar su desgaste a 0.",
            key=f"chk_reset_{maq['codigo']}"
        )
        
        # El parámetro 'disabled' recibe lo contrario de 'confirmar_borrado' (usando 'not').
        # Si el checkbox NO está marcado, disabled es True (botón bloqueado).
        if st.button(
            "🔄 Reiniciar Desgaste a Cero y Dejar Disponible", 
            disabled=not confirmar_borrado, 
            type="primary",
            use_container_width=True
        ):
            reiniciar_desgaste_bd(maq["codigo"], responsable, costo, nota_mant)
            st.success(f"¡Desgaste de {maq['codigo']} reiniciado a 0 con éxito!")
            st.rerun()

# ==========================================
# 5. CONTROLADOR PRINCIPAL (MAIN)
# ==========================================
def main():
    inicializar_db()
    df_equipos = obtener_datos("equipos")
    df_equipos["semaforo"] = df_equipos.apply(calcular_semaforo, axis=1)

    if "equipo_seleccionado" not in st.session_state:
        st.session_state.equipo_seleccionado = df_equipos["codigo"].iloc[0] if not df_equipos.empty else None

    # Barra Lateral Seria
    with st.sidebar:
        st.markdown("## ⚙️ Gestión de Flota")
        st.caption("Sistema de Control Interno")
        st.divider()
        
        vista = st.radio("Módulos del Sistema:", ["📋 Operación y Mantención", "📊 Historial Clínico"])
        
        st.divider()
        st.markdown("**Seleccionar Equipo para Mantención:**")
        lista_cod = df_equipos["codigo"].tolist()
        if lista_cod:
            idx_actual = lista_cod.index(st.session_state.equipo_seleccionado) if st.session_state.equipo_seleccionado in lista_cod else 0
            st.session_state.equipo_seleccionado = st.selectbox("Código de máquina:", lista_cod, index=idx_actual)
        else:
            st.session_state.equipo_seleccionado = None
            st.caption("No hay equipos registrados.")

    # Enrutamiento de vistas
    if vista == "📋 Operación y Mantención":
        mostrar_ficha_y_acciones(df_equipos)
    elif vista == "📊 Historial Clínico":
        st.title("Historial de Eventos y Mantenciones")
        df_hist = obtener_datos("historial")
        st.dataframe(df_hist, use_container_width=True, hide_index=True)

if __name__ == "__main__":
    main()