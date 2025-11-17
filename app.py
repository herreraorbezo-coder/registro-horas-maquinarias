# app.py - Versión profesional (Estilo A: Corporativo Azul/Gris + Logo)
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import datetime
import json
import io

# ---------------------------
# Configuración de página
# ---------------------------
st.set_page_config(
    page_title="Horas Maquinaria - Dashboard",
    page_icon="🚜",
    layout="wide",
)

# ---------------------------
# Estilos CSS personalizados
# ---------------------------
st.markdown("""
    <style>
    .main {background-color: #f5f7fa;}
    .stButton>button {background-color: #0a3d62; color: white; border-radius: 8px;}
    .stTextInput>div>div>input {border-radius: 8px; border: 1px solid #d1d8e0;}
    </style>
""", unsafe_allow_html=True)

# ---------------------------
# Logo
# ---------------------------
LOGO = "https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/assets/aguaytia_logo.png"
st.image(LOGO, width=200)

# ---------------------------
# Conexión a Google Sheets
# ---------------------------
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS_JSON = "creds.json"  # Archivo JSON de la cuenta de servicio
try:
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_JSON, SCOPE)
    client = gspread.authorize(creds)
except Exception as e:
    st.error(f"No se pudo conectar a Google Sheets: {e}")

# ---------------------------
# Selección de hoja
# ---------------------------
SHEET_NAME = "Horas Maquinaria"
try:
    sheet = client.open(SHEET_NAME).sheet1
except Exception as e:
    st.error(f"No se pudo abrir la hoja '{SHEET_NAME}': {e}")

# ---------------------------
# Funciones
# ---------------------------
def leer_datos():
    try:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        return df
    except Exception as e:
        st.error(f"Error al leer datos: {e}")
        return pd.DataFrame()

def agregar_registro(fecha, maquinaria, horas, observaciones):
    try:
        sheet.append_row([fecha, maquinaria, horas, observaciones])
        st.success("Registro agregado correctamente ✅")
    except Exception as e:
        st.error(f"No se pudo agregar registro: {e}")

# ---------------------------
# Interfaz de usuario
# ---------------------------
st.title("Dashboard de Horas de Maquinaria 🚜")
st.subheader("Registrar nueva actividad")

with st.form(key="form_registro"):
    col1, col2 = st.columns(2)
    with col1:
        fecha = st.date_input("Fecha", datetime.date.today())
        maquinaria = st.text_input("Maquinaria")
    with col2:
        horas = st.number_input("Horas trabajadas", min_value=0.0, step=0.5)
        observaciones = st.text_area("Observaciones")

    submit_button = st.form_submit_button(label="Agregar registro")
    if submit_button:
        agregar_registro(fecha.strftime("%d/%m/%Y"), maquinaria, horas, observaciones)

# ---------------------------
# Mostrar datos
# ---------------------------
st.subheader("Registro de horas")
df = leer_datos()
if not df.empty:
    st.dataframe(df)
    # Exportar a CSV
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Descargar CSV",
        data=csv,
        file_name="horas_maquinaria.csv",
        mime="text/csv"
    )
else:
    st.info("No hay registros aún.")

# ---------------------------
# Footer
# ---------------------------
st.markdown("""
    <div style='text-align:center; padding:10px; color:#576574;'>
    © 2025 Tu Empresa - Todos los derechos reservados
    </div>
""", unsafe_allow_html=True)
