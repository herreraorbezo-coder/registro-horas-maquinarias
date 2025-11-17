# app.py - Versión profesional (Estilo A: Corporativo Azul/Gris)
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import json
import pandas as pd
from openai import OpenAI
import io

# ---------------------------
# Configuración de página
# ---------------------------
st.set_page_config(page_title="Horas Maquinaria - Dashboard", page_icon="🚜", layout="wide")

# ---------------------------
# Estilos (CSS) - Estilo A
# ---------------------------
st.markdown(
    """
    <style>
    :root{
        --primary:#0052A2;
        --primary-soft:#D6E4F0;
        --text:#1F2937;
        --card-bg:#ffffff;
        --border:#E5E7EB;
    }
    .app-header{
        background: linear-gradient(90deg, rgba(0,82,162,1) 0%, rgba(0,74,145,1) 100%);
        color: white;
        padding: 18px;
        border-radius: 8px;
        margin-bottom: 18px;
    }
    .app-sub{
        color: #E6EEF8;
        margin-top: -6px;
        font-size:13px;
    }
    .card {
        background: var(--card-bg);
        padding: 14px;
        border-radius: 10px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.06);
        border: 1px solid var(--border);
    }
    .small {
        font-size:13px;
        color: #6B7280;
    }
    .kpi {
        font-size:22px;
        font-weight:700;
        color: var(--text);
    }
    .muted { color: #6B7280; font-size:13px; }
    .stButton>button { background-color: var(--primary); color: white; border: none; }
    .stDownloadButton>button { background-color: #0b69d6; color: white; border: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------
# Título y encabezado
# ---------------------------
st.markdown(
    """
    <div class="app-header">
        <h2 style="margin:0; font-weight:700">🚜 Control de Horas de Maquinaria - Panel</h2>
        <div class="app-sub">Registro | Observaciones por audio | Historial | Reportes</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------
# Sidebar - menú y configuración
# ---------------------------
st.sidebar.header("📁 Menú")
menu = st.sidebar.radio("", ["Registro de horas", "Observaciones por audio", "Historial", "Reportes", "Configuración"])

st.sidebar.markdown("---")
st.sidebar.header("🔒 Usuario")
usuario = st.sidebar.text_input("Usuario (opcional)")
st.sidebar.caption("La autenticación puede agregarse en Configuración.")

# ---------------------------
# Conexión a Google Sheets & OpenAI
# ---------------------------
@st.cache_resource
def init_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credenciales_info = json.loads(st.secrets["CREDENCIALES_GOOGLE"])
    credenciales = ServiceAccountCredentials.from_json_keyfile_dict(credenciales_info, scope)
    cliente = gspread.authorize(credenciales)
    sheet = cliente.open("Horas_Maquinaria").sheet1
    return sheet

@st.cache_resource
def init_openai():
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
    return client

# inicializar (si secrets no están configuradas, manejaremos el error más abajo)
gspread_error = None
openai_error = None
sheet = None
client = None
try:
    sheet = init_gspread()
except Exception as e:
    gspread_error = str(e)

try:
    client = init_openai()
except Exception as e:
    openai_error = str(e)

# ---------------------------
# Utilidades
# ---------------------------
def fetch_all_records(sheet_obj):
    try:
        rows = sheet_obj.get_all_records()
        df = pd.DataFrame(rows)
        if df.empty:
            # asegurar columnas consistentes
            df = pd.DataFrame(columns=["Fecha","Operador","Maquina","HorometroInicio","HorometroFinal","HorasTrabajadas","Observaciones"])
        return df
    except Exception:
        return pd.DataFrame(columns=["Fecha","Operador","Maquina","HorometroInicio","HorometroFinal","HorasTrabajadas","Observaciones"])

def append_record(sheet_obj, record_list):
    sheet_obj.append_row(record_list)

# ---------------------------
# Página: Registro de horas
# ---------------------------
if menu == "Registro de horas":
    col1, col2 = st.columns([2,1])

    with col1:
        st.markdown("### 📋 Datos del registro", unsafe_allow_html=True)
        with st.container():
            st.write("")
        with st.form("registro_form", clear_on_submit=False):
            operador = st.text_input("👷 Nombre del operador", max_chars=80)
            maquina = st.selectbox("🚜 Seleccionar máquina", [
                "Telehandler JCB",
                "UPTIMOS D600",
                "Retroexcavadora LIU GONG",
                "CAMION volkswagen 31-320",
                "EXCAVADORA HYUNDAI"
            ])
            fecha = st.date_input("📅 Fecha", datetime.date.today())
            horometro_inicial = st.number_input("🔢 Horómetro inicial (hrs)", min_value=0.0, format="%.2f")
            horometro_final = st.number_input("🔢 Horómetro final (hrs)", min_value=0.0, format="%.2f")
            observaciones = st.text_area("📝 Observaciones (puede añadirse por audio en la pestaña 'Observaciones por audio')", height=100)

            submitted = st.form_submit_button("Enviar registro")
            if submitted:
                # validaciones
                if horometro_final < horometro_inicial:
                    st.error("⚠️ El horómetro final no puede ser menor que el inicial.")
                elif not operador:
                    st.error("⚠️ Ingresa el nombre del operador.")
                else:
                    horas_trabajadas = round(horometro_final - horometro_inicial, 2)
                    # guardar en Google Sheets si está configurado
                    if sheet is None:
                        st.error("❌ Error: No se puede conectar a Google Sheets. Revisa tus secrets.")
                    else:
                        try:
                            append_record(sheet, [str(fecha), operador, maquina, float(horometro_inicial), float(horometro_final), float(horas_trabajadas), observaciones])
                            st.success(f"✅ Registro guardado. Horas trabajadas: {horas_trabajadas:.2f} hrs.")
                        except Exception as e:
                            st.error(f"❌ Error al guardar: {e}")

    with col2:
        st.markdown("### 📈 KPI rápido", unsafe_allow_html=True)
        card1, card2 = st.columns(2)
        df_all = fetch_all_records(sheet) if sheet is not None else pd.DataFrame()
        total_hours = 0.0
        registros = 0
        if not df_all.empty:
            # asegurar tipos
            df_all["HorasTrabajadas"] = pd.to_numeric(df_all.get("HorasTrabajadas", 0), errors="coerce").fillna(0)
            total_hours = df_all["HorasTrabajadas"].sum()
            registros = len(df_all)

        with card1:
            st.markdown('<div class="card"><div class="small muted">Total horas registradas</div><div class="kpi">{:.2f} hrs</div></div>'.format(total_hours), unsafe_allow_html=True)
        with card2:
            st.markdown('<div class="card"><div class="small muted">Total registros</div><div class="kpi">{}</div></div>'.format(registros), unsafe_allow_html=True)

# ---------------------------
# Página: Observaciones por audio
# ---------------------------
elif menu == "Observaciones por audio":
    st.markdown("### 🎤 Observaciones por audio → Texto", unsafe_allow_html=True)
    st.info("Sube un archivo de audio (mp3, wav, m4a). La transcripción se agregará al campo de observaciones al enviar el registro (o puedes copiarla manualmente).")

    audio_file = st.file_uploader("Sube tu audio (mp3, wav, m4a)", type=["mp3","wav","m4a"])
    transcribed_text = ""
    if audio_file:
        st.audio(audio_file)
        if client is None:
            st.warning("No está configurada la API de OpenAI: activa OPENAI_API_KEY en Secrets para transcribir automáticamente.")
        else:
            if st.button("Transcribir audio"):
                with st.spinner("Transcribiendo..."):
                    try:
                        # usar la API (Whisper) para transcribir
                        res = client.audio.transcriptions.create(
                            model="gpt-4o-transcribe",
                            file=audio_file
                        )
                        transcribed_text = res.text
                        st.success("✅ Transcripción completada.")
                        st.write(transcribed_text)
                    except Exception as e:
                        st.error(f"Error en la transcripción: {e}")

    st.markdown("---")
    st.markdown("### 📝 Insertar transcripción en un nuevo registro")
    with st.form("audio_to_record"):
        operador_a = st.text_input("👷 Nombre del operador (para este registro)", max_chars=80)
        maquina_a = st.selectbox("🚜 Máquina", [
            "Telehandler JCB",
            "UPTIMOS D600",
            "Retroexcavadora LIU GONG",
            "CAMION volkswagen 31-320",
            "EXCAVADORA HYUNDAI"
        ], key="maquina_a")
        fecha_a = st.date_input("📅 Fecha", datetime.date.today(), key="fecha_a")
        hor_in = st.number_input("Horómetro inicial (hrs)", min_value=0.0, format="%.2f", key="hor_in")
        hor_fin = st.number_input("Horómetro final (hrs)", min_value=0.0, format="%.2f", key="hor_fin")
        obs_manual = st.text_area("Observaciones (puedes editar la transcripción)", value=transcribed_text, height=120)

        enviar_audio_reg = st.form_submit_button("Enviar registro con observaciones")
        if enviar_audio_reg:
            if hor_fin < hor_in:
                st.error("⚠️ Horómetro final menor que inicial.")
            elif not operador_a:
                st.error("⚠️ Ingresa nombre del operador.")
            else:
                horas_t = round(hor_fin - hor_in, 2)
                if sheet is None:
                    st.error("❌ No hay conexión con Google Sheets.")
                else:
                    try:
                        append_record(sheet, [str(fecha_a), operador_a, maquina_a, float(hor_in), float(hor_fin), float(horas_t), obs_manual])
                        st.success(f"✅ Registro guardado con observaciones. Horas: {horas_t:.2f} hrs.")
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

# ---------------------------
# Página: Historial
# ---------------------------
elif menu == "Historial":
    st.markdown("### 📚 Historial de registros", unsafe_allow_html=True)
    if sheet is None:
        st.error("❌ No se puede conectar a Google Sheets. Revisa tus secrets.")
    else:
        df = fetch_all_records(sheet)
        if df.empty:
            st.info("No hay registros aún.")
        else:
            # Asegurar nombres de columnas (si la hoja tiene otras cabeceras)
            cols = df.columns.tolist()
            # filtros
            c1, c2, c3 = st.columns([2,2,2])
            with c1:
                filtro_op = st.selectbox("Filtrar por operador", options=["Todos"] + sorted(df["Operador"].dropna().unique().tolist()))
            with c2:
                filtro_maq = st.selectbox("Filtrar por máquina", options=["Todos"] + sorted(df["Maquina"].dropna().unique().tolist()))
            with c3:
                fecha_range = st.date_input("Rango de fecha (desde - hasta)", [df["Fecha"].min(), df["Fecha"].max()]) if "Fecha" in df.columns else None

            df_display = df.copy()
            # convertir Fecha a datetime si es string
            try:
                df_display["Fecha"] = pd.to_datetime(df_display["Fecha"]).dt.date
            except Exception:
                pass

            if filtro_op != "Todos":
                df_display = df_display[df_display["Operador"] == filtro_op]
            if filtro_maq != "Todos":
                df_display = df_display[df_display["Maquina"] == filtro_maq]
            if fecha_range and isinstance(fecha_range, list) and len(fecha_range) == 2:
                desde, hasta = fecha_range
                df_display = df_display[(df_display["Fecha"] >= desde) & (df_display["Fecha"] <= hasta)]

            st.markdown(f"**Registros mostrados:** {len(df_display)}")
            st.dataframe(df_display.reset_index(drop=True), use_container_width=True)

            # Descargar CSV
            csv = df_display.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descargar CSV", data=csv, file_name="historial_horas.csv", mime="text/csv")

# ---------------------------
# Página: Reportes
# ---------------------------
elif menu == "Reportes":
    st.markdown("### 📊 Reportes y gráficos", unsafe_allow_html=True)
    if sheet is None:
        st.error("❌ No se puede conectar a Google Sheets.")
    else:
        df = fetch_all_records(sheet)
        if df.empty:
            st.info("Aún no hay datos para graficar.")
        else:
            # limpieza y conversión
            df["HorasTrabajadas"] = pd.to_numeric(df.get("HorasTrabajadas", 0), errors="coerce").fillna(0)
            # Horas por máquina (últimos 30 días)
            st.markdown("**Horas por máquina (total)**")
            hours_by_machine = df.groupby("Maquina")["HorasTrabajadas"].sum().reset_index().sort_values("HorasTrabajadas", ascending=False)
            st.bar_chart(hours_by_machine.set_index("Maquina"))

            st.markdown("---")
            st.markdown("**Top operadores por horas**")
            top_ops = df.groupby("Operador")["HorasTrabajadas"].sum().reset_index().sort_values("HorasTrabajadas", ascending=False).head(10)
            st.table(top_ops)

# ---------------------------
# Página: Configuración
# ---------------------------
elif menu == "Configuración":
    st.markdown("### ⚙️ Configuración", unsafe_allow_html=True)
    st.markdown("Asegúrate de agregar los siguientes `secrets` en Streamlit Cloud:")
    st.code(
        """
# En Settings / Secrets (formato JSON / text)
OPENAI_API_KEY = "tu_api_key_openai"
CREDENCIALES_GOOGLE = '{ ... JSON completo de la cuenta de servicio ... }'
        """
    )
    st.markdown("Si quieres, puedo añadir autenticación (login) y roles (admin / operador) en la próxima versión.")

# ---------------------------
# Mensajes de errores de conexión (si los hay)
# ---------------------------
if gspread_error:
    st.sidebar.error("Error Google Sheets: revisa CREDENCIALES_GOOGLE en Secrets.")
if openai_error:
    st.sidebar.warning("OpenAI no configurado: activa OPENAI_API_KEY en Secrets si quieres transcripciones.")

# ---------------------------
# Footer / Créditos
# ---------------------------
st.markdown("---")
st.markdown('<div style="font-size:12px; color:#6B7280">Desarrollado para uso interno • Jhan C. Herrera Orbezo</div>', unsafe_allow_html=True)

