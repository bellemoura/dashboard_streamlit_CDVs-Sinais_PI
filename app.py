"""Dashboard de Inventário de Sinalização Ferroviária — Projeto Integrador.

Execute no terminal, a partir desta pasta:
    streamlit run app.py

A lógica de leitura e limpeza está explicada em processamento.py.
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from processamento import FUNCOES, calcular_resumo, ler_e_transformar

# 1. Configuramos a interface ANTES de exibir qualquer outro elemento.
st.set_page_config(
    page_title="Diagnóstico Ferroviário | Vias 1 e 2",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="expanded",
)

DIRETORIO = Path(__file__).resolve().parent
ARQUIVO_CDV = DIRETORIO / "levantamento BD CDVs via 1 e 2.xlsx"
ARQUIVO_SINAIS = DIRETORIO / "levantamento BD Sinais via 1 e 2.xlsx"

CORES_STATUS = {"Preenchido": "#1C8C88", "Pendente": "#ED9447", "Não utilizado": "#A4ADBD"}
ORDEM_STATUS = ["Preenchido", "Pendente", "Não utilizado"]
COR_AZUL = "#3157A4"
COR_TURQUESA = "#1C8C88"

st.markdown(
    """<style>
    .block-container {max-width: 1450px; padding-top: 1.8rem; padding-bottom: 3.5rem;}
    [data-testid="stMetricValue"] {font-size: 2.05rem; font-weight: 750;}
    [data-testid="stMetricLabel"] {font-size: .92rem;}
    div[data-testid="stTabs"] button {font-weight: 650;}
    </style>""",
    unsafe_allow_html=True,
)


# 2. Carregamento independente do computador: arquivo da pasta OU upload.
def bytes_planilha(caminho: Path, arquivo_enviado):
    if arquivo_enviado is not None:
        return arquivo_enviado.getvalue()
    return caminho.read_bytes() if caminho.is_file() else None


with st.sidebar:
    st.markdown("## 🚦 Painel ferroviário")
    st.caption("Projeto Integrador • Análise exploratória das bases BD")
    st.divider()
    st.markdown("#### Arquivos de entrada")
    upload_cdv = st.file_uploader("Substituir base de CDVs (opcional)", type="xlsx", key="cdvs")
    upload_sinais = st.file_uploader("Substituir base de Sinais (opcional)", type="xlsx", key="sinais")

conteudo_cdv = bytes_planilha(ARQUIVO_CDV, upload_cdv)
conteudo_sinais = bytes_planilha(ARQUIVO_SINAIS, upload_sinais)

if conteudo_cdv is None and conteudo_sinais is None:
    st.warning("Adicione os arquivos .xlsx na pasta do projeto ou envie-os pela barra lateral.")
    st.stop()

# 3. Cache: só reprocessamos os arquivos se seus bytes mudarem.
@st.cache_data(show_spinner="Lendo e organizando as planilhas...")
def obter_dados(cdv: bytes | None, sinais: bytes | None) -> pd.DataFrame:
    return ler_e_transformar(cdv, sinais)


try:
    dados = obter_dados(conteudo_cdv, conteudo_sinais)
except (ValueError, OSError, KeyError, IndexError) as erro:
    st.error(f"Não foi possível interpretar a planilha: {erro}")
    st.info("Confira se os arquivos são as planilhas originais de CDVs e Sinais.")
    st.stop()

if dados.empty:
    st.error("Os arquivos foram lidos, mas nenhum bloco de equipamento foi reconhecido.")
    st.stop()

with st.sidebar:
    if conteudo_cdv is None:
        st.info("Base de CDVs não fornecida. Exibindo apenas Sinais.")
    if conteudo_sinais is None:
        st.info("Base de Sinais não fornecida. Exibindo apenas CDVs.")
    st.divider()
    st.markdown("#### Filtros interativos")
    opcoes_ativo = [x for x in ("CDV", "Sinal") if x in dados.ativo.unique()]
    ativos = st.multiselect("Tipo de ativo", opcoes_ativo, default=opcoes_ativo)
    opcoes_via = sorted(dados.loc[dados.ativo == "CDV", "via"].unique().tolist())
    vias = st.multiselect("Via — somente para CDVs", opcoes_via, default=opcoes_via,
                          help="A base de Sinais não possui uma coluna que identifique a via.")
    opcoes_local = sorted(dados.tipo_local.unique().tolist())
    tipos_local = st.multiselect("Tipo de local", opcoes_local, default=opcoes_local)
    st.caption("Todos os indicadores e gráficos respondem aos filtros acima.")

# 4. A filtragem é aplicada a um único DataFrame compartilhado por todas as abas.
filtrado = dados.loc[
    dados.ativo.isin(ativos)
    & dados.tipo_local.isin(tipos_local)
    & ((dados.ativo != "CDV") | dados.via.isin(vias))
].copy()

cdvs = filtrado.loc[filtrado.ativo == "CDV"]
sinais = filtrado.loc[filtrado.ativo == "Sinal"]
resumo = calcular_resumo(filtrado)


def formato_numero(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def exibir_grafico(fig, altura: int = 380) -> None:
    """Um formato visual consistente facilita comparar os resultados."""
    fig.update_layout(
        template="plotly_white",
        height=altura,
        margin=dict(l=8, r=10, t=55, b=30),
        legend_title_text="",
        font=dict(size=12),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def grafico_status(df: pd.DataFrame, campo: str, titulo: str):
    tabela = df.groupby([campo, "status"]).size().reset_index(name="Quantidade")
    fig = px.bar(
        tabela, x=campo, y="Quantidade", color="status", barmode="stack",
        text_auto=True, color_discrete_map=CORES_STATUS,
        category_orders={"status": ORDEM_STATUS}, title=titulo,
    )
    fig.update_xaxes(title=None)
    return fig


def ranking_por_status(df: pd.DataFrame, status: str, titulo: str, limite: int = 15):
    subset = df.loc[df.status == status]
    if subset.empty:
        st.success(f"Não há registros com status '{status.lower()}' neste recorte.")
        return
    tabela = (subset.groupby("equipamento").size()
              .nlargest(limite).sort_values().reset_index(name="Quantidade"))
    fig = px.bar(tabela, x="Quantidade", y="equipamento", orientation="h", text_auto=True,
                 title=titulo, color_discrete_sequence=[CORES_STATUS[status]])
    fig.update_yaxes(title=None)
    exibir_grafico(fig, max(340, 27 * len(tabela) + 140))


# Cabeçalho e cartões de indicadores
st.markdown("# Diagnóstico de sinalização ferroviária")
st.caption("Levantamento de BD • Vias 1 e 2 | CDVs e Sinais | Análise exploratória de registros")
st.write("Este painel organiza os pontos registrados nas planilhas para acompanhar preenchimento,"
         " distribuição por função e possíveis inconsistências de escrita.")

if filtrado.empty:
    st.warning("Os filtros selecionados não retornaram registros. Altere as opções na lateral.")
    st.stop()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("CDVs distintos", formato_numero(resumo["cdvs"]))
m2.metric("Sinais distintos", formato_numero(resumo["sinais"]))
m3.metric("Pontos preenchidos", formato_numero(resumo["preenchidos"]))
m4.metric("Preenchimento", f"{resumo['taxa']:.1%}".replace(".", ","))
m5.metric("Células pendentes", formato_numero(resumo["pendentes"]))

with st.expander("Como interpretar os indicadores?", expanded=False):
    st.markdown(
        """- **Ponto** = uma célula na interseção entre local e função (não é necessariamente um ponto físico único).
