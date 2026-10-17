"""Transformação das planilhas originais em registros prontos para visualização.

A base vem em blocos horizontais. Cada registro final representa UMA célula
na interseção entre um local e uma função, e não um equipamento físico distinto.
"""
from __future__ import annotations

import re
from io import BytesIO

import pandas as pd

# Descrições extraídas dos cabeçalhos das próprias planilhas.
FUNCOES = {
    "CDV": (("Codificação", "NCTP"), ("Codificação", "SCTP"),
            ("Codificação", "N12-CTP"), ("Indicação", "TPR"), ("Indicação", "TPRN")),
    "Sinal": (("Vermelho", "RGE"), ("Vermelho", "RGENX"),
              ("Amarelo", "YGE"), ("Amarelo", "YGENX")),
}

# Hipóteses de formato para TRIAGEM: não são normas oficiais de engenharia.
PADROES_ESCRITA = {
    "Locação": re.compile(r"^L[BC] [A-Z]{1,2}-\d+$", flags=re.I),
    "Armário TB": re.compile(r"^TB\d+-[A-Z]\d+$", flags=re.I),
    "Interface": re.compile(r"^B\d{2} \d{2}$", flags=re.I),
}

COLUNAS = ["ativo", "equipamento", "bloco", "via", "sentido", "tipo_local", "local",
           "categoria", "funcao", "codigo", "ponto", "status", "familia",
           "possivel_inconsistencia", "bloco_repetido", "linha_excel", "coluna_excel"]


def texto(valor: object) -> str:
    """Transforma vazios do Excel em string vazia, mantendo o restante legível."""
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def classificar_status(ponto: str) -> str:
    """Critério de trabalho: '-' não equivale a dado faltante."""
    if not ponto:
        return "Pendente"
    if ponto == "-":
        return "Não utilizado"
    return "Preenchido"


def identificar_local(rotulo: str) -> str:
    rot = rotulo.casefold()
    if rot.startswith("locação") or rot.startswith("locacao"):
        return "Locação"
    if rot.startswith("armário") or rot.startswith("armario"):
        return "Armário TB"
    if rot.startswith("interface"):
        return "Interface"
    if rot.startswith("bastidor"):
        return "Bastidor"
    return "Outro"


def extrair_familia(tipo_local: str, ponto: str) -> str:
    if classificar_status(ponto) != "Preenchido":
        return ""
    primeiro = ponto.split("/")[0].strip().upper()
    if tipo_local == "Locação":
        return primeiro[:2] if primeiro.startswith(("LB", "LC")) else "Outros"
    if tipo_local == "Armário TB":
        match = re.match(r"^TB\d+", primeiro)
        return match.group() if match else "Outros"
    return tipo_local


def verificar_escrita(tipo_local: str, ponto: str) -> bool:
    """Sinaliza padrões diferentes do predominante; não comprova erro."""
    modelo = PADROES_ESCRITA.get(tipo_local)
    if modelo is None or classificar_status(ponto) != "Preenchido":
        return False
    return any(not modelo.fullmatch(parte.strip()) for parte in ponto.split("/"))


