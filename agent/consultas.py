"""A fronteira de governança: o único lugar do projeto que monta DAX.

O modelo de linguagem nunca escreve consulta. Ele escolhe, de listas
fechadas, uma medida certificada, cortes e valores — e este módulo
monta o DAX correspondente de forma determinística. Escolha inválida
vira erro com as opções válidas, não uma consulta improvisada.

Isso é o que a palavra "governado" significa neste projeto: o conjunto
de perguntas respondíveis é exatamente o conjunto de combinações que a
camada semântica certifica.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import catalogo
from .catalogo import CORTES, CorteDesconhecido
from .fabric import executar_dax

LIMITE_MAXIMO = 500


@dataclass
class Resultado:
    linhas: list[dict[str, Any]]
    dax: str
    medidas: list[str]
    corte: str | None = None

    def vazio(self) -> bool:
        return not self.linhas


def _literal(valor: Any) -> str:
    """Converte um valor já validado em literal DAX.

    A segurança aqui não vem desta função e sim de `validar_valor`: só
    chega um valor idêntico a um que existe no modelo. As aspas duplicadas
    são defesa em profundidade, não a linha principal.
    """
    if isinstance(valor, bool):
        return "TRUE()" if valor else "FALSE()"
    if isinstance(valor, (int, float)):
        return str(valor)
    return '"' + str(valor).replace('"', '""') + '"'


def _clausula_de_filtro(corte: str, valores: list[Any]) -> str:
    tabela, coluna = CORTES[corte]
    validados = [catalogo.validar_valor(corte, v) for v in valores]
    lista = ", ".join(_literal(v) for v in validados)
    return (
        f"FILTER ( ALL ( {tabela}[{coluna}] ), "
        f"{tabela}[{coluna}] IN {{ {lista} }} )"
    )


def _normalizar_filtros(filtros: dict[str, Any] | None) -> dict[str, list[Any]]:
    if not filtros:
        return {}
    normalizados: dict[str, list[Any]] = {}
    for corte, valor in filtros.items():
        if corte not in CORTES:
            raise CorteDesconhecido(corte)
        normalizados[corte] = valor if isinstance(valor, list) else [valor]
    return normalizados


def consultar(
    medidas: list[str],
    filtros: dict[str, Any] | None = None,
    agrupar_por: str | None = None,
    ordenar_por: str | None = None,
    descendente: bool = True,
    limite: int | None = None,
) -> Resultado:
    """Consulta medidas certificadas, opcionalmente quebradas por um corte.

    Sem `agrupar_por`, devolve uma linha com os valores no contexto dos
    filtros. Com `agrupar_por`, devolve uma linha por valor do corte —
    é assim que comparações e rankings são respondidos.
    """
    cat = catalogo.carregar()
    if not medidas:
        raise ValueError("Informe ao menos uma medida certificada.")
    validadas = [cat.validar_medida(nome) for nome in medidas]

    if agrupar_por is not None and agrupar_por not in CORTES:
        raise CorteDesconhecido(agrupar_por)
    if ordenar_por is not None and ordenar_por not in [m.nome for m in validadas]:
        raise ValueError(
            f"'{ordenar_por}' não está entre as medidas consultadas. "
            f"Ordene por uma destas: {', '.join(m.nome for m in validadas)}."
        )

    clausulas = [
        _clausula_de_filtro(corte, valores)
        for corte, valores in _normalizar_filtros(filtros).items()
    ]
    projecoes = ", ".join(
        f'"{m.nome}", {m.referencia_dax()}' for m in validadas
    )

    if agrupar_por is None:
        corpo = f"ROW ( {projecoes} )"
        dax = (
            f"EVALUATE CALCULATETABLE ( {corpo}, {', '.join(clausulas)} )"
            if clausulas
            else f"EVALUATE {corpo}"
        )
    else:
        tabela, coluna = CORTES[agrupar_por]
        partes = [f"{tabela}[{coluna}]", *clausulas, projecoes]
        corpo = f"SUMMARIZECOLUMNS ( {', '.join(partes)} )"
        chave_ordem = f"[{ordenar_por or validadas[0].nome}]"
        direcao = "DESC" if descendente else "ASC"
        if limite:
            corpo = f"TOPN ( {min(limite, LIMITE_MAXIMO)}, {corpo}, {chave_ordem}, {direcao} )"
        dax = f"EVALUATE {corpo} ORDER BY {chave_ordem} {direcao}"

    linhas = executar_dax(dax)
    return Resultado(
        linhas=[_renomear(linha, agrupar_por) for linha in linhas],
        dax=dax,
        medidas=[m.nome for m in validadas],
        corte=agrupar_por,
    )


def _renomear(linha: dict[str, Any], agrupar_por: str | None) -> dict[str, Any]:
    """Troca as chaves do DAX (`dim_uf[nome_uf]`, `[Medida]`) pelos nomes
    que o agente e a interface usam."""
    renomeada: dict[str, Any] = {}
    chave_do_corte = (
        "{}[{}]".format(*CORTES[agrupar_por]) if agrupar_por else None
    )
    for chave, valor in linha.items():
        if chave == chave_do_corte:
            renomeada[agrupar_por] = valor  # type: ignore[index]
        else:
            renomeada[chave.strip("[]")] = valor
    return renomeada


def descrever_catalogo() -> dict[str, Any]:
    """O que o agente pode perguntar — usado para montar a ferramenta."""
    cat = catalogo.carregar()
    return {
        "medidas": [
            {"nome": m.nome, "descricao": m.descricao}
            for m in sorted(cat.medidas.values(), key=lambda m: m.nome)
        ],
        "cortes": sorted(CORTES),
    }
