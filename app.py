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
import streamlit as st
import pandas as pd
import requests
import numpy as np
import unicodedata
from datetime import datetime

# CONFIG
