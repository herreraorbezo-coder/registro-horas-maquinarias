# app.py (PARTE A) - Inicio, imports, estilo (Oscuro negro/amarillo), conexión segura a Google Sheets
# Requisitos (requirements.txt): streamlit, gspread, oauth2client, pandas, openai (opcional)

import streamlit as st
import json
import pandas as pd
import datetime
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re

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
# Page config & dark style (Estilo B: Negro/Amarillo)
# ---------------------------
st.set_page_config(page_title="Horas Maquinaria - Dashboard", page_icon="🚜", layout="wide")
st.markdown(
    """
    <style>
    :root{
      --bg:#0b0b0d;
      --card:#0f1720;
      --accent:#f6c94a;
      --muted:#9aa0a6;
      --border:#1f2933;
      --text:#e6e6e6;
    }
    html, body, .stApp { background: var(--bg); color: var(--text); }
    .app-header{ background: linear-gradient(90deg, #070708 0%, #101214 100%); color: var(--text); padding: 18px; border-radius: 8px; margin-bottom: 14px; border: 1px solid var(--border); }
    .app-sub{ color: var(--muted); margin-top: -6px; font-size:13px; }
    .card{ background: var(--card); padding: 12px; border-radius: 10px; border: 1px solid var(--border); }
    .kpi-dark{ background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)); padding:12px; border-radius:10px; border-left:6px solid var(--accent); }
    .kpi-value { font-size:20px; font-weight:800; color: var(--accent); }
    .kpi-label { font-size:12px; color: var(--muted); }
    .muted{ color: var(--muted); font-size:13px; }
    .stButton>button{ background-color: var(--accent); color: #000; border: none; font-weight:700; }
    .stDownloadButton>button{ background-color: #ffd966; color: #000; border: none; }
    table.dataframe { color: var(--text) !important; }
    .streamlit-expanderHeader { color: var(--text) !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="app-header">
        <h2 style="margin:0; font-weight:700">🚜 CONTROL DE HORAS MAQUINARIA - AGUAYTIA ENERGY PERÚ</h2>
        <div class="app-sub">Registro · Observaciones por audio · Historial · Reportes · KPIs mantenimiento</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------
# Conexión segura a Google Sheets (manejo robusto de formatos de secrets)
# ---------------------------
gspread_error = None
sheet = None
gc = None

try:
    if "gcp_service_account" not in st.secrets:
        raise KeyError("No se encontró el bloque [gcp_service_account] en Streamlit Secrets.")

    gcp_secret = st.secrets["gcp_service_account"]

    # Caso A: secrets tiene CREDENCIALES_GOOGLE como JSON string
    service_account_info = None
    if isinstance(gcp_secret, dict) and "CREDENCIALES_GOOGLE" in gcp_secret and isinstance(gcp_secret["CREDENCIALES_GOOGLE"], str) and gcp_secret["CREDENCIALES_GOOGLE"].strip() != "":
        # intenta parsear JSON
        try:
            service_account_info = json.loads(gcp_secret["CREDENCIALES_GOOGLE"])
        except Exception as e_json:
            # si falla, intentamos limpiar comillas y nuevos saltos
            s = gcp_secret["CREDENCIALES_GOOGLE"]
            s = s.strip().strip("'").strip('"')
            try:
                service_account_info = json.loads(s)
            except Exception:
                raise ValueError("CREDENCIALES_GOOGLE existe pero no es JSON válido: " + str(e_json))
    elif isinstance(gcp_secret, dict) and "type" in gcp_secret and gcp_secret.get("type") == "service_account":
        # Caso B: secrets contiene directamente las claves TOML (type, project_id, private_key, ...)
        service_account_info = dict(gcp_secret)
        # Si private_key contiene '\n' como literales sin escapes, ya está bien.
        # Si el private_key fue pegado multilínea, Streamlit lo puede almacenar reemplazando saltos; ambos casos manejables.
    else:
        # Soporte adicional: si gcp_secret es string con JSON
        if isinstance(gcp_secret, str):
            try:
                service_account_info = json.loads(gcp_secret)
            except Exception:
                raise ValueError("El bloque [gcp_service_account] no está en formato esperado (string no JSON).")
        else:
            raise ValueError("El bloque [gcp_service_account] no está en formato esperado.")

    # Asegurar presence de campo 'private_key' con saltos \n en forma de escape
    if "private_key" in service_account_info and isinstance(service_account_info["private_key"], str):
        pk = service_account_info["private_key"]
        # Si la key contiene caracteres reales de nueva línea, reemplazamos por \n escapes para compatibilidad
        if "\n" in pk and "\\n" not in pk:
            # Convertir a escaped newline string (gspread/oauth2client acepta con \n o con newlines; keep as-is)
            # Algunos entornos requieren literal \n inside string; oauth2client handles actual newlines fine.
            service_account_info["private_key"] = pk
    else:
        raise ValueError("La credencial no contiene private_key válido.")

    # Scope para Sheets y Drive
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(service_account_info, scope)
    gc = gspread.authorize(creds)

    SHEET_NAME = "Horas_Maquinaria"
    sh = gc.open(SHEET_NAME)
    sheet = sh.sheet1

except Exception as e:
    gspread_error = str(e)
    sheet = None
    gc = None
# app.py (PARTE B) - utilidades, fetch/append, KPIs, Registro de horas UI

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
            st.markdown(f'<div class="kpi-dark"><div class="kpi-value">{kpis["horas_hoy"]:.2f} hrs</div><div class="kpi-label">Horas hoy</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="height:8px"></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="kpi-dark"><div class="kpi-value">{kpis["horas_7dias"]:.2f} hrs</div><div class="kpi-label">Horas últimos 7 días</div></div>', unsafe_allow_html=True)
        with c2:
            st.markdown(f'<div class="kpi-dark"><div class="kpi-value">{kpis["promedio_horas"]:.2f} hrs</div><div class="kpi-label">Promedio por registro</div></div>', unsafe_allow_html=True)
            st.markdown(f'<div style="height:8px"></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="kpi-dark"><div class="kpi-value">{kpis["maquina_top"][0]}</div><div class="kpi-label">Máquina top ({kpis["maquina_top"][1]:.1f} h)</div></div>', unsafe_allow_html=True)
# app.py (PARTE C) - Historial, Reportes, Configuración, Footer

# ---------------------------
# Página: Observaciones por audio
# (ya incluida arriba; continuar con Historial)
# ---------------------------

# ---------------------------
# Página: Historial
# ---------------------------
elif menu == "Historial":
    st.markdown("### 📚 Historial de registros")
    if df_all.empty:
        st.info("No hay registros aún.")
    else:
        # convertir Fecha a datetime.date si no lo es
        try:
            df_all["Fecha"] = pd.to_datetime(df_all["Fecha"]).dt.date
        except Exception:
            pass

        # filtros
        c1, c2, c3 = st.columns([2,2,2])
        with c1:
            filtro_op = st.selectbox("Filtrar por operador", options=["Todos"] + sorted(df_all["Operador"].dropna().unique().tolist()))
        with c2:
            filtro_maq = st.selectbox("Filtrar por máquina", options=["Todos"] + sorted(df_all["Maquina"].dropna().unique().tolist()))
        with c3:
            fecha_min = df_all["Fecha"].min() if not df_all.empty else datetime.date.today()
            fecha_max = df_all["Fecha"].max() if not df_all.empty else datetime.date.today()
            fecha_range = st.date_input("Rango de fecha (desde - hasta)", [fecha_min, fecha_max])

        df_display = df_all.copy()
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
# Página: Reportes y KPIs avanzados
# ---------------------------
elif menu == "Reportes":
    st.markdown("### 📊 Reportes y KPIs")
    kpis = compute_kpis(df_all)

    # KPIs generales
    cols = st.columns(4)
    cols[0].markdown(f'<div class="kpi-dark"><div class="kpi-value">{kpis["horas_hoy"]:.1f} hrs</div><div class="kpi-label">Horas hoy</div></div>', unsafe_allow_html=True)
    cols[1].markdown(f'<div class="kpi-dark"><div class="kpi-value">{kpis["horas_7dias"]:.1f} hrs</div><div class="kpi-label">Horas últimos 7 días</div></div>', unsafe_allow_html=True)
    cols[2].markdown(f'<div class="kpi-dark"><div class="kpi-value">{kpis["horas_mes"]:.1f} hrs</div><div class="kpi-label">Horas últimos 30 días</div></div>', unsafe_allow_html=True)
    cols[3].markdown(f'<div class="kpi-dark"><div class="kpi-value">{kpis["promedio_horas"]:.2f} hrs</div><div class="kpi-label">Promedio por registro</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    # Horas por máquina (total)
    st.markdown("**Horas por máquina (total)**")
    hours_by_machine = pd.DataFrame(list(kpis["hours_by_machine"].items()), columns=["Maquina","Horas"]).sort_values("Horas", ascending=False)
    if not hours_by_machine.empty:
        st.bar_chart(hours_by_machine.set_index("Maquina"))
    else:
        st.info("No hay datos por máquina para graficar.")

    st.markdown("---")
    # Top operadores
    st.markdown("**Top operadores por horas**")
    top_ops = df_all.groupby("Operador")["HorasTrabajadas"].sum().reset_index().sort_values("HorasTrabajadas", ascending=False).head(10)
    st.table(top_ops)

    st.markdown("---")
    # KPIs de mantenimiento (estimados)
    st.markdown("### 🛠️ KPIs de mantenimiento (estimaciones a partir de Observaciones)")
    col_a, col_b = st.columns([2,3])
    with col_a:
        st.markdown("**Disponibilidad (últimos 30 días)**")
        av_df = pd.DataFrame(list(kpis["availability_30d"].items()), columns=["Maquina","Disponibilidad_30d_%"]).sort_values("Disponibilidad_30d_%", ascending=False)
        st.dataframe(av_df)
    with col_b:
        st.markdown("**MTBF / MTTR (estimados)**")
        mtbf_df = pd.DataFrame(list(kpis["mtbf_by_machine"].items()), columns=["Maquina","MTBF_h"])
        mttr_df = pd.DataFrame(list(kpis["mttr_by_machine"].items()), columns=["Maquina","MTTR_h_est"])
        mt_df = mtbf_df.merge(mttr_df, on="Maquina", how="outer")
        st.dataframe(mt_df.fillna("N/A"))

    st.markdown("---")
    st.markdown("**Máquinas sin uso en últimos 7 días**")
    st.write(kpis["maquinas_inactivas_7d"] or "Ninguna")

    st.markdown("---")
    st.markdown("**Días sin uso por máquina (desde última fecha registrada)**")
    st.dataframe(pd.DataFrame(list(kpis["dias_inactivos_por_maquina"].items()), columns=["Maquina","Dias_sin_uso"]).sort_values("Dias_sin_uso", ascending=False))

    st.markdown("---")
    st.markdown("**Registros con observaciones / %**")
    st.write(f'{kpis["registros_con_observaciones"]} registros ({kpis["porc_registros_con_observaciones"]}%)')

# ---------------------------
# Página: Configuración
# ---------------------------
elif menu == "Configuración":
    st.markdown("### ⚙️ Configuración")
    st.markdown("Asegúrate de agregar los siguientes `secrets` en Streamlit Cloud (ejemplo):")
    st.code(
        """
# En Settings / Secrets (TOML)
OPENAI_API_KEY = "tu_api_key_openai"

[gcp_service_account]
type = "service_account"
project_id = "registro-horas-maquinaria"
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----"
client_email = "acceso-sheets@registro-horas-maquinaria.iam.gserviceaccount.com"
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
        """
    )
    st.markdown("Si lo deseas, puedo añadir validaciones, intervalos de mantenimiento (250h/500h) y alertas (Telegram/Correo).")

# ---------------------------
# Footer / Créditos
# ---------------------------
st.markdown("---")
st.markdown('<div style="font-size:12px; color:#9aa0a6">Desarrollado para uso interno • Jhan C. Herrera Orbezo</div>', unsafe_allow_html=True)