def numero_coluna_excel(indice_zero: int) -> str:
    """Converte índice zero-based em letra(s) do Excel: 0->A, 26->AA."""
    n = indice_zero + 1
    letras = ""
    while n > 0:
        n, resto = divmod(n - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def transformar_planilha(matriz: pd.DataFrame, ativo: str) -> pd.DataFrame:
    """Descobre os cabeçalhos e percorre cada bloco sem depender da posição fixa.

    CDVs: dados começam 4 linhas abaixo do título (após 3 linhas de cabeçalho).
    Sinais: começam 5 linhas abaixo (há uma linha 'Sinaleiro - TB' adicional).
    """
    if ativo not in FUNCOES:
        raise ValueError(f"Tipo de equipamento inesperado: {ativo}")
    if matriz.empty:
        return pd.DataFrame(columns=COLUNAS)

    titulo = re.compile(r"^CDV\s+(.+?)\s+LUZ$" if ativo == "CDV" else
                        r"^SINAL\s+(.+?)\s+LUZ$", flags=re.I)
    offset_inicio = 4 if ativo == "CDV" else 5
    funcoes = FUNCOES[ativo]
    registros: list[dict] = []
    vezes_visto: dict[str, int] = {}

    # Procura títulos de blocos independentemente da coluna em que aparecem.
    for c in range(matriz.shape[1]):
        linha = 0
        while linha < len(matriz):
            match = titulo.fullmatch(texto(matriz.iat[linha, c]))
            if match is None:
                linha += 1
                continue
            nome = match.group(1).strip()
            vezes_visto[nome] = vezes_visto.get(nome, 0) + 1
            ocorrencia = vezes_visto[nome]
            id_bloco = nome if ocorrencia == 1 else f"{nome} (bloco {ocorrencia})"

            # O código do CDV inclui via e sentido; o número do sinal não informa via.
            info_cdv = re.match(r"^([12])([NS])", nome, flags=re.I) if ativo == "CDV" else None
            via = f"Via {info_cdv.group(1)}" if info_cdv else "Não identificada"
            sentido = {"N": "Norte", "S": "Sul"}.get(info_cdv.group(2).upper(), "Não identificado") if info_cdv else "Não identificado"
            linha_codigos = linha + 3
            codigos = [texto(matriz.iat[linha_codigos, c + i + 1])
                       if linha_codigos < len(matriz) and c + i + 1 < matriz.shape[1] else ""
                       for i in range(len(funcoes))]

            r = linha + offset_inicio
            while r < len(matriz):
                rotulo_local = texto(matriz.iat[r, c])
                if not rotulo_local or titulo.fullmatch(rotulo_local):
                    break
                tipo_local = identificar_local(rotulo_local)
                for i, (categoria, funcao) in enumerate(funcoes):
                    coluna_ponto = c + i + 1
                    ponto = texto(matriz.iat[r, coluna_ponto]) if coluna_ponto < matriz.shape[1] else ""
                    registros.append({
                        "ativo": ativo,
                        "equipamento": nome,
                        "bloco": id_bloco,
                        "via": via,
                        "sentido": sentido,
                        "tipo_local": tipo_local,
                        "local": rotulo_local,
                        "categoria": categoria,
                        "funcao": funcao,
                        "codigo": codigos[i],
                        "ponto": ponto,
                        "status": classificar_status(ponto),
                        "familia": extrair_familia(tipo_local, ponto),
                        "possivel_inconsistencia": verificar_escrita(tipo_local, ponto),
                        "bloco_repetido": False,  # atualizado depois da leitura completa
                        "linha_excel": r + 1,
                        "coluna_excel": numero_coluna_excel(coluna_ponto),
                    })
                r += 1
            linha = max(linha + 1, r)

    for reg in registros:
        reg["bloco_repetido"] = vezes_visto[reg["equipamento"]] > 1
    return pd.DataFrame(registros, columns=COLUNAS)


def ler_e_transformar(conteudo_cdv: bytes | None, conteudo_sinais: bytes | None) -> pd.DataFrame:
    """Recebe bytes (da pasta ou do upload) e devolve as duas bases unificadas."""
    tabelas = []
    for ativo, conteudo in (("CDV", conteudo_cdv), ("Sinal", conteudo_sinais)):
        if conteudo is None:
            continue
        matriz = pd.read_excel(BytesIO(conteudo), header=None, sheet_name=0, dtype=object)
        tabelas.append(transformar_planilha(matriz, ativo))
    if not tabelas:
        return pd.DataFrame(columns=COLUNAS)
    return pd.concat(tabelas, ignore_index=True)


def calcular_resumo(df: pd.DataFrame) -> dict:
    """Conta células, ignorando o '-' no denominador da taxa de preenchimento."""
    contagem = df.status.value_counts()
    preenchidos = int(contagem.get("Preenchido", 0))
    pendentes = int(contagem.get("Pendente", 0))
    nao_utilizados = int(contagem.get("Não utilizado", 0))
    aplicaveis = preenchidos + pendentes
    return {
        "preenchidos": preenchidos,
        "pendentes": pendentes,
        "nao_utilizados": nao_utilizados,
        "aplicaveis": aplicaveis,
        "taxa": preenchidos / aplicaveis if aplicaveis else 0.0,
        "cdvs": int(df.loc[df.ativo == "CDV", "equipamento"].nunique()),
        "sinais": int(df.loc[df.ativo == "Sinal", "equipamento"].nunique()),
        "possiveis_inconsistencias": int(df.possivel_inconsistencia.sum()) if not df.empty else 0,
    }
