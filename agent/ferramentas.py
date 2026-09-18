"""As ferramentas que o modelo pode chamar — agnósticas de provedor.

São funções Python comuns, com tipos simples de propósito: cada
provedor de LLM gera o schema da ferramenta a partir da assinatura, e
tipos exóticos (uniões, dicionários livres) traduzem mal. Filtros
chegam como JSON em texto e são validados aqui, não pelo schema.

Nenhuma destas funções confia no que recebe: tudo passa por
`consultas.py`, que recusa medida, corte ou valor que não exista no
catálogo certificado.
"""

from __future__ import annotations

import contextvars
import json
from typing import Any

from . import catalogo, consultas

# Registro das consultas de uma execução, para a interface poder mostrar
# exatamente o que foi perguntado ao modelo semântico. É o que torna a
# resposta auditável em vez de só plausível.
execucao: contextvars.ContextVar[list[consultas.Resultado]] = contextvars.ContextVar(
    "execucao"
)


def formatar(valor: Any, formato: str) -> str:
    """Formata segundo o FormatString da medida certificada.

    Feito em Python, não pelo modelo: assim o agente não precisa decidir
    se 0,041 é "0,041" ou "4,1%" — a própria definição da medida decide.
    """
    if valor is None:
        return "sem valor"
    if not isinstance(valor, (int, float)) or isinstance(valor, bool):
        return str(valor)
    if "%" in formato:
        return f"{valor * 100:.2f}".replace(".", ",") + "%"
    if "R$" in formato:
        for limite, sufixo in ((1e12, "Tri"), (1e9, "Bi"), (1e6, "Mi")):
            if abs(valor) >= limite:
                return "R$ " + _br(valor / limite) + f" {sufixo}"
        return "R$ " + _br(valor)
    if isinstance(valor, float):
        return _br(valor)
    return f"{valor:,}".replace(",", ".")


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
            formatada[chave] = formatar(valor, medida.formato) if medida else valor
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
    try:
        valores = catalogo.valores_do_corte(corte)
    except catalogo.CorteDesconhecido as erro:
        return str(erro)
    if len(valores) > 60:
        amostra = ", ".join(str(v) for v in valores[:60])
        return f"{len(valores)} valores em '{corte}'. Primeiros 60: {amostra}"
    return f"Valores de '{corte}': " + ", ".join(str(v) for v in valores)


DISPONIVEIS = [consultar_metricas, listar_valores]
