# app.py - Dashboard de Recursos Humanos
# Como rodar:
# 1) Ative a venv -> .venv\Scripts\Activate.ps1 (Windows) | source .venv/bin/activate (Mac/Linux)
# 2) Instale deps -> pip install streamlit pandas numpy plotly openpyxl python-date-util
# 3) Rode        -> streamlit run app.py

import os
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import date
from io import BytesIO

# --- Configuração da Página ---
st.set_page_config(page_title="Dashboard de RH", layout="wide", initial_sidebar_state="expanded")

# --- Lógica do tema claro/escuro e layout do cabeçalho ---
col_main, col_toggle = st.columns([0.8, 0.2])
with col_main:
    st.title("Dashboard de Recursos Humanos")
    st.markdown("Uma análise completa da equipe, com métricas e visualizações interativas.")
with col_toggle:
    st.markdown("<br>", unsafe_allow_html=True) # Espaçamento para alinha
    modo_escuro = st.toggle("Modo Escuro", value=False, help="Ative para alternar para o tema escuro")

# Define as cores do tema e do Plotly
tema_plotly = "plotly_dark" if modo_escuro else "plotly_white"
cor_fundo_app = "#0E1117" if modo_escuro else "#FFFFFF"
cor_fundo_caixas = "#1a1a1a" if modo_escuro else "#F0F2F6"
cor_texto = "#FAFAFA" if modo_escuro else "#262730"

# Injeta CSS dinâmico
if modo_escuro:
    tema_css = f"""
    <style>
        .stApp {{
            background-color: {cor_fundo_app};
            color: {cor_texto};
        }}
        /* Sidebar e caixas */
        .st-emotion-cache-1ldf05h {{
            background-color: {cor_fundo_caixas};
        }}
        /* Tabela st.dataframe */
        div[data-testid="stDataFrame"] .ag-theme-streamlit {{
            background-color: {cor_fundo_caixas} !important;
        }}
        div[data-testid="stDataFrame"] .ag-theme-streamlit .ag-header {{
            background-color: #262730 !important;
            color: {cor_texto} !important;
        }}
        div[data-testid="stDataFrame"] .ag-theme-streamlit .ag-cell {{
            background-color: {cor_fundo_caixas} !important;
            color: {cor_texto} !important;
        }}
        /* Botões de download */
        div[data-testid="stDownloadButton"] button {{
            background-color: #4c78a8;
            color: white;
            border: none;
        }}
    </style>
    """
else:
    tema_css = f"""
    <style>
        .stApp {{
            background-color: {cor_fundo_app};
            color: {cor_texto};
        }}
        /* Sidebar e caixas */
        .st-emotion-cache-1ldf05h {{
            background-color: {cor_fundo_caixas};
        }}
        /* Tabela st.dataframe */
        div[data-testid="stDataFrame"] .ag-theme-streamlit {{
            background-color: {cor_fundo_caixas} !important;
        }}
        div[data-testid="stDataFrame"] .ag-theme-streamlit .ag-header {{
            background-color: #FFFFFF !important;
            color: {cor_texto} !important;
        }}
        div[data-testid="stDataFrame"] .ag-theme-streamlit .ag-cell {{
            background-color: {cor_fundo_caixas} !important;
            color: {cor_texto} !important;
        }}
        /* Botões de download */
        div[data-testid="stDownloadButton"] button {{
            background-color: #f0f2f6;
            color: #262730;
            border: 1px solid #262730;
        }}
    </style>
    """
st.markdown(tema_css, unsafe_allow_html=True)

# --- Constantes e Variáveis Globais ---
DEFAULT_EXCEL_PATH = "BaseFuncionarios.xlsx"
DATE_COLUMNS = ["Data de Nascimento", "Data de Contratacao", "Data de Demissao"]
MONEY_COLUMNS = ["Salario Base", "Impostos", "Beneficios", "VT", "VR"]

# --- Funções de Preparação e Tratamento de Dados ---

def formatar_moeda_brl(valor: float) -> str:
    """Formata um número para o padrão de moeda R$ (BRL)."""
    try:
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "R$ 0,00"

def formatar_moeda_compacto(valor: float) -> str:
    """Formata um número para o padrão de moeda R$ (BRL) em formato compacto (mil, mi, bi)."""
    try:
        if valor >= 1_000_000_000:
            return f"R$ {valor / 1_000_000_000:.2f} bi"
        elif valor >= 1_000_000:
            return f"R$ {valor / 1_000_000:.2f} mi"
        elif valor >= 1_000:
            return f"R$ {valor / 1_000:.2f} mil"
        return formatar_moeda_brl(valor)
    except (TypeError, ValueError):
        return "R$ 0,00"

