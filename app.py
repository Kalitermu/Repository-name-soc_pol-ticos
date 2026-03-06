<<<<<<< HEAD
import requests
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Radar Transparência Pública", page_icon="🚨", layout="wide")

MUNICIPIOS = {
    "Santos": 3548500,
    "Praia Grande": 3541000,
    "São Vicente": 3551009,
    "Guarujá": 3518701,
    "Cubatão": 3513504,
    "Mongaguá": 3531107,
}

URL_RREO = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo"

def brl(x):
    try:
        return f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

def consultar_rreo(ano, bimestre, id_ente):
    params = {
        "an_exercicio": int(ano),
        "nr_periodo": int(bimestre),
        "id_ente": int(id_ente),
        "co_tipo_demonstrativo": "RREO",
    }
    try:
        r = requests.get(URL_RREO, params=params, timeout=40)
        if r.status_code != 200:
            return pd.DataFrame(), f"HTTP {r.status_code}"
        data = r.json().get("items", [])
        return pd.DataFrame(data), None
    except Exception as e:
        return pd.DataFrame(), str(e)

def encontrar_coluna_valor(df):
    prioridades = ["valor", "vl", "vl_receita", "vl_despesa", "vl_saldo"]
    for c in prioridades:
        if c in df.columns:
            s = pd.to_numeric(df[c], errors="coerce")
            if s.notna().any():
                return c
    for c in df.columns:
        s = pd.to_numeric(df[c], errors="coerce")
        if s.notna().any():
            return c
    return None

def encontrar_coluna_conta(df):
    for c in ["no_conta", "co_conta", "descricao", "no_anexo"]:
        if c in df.columns:
            return c
    return None

def preparar_df(df):
    if df.empty:
        return df

    valor_col = encontrar_coluna_valor(df)
    conta_col = encontrar_coluna_conta(df)

    if valor_col is None:
        df["_valor_base"] = 0.0
    else:
        df["_valor_base"] = pd.to_numeric(df[valor_col], errors="coerce").fillna(0)

    df["_valor_abs"] = df["_valor_base"].abs()

    if conta_col:
        df["_conta_ref"] = df[conta_col].astype(str)
    else:
        df["_conta_ref"] = "SEM_CONTA"

    return df

st.title("🚨 Radar Transparência Pública")
st.caption("Auditoria automática em dados públicos do Tesouro (SICONFI/RREO).")

with st.sidebar:
    st.header("⚙️ Filtros")
    municipio = st.selectbox("Município", list(MUNICIPIOS.keys()), index=2)
    ano = st.selectbox("Ano", [2025, 2024, 2023, 2022], index=2)
    bimestre = st.selectbox("Bimestre", [1, 2, 3, 4, 5, 6], index=0)
    valor_min = st.number_input("Modo investigação (R$)", min_value=0.0, value=100000000.0, step=50000000.0)
    consultar = st.button("Consultar", use_container_width=True)

if consultar:
    id_ente = MUNICIPIOS[municipio]

    st.markdown("### 🏙️ Município (SICONFI)")
    st.success(f"{municipio} | id_ente: {id_ente}")

    with st.spinner("Consultando dados do Tesouro..."):
        df, erro = consultar_rreo(ano, bimestre, id_ente)

    if erro:
        st.error(f"Erro na consulta: {erro}")
        st.stop()

    if df.empty:
        st.warning("Nenhum dado encontrado para esse filtro.")
        st.stop()

    df = preparar_df(df)

    soma = df["_valor_abs"].sum()
    media = df["_valor_abs"].mean()
    desvio = df["_valor_abs"].std()

    st.markdown("### 📥 Dados RREO")
    c1, c2, c3 = st.columns(3)
    c1.metric("💰 Somatório", brl(soma))
    c2.metric("📊 Média", brl(media))
    c3.metric("📉 Desvio", brl(0 if pd.isna(desvio) else desvio))

    st.metric("📋 Linhas", len(df))

    st.markdown("### 🔥 Top 20 valores")
    top20 = df.sort_values("_valor_abs", ascending=False).head(20)
    st.dataframe(top20[["_conta_ref", "_valor_base"]], use_container_width=True, hide_index=True)

    st.markdown("### ♻️ Repetições suspeitas")
    repet = (
        df["_valor_base"].round(2)
        .value_counts()
        .reset_index()
    )
    repet.columns = ["valor", "quantidade"]
    repet = repet[repet["quantidade"] >= 3].head(20)
    if repet.empty:
        st.info("Nenhuma repetição forte encontrada.")
    else:
        repet["valor"] = repet["valor"].apply(brl)
        st.dataframe(repet, use_container_width=True, hide_index=True)

    st.markdown("### 🧩 Concentração por conta")
    por_conta = (
        df.groupby("_conta_ref")["_valor_abs"]
        .sum()
        .reset_index()
        .sort_values("_valor_abs", ascending=False)
        .head(20)
    )
    por_conta["_valor_abs"] = por_conta["_valor_abs"].apply(brl)
    por_conta.columns = ["Conta", "Total"]
    st.dataframe(por_conta, use_container_width=True, hide_index=True)

    st.markdown("### 🔎 Caminho do dinheiro")
    fluxo = (
        df.groupby("_conta_ref")["_valor_abs"]
        .sum()
        .reset_index()
        .sort_values("_valor_abs", ascending=False)
        .head(20)
    )
    fluxo["_valor_abs"] = fluxo["_valor_abs"].apply(brl)
    fluxo.columns = ["Conta", "Dinheiro movimentado"]
    st.dataframe(fluxo, use_container_width=True, hide_index=True)

    st.markdown("### 🕵️ Modo investigação")
    inv = df[df["_valor_abs"] >= valor_min].copy()
    if inv.empty:
        st.info("Nenhuma linha acima do valor mínimo.")
    else:
        st.dataframe(inv[["_conta_ref", "_valor_base"]], use_container_width=True, hide_index=True)

    st.markdown("### 📊 Mapa do dinheiro público")
    graf = (
        df.groupby("_conta_ref")["_valor_abs"]
        .sum()
        .reset_index()
        .sort_values("_valor_abs", ascending=False)
        .head(10)
    )
    fig = px.bar(
        graf,
        x="_conta_ref",
        y="_valor_abs",
        title="Top 10 contas por valor",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🏢 Contratos públicos")
    st.write("Consulta oficial de contratos públicos:")
    st.markdown("[Abrir busca de contratos no PNCP](https://pncp.gov.br/app/contratos)")
    st.info("Use o PNCP para pesquisar empresas, contratos e valores por órgãos públicos.")

    st.markdown("### 🌊 Comparação entre cidades da Baixada Santista")
    dados_cidades = []

    for nome, cidade_id in MUNICIPIOS.items():
        try:
            df_tmp, _ = consultar_rreo(ano, bimestre, cidade_id)
            if not df_tmp.empty:
                df_tmp = preparar_df(df_tmp)
                dados_cidades.append({
                    "Município": nome,
                    "Orçamento": df_tmp["_valor_abs"].sum()
                })
        except Exception:
            pass

    if dados_cidades:
        df_comp = pd.DataFrame(dados_cidades)
        st.dataframe(df_comp, use_container_width=True, hide_index=True)
        fig2 = px.bar(df_comp, x="Município", y="Orçamento", title="Comparação de orçamento entre cidades")
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### 📋 Tabela completa")
    st.dataframe(df, use_container_width=True, hide_index=True)

else:
    st.info("Escolha os filtros e toque em Consultar.")
=======
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
>>>>>>> ac50f7b16889d8f15d5deb28980314fc4c43641a
