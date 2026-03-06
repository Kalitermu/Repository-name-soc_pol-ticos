import time
import requests
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Radar Transparência", page_icon="🚨", layout="wide")

MUNICIPIOS_SP = {
    "Praia Grande":3541000,
    "São Vicente":3551009,
    "Santos":3548500,
    "Guarujá":3518701,
    "São Paulo":3550308
}

URL="https://apidatalake.tesouro.gov.br/ords/siconfi/tt/rreo"

def brl(x):
    try:
        return f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X",".")
    except:
        return "R$ 0"

def consultar_rreo(ano,bim,id_ente):
    params={
        "an_exercicio":ano,
        "nr_periodo":bim,
        "id_ente":id_ente,
        "co_tipo_demonstrativo":"RREO"
    }

    r=requests.get(URL,params=params,timeout=30)

    if r.status_code!=200:
        return pd.DataFrame()

    data=r.json().get("items",[])
    return pd.DataFrame(data)

def preparar(df):

    if df.empty:
        return df

    valor=None

    for c in df.columns:
        s=pd.to_numeric(df[c],errors="coerce")
        if s.notna().sum()>0:
            valor=c
            break

    df["_valor_base"]=pd.to_numeric(df[valor],errors="coerce")
    df["_valor_abs"]=df["_valor_base"].abs()

    conta=None

    for c in ["no_conta","co_conta","descricao","no_anexo"]:
        if c in df.columns:
            conta=c
            break

    if conta:
        df["_conta_ref"]=df[conta].astype(str)
    else:
        df["_conta_ref"]="SEM_CONTA"

    return df

def score(df):

    s=df["_valor_base"].dropna()

    if len(s)<2:
        df["_score"]=0
        return df

    media=s.mean()
    desvio=s.std()

    df["_z"]=(df["_valor_base"]-media)/desvio

    df["_score"]=0
    df.loc[df["_valor_abs"]>100000000,"_score"]+=1
    df.loc[df["_valor_abs"]>500000000,"_score"]+=2
    df.loc[df["_z"]>3,"_score"]+=2

    return df

st.title("🚨 Radar Transparência Pública")

with st.sidebar:

    municipio=st.selectbox("Município",list(MUNICIPIOS_SP.keys()))
    ano=st.selectbox("Ano",[2024,2023,2022])
    bim=st.selectbox("Bimestre",[1,2,3,4,5,6])

    valor_min=st.number_input("Modo investigação (R$)",0.0,100000000000.0,100000000.0)

    consultar=st.button("Consultar")

if consultar:

    id_ente=MUNICIPIOS_SP[municipio]

    with st.spinner("Consultando Tesouro..."):
        df=consultar_rreo(ano,bim,id_ente)

    if df.empty:
        st.warning("Sem dados")
        st.stop()

    df=preparar(df)
    df=score(df)

    soma=df["_valor_base"].sum()
    media=df["_valor_base"].mean()
    desvio=df["_valor_base"].std()

    c1,c2,c3=st.columns(3)

    c1.metric("Somatório",brl(soma))
    c2.metric("Média",brl(media))
    c3.metric("Desvio",brl(desvio))

    st.markdown("### 🔥 Top 20 valores")

    top=df.sort_values("_valor_abs",ascending=False).head(20)

    st.dataframe(top,use_container_width=True)

    st.markdown("### ♻️ Repetições suspeitas")

    rep=df["_valor_base"].round(2).value_counts().reset_index()
    rep.columns=["valor","quantidade"]

    rep=rep[rep["quantidade"]>=3].head(20)

    st.dataframe(rep)

    st.markdown("### 🧩 Concentração por conta")

    por_conta=df.groupby("_conta_ref")["_valor_abs"].sum().reset_index()

    por_conta=por_conta.sort_values("_valor_abs",ascending=False).head(20)

    st.dataframe(por_conta)

    st.markdown("### 🔎 Caminho do dinheiro")

    fluxo=df.groupby("_conta_ref")["_valor_abs"].sum().reset_index()

    fluxo=fluxo.sort_values("_valor_abs",ascending=False)

    st.dataframe(fluxo.head(20))

    st.markdown("### 🕵️ Modo investigação")

    inv=df[df["_valor_abs"]>=valor_min]

    st.dataframe(inv,use_container_width=True)

    st.markdown("### 📋 Tabela completa")

    st.dataframe(df,use_container_width=True)


import requests





st.markdown("## 🏢 Contratos públicos")

st.write("Consulta oficial de contratos públicos:")

st.markdown(
"[Abrir busca de contratos no PNCP](https://pncp.gov.br/app/contratos)"
)

st.info(
"Use o PNCP para pesquisar empresas, contratos e valores pagos por órgãos públicos."
)


