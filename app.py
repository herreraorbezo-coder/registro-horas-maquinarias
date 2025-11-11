import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import json

st.title("📋 Registro de Horas de Maquinaria Pesada")

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credenciales_info = json.loads(st.secrets["CREDENCIALES_GOOGLE"])
credenciales = ServiceAccountCredentials.from_json_keyfile_dict(credenciales_info, scope)
cliente = gspread.authorize(credenciales)

sheet = cliente.open("Horas_Maquinaria").sheet1

operador = st.text_input("👷 Nombre del operador")
maquina = st.selectbox("🚜 Seleccionar máquina", ["Telehandler JCB", "UPTIMOS D600", "CRetroexcavadora LIU GONG", "CAMION volkswagen 31-320", "EXCAVADORA HYUNDAI"])
horometro_inicial = st.number_input("🔢 Horómetro inicial (hrs)", min_value=0.0)
horometro_final = st.number_input("🔢 Horómetro final (hrs)", min_value=0.0)
fecha = st.date_input("📅 Fecha", datetime.date.today())
observaciones = st.text_area("📝 Observaciones")

if st.button("Enviar registro"):
    horas_trabajadas = horometro_final - horometro_inicial
    sheet.append_row([str(fecha), operador, maquina, horometro_inicial, horometro_final, horas_trabajadas, observaciones])
    st.success(f"✅ Registro enviado correctamente. Total de horas: {horas_trabajadas:.2f} hrs.")