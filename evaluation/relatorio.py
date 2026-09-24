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
}

# Perguntas em que as duas rodadas discordaram, e por quê. As cinco do
# token vencido são o bug de infraestrutura que invalidou a rodada 1
# (METODOLOGIA.md); B10 é a única variação do próprio modelo.
VARIABILIDADE = {
    "B10": "errou na rodada 1 (submodalidade trocada) e acertou na 2 — variação do modelo",
    "D08": "rodada 1 falhou por token vencido (bug de infraestrutura, corrigido)",
    "D09": "rodada 1 falhou por token vencido (bug de infraestrutura, corrigido)",
    "D10": "rodada 1 falhou por token vencido (bug de infraestrutura, corrigido)",
    "E01": "rodada 1 falhou por token vencido (bug de infraestrutura, corrigido)",
    "E02": "rodada 1 falhou por token vencido (bug de infraestrutura, corrigido)",
}

# Cada número que o detector marcou como "sem lastro", lido à mão. Um
# alerta publicado sem leitura vale menos que nenhum: dos três, dois são
# aritmética do próprio agente sobre valores certificados, e um é falso
# positivo já corrigido no detector — depois desta rodada, por isso ainda
# aparece aqui.
LASTRO = {
    "D07": "diferença entre dois valores certificados que o próprio agente consultou",
    "E01": "falso positivo: 433 é o código da série SGS, que vem da descrição da medida",
    "E03": "razão entre dois valores certificados que o próprio agente consultou",
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
    espera = sum(d.get("espera_cota_s") or 0 for d in dados)
    if espera:
        partes.append(
            f"A latência acima é tempo de modelo: os {espera:.0f} s de espera "
            "impostos pelo teto de tokens por minuto da cota gratuita estão "
            "descontados (ver METODOLOGIA.md).\n"
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

    partes.append("## Reprodutibilidade\n")
    partes.append(
        "A rodada 1 foi invalidada por três bugs de infraestrutura (ver "
        "METODOLOGIA.md), mas as 84 respostas que ela alcançou servem para "
        "medir estabilidade. Nas perguntas que as duas rodadas têm em comum:\n"
    )
    partes.append(
        "- **Baseline: nenhuma divergência entre as rodadas.** Os erros de "
        "fonte trocada se repetem pergunta a pergunta — são sistemáticos, "
        "não ruído de amostragem."
    )
    partes.append("- **Agente: 6 divergências**, assim explicadas:")
    for pergunta, motivo in VARIABILIDADE.items():
        partes.append(f"  - `{pergunta}`: {motivo}")
    partes.append(
        "\nDescontada a infraestrutura, o agente variou em 1 das 42 perguntas "
        "comparáveis. O placar não deve ser lido como exato até a segunda "
        "casa; deve ser lido como uma diferença grande o bastante para não "
        "ser explicada por essa variação.\n"
    )

    if sem_lastro:
        partes.append("## Números sem lastro no agente\n")
        for d in sorted(sem_lastro, key=lambda d: d["id"]):
            nota = LASTRO.get(d["id"], "não classificado")
            partes.append(f"- `{d['id']}`: {', '.join(d['sem_lastro'])} — {nota}")
        partes.append(
            "\nNenhum dos três é um número inventado. O detector é "
            "deliberadamente severo: ele acusa qualquer número da resposta "
            "que não tenha saído de uma consulta, inclusive conta feita pelo "
            "agente sobre valores que ele mesmo consultou.\n"
        )
    return "\n".join(partes)


def main() -> int:
    arquivo = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evaluation/resultados/rodada2.jsonl")
    destino = arquivo.parent / f"{arquivo.stem}.md"
    destino.write_text(gerar(arquivo), encoding="utf-8")
    print(f"Relatório gravado em {destino}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