def preparar_dados(df: pd.DataFrame) -> pd.DataFrame:
    """Limpa e enriquece o DataFrame para a análise do dashboard."""
    # Garante que textos sejam strings e remove espaços
    for c in df.select_dtypes(include="object").columns:
        df[c] = df[c].astype(str).str.strip()

    # Converte colunas de data
    for c in DATE_COLUMNS:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], dayfirst=True, errors="coerce")

    # Padroniza a coluna 'Sexo'
    if "Sexo" in df.columns:
        df["Sexo"] = df["Sexo"].str.upper().replace({"MASCULINO": "M", "FEMININO": "F"})

    # Garante colunas de dinheiro e as converte para numérico
    for col in MONEY_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Cria colunas derivadas (Idade, Tempo de Casa, Status, Custo Total)
    today = pd.Timestamp(date.today())

    if "Data de Nascimento" in df.columns:
        df["Idade"] = ((today - df["Data de Nascimento"]).dt.days // 365).clip(lower=0)
    
    if "Data de Contratacao" in df.columns:
        meses = (today.year - df["Data de Contratacao"].dt.year) * 12 + \
                (today.month - df["Data de Contratacao"].dt.month)
        df["Tempo de Casa (meses)"] = meses.clip(lower=0)

    if "Data de Demissao" in df.columns:
        df["Status"] = np.where(df["Data de Demissao"].notna(), "Desligado", "Ativo")
    else:
        df["Status"] = "Ativo"

    df["Custo Total Mensal"] = df[MONEY_COLUMNS].sum(axis=1)
    
    return df

@st.cache_data
def carregar_do_caminho(path: str) -> pd.DataFrame:
    """Carrega o DataFrame a partir de um caminho de arquivo .xlsx."""
    df_raw = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    return preparar_dados(df_raw)

@st.cache_data
def carregar_dos_bytes(uploaded_bytes) -> pd.DataFrame:
    """Carrega o DataFrame a partir de um arquivo .xlsx enviado pelo usuário."""
    df_raw = pd.read_excel(uploaded_bytes, sheet_name=0, engine="openpyxl")
    return preparar_dados(df_raw)

# --- Seção de Carregamento de Dados ---
df = None
fonte_dados = "Não carregado"
with st.sidebar:
    st.header("Fonte de Dados")
    uploaded_file = st.file_uploader("Carregar Excel (.xlsx)", type=["xlsx"])
    caminho_manual = st.text_input("Ou caminho do Excel", value=DEFAULT_EXCEL_PATH)
    st.divider()

    if uploaded_file:
        try:
            df = carregar_dos_bytes(uploaded_file)
            fonte_dados = "Upload"
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            st.stop()
    else:
        if not os.path.exists(caminho_manual):
            st.warning(f"Arquivo não encontrado em **{caminho_manual}**.")
            st.info("Dica: coloque o arquivo .xlsx na mesma pasta ou ajuste o caminho.")
            st.stop()
        try:
            df = carregar_do_caminho(caminho_manual)
            fonte_dados = "Caminho Manual"
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            st.stop()

st.caption(f"Dados carregados via **{fonte_dados}**. Linhas: {len(df)} | Colunas: {len(df.columns)}")

with st.expander("Ver Colunas Detectadas"):
    st.write(list(df.columns))

# --- Seção de Filtros (Sidebar) ---
st.sidebar.header("Filtros de Análise")

# Helper para multiselects e sliders
def get_multiselect(col_name: str, df: pd.DataFrame):
    if col_name in df.columns:
        values = sorted(df[col_name].dropna().unique())
        return st.sidebar.multiselect(col_name, values)
    return []

def get_slider(col_name: str, df: pd.DataFrame, label: str):
    if col_name in df.columns and not df[col_name].dropna().empty:
        min_val, max_val = df[col_name].min(), df[col_name].max()
        return st.sidebar.slider(label, min_val, max_val, (min_val, max_val))
    return None

area_sel = get_multiselect("Área", df)
nivel_sel = get_multiselect("Nível", df)
cargo_sel = get_multiselect("Cargo", df)
sexo_sel = get_multiselect("Sexo", df)
status_sel = get_multiselect("Status", df)

nome_busca = st.sidebar.text_input("Buscar por Nome Completo")

if "Data de Contratacao" in df.columns:
    contr_min, contr_max = df["Data de Contratacao"].min().date(), df["Data de Contratacao"].max().date()
    periodo_contr = st.sidebar.date_input("Período de Contratação", value=(contr_min, contr_max))
else:
    periodo_contr = None

if "Data de Demissao" in df.columns:
    demis_min, demis_max = df["Data de Demissao"].min().date(), df["Data de Demissao"].max().date()
    periodo_demis = st.sidebar.date_input("Período de Demissão", value=(demis_min, demis_max))
else:
    periodo_demis = None

faixa_idade = get_slider("Idade", df, "Faixa Etária")
faixa_salario = get_slider("Salario Base", df, "Faixa de Salário Base")

# Aplica os filtros
df_filtrado = df.copy()

if area_sel:
    df_filtrado = df_filtrado[df_filtrado["Área"].isin(area_sel)]
if nivel_sel:
    df_filtrado = df_filtrado[df_filtrado["Nível"].isin(nivel_sel)]
if cargo_sel:
    df_filtrado = df_filtrado[df_filtrado["Cargo"].isin(cargo_sel)]
if sexo_sel:
    df_filtrado = df_filtrado[df_filtrado["Sexo"].isin(sexo_sel)]
if status_sel:
    df_filtrado = df_filtrado[df_filtrado["Status"].isin(status_sel)]

if nome_busca and "Nome Completo" in df_filtrado.columns:
    df_filtrado = df_filtrado[df_filtrado["Nome Completo"].str.contains(nome_busca, case=False, na=False)]

if faixa_idade and "Idade" in df_filtrado.columns:
    df_filtrado = df_filtrado[(df_filtrado["Idade"] >= faixa_idade[0]) & (df_filtrado["Idade"] <= faixa_idade[1])]

if faixa_salario and "Salario Base" in df_filtrado.columns:
    df_filtrado = df_filtrado[(df_filtrado["Salario Base"] >= faixa_salario[0]) & (df_filtrado["Salario Base"] <= faixa_salario[1])]

if periodo_contr and "Data de Contratacao" in df_filtrado.columns:
    start, end = pd.to_datetime(periodo_contr[0]), pd.to_datetime(periodo_contr[1])
    df_filtrado = df_filtrado[
        (df_filtrado["Data de Contratacao"].isna()) |
        ((df_filtrado["Data de Contratacao"] >= start) & (df_filtrado["Data de Contratacao"] <= end))
    ]

if periodo_demis and "Data de Demissao" in df_filtrado.columns:
    start, end = pd.to_datetime(periodo_demis[0]), pd.to_datetime(periodo_demis[1])
    df_filtrado = df_filtrado[
        (df_filtrado["Data de Demissao"].isna()) |
        ((df_filtrado["Data de Demissao"] >= start) & (df_filtrado["Data de Demissao"] <= end))
    ]


# --- Seção de KPIs (Key Performance Indicators) ---
st.subheader("Indicadores de Performance")
col_kpi_1, col_kpi_2, col_kpi_3 = st.columns(3)
col_kpi_4, col_kpi_5, col_kpi_6 = st.columns(3)

kpis = {
    "Headcount Ativo": df_filtrado.loc[df_filtrado["Status"] == "Ativo"].shape[0],
    "Desligados": df_filtrado.loc[df_filtrado["Status"] == "Desligado"].shape[0],
    "Folha Salarial": formatar_moeda_compacto(df_filtrado.loc[df_filtrado["Status"] == "Ativo", "Salario Base"].sum()),
    "Custo Total": formatar_moeda_compacto(df_filtrado.loc[df_filtrado["Status"] == "Ativo", "Custo Total Mensal"].sum()),
    "Idade Média": f"{df_filtrado['Idade'].mean():.1f} anos" if "Idade" in df_filtrado.columns and not df_filtrado['Idade'].empty else "N/A",
    "Avaliação Média": f"{df_filtrado['Avaliação do Funcionário'].mean():.2f}" if "Avaliação do Funcionário" in df_filtrado.columns and not df_filtrado['Avaliação do Funcionário'].empty else "N/A"
}

# Primeira linha de KPIs
with col_kpi_1:
    st.metric("Headcount Ativo", kpis["Headcount Ativo"])
with col_kpi_2:
    st.metric("Desligados", kpis["Desligados"])
with col_kpi_3:
    st.metric("Folha Salarial", kpis["Folha Salarial"])

# Segunda linha de KPIs
with col_kpi_4:
    st.metric("Custo Total", kpis["Custo Total"])
with col_kpi_5:
    st.metric("Idade Média", kpis["Idade Média"])
with col_kpi_6:
    st.metric("Avaliação Média", kpis["Avaliação Média"])

st.divider()

# --- Seção de Gráficos ---
st.subheader("Visualizações")

# Paleta de cores para os gráficos
PALETA_CORES_PRINCIPAIS = ["#4c78a8", "#f58518", "#e45756", "#72b7b2", "#54a24b", "#eeca3b", "#b279a2", "#ff9da7", "#9d755d", "#bab0ac"]

# Configurações dinâmicas para o fundo dos gráficos
bg_color = "#1a1a1a" if modo_escuro else "white"
font_color = "white" if modo_escuro else "black"

col_charts1, col_charts2 = st.columns(2)
with col_charts1:
    if "Área" in df_filtrado.columns and not df_filtrado.empty:
        d = df_filtrado["Área"].value_counts().reset_index(name="Número de Funcionarios")
        fig = px.bar(d, x="Área", y="Número de Funcionarios", title="Número de Funcionários por Área", color_discrete_sequence=PALETA_CORES_PRINCIPAIS)
        fig.update_layout(
            title_font_size=20, 
            yaxis_title="Número de Funcionários",
            template=tema_plotly,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font_color=font_color
        )
        st.plotly_chart(fig, use_container_width=True)
with col_charts2:
    if "Cargo" in df_filtrado.columns and "Salario Base" in df_filtrado.columns and not df_filtrado.empty:
        d = df_filtrado.groupby("Cargo", as_index=False)["Salario Base"].mean().sort_values("Salario Base", ascending=False)
        fig = px.bar(d, x="Cargo", y="Salario Base", title="Salário Médio por Cargo", color_discrete_sequence=PALETA_CORES_PRINCIPAIS)
        fig.update_layout(
            title_font_size=20, 
            yaxis_title="Salário Base (R$)",
            template=tema_plotly,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font_color=font_color
        )
        st.plotly_chart(fig, use_container_width=True)

col_charts3, col_charts4 = st.columns(2)
with col_charts3:
    if "Idade" in df_filtrado.columns and not df_filtrado.empty:
        fig = px.histogram(df_filtrado, x="Idade", nbins=20, title="Distribuição de Idade", color_discrete_sequence=PALETA_CORES_PRINCIPAIS)
        fig.update_layout(
            title_font_size=20, 
            yaxis_title="Contagem",
            template=tema_plotly,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font_color=font_color
        )
        st.plotly_chart(fig, use_container_width=True)
with col_charts4:
    if "Sexo" in df_filtrado.columns and not df_filtrado.empty:
        d = df_filtrado["Sexo"].value_counts().reset_index()
        d.columns = ["Sexo", "Contagem"]
        fig = px.pie(d, values="Contagem", names="Sexo", title="Distribuição por Sexo", color_discrete_sequence=PALETA_CORES_PRINCIPAIS)
        fig.update_layout(
            title_font_size=20,
            template=tema_plotly,
            paper_bgcolor=bg_color,
            font_color=font_color
        )
        st.plotly_chart(fig, use_container_width=True)

st.divider()
st.subheader("Análises Adicionais")

col_charts5, col_charts6 = st.columns(2)
with col_charts5:
    if "Nível" in df_filtrado.columns and "Salario Base" in df_filtrado.columns and not df_filtrado.empty:
        fig = px.box(df_filtrado, x="Nível", y="Salario Base", color="Nível",
                     title="Distribuição Salarial por Nível",
                     labels={"Salario Base": "Salário Base (R$)"},
                     color_discrete_sequence=PALETA_CORES_PRINCIPAIS)
        fig.update_layout(
            title_font_size=20,
            template=tema_plotly,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font_color=font_color
        )
        st.plotly_chart(fig, use_container_width=True)
with col_charts6:
    if "Área" in df_filtrado.columns and "Avaliação do Funcionário" in df_filtrado.columns and not df_filtrado.empty:
        d = df_filtrado.groupby("Área", as_index=False)["Avaliação do Funcionário"].mean().sort_values("Avaliação do Funcionário", ascending=False)
        fig = px.bar(d, x="Área", y="Avaliação do Funcionário",
                     title="Avaliação Média por Área",
                     labels={"Avaliação do Funcionário": "Avaliação Média"},
                     color_discrete_sequence=PALETA_CORES_PRINCIPAIS)
        fig.update_layout(
            title_font_size=20,
            template=tema_plotly,
            paper_bgcolor=bg_color,
            plot_bgcolor=bg_color,
            font_color=font_color
        )
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- Tabela e Opções de Download ---
st.subheader("Tabela de Dados Filtrados")
st.dataframe(df_filtrado, use_container_width=True)

csv_data = df_filtrado.to_csv(index=False).encode("utf-8")
st.download_button(
    "Baixar como CSV",
    data=csv_data,
    file_name="dados_rh_filtrados.csv",
    mime="text/csv"
)

# Adiciona um toggle para o download do Excel
if st.toggle("Baixar como Excel"):
    buffer_excel = BytesIO()
    with pd.ExcelWriter(buffer_excel, engine="xlsxwriter") as writer:
        df_filtrado.to_excel(writer, index=False, sheet_name="Dados Filtrados")
    
    st.download_button(
        "Download Excel",
        data=buffer_excel.getvalue(),
        file_name="dados_rh_filtrados.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
