"""Relatório do benchmark em Markdown, a partir do arquivo de resultados.

Rodar com:  python -m evaluation.relatorio evaluation/resultados/rodada2.jsonl

Gera a tabela por categoria, a lista de erros de cada abordagem e os
indicadores que a Sprint 12 pede (recusa correta, recusa indevida,
latência, lastro). Não consome cota: lê só o que já foi gravado.

A classificação dos erros é feita à mão, no dicionário CLASSIFICACAO: um
erro de fonte e um erro de arredondamento contam igual no placar, mas
dizem coisas diferentes, e a análise de erros é o que o plano pede que
seja publicado — inclusive os erros do agente.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

CATEGORIAS = {
    "A": "Consulta direta",
    "B": "Filtros e cortes",
    "C": "Rankings e comparações",
    "D": "Semiaditividade (pegadinha)",
    "E": "Macro e deflacionamento (pegadinha)",
    "F": "Fora de escopo (recusar)",
}

# Preenchido à mão depois de ler cada resposta errada (ver METODOLOGIA.md).
CLASSIFICACAO = {
    ("baseline", "A02"): "fonte trocada: usou a série do BCB e atribuiu ao SCR",
    ("baseline", "B06"): "fonte trocada: usou a série do BCB e atribuiu ao SCR",
    ("baseline", "D04"): "fonte trocada: usou a série do BCB e atribuiu ao SCR",
    ("baseline", "D07"): "fonte trocada: variação calculada sobre a série do BCB",
    ("baseline", "D10"): "fonte trocada: série do BCB nos quatro trimestres",
    ("baseline", "E09"): "recusa indevida: procurou concessões só na tabela de crédito",
    ("baseline", "E10"): "arredondamento: método certo, 5,68% contra 5,69%",
    ("agente", "B09"): "filtro perdido: respondeu PJ inteiro, sem a modalidade",
    ("agente", "B10"): "mapeamento: usou uma modalidade no lugar da submodalidade",
}


def carregar(arquivo: Path) -> list[dict]:
    linhas = [json.loads(linha) for linha in arquivo.read_text(encoding="utf-8").splitlines()]
    return [d for d in linhas if not d.get("erro")]


def gerar(arquivo: Path) -> str:
    dados = carregar(arquivo)
    abordagens = ["agente", "baseline"]
    por = defaultdict(lambda: {"total": 0, "acertos": 0})
    for d in dados:
        for chave in ((d["categoria"], d["abordagem"]), ("Total", d["abordagem"])):
            por[chave]["total"] += 1
            por[chave]["acertos"] += d["acertou"]

    modelo = dados[0]["modelo"] if dados else "?"
    partes = [
        "# Benchmark: agente governado × text-to-SQL\n",
        f"Rodada `{arquivo.stem}` · modelo `{modelo}` nas duas abordagens · "
        f"gabarito verificado em {dados[0]['gabarito_verificado_em'][:10]} · "
        f"critérios em [METODOLOGIA.md](METODOLOGIA.md).\n",
        "## Acurácia por categoria\n",
        "| Categoria | Agente | Baseline |",
        "|---|---|---|",
    ]
    for sigla, nome in CATEGORIAS.items():
        celulas = []
        for abordagem in abordagens:
            c = por[(sigla, abordagem)]
            celulas.append(f"{c['acertos']}/{c['total']}" if c["total"] else "—")
        partes.append(f"| {sigla} — {nome} | {celulas[0]} | {celulas[1]} |")
    totais = [por[("Total", a)] for a in abordagens]
    partes.append(
        f"| **Total** | **{totais[0]['acertos']}/{totais[0]['total']}** | "
        f"**{totais[1]['acertos']}/{totais[1]['total']}** |\n"
    )

    partes.append("## Outros indicadores\n")
    partes.append("| Indicador | Agente | Baseline |")
    partes.append("|---|---|---|")
    linha_recusa, linha_latencia = [], []
    for abordagem in abordagens:
        do_lado = [d for d in dados if d["abordagem"] == abordagem]
        linha_recusa.append(str(sum(d["recusa_indevida"] for d in do_lado)))
        latencias = sorted(d["latencia_s"] for d in do_lado)
        linha_latencia.append(f"{latencias[len(latencias) // 2]:.0f} s" if latencias else "—")
    partes.append(f"| Recusas indevidas (pergunta respondível) | {linha_recusa[0]} | {linha_recusa[1]} |")
    partes.append(f"| Latência mediana | {linha_latencia[0]} | {linha_latencia[1]} |")
    sem_lastro = [d for d in dados if d["abordagem"] == "agente" and d.get("sem_lastro")]
    partes.append(
        f"| Números sem lastro (só o agente tem o conceito) | {len(sem_lastro)} | — |\n"
    )

    partes.append("## Erros, um a um\n")
    for abordagem in abordagens:
        erros = [d for d in dados if d["abordagem"] == abordagem and not d["acertou"]]
        partes.append(f"**{abordagem}** — {len(erros)} erro(s)\n")
        for d in sorted(erros, key=lambda d: d["id"]):
            classificacao = CLASSIFICACAO.get((abordagem, d["id"]), "não classificado")
            partes.append(f"- `{d['id']}` {d['pergunta']}")
            partes.append(f"  - esperado: {', '.join(d['faltou'])} — {classificacao}")
        partes.append("")

    if sem_lastro:
        partes.append("## Números sem lastro no agente\n")
        for d in sorted(sem_lastro, key=lambda d: d["id"]):
            partes.append(f"- `{d['id']}`: {', '.join(d['sem_lastro'])}")
        partes.append("")
    return "\n".join(partes)


def main() -> int:
    arquivo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evaluation/resultados/rodada2.jsonl")
    destino = arquivo.parent / f"{arquivo.stem}.md"
    destino.write_text(gerar(arquivo), encoding="utf-8")
    print(f"Relatório gravado em {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