- **Preenchido** = a célula contém um valor diferente de `-`.
- **Pendente** = a célula está vazia na planilha original.
- **Não utilizado** = a célula contém `-` (não é contabilizada como pendência).
- **Taxa de preenchimento** = preenchidos / (preenchidos + pendentes). Exclui `-`.
- **Equipamentos distintos** = contagem de nomes diferentes, mesmo que um nome apareça em mais de um bloco.

Essas classificações são hipóteses operacionais para análise de dados, não um laudo de engenharia."""
    )

aba_geral, aba_cdv, aba_sinal, aba_qualidade, aba_dados = st.tabs(
    ["📊 Visão geral", "🛤️ CDVs", "🚥 Sinais", "🔎 Qualidade dos dados", "📁 Base tratada"]
)

# 5. Visão geral: como os dois tipos de equipamento se distribuem.
with aba_geral:
    st.subheader("Panorama dos registros")
    esquerda, direita = st.columns(2)
    with esquerda:
        exibir_grafico(grafico_status(filtrado, "ativo", "Situação por tipo de ativo"))
    with direita:
        pontos_validos = filtrado.loc[filtrado.status == "Preenchido"]
        if not pontos_validos.empty:
            por_local = (pontos_validos.groupby(["tipo_local", "ativo"])
                         .size().reset_index(name="Quantidade"))
            fig = px.bar(por_local, x="tipo_local", y="Quantidade", color="ativo",
                         barmode="group", text_auto=True,
                         color_discrete_map={"CDV": COR_AZUL, "Sinal": COR_TURQUESA},
                         title="Pontos preenchidos por tipo de local")
            fig.update_xaxes(title=None)
            exibir_grafico(fig)

    st.markdown("#### Comparativo de preenchimento")
    resumo_ativos = []
    for ativo, grupo in filtrado.groupby("ativo"):
        r = calcular_resumo(grupo)
        resumo_ativos.append({
            "Ativo": ativo,
            "Preenchidos": r["preenchidos"],
            "Pendentes": r["pendentes"],
            "Não utilizados": r["nao_utilizados"],
            "Preenchimento (%)": round(r["taxa"] * 100, 1),
        })
    st.dataframe(pd.DataFrame(resumo_ativos), hide_index=True, use_container_width=True)
    st.caption("Não há data de medição nas planilhas: por isso usamos gráficos de distribuição, e não séries temporais.")

# 6. Análises específicas para CDVs.
with aba_cdv:
    st.subheader("Circuitos de via (CDVs)")
    if cdvs.empty:
        st.info("Nenhum CDV está incluído nos filtros atuais.")
    else:
        st.write("A identificação de cada CDV permite comparar **vias** e **sentidos** (Norte/Sul).")
        esquerda, direita = st.columns(2)
        with esquerda:
            exibir_grafico(grafico_status(cdvs, "via", "Distribuição dos registros por via"))
        with direita:
            exibir_grafico(grafico_status(cdvs, "sentido", "Distribuição por sentido"))

        st.markdown("#### Funções e preenchimento")
        so_preenchidos = cdvs.loc[cdvs.status == "Preenchido"]
        if not so_preenchidos.empty:
            tab = so_preenchidos.groupby(["funcao", "categoria"]).size().reset_index(name="Quantidade")
            fig = px.bar(tab, x="funcao", y="Quantidade", color="categoria", text_auto=True,
                         title="Registros preenchidos por função",
                         category_orders={"funcao": [f for _, f in FUNCOES["CDV"]]})
            fig.update_xaxes(title=None)
            exibir_grafico(fig)
            matriz = so_preenchidos.pivot_table(index="equipamento", columns="funcao",
                                                values="ponto", aggfunc="count", fill_value=0)
            ordem_funcoes = [f for _, f in FUNCOES["CDV"]]
            matriz = matriz.reindex(columns=ordem_funcoes, fill_value=0).sort_index()
            if not matriz.empty:
                fig = px.imshow(matriz, text_auto=True, aspect="auto", color_continuous_scale="Teal",
                                title="Mapa de calor: CDV × função (células preenchidas)",
                                labels=dict(x="Função", y="CDV", color="Quantidade"))
                exibir_grafico(fig, max(450, 27 * len(matriz) + 140))

# 7. Análises específicas para Sinais.
with aba_sinal:
    st.subheader("Sinais ferroviários")
    if sinais.empty:
        st.info("Nenhum Sinal está incluído nos filtros atuais.")
    else:
        st.write("Os sinais possuem funções associadas aos aspectos **Vermelho** e **Amarelo**.")
        st.caption("A planilha de Sinais não permite identificar sua via com segurança.")
        preenchidos_sinal = sinais.loc[sinais.status == "Preenchido"]
        esquerda, direita = st.columns(2)
        with esquerda:
            if not preenchidos_sinal.empty:
                tab = (preenchidos_sinal.groupby(["categoria", "funcao"]).size()
                       .reset_index(name="Quantidade"))
                fig = px.bar(tab, x="funcao", y="Quantidade", color="categoria",
                             text_auto=True, title="Pontos preenchidos por aspecto e função")
                fig.update_xaxes(title=None)
                exibir_grafico(fig)
        with direita:
            if not preenchidos_sinal.empty:
                tab = (preenchidos_sinal.groupby("tipo_local").size()
                       .reset_index(name="Quantidade"))
                fig = px.pie(tab, values="Quantidade", names="tipo_local", hole=0.54,
                             title="Onde os registros preenchidos aparecem")
                exibir_grafico(fig)
        st.markdown("#### Sinais que concentram células vazias")
        ranking_por_status(sinais, "Pendente", "Pendências por sinal")

# 8. Auditoria de qualidade: localizar, não corrigir automaticamente, divergências.
with aba_qualidade:
    st.subheader("Qualidade dos dados e pontos para revisão")
    st.write("Esta aba destaca **possíveis** problemas de preenchimento. Uma grafia diferente não é,"
             " por si só, um erro de engenharia.")

    ocorrencias = (filtrado.loc[filtrado.bloco_repetido]
                   .groupby(["ativo", "equipamento"])["bloco"].nunique()
                   .reset_index(name="Blocos no recorte"))
    q1, q2, q3 = st.columns(3)
    q1.metric("Células vazias", formato_numero(resumo["pendentes"]))
    q2.metric("Grafias para revisar", formato_numero(resumo["possiveis_inconsistencias"]))
    q3.metric("Nomes de bloco repetidos", formato_numero(len(ocorrencias)))

    st.markdown("#### Células pendentes")
    colunas_auditoria = ["ativo", "equipamento", "local", "funcao", "codigo", "ponto",
                         "linha_excel", "coluna_excel"]
    pendentes = filtrado.loc[filtrado.status == "Pendente", colunas_auditoria]
    st.dataframe(pendentes, hide_index=True, use_container_width=True)

    st.markdown("#### Escritas diferentes do padrão predominante")
    suspeitos = filtrado.loc[filtrado.possivel_inconsistencia, colunas_auditoria]
    st.dataframe(suspeitos, hide_index=True, use_container_width=True)
    st.caption("A coluna e a linha indicam onde procurar o valor na planilha original correspondente ao ativo.")

    st.markdown("#### Nomes de equipamento presentes em mais de um bloco")
    st.dataframe(ocorrencias, hide_index=True, use_container_width=True)
    st.info("Os limites de formato usados na triagem são heurísticos, baseados em exemplos recorrentes da planilha.")
    st.download_button("⬇️ Exportar itens para revisão (CSV)",
                       data=pd.concat([pendentes.assign(motivo="Célula vazia"),
                                       suspeitos.assign(motivo="Grafia diferente")], ignore_index=True)
                       .to_csv(index=False).encode("utf-8-sig"),
                       file_name="itens_para_revisao.csv", mime="text/csv")

# 9. Tabela de dados normalizados e exportação para outras análises.
with aba_dados:
    st.subheader("Base de dados normalizada")
    st.write("As planilhas originais estão organizadas em blocos lado a lado."
             " Aqui, **cada linha corresponde a uma função de um equipamento em um local**.")
    selecionar_status = st.multiselect("Mostrar status na tabela", ORDEM_STATUS,
                                      default=ORDEM_STATUS)
    tabela_filtrada = filtrado.loc[filtrado.status.isin(selecionar_status)]
    colunas_visiveis = ["ativo", "equipamento", "bloco", "via", "sentido", "tipo_local", "local",
                        "categoria", "funcao", "codigo", "ponto", "status", "familia",
                        "possivel_inconsistencia", "linha_excel", "coluna_excel"]
    st.dataframe(tabela_filtrada[colunas_visiveis], hide_index=True,
                 use_container_width=True, height=450)
    st.caption(f"{formato_numero(len(tabela_filtrada))} registros no recorte selecionado.")
    st.download_button("⬇️ Baixar base filtrada (CSV)",
                       data=tabela_filtrada.to_csv(index=False).encode("utf-8-sig"),
                       file_name="dados_ferroviarios_tratados.csv", mime="text/csv")

st.divider()
st.caption("Projeto Integrador • Fonte: levantamentos de BD de CDVs e Sinais (Vias 1 e 2)."
           " O painel não determina condição operacional, risco ou segurança do sistema ferroviário.")
