# app.py - Final (Google Sheets + KPIs + OpenAI opcional)
# Requisitos (requirements.txt): streamlit, gspread, oauth2client, pandas, openai (opcional)

import streamlit as st
import json
import pandas as pd
import datetime
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------------------------
# Opcional: cliente OpenAI (si OPENAI_API_KEY en secrets)
# ---------------------------
openai_client = None
try:
    if st.secrets.get("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            openai_client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        except Exception:
            openai_client = None
except Exception:
    openai_client = None

# ---------------------------
# Page config & styles
# ---------------------------
st.set_page_config(page_title="Horas Maquinaria - Dashboard", page_icon="🚜", layout="wide")
st.markdown(
    """
    <style>
    :root{--primary:#0052A2;--text:#1F2937;--card-bg:#ffffff;--border:#E5E7EB;}
    .app-header{background: linear-gradient(90deg,#0052A2 0%,#004A91 100%); color:#fff; padding:18px; border-radius:8px; margin-bottom:16px;}
    .app-sub{color:#E6EEF8; margin-top:-6px; font-size:13px;}
    .card{background:var(--card-bg); padding:14px; border-radius:10px; box-shadow:0 4px 10px rgba(0,0,0,0.06); border:1px solid var(--border);}
    .kpi-card{background:#fff;padding:12px;border-radius:10px;border:1px solid #e6edf6;text-align:center;}
    .kpi-value{font-size:20px;font-weight:700;color:#0b69d6;}
    .kpi-label{font-size:12px;color:#6b7280;}
    .muted{color:#6b7280;font-size:13px;}
    .stButton>button{background-color:var(--primary); color:white; border: none;}
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
# Google Sheets connection via Streamlit Secrets
# ---------------------------
gspread_error = None
sheet = None
gc = None

try:
    if "gcp_service_account" not in st.secrets:
        raise KeyError("No se encontró el bloque [gcp_service_account] en Streamlit Secrets.")

    # Dos formatos posibles en secrets:
    # 1) st.secrets["gcp_service_account"]["CREDENCIALES_GOOGLE"] -> JSON string
    # 2) st.secrets["gcp_service_account"] -> dict con keys directas (type, project_id, private_key, ...)
    gcp_secret = st.secrets["gcp_service_account"]

    # Detectar y parsear JSON string si existe
    if isinstance(gcp_secret, dict) and "CREDENCIALES_GOOGLE" in gcp_secret and gcp_secret["CREDENCIALES_GOOGLE"]:
        try:
            service_account_info = json.loads(gcp_secret["CREDENCIALES_GOOGLE"])
        except Exception as e:
            raise ValueError("El campo CREDENCIALES_GOOGLE no contiene JSON válido: " + str(e))
    elif isinstance(gcp_secret, dict) and "type" in gcp_secret:
        # El usuario pegó las claves directamente como TOML -> ya es dict válido
        service_account_info = gcp_secret
    else:
        raise ValueError("El bloque [gcp_service_account] no está en formato esperado.")

    # Scopes para Sheets & Drive
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
    gc = gspread.authorize(creds)

    # Abrir el Google Sheet (nombre que diste)
    SHEET_NAME = "Horas_Maquinaria"
    sh = gc.open(SHEET_NAME)
    sheet = sh.sheet1  # primera hoja; cambiar si necesitas otra
except Exception as e:
    gspread_error = str(e)
    sheet = None
    gc = None

# ---------------------------
# Utilidades: leer y escribir
# ---------------------------
def fetch_all_records(sheet_obj):
    try:
        rows = sheet_obj.get_all_records()
        df = pd.DataFrame(rows)
    except Exception:
        df = pd.DataFrame(columns=["Fecha","Operador","Maquina","HorometroInicio","HorometroFinal","HorasTrabajadas","Observaciones"])

    # Normalizar y asegurar columnas mínimas
    expected = ["Fecha","Operador","Maquina","HorometroInicio","HorometroFinal","HorasTrabajadas","Observaciones"]
    for c in expected:
        if c not in df.columns:
            df[c] = ""

    # Convertir tipos
    try:
        df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.date
    except Exception:
        pass
    df["HorasTrabajadas"] = pd.to_numeric(df.get("HorasTrabajadas", 0), errors="coerce").fillna(0)

    return df[expected]

def append_record(sheet_obj, record_list):
    sheet_obj.append_row(record_list)

# Inicializar dataframe global
df_all = fetch_all_records(sheet) if sheet is not None else pd.DataFrame(columns=["Fecha","Operador","Maquina","HorometroInicio","HorometroFinal","HorasTrabajadas","Observaciones"])

# Mostrar error de conexión si existe
if gspread_error:
    st.sidebar.error("Error Google Sheets: " + gspread_error)
    st.error("Error conectando a Google Sheets. Revisa tus Secrets y el nombre del sheet.")

# ---------------------------
# KPI computation
# ---------------------------
def compute_kpis(df):
    hoy = datetime.date.today()
    ult7 = hoy - datetime.timedelta(days=7)
    ult30 = hoy - datetime.timedelta(days=30)

    result = {}
    if df.empty:
        return {
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
            "hours_by_machine": {},
            "availability_30d": {},
            "mtbf_by_machine": {},
            "mttr_by_machine": {}
        }

    # ensure types
    df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce").dt.date
    df["HorasTrabajadas"] = pd.to_numeric(df.get("HorasTrabajadas", 0), errors="coerce").fillna(0)

    result["horas_hoy"] = float(df[df["Fecha"] == hoy]["HorasTrabajadas"].sum())
    result["horas_7dias"] = float(df[df["Fecha"] >= ult7]["HorasTrabajadas"].sum())
    result["horas_mes"] = float(df[df["Fecha"] >= ult30]["HorasTrabajadas"].sum())
    result["promedio_horas"] = float(df["HorasTrabajadas"].mean() if len(df) > 0 else 0.0)

    # top maquina / operador
    try:
        agg_mq = df.groupby("Maquina")["HorasTrabajadas"].sum()
        mq_top = agg_mq.idxmax()
        mq_top_h = float(agg_mq.max())
        result["maquina_top"] = (mq_top, mq_top_h)
    except Exception:
        result["maquina_top"] = ("-", 0.0)

    try:
        agg_op = df.groupby("Operador")["HorasTrabajadas"].sum()
        op_top = agg_op.idxmax()
        op_top_h = float(agg_op.max())
        result["operador_top"] = (op_top, op_top_h)
    except Exception:
        result["operador_top"] = ("-", 0.0)

    # maquinas inactivas 7d
    maquinas_activas_7 = set(df[df["Fecha"] >= ult7]["Maquina"].dropna().unique().tolist())
    todas_maquinas = set(df["Maquina"].dropna().unique().tolist())
    result["maquinas_inactivas_7d"] = sorted(list(todas_maquinas - maquinas_activas_7))

    # observaciones %
    df["Observaciones"] = df["Observaciones"].astype(str)
    reg_obs = df[df["Observaciones"].str.strip() != ""].shape[0]
    result["registros_con_observaciones"] = int(reg_obs)
    result["porc_registros_con_observaciones"] = round((reg_obs / len(df)) * 100, 1) if len(df) > 0 else 0.0

    # dias inactivos por maquina
    dias_inact = {}
    for m in todas_maquinas:
        try:
            ult = df[df["Maquina"] == m]["Fecha"].dropna().max()
            dias = (hoy - ult).days if pd.notna(ult) else None
            dias_inact[m] = dias
        except Exception:
            dias_inact[m] = None
    result["dias_inactivos_por_maquina"] = dias_inact

    # hours by machine
    result["hours_by_machine"] = df.groupby("Maquina")["HorasTrabajadas"].sum().to_dict()

    # availability last 30 days (days used / 30)
    availability = {}
    for m in todas_maquinas:
        used_days = df[(df["Maquina"] == m) & (df["Fecha"] >= ult30)]["Fecha"].nunique()
        availability[m] = round((used_days / 30) * 100, 1)
    result["availability_30d"] = availability

    # detect failures by keywords and estimate MTBF/MTTR
    keywords_fail = ["falla","parada","parado","repar","fault","stop","detenido","avería","averia","rotura"]
    df["has_fail"] = df["Observaciones"].str.lower().apply(lambda s: any(k in s for k in keywords_fail))
    failures_df = df[df["has_fail"]]

    mtbf = {}
    mttr = {}
    for m in todas_maquinas:
        total_hours = float(result["hours_by_machine"].get(m, 0.0))
        failures = int(failures_df[failures_df["Maquina"] == m].shape[0])
        mtbf[m] = round(total_hours / failures, 2) if failures > 0 and total_hours > 0 else None

        # try to parse durations in observations e.g. "2h", "3 horas"
        import re
        durations = []
        for obs in failures_df[failures_df["Maquina"] == m]["Observaciones"].astype(str).tolist():
            matches = re.findall(r"(\d+(\.\d+)?)\s*(h|hr|hrs|hora|horas)", obs.lower())
            for match in matches:
                try:
                    durations.append(float(match[0]))
                except:
                    pass
        mttr[m] = round(sum(durations)/len(durations),2) if durations else None

    result["mtbf_by_machine"] = mtbf
    result["mttr_by_machine"] = mttr

    return result

# ---------------------------
# Sidebar & menu
# ---------------------------
st.sidebar.header("📁 Menú")
menu = st.sidebar.radio("", ["Registro de horas", "Observaciones por audio", "Historial", "Reportes", "Configuración"])
st.sidebar.markdown("---")
st.sidebar.header("🔒 Usuario")
usuario = st.sidebar.text_input("Usuario (opcional)")

# ---------------------------
# Página: Registro de horas
# ---------------------------
if menu == "Registro de horas":
    col1, col2 = st.columns([2,1])
    with col1:
        st.markdown("### 📋 Datos del registro")
        with st.form("registro_form", clear_on_submit=False):
            operador = st.text_input("👷 Nombre del operador", max_chars=80)
            maquinas_list = sorted(df_all["Maquina"].dropna().unique().tolist()) if not df_all.empty else ["Telehandler JCB","UPTIMOS D600","Retroexcavadora LIU GONG","CAMION volkswagen 31-320","EXCAVADORA HYUNDAI"]
            maquina = st.selectbox("🚜 Seleccionar máquina", maquinas_list)
            fecha = st.date_input("📅 Fecha", datetime.date.today())
            horometro_inicial = st.number_input("🔢 Horómetro inicial (hrs)", min_value=0.0, format="%.2f")
            horometro_final = st.number_input("🔢 Horómetro final (hrs)", min_value=0.0, format="%.2f")
            observaciones = st.text_area("📝 Observaciones", height=120)
            submitted = st.form_submit_button("Enviar registro")
            if submitted:
                if horometro_final < horometro_inicial:
                    st.error("⚠️ El horómetro final no puede ser menor que el inicial.")
                elif not operador:
                    st.error("⚠️ Ingresa el nombre del operador.")
                else:
                    horas_trabajadas = round(horometro_final - horometro_inicial, 2)
                    if sheet is None:
                        st.error("❌ No se puede conectar a Google Sheets. Revisa tus Secrets.")
                    else:
                        try:
                            append_record(sheet, [str(fecha), operador, maquina, float(horometro_inicial), float(horometro_final), float(horas_trabajadas), observaciones])
                            st.success(f"✅ Registro guardado. Horas trabajadas: {horas_trabajadas:.2f} hrs.")
                            df_all = fetch_all_records(sheet)
                        except Exception as e:
                            st.error(f"❌ Error al guardar: {e}")

    with col2:
        st.markdown("### 📈 KPI rápido")
        kpis = compute_kpis(df_all)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f'<div class="kpi-card"><div class="kpi-value">{kpis["horas_hoy"]:.2f} hrs</div><div class="kpi-label">Horas hoy</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="height:8px"></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="kpi-card"><div class="kpi-value">{kpis["horas_7dias"]:.2f} hrs</div><div class="kpi-label">Horas últimos 7 días</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="kpi-card"><div class="kpi-value">{kpis["promedio_horas"]:.2f} hrs</div><div class="kpi-label">Promedio por registro</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="height:8px"></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="kpi-card"><div class="kpi-value">{kpis["maquina_top"][0]}</div><div class="kpi-label">Máquina top ({kpis["maquina_top"][1]:.1f} h)</div></div>', unsafe_allow_html=True)

# ---------------------------
# Página: Observaciones por audio
# ---------------------------
elif menu == "Observaciones por audio":
    st.markdown("### 🎤 Observaciones por audio → Texto")
    st.info("Sube un archivo de audio (mp3, wav, m4a). La transcripción se agregará al campo de observaciones al enviar el registro.")
    audio_file = st.file_uploader("Sube tu audio (mp3, wav, m4a)", type=["mp3","wav","m4a"])
    transcribed_text = ""
    if audio_file:
        st.audio(audio_file)
        if openai_client is None:
            st.warning("OpenAI no configurado o cliente no disponible: activa OPENAI_API_KEY en Secrets para transcribir automáticamente.")
        else:
            if st.button("Transcribir audio"):
                with st.spinner("Transcribiendo..."):
                    try:
                        res = openai_client.audio.transcriptions.create(model="gpt-4o-transcribe", file=audio_file)
                        transcribed_text = getattr(res, "text", None) or res.get("text", "") or str(res)
                        st.success("✅ Transcripción completada.")
                        st.write(transcribed_text)
                    except Exception as e:
                        st.error(f"Error en la transcripción: {e}")

    st.markdown("---")
    st.markdown("### 📝 Insertar transcripción en un nuevo registro")
    with st.form("audio_to_record"):
        operador_a = st.text_input("👷 Nombre del operador (para este registro)", max_chars=80)
        maquinas_list = sorted(df_all["Maquina"].dropna().unique().tolist()) if not df_all.empty else ["Telehandler JCB","UPTIMOS D600","Retroexcavadora LIU GONG","CAMION volkswagen 31-320","EXCAVADORA HYUNDAI"]
        maquina_a = st.selectbox("🚜 Máquina", maquinas_list, key="maquina_a")
        fecha_a = st.date_input("📅 Fecha", datetime.date.today(), key="fecha_a")
        hor_in = st.number_input("Horómetro inicial (hrs)", min_value=0.0, format="%.2f", key="hor_in")
        hor_fin = st.number_input("Horómetro final (hrs)", min_value=0.0, format="%.2f", key="hor_fin")
        obs_manual = st.text_area("Observaciones (puedes editar la transcripción)", value=transcribed_text, height=120)
        enviar_audio_reg = st.form_submit_button("Enviar registro con observaciones")
        if enviar_audio_reg:
            if hor_fin < hor_in:
                st.error
