"""As ferramentas que o modelo pode chamar — agnósticas de provedor.

São funções Python comuns, com tipos simples de propósito: cada
provedor de LLM gera o schema da ferramenta a partir da assinatura, e
tipos exóticos (uniões, dicionários livres) traduzem mal. Filtros
chegam como JSON em texto e são validados aqui, não pelo schema.

Nenhuma destas funções confia no que recebe: tudo passa por
`consultas.py`, que recusa medida, corte ou valor que não exista no
catálogo certificado.

Este módulo não usa `from __future__ import annotations`, de propósito:
o SDK do Gemini lê as anotações para validar os argumentos antes de
chamar a função, e com anotações em texto ele compara o valor contra a
string "list[str]" e quebra — foi a causa de a ferramenta nunca executar
nos primeiros testes (ver test_ferramentas_executam_pelo_caminho_do_sdk).
"""

import contextvars
import json
from typing import Any

from . import catalogo, consultas, ritmo

# Registro das consultas de uma execução, para a interface poder mostrar
# exatamente o que foi perguntado ao modelo semântico. É o que torna a
# resposta auditável em vez de só plausível.
execucao: contextvars.ContextVar[list[consultas.Resultado]] = contextvars.ContextVar(
    "execucao"
)


def formatar(valor: Any, unidade: str = "numero") -> str:
    """Apresenta o valor segundo a unidade declarada em `catalogo.UNIDADES`.

    Feito aqui e não pelo modelo de linguagem: 0,041 virar "0,04%" é o
    tipo de erro que a camada certificada existe para impedir.
    """
    if valor is None:
        return "sem valor"
    if unidade == "data":
        texto = str(valor)
        return f"{texto[8:10]}/{texto[5:7]}/{texto[:4]}" if len(texto) >= 10 else texto
    if not isinstance(valor, (int, float)) or isinstance(valor, bool):
        return str(valor)

    if unidade == "fracao":
        return _br(valor * 100) + "%"
    if unidade == "percentual":
        return _br(valor) + "%"
    if unidade == "pp":
        return _br(valor) + " pp"
    if unidade == "reais_milhoes":
        return _reais(valor * 1e6)
    if unidade == "reais":
        return _reais(valor)
    if unidade == "contagem":
        return f"{int(valor):,}".replace(",", ".")
    if unidade == "meses":
        return f"{int(valor)} meses"
    return _br(valor) if isinstance(valor, float) else f"{valor:,}".replace(",", ".")


def _reais(valor: float) -> str:
    for limite, sufixo in ((1e12, "Tri"), (1e9, "Bi"), (1e6, "Mi")):
        if abs(valor) >= limite:
            return "R$ " + _br(valor / limite) + f" {sufixo}"
    return "R$ " + _br(valor)


def _br(numero: float) -> str:
    return f"{numero:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def consultar_metricas(
    medidas: list[str],
    filtros_json: str = "",
    agrupar_por: str = "",
    ordenar_por: str = "",
    descendente: bool = True,
    limite: int = 0,
) -> str:
    """Consulta medidas certificadas do modelo semântico do Lumen.

    Use para obter QUALQUER número. Nunca responda com um valor que não
    tenha vindo desta ferramenta.

    Args:
        medidas: nomes exatos de medidas certificadas, como no catálogo.
        filtros_json: filtros em JSON, ex.: '{"cliente": "PF", "uf": "São Paulo"}'.
            Use lista para vários valores: '{"ano": [2024, 2025]}'. Vazio = sem filtro.
        agrupar_por: corte para quebrar o resultado em linhas, ex.: "uf".
            Use para comparações e rankings. Vazio = valor único.
        ordenar_por: medida pela qual ordenar quando houver agrupamento.
        descendente: ordem decrescente (padrão) ou crescente.
        limite: máximo de linhas quando houver agrupamento. 0 = sem limite.
    """
    ritmo.espacar()
    # O modelo às vezes manda uma medida solta em vez de lista; iterar a
    # string caractere a caractere daria um erro incompreensível ("'T' não
    # é uma medida certificada").
    if isinstance(medidas, str):
        medidas = [medidas]

    try:
        filtros = json.loads(filtros_json) if filtros_json.strip() else None
    except json.JSONDecodeError as erro:
        return f"filtros_json não é JSON válido ({erro}). Exemplo: {{\"cliente\": \"PF\"}}"
    if filtros is not None and not isinstance(filtros, dict):
        return 'filtros_json precisa ser um objeto JSON, ex.: {"cliente": "PF"}'

    try:
        resultado = consultas.consultar(
            medidas=medidas,
            filtros=filtros,
            agrupar_por=agrupar_por or None,
            ordenar_por=ordenar_por or None,
            descendente=descendente,
            limite=limite or None,
        )
    except (ValueError, consultas.CorteDesconhecido) as erro:
        # Erro de escolha volta como texto para o modelo se corrigir — não
        # como exceção. A mensagem já traz as opções válidas.
        return f"Consulta recusada: {erro}"

    registro = execucao.get(None)
    if registro is not None:
        registro.append(resultado)

    cat = catalogo.carregar()
    linhas = []
    for linha in resultado.linhas:
        formatada = {}
        for chave, valor in linha.items():
            medida = cat.medidas.get(chave)
            formatada[chave] = formatar(valor, medida.unidade) if medida else valor
        linhas.append(formatada)

    if not linhas:
        return "Nenhuma linha retornada para esses filtros."
    return json.dumps({"linhas": linhas}, ensure_ascii=False)


def listar_valores(corte: str) -> str:
    """Lista os valores válidos de um corte, para usar em filtros_json.

    Use antes de filtrar quando não tiver certeza da grafia exata de um
    valor (nomes de modalidade e de UF são longos e específicos).

    Args:
        corte: nome do corte, ex.: "uf", "modalidade", "competencia".
    """
    ritmo.espacar()
    try:
        valores = catalogo.valores_do_corte(corte)
    except catalogo.CorteDesconhecido as erro:
        return str(erro)
    if len(valores) > 60:
        amostra = ", ".join(str(v) for v in valores[:60])
        return f"{len(valores)} valores em '{corte}'. Primeiros 60: {amostra}"
    return f"Valores de '{corte}': " + ", ".join(str(v) for v in valores)


DISPONIVEIS = [consultar_metricas, listar_valores]
