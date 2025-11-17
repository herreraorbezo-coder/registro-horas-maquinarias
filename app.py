# app.py - Versión profesional con logo desde GitHub (compatible Streamlit Cloud)
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import json
import pandas as pd
from openai import OpenAI

# --------------------------------------------------------------------
# CONFIGURACIÓN: LOGO (CAMBIAR POR EL TUYO)
# --------------------------------------------------------------------
LOGO = "https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/assets/aguaytia_logo.png"

# --------------------------------------------------------------------
# Configuración de página
# --------------------------------------------------------------------
st.set_page_config(page_title="Horas Maquinaria - Dashboard", page_icon="🚜", layout="wide")

# --------------------------------------------------------------------
# Estilos CSS
# --------------------------------------------------------------------
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
        display: flex;
        align-items: center;
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
    .small { font-size:13px; color: #6B7280; }
    .kpi { font-size:22px; font-weight:700; color: var(--text); }
    .muted { color: #6B7280; font-size:13px; }
    .stButton>button { background-color: var(--primary); color: white; border: none; }
    .stDownloadButton>button { background-color: #0b69d6; color: white; border: none; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------
# ENCABEZADO CON LOGO (FUNCIONAL VERSION STREAMLIT)
# --------------------------------------------------------------------
st.markdown(
    f"""
    <div class="app-header">
        <img src="{LOGO}" width="80" style="margin-right:15px">
        <div>
            <h2 style="margin:0; font-weight:700">🚜 CONTROL DE HORAS DE MAQUINARIA - AGUAYTIA ENERGY PERÚ</h2>
            <div class="app-sub">Registro | Observaciones por audio | Historial | Reportes</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------
# Sidebar menú
# --------------------------------------------------------------------
st.sidebar.header("📁 Menú")
menu = st.sidebar.radio("", ["Registro de horas", "Observaciones por audio", "Historial", "Reportes", "Configuración"])

st.sidebar.markdown("---")
st.sidebar.header("🔒 Usuario")
usuario = st.sidebar.text_input("Usuario (opcional)")

# --------------------------------------------------------------------
# Conexiones
# --------------------------------------------------------------------
@st.cache_resource
def init_gspread():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_info = json.loads(st.secrets["CREDENCIALES_GOOGLE"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_info, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Horas_Maquinaria").sheet1
    return sheet

@st.cache_resource
def init_openai():
    return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

sheet = None
client = None
try:
    sheet = init_gspread()
except Exception as e:
    st.sidebar.error("⚠️ Google Sheets: " + str(e))

try:
    client = init_openai()
except:
    st.sidebar.warning("⚠️ OpenAI no configurado (solo afecta transcripciones).")

# --------------------------------------------------------------------
# Utilidades
# --------------------------------------------------------------------
def fetch_all_records(sheet_obj):
    try:
        df = pd.DataFrame(sheet_obj.get_all_records())
        if df.empty:
            return pd.DataFrame(columns=["Fecha","Operador","Maquina","HorometroInicio","HorometroFinal","HorasTrabajadas","Observaciones"])
        return df
    except:
        return pd.DataFrame()

def append_record(sheet_obj, record_list):
    sheet_obj.append_row(record_list)

# --------------------------------------------------------------------
# PÁGINA 1: Registro de horas
# --------------------------------------------------------------------
if menu == "Registro de horas":
    col1, col2 = st.columns([2,1])

    with col1:
        st.markdown("### 📋 Datos del registro")
        with st.form("registro_form"):
            operador = st.text_input("👷 Operador")
            maquina = st.selectbox("🚜 Máquina", [
                "Telehandler JCB", "UPTIMOS D600",
                "Retroexcavadora LIU GONG",
                "CAMION volkswagen 31-320",
                "EXCAVADORA HYUNDAI"
            ])
            fecha = st.date_input("📅 Fecha", datetime.date.today())
            hor_ini = st.number_input("Horómetro inicial", min_value=0.0, format="%.2f")
            hor_fin = st.number_input("Horómetro final", min_value=0.0, format="%.2f")
            obs = st.text_area("📝 Observaciones")

            enviar = st.form_submit_button("Enviar registro")

            if enviar:
                if hor_fin < hor_ini:
                    st.error("⚠️ Horómetro final inválido.")
                elif operador == "":
                    st.error("⚠️ Falta operador.")
                else:
                    horas = round(hor_fin - hor_ini, 2)
                    append_record(sheet, [str(fecha), operador, maquina, hor_ini, hor_fin, horas, obs])
                    st.success(f"Registro guardado. Horas: {horas}")

    with col2:
        df = fetch_all_records(sheet)
        total_horas = df["HorasTrabajadas"].astype(float).sum() if not df.empty else 0
        total_regs = len(df)

        card1, card2 = st.columns(2)
        card1.markdown(f'<div class="card"><div class="small">Total horas</div><div class="kpi">{total_horas:.2f}</div></div>', unsafe_allow_html=True)
        card2.markdown(f'<div class="card"><div class="small">Registros</div><div class="kpi">{total_regs}</div></div>', unsafe_allow_html=True)

# --------------------------------------------------------------------
# PÁGINA 2: Observaciones por audio
# --------------------------------------------------------------------
elif menu == "Observaciones por audio":
    st.markdown("### 🎤 Transcribir audio a texto")
    audio_file = st.file_uploader("Subir audio", type=["mp3","wav","m4a"])

    texto = ""
    if audio_file and client:
        if st.button("Transcribir"):
            res = client.audio.transcriptions.create(
                model="gpt-4o-transcribe",
                file=audio_file
            )
            texto = res.text
            st.success("Transcripción completada")
            st.write(texto)

# --------------------------------------------------------------------
# PÁGINA 3: Historial
# --------------------------------------------------------------------
elif menu == "Historial":
    st.markdown("### 📚 Historial")
    df = fetch_all_records(sheet)
    if df.empty:
        st.info("No hay datos.")
    else:
        st.dataframe(df)
        st.download_button("Descargar CSV", df.to_csv(index=False), "historial.csv")

# --------------------------------------------------------------------
# PÁGINA 4: Reportes
# --------------------------------------------------------------------
elif menu == "Reportes":
    df = fetch_all_records(sheet)
    if df.empty:
        st.info("No hay datos.")
    else:
        df["HorasTrabajadas"] = pd.to_numeric(df["HorasTrabajadas"], errors="coerce")
        st.bar_chart(df.groupby("Maquina")["HorasTrabajadas"].sum())

# --------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------
elif menu == "Configuración":
    st.markdown("### ⚙️ Secrets necesarios:")
    st.code("""
OPENAI_API_KEY = "tu_api_key"
CREDENCIALES_GOOGLE = '{ JSON COMPLETO }'
    """)

# --------------------------------------------------------------------
# FOOTER
# --------------------------------------------------------------------
st.markdown("---")
st.markdown('<div style="font-size:12px; color:#6B7280">Desarrollado para uso interno • Jhan Carlos Herrera Orbezo</div>', unsafe_allow_html=True)
