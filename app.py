import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import pandas as pd
from openai import OpenAI
import json
import io

# ---------------------------
# Configuración de página
# ---------------------------
st.set_page_config(page_title="Horas Maquinaria - Dashboard", page_icon="🚜", layout="wide")

st.markdown("""
    <style>
        .kpi-card {
            background-color: #1f3b4d;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            color: white;
            font-weight: bold;
            box-shadow: 0px 4px 10px rgba(0,0,0,0.3);
            border-left: 6px solid #4fa3d1;
        }
        .kpi-value {
            font-size: 28px;
            color: #4fa3d1;
            font-weight: bold;
        }
        .kpi-label {
            font-size: 14px;
            color: #d9e6f2;
        }
    </style>
""", unsafe_allow_html=True)

# ---------------------------
# Conexión con Google Sheets
# ---------------------------
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
client = gspread.authorize(creds)

SHEET_NAME = "RegistroHoras"
sheet = client.open(SHEET_NAME).sheet1

# ---------------------------
# Cargar datos
# ---------------------------
data = sheet.get_all_records()

df_all = pd.DataFrame(data)

if df_all.empty:
    st.warning("No hay datos en Google Sheets todavía.")
    st.stop()

# Convertir fechas
df_all["Fecha"] = pd.to_datetime(df_all["Fecha"], errors='coerce').dt.date
df_all["HorasTrabajadas"] = pd.to_numeric(df_all["HorasTrabajadas"], errors='coerce')

hoy = datetime.date.today()
ultimos_7 = hoy - datetime.timedelta(days=7)

# ---------------------------
# KPIs PROCESADOS
# ---------------------------

# KPI 1: Horas trabajadas HOY
horas_hoy = df_all[df_all["Fecha"] == hoy]["HorasTrabajadas"].sum()

# KPI 2: Horas últimos 7 días
horas_7dias = df_all[df_all["Fecha"] >= ultimos_7]["HorasTrabajadas"].sum()

# KPI 3: Promedio de horas por registro
promedio_horas = df_all["HorasTrabajadas"].mean()

# KPI 4: Máquina más utilizada (horas totales)
maquina_top = df_all.groupby("Maquina")["HorasTrabajadas"].sum().idxmax()
maquina_top_horas = df_all.groupby("Maquina")["HorasTrabajadas"].sum().max()

# KPI 5: Operador top
operador_top = df_all.groupby("Operador")["HorasTrabajadas"].sum().idxmax()
operador_top_horas = df_all.groupby("Operador")["HorasTrabajadas"].sum().max()

# KPI 6: Máquinas sin uso últimos 7 días
maquinas_activas = df_all[df_all["Fecha"] >= ultimos_7]["Maquina"].unique()
todas_maquinas = df_all["Maquina"].unique()
maquinas_inactivas = [m for m in todas_maquinas if m not in maquinas_activas]

# KPI 7: Registros con observaciones
reg_obs = df_all[df_all["Observaciones"].astype(str).str.strip() != ""].shape[0]

# KPI 8: % de registros con observaciones
porc_obs = round((reg_obs / len(df_all)) * 100, 1)

# KPI 9: Días sin actividad por máquina
dias_inactivos = {}
for m in todas_maquinas:
    ult_fecha = df_all[df_all["Maquina"] == m]["Fecha"].max()
    dias_inactivos[m] = (hoy - ult_fecha).days

# ---------------------------
# MOSTRAR KPIs EN TARJETAS
# ---------------------------
st.title("🚜 Dashboard de Control de Horas - Maquinarias")

col1, col2, col3, col4 = st.columns(4)
col5, col6, col7, col8 = st.columns(4)

col1.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value">{horas_hoy:.1f}</div>
        <div class="kpi-label">Horas trabajadas hoy</div>
    </div>
""", unsafe_allow_html=True)

col2.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value">{horas_7dias:.1f}</div>
        <div class="kpi-label">Horas últimos 7 días</div>
    </div>
""", unsafe_allow_html=True)

col3.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value">{promedio_horas:.2f}</div>
        <div class="kpi-label">Promedio horas por registro</div>
    </div>
""", unsafe_allow_html=True)

col4.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value">{maquina_top}</div>
        <div class="kpi-label">Máquina más utilizada ({maquina_top_horas:.1f} h)</div>
    </div>
""", unsafe_allow_html=True)

col5.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value">{operador_top}</div>
        <div class="kpi-label">Operador con más horas ({operador_top_horas:.1f} h)</div>
    </div>
""", unsafe_allow_html=True)

col6.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value">{len(maquinas_inactivas)}</div>
        <div class="kpi-label">Máquinas sin uso últimos 7 días</div>
    </div>
""", unsafe_allow_html=True)

col7.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value">{reg_obs}</div>
        <div class="kpi-label">Registros con observaciones</div>
    </div>
""", unsafe_allow_html=True)

col8.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value">{porc_obs}%</div>
        <div class="kpi-label">Porcentaje con observaciones</div>
    </div>
""", unsafe_allow_html=True)

# ---------------------------
# TABLAS DE APOYO
# ---------------------------
st.subheader("📌 Máquinas con días sin actividad")
df_dias_inactivos = pd.DataFrame({
    "Máquina": dias_inactivos.keys(),
    "Días sin uso": dias_inactivos.values()
})
st.dataframe(df_dias_inactivos)

st.subheader("📌 Datos completos")
st.dataframe(df_all)