st.markdown("## 🚨 Detector automático de risco")

try:

    if "df" in locals() and not df.empty and "_valor_abs" in df.columns:

        df_risco = df.copy()

        media = df_risco["_valor_abs"].mean()
        desvio = df_risco["_valor_abs"].std()

        if desvio > 0:
            df_risco["_zscore"] = (df_risco["_valor_abs"] - media) / desvio
        else:
            df_risco["_zscore"] = 0

        df_risco["_risco"] = 0

        df_risco.loc[df_risco["_valor_abs"] > media*5, "_risco"] += 1
        df_risco.loc[df_risco["_zscore"] > 3, "_risco"] += 2
        df_risco.loc[df_risco["_valor_abs"] > 100000000, "_risco"] += 2

        suspeitos = df_risco[df_risco["_risco"] >= 2]

        if not suspeitos.empty:

            st.markdown("### ⚠️ Possíveis valores suspeitos")

            suspeitos = suspeitos.sort_values("_valor_abs", ascending=False)

            st.dataframe(
                suspeitos.head(20),
                use_container_width=True
            )

        else:

            st.info("Nenhum padrão de risco forte encontrado.")

    else:

        st.info("Execute uma consulta primeiro.")

except Exception:

    st.warning("Erro ao analisar riscos.")


st.markdown("## 🧠 Detector de anomalias por conta")

try:

    if "df" in locals() and not df.empty and "_valor_abs" in df.columns and "_conta_ref" in df.columns:

        resultados = []

        for conta, grupo in df.groupby("_conta_ref"):

            valores = grupo["_valor_abs"].dropna()

            if len(valores) < 5:
                continue

            media = valores.mean()
            desvio = valores.std()

            if desvio == 0:
                continue

            grupo = grupo.copy()

            grupo["_z_conta"] = (grupo["_valor_abs"] - media) / desvio

            suspeitos = grupo[grupo["_z_conta"] > 3]

            if not suspeitos.empty:

                resultados.append(suspeitos)

        if resultados:

            df_anomalias = pd.concat(resultados)

            df_anomalias = df_anomalias.sort_values("_valor_abs", ascending=False)

            st.markdown("### ⚠️ Possíveis anomalias dentro das contas")

            st.dataframe(df_anomalias.head(20), use_container_width=True)

        else:

            st.info("Nenhuma anomalia forte encontrada dentro das contas.")

    else:

        st.info("Execute uma consulta primeiro.")

except Exception:

    st.warning("Erro ao analisar anomalias por conta.")


import plotly.express as px

st.markdown("## 📊 Mapa do dinheiro público")

try:

    if "df" in locals() and not df.empty and "_conta_ref" in df.columns:

        resumo = (
            df.groupby("_conta_ref")["_valor_abs"]
            .sum()
            .reset_index()
            .sort_values("_valor_abs", ascending=False)
        )

        top = resumo.head(10)

        fig = px.bar(
            top,
            x="_valor_abs",
            y="_conta_ref",
            orientation="h",
            title="Contas com maior volume de dinheiro",
        )

        st.plotly_chart(fig, use_container_width=True)

    else:

        st.info("Execute uma consulta primeiro.")

except Exception:

    st.warning("Erro ao gerar gráfico.")


st.markdown("## 📊 Métricas rápidas")

col1, col2, col3, col4 = st.columns(4)

col1.metric("💰 Somatório", brl(soma))
col2.metric("📊 Média", brl(media))
col3.metric("📉 Desvio", brl(desvio))
col4.metric("⚠️ Alertas", len(suspeitos) if 'suspeitos' in locals() else 0)


st.markdown("## 🌊 Comparação entre cidades da Baixada Santista")

cidades = {
"Santos":3548500,
"Praia Grande":3541000,
"São Vicente":3551009,
"Guarujá":3518701,
"Cubatão":3513502,
"Mongaguá":3531107
}

dados_cidades = []

for nome,id_cidade in cidades.items():

    try:

        df_tmp = consultar_rreo(ano,bim,id_cidade)

        if not df_tmp.empty:

            df_tmp = preparar(df_tmp)

            total = df_tmp["_valor_base"].sum()

            dados_cidades.append({
                "Município": nome,
                "Orçamento": total
            })

    except:
        pass

if dados_cidades:

    df_comp = pd.DataFrame(dados_cidades)

    st.dataframe(df_comp)

    import plotly.express as px

    fig = px.bar(
        df_comp,
        x="Município",
        y="Orçamento",
        title="Comparação de orçamento entre cidades"
    )

    st.plotly_chart(fig, use_container_width=True)


# calcular estatísticas
soma = df["_valor_abs"].sum()
media = df["_valor_abs"].mean()
desvio = df["_valor_abs"].std()

