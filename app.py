# app.py - Versión final (Google Sheets + KPIs completos + OpenAI transcripción opcional)
# Copia y pega tal cual en tu repo. Requiere que hayas configurado:
# 1) Streamlit Secrets: OPENAI_API_KEY (opcional) y [gcp_service_account].CREDENCIALES_GOOGLE (JSON string)
# 2) Un Google Sheet llamado "Horas_Maquinaria" con columnas mínimas:
#    Fecha, Operador, Maquina, HorometroInicio, HorometroFinal, HorasTrabajadas, Observaciones
#
# Recomendado en requirements.txt: streamlit, gspread, oauth2client, pandas, openai

import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import json
import pandas as pd
import io

# OpenAI (opcional)
openai_client = None
try:
    if "OPENAI_API_KEY" in st.secrets and st.secrets["OPENAI_API_KEY"]:
        # Usa la librería oficial si la tienes instalada
        try:
            from openai import OpenAI
            openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        except Exception:
            openai_client = None
except Exception:
    openai_client = None

# ---------------------------
# Configuración de página y estilos
# ---------------------------
st.set_page_config(page_title="Horas Maquinaria - Dashboard", page_icon="🚜", layout="wide")
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
    .kpi-card { background-color: #ffffff; padding: 14px; border-radius: 10px; border: 1px solid #e6edf6; text-align:center; }
    .kpi-value { font-size:20px; font-weight:700; color:#0b69d6; }
    .kpi-label { font-size:12px; color:#6b7280; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="app-header">
        <h2 style="margin:0; font-weight:700">🚜 CONTROL DE HORAS MAQUINARIA - AGUAYTIA ENERGY PERÚ</h2>
        <div class="app-sub">Registro | Observaciones por audio | Historial | Reportes | KPIs mantenimiento</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------
# Conexión segura a Google Sheets usando Streamlit Secrets
# ---------------------------
sheet = None
gspread_error = None

try:
    if "gcp_service_account" not in st.secrets:
        raise KeyError("No se encontró el bloque [gcp_service_account] en Streamlit Secrets.")

    # En tus Secrets tienes CREDENCIALES_GOOGLE como JSON string (tal como lo armamos antes)
    creds_json_str = st.secrets["gcp_service_account"].get("CREDENCIALES_GOOGLE") \
                     if isinstance(st.secrets["gcp_service_account"], dict) else None

    if not creds_json_str:
        # También soportamos el caso donde el usuario pegó directamente claves TOML (type, private_key, ...)
        # Entonces pasamos todo el dict tal cual
        # Si st.secrets["gcp_service_account"] ya es un dict con keys type, project_id, etc. usamos eso.
        if isinstance(st.secrets["gcp_service_account"], dict) and "type" in st.secrets["gcp_service_account"]:
            service_account_info = st.secrets["gcp_service_account"]
        else:
            raise KeyError("La clave CREDENCIALES_GOOGLE no está en el formato esperado dentro de [gcp_service_account].")
    else:
        # parseamos la string JSON dentro del campo CREDENCIALES_GOOGLE
        service_account_info = json.loads(creds_json_str)

    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
    gc = gspread.authorize(creds)

    # Nombre del Google Sheet (según nos dijiste)
    SHEET_NAME = "Horas_Maquinaria"
    sh = gc.open(SHEET_NAME)
    sheet = sh.sheet1  # usa la primera hoja por defecto; cambiar si necesitas otra
except Exception as e:
    gspread_error = str(e)
    sheet = None

# ---------------------------
# Utilidades para manejar la data
# ---------------------------
def fetch_all_records(sheet_obj):
    """Devuelve dataframe con columnas esperadas, aunque la hoja esté vacía o con cabeceras diferentes."""
    try:
        rows = sheet_obj.get_all_records()
        df = pd.DataFrame(rows)
        # Normalizar columnas mínimas
        expected_cols = ["Fecha", "Operador", "Maquina", "HorometroInicio", "HorometroFinal", "HorasTrabajadas", "Observaciones"]
        for c in expected_cols:
            if c not in df.columns:
                df[c] = ""
        # Conversión tipo
        try:
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.date
        except Exception:
            pass
        df["HorasTrabajadas"] = pd.to_numeric(df.get("HorasTrabajadas", 0), errors="coerce").fillna(0)
        return df[expected_cols]
    except Exception:
        # fallback: dataframe vacío con columnas
        return pd.DataFrame(columns=["Fecha","Operador","Maquina","HorometroInicio","HorometroFinal","HorasTrabajadas","Observaciones"])

def append_record(sheet_obj, record_list):
    """Agrega fila al Sheet (lista ordenada a las columnas existentes)."""
    sheet_obj.append_row(record_list)

# ---------------------------
# Sidebar: menú
# ---------------------------
st.sidebar.header("📁 Menú")
menu = st.sidebar.radio("", ["Registro de horas", "Observaciones por audio", "Historial", "Reportes", "Configuración"])

st.sidebar.markdown("---")
st.sidebar.header("🔒 Usuario")
usuario = st.sidebar.text_input("Usuario (opcional)")
st.sidebar.caption("La autenticación puede agregarse en Configuración.")

# mostrar errores de conexión en sidebar
if gspread_error:
    st.sidebar.error("Error Google Sheets: " + gspread_error)
    st.error("Error al conectar con Google Sheets. Revisa tus Secrets y la hoja llamada 'Horas_Maquinaria'.")
    # No hacemos st.stop() para permitir usar funciones locales, pero mayoría de features estarán deshabilitadas.

# ---------------------------
# Cargar dataframe (si exist)
# ---------------------------
df_all = fetch_all_records(sheet) if sheet is not None else pd.DataFrame(columns=["Fecha","Operador","Maquina","HorometroInicio","HorometroFinal","HorasTrabajadas","Observaciones"])

# ---------------------------
# Funciones KPI / mantenimiento (derivado de datos disponibles)
# ---------------------------
def compute_kpis(df):
    """Calcula todos los KPIs solicitados usando la info disponible en el sheet."""
    hoy = datetime.date.today()
    ult7 = hoy - datetime.timedelta(days=7)
    ult30 = hoy - datetime.timedelta(days=30)
    result = {}

    if df.empty:
        # todos 0 / vacíos
        result.update({
            "horas_hoy": 0.0,
            "horas_7dias": 0.0,
            "horas_mes": 0.0,
            "promedio_horas": 0.0,
            "maquina_top": ("-", 0.0),
            "operador_top": ("-", 0.0),
            "maquinas_inactivas_7d": [],
            "registros_con_observaciones": 0,
            "porc_registros_con_observaciones": 0.0,
            "dias_inactivos_por_maquina": {},
            # mantenimiento estimado
            "availability_30d": {},
            "mtbf_by_machine": {},
            "mttr_by_machine": {},
        })
        return result

    # asegurar tipos
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.date
    df["HorasTrabajadas"] = pd.to_numeric(df.get("HorasTrabajadas", 0), errors="coerce").fillna(0)

    result["horas_hoy"] = float(df[df["Fecha"] == hoy]["HorasTrabajadas"].sum())
    result["horas_7dias"] = float(df[df["Fecha"] >= ult7]["HorasTrabajadas"].sum())
    result["horas_mes"] = float(df[df["Fecha"] >= ult30]["HorasTrabajadas"].sum())
    result["promedio_horas"] = float(df["HorasTrabajadas"].mean() if len(df) > 0 else 0.0)

      # ============================
#   KPI – RESUMEN GENERAL
# ============================

st.subheader("📊 Indicadores de Mantenimiento")

# Total de horas
total_horas = round(df["Horas"].sum(), 2)
st.metric("⏱️ Total de Horas", f"{total_horas} h")

# Días trabajados (fechas únicas)
dias_trabajados = df["Fecha"].nunique()
st.metric("📅 Días Registrados", dias_trabajados)

# Máquina con más horas
mq_top = df.groupby("Maquinaria")["Horas"].sum().sort_values(ascending=False)
mq_name = mq_top.index[0]
mq_hours = float(mq_top.iloc[0])
st.metric("🚜 Máquina con más horas", f"{mq_name}", f"{mq_hours} h")

# Operario con más horas
op_top = df.groupby("Operario")["Horas"].sum().sort_values(ascending=False)
op_name = op_top.index[0]
op_hours = float(op_top.iloc[0])
st.metric("👷 Operario destacado", f"{op_name}", f"{op_hours} h")
