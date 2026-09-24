"""Verifica o gabarito por dois caminhos independentes e o congela.

Rodar com:  python -m evaluation.verificar_gabarito

Para cada pergunta, executa o SQL escrito à mão sobre a Gold e a consulta
equivalente na camada semântica, e compara. Se todas baterem, grava
`gabarito_congelado.json` com as respostas e a data de verificação. Se
qualquer uma divergir, não grava nada: divergência é para investigar
antes de congelar, não para escolher um dos lados.

Não consome cota de LLM.
"""

import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from agent import consultas
from agent.ferramentas import formatar
from evaluation.sql_gold import executar_sql

PASTA = Path(__file__).parent
TOLERANCIA_RELATIVA = 1e-6  # SQL e DAX somam em ordens diferentes


def _iguais(a: Any, b: Any) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(float(a), float(b), rel_tol=TOLERANCIA_RELATIVA, abs_tol=1e-12)
    return str(a).strip() == str(b).strip()


def verificar(pergunta: dict) -> tuple[dict, list[str]]:
    """Devolve a resposta esperada e a lista de divergências (vazia = ok)."""
    tipo = pergunta["tipo"]
    if tipo == "recusa":
        return {"recusa": True}, []

    linhas_sql = executar_sql(pergunta["sql"])
    unidade = pergunta["unidade"]
    problemas: list[str] = []

    certificada = pergunta.get("certificada")
    linhas_cert = consultas.consultar(**certificada).linhas if certificada else None
    medida = certificada["medidas"][0] if certificada else None
    corte = certificada.get("agrupar_por") if certificada else None

    if tipo == "valor":
        bruto = linhas_sql[0]["valor"]
        if linhas_cert is not None and not _iguais(bruto, linhas_cert[0][medida]):
            problemas.append(f"SQL={bruto} certificada={linhas_cert[0][medida]}")
        return {"brutos": [bruto], "texto": [formatar(bruto, unidade)], "nomes": []}, problemas

    if tipo == "ranking":
        n = certificada["limite"] if certificada else 1
        topo = linhas_sql[:n]
        if linhas_cert is not None:
            for s, c in zip(topo, linhas_cert, strict=False):
                if not _iguais(s["nome"], c[corte]) or not _iguais(s["valor"], c[medida]):
                    problemas.append(f"SQL={s} certificada={c}")
        return {
            "brutos": [s["valor"] for s in topo],
            "texto": [formatar(s["valor"], unidade) for s in topo],
            "nomes": [str(s["nome"]).strip() for s in topo],
        }, problemas

    if tipo == "valores":
        if linhas_cert is not None:
            por_rotulo = {str(c[corte]).strip(): c[medida] for c in linhas_cert}
            for s in linhas_sql:
                certo = por_rotulo.get(str(s["rotulo"]).strip())
                if certo is None or not _iguais(s["valor"], certo):
                    problemas.append(f"{s['rotulo']}: SQL={s['valor']} certificada={certo}")
        return {
            "brutos": [s["valor"] for s in linhas_sql],
            "texto": [formatar(s["valor"], unidade) for s in linhas_sql],
            "nomes": [],
            "rotulos": [str(s["rotulo"]).strip() for s in linhas_sql],
        }, problemas

    raise ValueError(f"tipo desconhecido: {tipo}")


def main() -> int:
    perguntas = yaml.safe_load((PASTA / "gabarito.yaml").read_text(encoding="utf-8"))["perguntas"]
    congelado, divergencias = [], 0
    for p in perguntas:
        esperado, problemas = verificar(p)
        situacao = "ok" if not problemas else "DIVERGE"
        mostra = esperado.get("texto") or ["recusa"]
        nomes = f"{esperado['nomes']} " if esperado.get("nomes") else ""
        print(f"[{p['id']}] {situacao:<7} {nomes}{', '.join(mostra)}")
        for problema in problemas:
            print(f"        {problema}")
        divergencias += bool(problemas)
        congelado.append(
            {k: p[k] for k in ("id", "categoria", "pergunta", "tipo")}
            | {"unidade": p.get("unidade"), "esperado": esperado}
        )

    if divergencias:
        print(f"\n{divergencias} divergência(s): gabarito NÃO congelado. Investigar antes.")
        return 1

    destino = PASTA / "gabarito_congelado.json"
    destino.write_text(
        json.dumps(
            {
                "verificado_em": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(
                    timespec="seconds"
                ),
                "perguntas": congelado,
            },
            ensure_ascii=False,
            indent=2,
            default=float,
        ),
        encoding="utf-8",
    )
    print(f"\n{len(congelado)} perguntas verificadas pelos dois caminhos. Congelado em {destino.name}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
