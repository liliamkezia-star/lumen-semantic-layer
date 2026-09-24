"""Benchmark: agente governado × baseline text-to-SQL (Sprint 12).

Rodar com:   python -m evaluation.benchmark [--rodada NOME]
Placar:      python -m evaluation.benchmark --placar evaluation/resultados/NOME.jsonl

Faz as 60 perguntas do gabarito congelado às duas abordagens, com o mesmo
modelo, e corrige pelos critérios de METODOLOGIA.md. Consome cota da API
do LLM; no nível gratuito leva algumas horas.

Cada resposta é gravada assim que chega (uma linha JSON por pergunta e
abordagem). Interrompido, é só rodar de novo com o mesmo --rodada: o que
já foi feito é pulado. Agente e baseline se alternam pergunta a pergunta,
para os dois rodarem nas mesmas condições de cota e horário.
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from agent import avaliacao, ritmo
from agent.agente import Agente, ModelosIndisponiveis
from evaluation.baseline_text2sql import MODELO, BaselineTextToSql
from evaluation.corretor import corrigir

PASTA = Path(__file__).parent
RESULTADOS = PASTA / "resultados"
PAUSA_ENTRE_CHAMADAS = 8  # s
ESPERA_POR_COTA = 70  # s: o limite gratuito é por minuto
TENTATIVAS_POR_COTA = 10

# O teto da cota gratuita é de tokens de ENTRADA por minuto (16.000 no
# gemma-4-26b), e cada chamada com ferramenta reenvia a conversa inteira.
# Uma pergunta que consulta várias vezes estoura o teto sozinha, e repetir
# a pergunta só reproduz o estouro. Espaçar as chamadas resolve, e vale
# para as duas abordagens: ver agent/ritmo.py e METODOLOGIA.md.
PAUSA_FERRAMENTA = 20  # s

ABORDAGENS = {
    "agente": lambda: Agente(modelo=MODELO),
    "baseline": lambda: BaselineTextToSql(modelo=MODELO),
}


def _sem_lastro(texto: str, resultados: list) -> list[str]:
    """Números da resposta do agente que não vieram de consulta."""
    lastro = avaliacao.lastro_da_conversa(resultados)
    return [
        f"{v:.{c}f}".replace(".", ",")
        for v, c in avaliacao.extrair_numeros(texto)
        if not avaliacao.e_irrelevante(v, c) and not avaliacao.tem_lastro(v, c, lastro)
    ]


def responder(abordagem: str, pergunta: dict) -> dict:
    """Uma pergunta, uma abordagem, sem histórico: cada pergunta é independente."""
    for tentativa in range(1, TENTATIVAS_POR_COTA + 1):
        respondente = ABORDAGENS[abordagem]()
        ritmo.zerar()
        inicio = time.monotonic()
        try:
            resposta = respondente.perguntar(pergunta["pergunta"])
        except ModelosIndisponiveis as erro:
            if tentativa == TENTATIVAS_POR_COTA:
                return {"erro": str(erro)}
            print(f"(sem cota, aguardando {ESPERA_POR_COTA}s)", end=" ", flush=True)
            time.sleep(ESPERA_POR_COTA)
            continue
        # A espera imposta pela cota não é tempo de modelo, e sairia no
        # indicador de latência como se fosse lentidão da abordagem.
        espera = ritmo.dormido()
        latencia = time.monotonic() - inicio - espera
        break

    nota = corrigir(pergunta, resposta.texto)
    registro = {
        "resposta": resposta.texto,
        "latencia_s": round(latencia, 1),
        "espera_cota_s": round(espera, 1),
        "acertou": nota.acertou,
        "recusa_indevida": nota.recusa_indevida,
        "faltou": nota.faltou,
    }
    if abordagem == "agente":
        registro["consultas"] = [r.dax for r in resposta.consultas]
        registro["sem_lastro"] = _sem_lastro(resposta.texto, resposta.consultas)
    else:
        registro["consultas"] = list(resposta.consultas)
    return registro


def rodar(rodada: str) -> Path:
    gabarito = json.loads((PASTA / "gabarito_congelado.json").read_text(encoding="utf-8"))
    RESULTADOS.mkdir(exist_ok=True)
    arquivo = RESULTADOS / f"{rodada}.jsonl"
    feitos = set()
    if arquivo.exists():
        for linha in arquivo.read_text(encoding="utf-8").splitlines():
            d = json.loads(linha)
            if not d.get("erro"):
                feitos.add((d["id"], d["abordagem"]))

    perguntas = gabarito["perguntas"]
    for indice, pergunta in enumerate(perguntas, start=1):
        for abordagem in ABORDAGENS:
            if (pergunta["id"], abordagem) in feitos:
                continue
            print(f"[{indice:>2}/{len(perguntas)}] {pergunta['id']} {abordagem:<8}", end=" ", flush=True)
            registro = {
                "id": pergunta["id"],
                "categoria": pergunta["categoria"],
                "tipo": pergunta["tipo"],
                "abordagem": abordagem,
                "modelo": MODELO,
                "pergunta": pergunta["pergunta"],
                "gabarito_verificado_em": gabarito["verificado_em"],
                "quando": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds"),
            } | responder(abordagem, pergunta)
            with arquivo.open("a", encoding="utf-8") as saida:
                saida.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
            if registro.get("erro"):
                print("ERRO — interrompido; rode de novo com o mesmo --rodada para retomar.")
                return arquivo
            print("ok" if registro["acertou"] else "errou", f"({registro['latencia_s']} s)")
            time.sleep(PAUSA_ENTRE_CHAMADAS)
    return arquivo


def placar(arquivo: Path) -> None:
    linhas = [json.loads(linha) for linha in arquivo.read_text(encoding="utf-8").splitlines()]
    validas = [d for d in linhas if not d.get("erro")]
    por = defaultdict(lambda: {"total": 0, "acertos": 0, "recusa_indevida": 0})
    for d in validas:
        for chave in ((d["categoria"], d["abordagem"]), ("Total", d["abordagem"])):
            por[chave]["total"] += 1
            por[chave]["acertos"] += d["acertou"]
            por[chave]["recusa_indevida"] += d["recusa_indevida"]

    print(f"\n{'Categoria':<10}{'Agente':>14}{'Baseline':>14}")
    for categoria in [*sorted({d["categoria"] for d in validas}), "Total"]:
        celulas = []
        for abordagem in ABORDAGENS:
            c = por[(categoria, abordagem)]
            celulas.append(f"{c['acertos']}/{c['total']}" if c["total"] else "—")
        print(f"{categoria:<10}{celulas[0]:>14}{celulas[1]:>14}")

    for abordagem in ABORDAGENS:
        c = por[("Total", abordagem)]
        latencias = sorted(d["latencia_s"] for d in validas if d["abordagem"] == abordagem)
        mediana = latencias[len(latencias) // 2] if latencias else 0
        print(f"\n{abordagem}: {c['recusa_indevida']} recusa(s) indevida(s), latência mediana {mediana} s")
    sem_lastro = [d["id"] for d in validas if d["abordagem"] == "agente" and d.get("sem_lastro")]
    print(f"agente: {len(sem_lastro)} resposta(s) com número sem lastro {sem_lastro or ''}")


def main() -> int:
    load_dotenv()
    # setdefault, e não atribuição: quem quiser reproduzir a rodada com
    # outro espaçamento (ou sem nenhum) manda pela variável de ambiente.
    os.environ.setdefault(ritmo.VARIAVEL, str(PAUSA_FERRAMENTA))
    parser = argparse.ArgumentParser(prog="python -m evaluation.benchmark")
    parser.add_argument("--rodada", default=datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d_%H%M"))
    parser.add_argument("--placar", type=Path)
    argumentos = parser.parse_args()
    if argumentos.placar:
        placar(argumentos.placar)
        return 0
    arquivo = rodar(argumentos.rodada)
    placar(arquivo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
