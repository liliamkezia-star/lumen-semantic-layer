"""Duelo ao vivo: a mesma pergunta para as duas abordagens, lado a lado.

Rodar com:
    python -m evaluation.duelo --id D04
    python -m evaluation.duelo "Qual era a carteira de credito ativa em dezembro de 2025?"

Existe para ser gravado. O benchmark completo produz um número; este
comando mostra o número acontecendo — a pergunta, a resposta de cada
lado, e principalmente **a consulta que cada um rodou**, que é onde o
erro de fonte fica visível a olho nu.

Com `--id`, usa uma das 60 perguntas do gabarito congelado e sabe a
resposta certa, então fecha com o veredito. Sem `--id`, aceita qualquer
pergunta e só mostra os dois lados.

Consome cota da API: duas respostas por execução.
"""

import argparse
import json
import os
import sys
import textwrap
import time
from pathlib import Path

from dotenv import load_dotenv

from agent import ritmo
from agent.agente import Agente, ModelosIndisponiveis
from evaluation.baseline_text2sql import MODELO, BaselineTextToSql

GABARITO = Path(__file__).parent / "gabarito_congelado.json"

# O teto da cota gratuita é de tokens de entrada por minuto, e uma
# pergunta com várias consultas o estoura sozinha (ver agent/ritmo.py).
PAUSA_FERRAMENTA = 20  # s

LARGURA = 78

# Cor no terminal deixa a gravação legível; sem cor, continua funcionando.
COR = {
    "titulo": "\033[1;97m",
    "agente": "\033[1;36m",
    "baseline": "\033[1;33m",
    "certo": "\033[1;32m",
    "errado": "\033[1;31m",
    "fraco": "\033[90m",
    "fim": "\033[0m",
}


def pintar(texto: str, cor: str) -> str:
    if os.getenv("NO_COLOR") or not sys.stdout.isatty():
        return texto
    return f"{COR[cor]}{texto}{COR['fim']}"


def regua(rotulo: str = "", cor: str = "fraco") -> None:
    if not rotulo:
        print(pintar("─" * LARGURA, cor))
        return
    enchimento = "─" * max(LARGURA - len(rotulo) - 3, 0)
    print(pintar(f"── {rotulo} {enchimento}", cor))


def paragrafo(texto: str, recuo: str = "  ") -> None:
    for linha in texto.strip().splitlines():
        if not linha.strip():
            print()
            continue
        print(textwrap.fill(linha.strip(), width=LARGURA, initial_indent=recuo, subsequent_indent=recuo))


def mostrar_consulta(consulta: str) -> None:
    """Quebra linhas longas: o DAX sai em uma linha só e, numa gravação,
    o que estoura a largura do terminal some do vídeo."""
    for linha in str(consulta).strip().splitlines():
        pedacos = textwrap.wrap(linha.rstrip(), width=LARGURA - 6) or [""]
        for i, pedaco in enumerate(pedacos):
            print(pintar(("    " if i == 0 else "      ") + pedaco, "fraco"))


def perguntar(nome: str, construtor, pergunta: str) -> tuple[str, list, float]:
    """Faz a pergunta, cronometrando só o tempo de modelo."""
    cor = "agente" if nome == "agente" else "baseline"
    print()
    regua(nome.upper(), cor)
    print(pintar("  pensando...", "fraco"), end="", flush=True)

    ritmo.zerar()
    inicio = time.monotonic()
    try:
        resposta = construtor().perguntar(pergunta)
    except ModelosIndisponiveis as erro:
        print("\r" + " " * 40)
        print(pintar(f"  cota esgotada: {erro}", "errado"))
        return "", [], 0.0
    # A espera imposta pela cota não é tempo de modelo.
    latencia = time.monotonic() - inicio - ritmo.dormido()
    print("\r" + " " * 40 + "\r", end="")

    print()
    paragrafo(resposta.texto)
    consultas = [getattr(c, "dax", c) for c in resposta.consultas]
    print()
    if consultas:
        rotulo = "DAX montado pelo código" if nome == "agente" else "SQL escrito pelo modelo"
        print(pintar(f"  {rotulo}:", "fraco"))
        for consulta in consultas:
            mostrar_consulta(consulta)
    else:
        print(pintar("  nenhuma consulta: respondeu sem ir ao banco", "fraco"))
    print()
    print(pintar(f"  {latencia:.0f}s", "fraco"))
    return resposta.texto, consultas, latencia


def carregar_do_gabarito(identificador: str) -> dict:
    dados = json.loads(GABARITO.read_text(encoding="utf-8"))
    for questao in dados["perguntas"]:
        if questao["id"].upper() == identificador.upper():
            return questao
    disponiveis = ", ".join(q["id"] for q in dados["perguntas"])
    raise SystemExit(f"id nao encontrado. Use um destes:\n{disponiveis}")


def esperado_em_texto(questao: dict) -> str:
    esperado = questao["esperado"]
    if esperado.get("recusa"):
        return "recusar a pergunta"
    return " · ".join(esperado.get("texto") or esperado.get("nomes") or ["?"])


def main() -> int:
    load_dotenv()
    os.environ.setdefault(ritmo.VARIAVEL, str(PAUSA_FERRAMENTA))

    analisador = argparse.ArgumentParser(prog="python -m evaluation.duelo")
    analisador.add_argument("pergunta", nargs="?", help="pergunta livre, entre aspas")
    analisador.add_argument("--id", dest="identificador", help="id do gabarito, ex.: D04")
    analisador.add_argument(
        "--pausa",
        action="store_true",
        help="espera Enter entre um lado e outro (util para gravar)",
    )
    argumentos = analisador.parse_args()

    questao = None
    if argumentos.identificador:
        questao = carregar_do_gabarito(argumentos.identificador)
        pergunta = questao["pergunta"]
    elif argumentos.pergunta:
        pergunta = argumentos.pergunta
    else:
        analisador.error("informe uma pergunta ou --id")

    print()
    regua()
    print(pintar(textwrap.fill(pergunta, width=LARGURA), "titulo"))
    if questao:
        print(pintar(f"  resposta certa: {esperado_em_texto(questao)}", "fraco"))
    regua()

    perguntar("agente", lambda: Agente(modelo=MODELO), pergunta)
    if argumentos.pausa:
        input(pintar("\n  [Enter para o text-to-SQL]", "fraco"))
    perguntar("baseline", lambda: BaselineTextToSql(modelo=MODELO), pergunta)

    print()
    regua()
    if questao:
        print(pintar(f"  resposta certa: {esperado_em_texto(questao)}", "titulo"))
    print(pintar(f"  mesmo modelo nos dois lados: {MODELO}", "fraco"))
    regua()
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
