import streamlit as st
import pandas as pd
import requests
import numpy as np
import unicodedata
from datetime import datetime

# ===============================
# CONFIG
# ===============================
st.set_page_config(page_title="Radar Transparência ABSURDO FINAL", layout="wide")

SICONFI = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"
UA = {"User-Agent":"RadarTransparencia/3.0"}

st.title("🚨 Radar Transparência — ABSURDO FINAL (SICONFI/RREO)")
st.caption("Auditoria automática em dados públicos do Tesouro (SICONFI).")

# ===============================
# HELPERS
# ===============================
def normalize(txt):
    txt = str(txt)
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return txt.lower().strip()

def money(v):
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X",".")
    except:
        return "R$ 0,00"

def get_json(url, params=None):
    r = requests.get(url, params=params, timeout=40, headers=UA)
    r.raise_for_status()
    return r.json()

def pick(df, names):
    for n in names:
        if n in df.columns:
            return n
    return None

# ===============================
# CACHE
# ===============================
@st.cache_data(show_spinner=False)
def load_entes():
    data = get_json(f"{SICONFI}/entes")
    return pd.DataFrame(data.get("items",[]))

@st.cache_data(show_spinner=False)
def load_rreo(id_ente, ano, bimestre):
    params = {
        "id_ente": id_ente,
        "an_exercicio": ano,
        "nr_periodo": bimestre,
        "co_tipo_demonstrativo":"RREO"
    }
    data = get_json(f"{SICONFI}/rreo", params=params)
    return pd.DataFrame(data.get("items",[]))

# ===============================
# SIDEBAR
# ===============================
with st.sidebar:
    st.header("⚙️ Filtros")
    municipio = st.text_input("Município","São Vicente")
    uf = st.text_input("UF","SP").upper()

    ano = st.number_input("Ano",2018,2030,2025)
    bimestre = st.number_input("Bimestre",1,6,6)

    st.divider()
    st.subheader("🧠 Auditor")
    anos_hist = st.slider("Histórico",1,8,4)
    z_thr = st.slider("Z-score",1.5,6.0,2.5)
    min_val = st.number_input("Valor mínimo",0.0,1000000.0)

# ===============================
# MUNICIPIO
# ===============================
st.subheader("🏙️ Município (SICONFI)")

entes = load_entes()

col_nome = pick(entes,["ente","no_ente","nome"])
col_uf = pick(entes,["uf","sg_uf"])
col_cod = pick(entes,["cod_ibge","id_ente","co_ibge"])

entes["_nome_norm"] = entes[col_nome].apply(normalize)
mun_norm = normalize(municipio)

filtro = entes[
    (entes["_nome_norm"].str.contains(mun_norm, na=False)) &
    (entes[col_uf].astype(str).str.upper()==uf)
]

if filtro.empty:
    st.error("Município não encontrado.")
    st.stop()

filtro["label"] = filtro[col_nome]+" | "+filtro[col_uf].astype(str)
label = st.selectbox("Selecione", filtro["label"])

row = filtro[filtro["label"]==label].iloc[0]
id_ente = int(row[col_cod])

st.success(f"✅ {row[col_nome]} / {row[col_uf]} | id_ente: {id_ente}")

# ===============================
# LOAD RREO
# ===============================
st.subheader("📥 Dados RREO")

df = load_rreo(id_ente,int(ano),int(bimestre))

if df.empty:
    st.error("RREO vazio.")
    st.stop()

col_val = pick(df,["valor","vl_valor","valor_contabil"])
col_txt = pick(df,["conta","ds_conta","descricao","rotulo"])

df[col_val] = pd.to_numeric(df[col_val], errors="coerce")
df = df.dropna(subset=[col_val])

df[col_txt] = df[col_txt].astype(str)

# remove TOTAL
df = df[~df[col_txt].str.upper().str.contains("TOTAL|SUBTOTAL",na=False)]

agg = df.groupby(col_txt,as_index=False)[col_val].sum()
agg.columns=["conta","valor"]

total = float(agg["valor"].sum())

st.metric("💰 Somatório", money(total))
st.metric("📊 Linhas", len(agg))

# ===============================
# HISTÓRICO
# ===============================
hist=[]
for y in range(int(ano)-anos_hist,int(ano)):
    try:
        h = load_rreo(id_ente,y,int(bimestre))
        if h.empty:
            continue
        h[col_val]=pd.to_numeric(h[col_val],errors="coerce")
        h=h.dropna(subset=[col_val])
        h[col_txt]=h[col_txt].astype(str)
        h=h[~h[col_txt].str.upper().str.contains("TOTAL|SUBTOTAL",na=False)]
        tmp=h.groupby(col_txt,as_index=False)[col_val].sum()
        tmp["ano"]=y
        tmp.columns=["conta","valor","ano"]
        hist.append(tmp)
    except:
        pass

hist_df = pd.concat(hist) if hist else pd.DataFrame()

# ===============================
# ANOMALIAS
# ===============================
st.subheader("🚨 Anomalias automáticas")

if not hist_df.empty:
    stats=hist_df.groupby("conta")["valor"].agg(["mean","std","count"]).reset_index()
    base=agg.merge(stats,on="conta",how="left")
    base["z"]=(base["valor"]-base["mean"])/base["std"]
    base["z"]=base["z"].replace([np.inf,-np.inf],np.nan)

    alertas=base[
        (base["valor"]>=min_val) &
        (base["z"]>=z_thr) &
        (base["count"]>=2)
    ].sort_values("z",ascending=False)

else:
    alertas=agg.sort_values("valor",ascending=False).head(50)

st.dataframe(alertas,use_container_width=True)

csv=alertas.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Baixar relatório",csv,"alertas.csv")

# ===============================
# DASHBOARD
# ===============================
st.subheader("🔥 Top 20")

top=agg.sort_values("valor",ascending=False).head(20)
st.dataframe(top,use_container_width=True)
st.bar_chart(top.set_index("conta")["valor"])

st.caption("Gerado em "+datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
