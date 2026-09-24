"""Avaliação do agente contra respostas conhecidas (ADR-015).

Rodar com:  python -m agent.avaliacao

Consome cota da API do modelo de linguagem, por isso não faz parte do
pytest. Mede três coisas:

1. Acerto: a resposta traz o valor (e, em ranking, o nome) certo.
2. Recusa: pergunta fora do catálogo é recusada, não aproximada.
3. Lastro: todo número escrito na resposta aparece nos resultados das
   consultas feitas naquela conversa. É a regra central do agente medida
   diretamente — acertar o número principal e inventar um secundário
   ainda é falha de governança. (Até 2026-09-18 o lastro valia só para o
   turno; ver ADR-015, "Ajuste da regra de lastro".)

O gabarito não é escrito à mão: é calculado na hora pela própria camada
certificada. Um "4,10%" fixo aqui quebraria no dia em que a Gold ganhar
uma competência nova — a mesma armadilha das datas fixas das ADR-010,
011 e 014.
"""

from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from . import catalogo, consultas
from .ferramentas import formatar

PAUSA_ENTRE_TURNOS = 6  # segundos; o nível gratuito limita requisições por minuto
# O limite que interrompia as rodadas era por minuto, não por dia (medido:
# a cota esgotava sempre após ~3 casos e voltava minutos depois). Então,
# ao esgotar, espera a janela virar e repete o caso, em vez de abortar.
ESPERA_POR_COTA = 70  # segundos
TENTATIVAS_POR_COTA = 6
RESULTADOS = Path(__file__).parent / "avaliacao_resultados"

TAXA = "Taxa de Inadimplência (SCR.data)"


@dataclass
class Caso:
    nome: str
    perguntas: list[str]  # mais de uma = conversa; só a última é avaliada
    gabarito: dict[str, Any] | None = None  # argumentos de consultas.consultar
    deve_recusar: bool = False


CASOS = [
    Caso("taxa mais recente", ["Qual a taxa de inadimplência mais recente?"],
         {"medidas": [TAXA]}),
    Caso("carteira ativa", ["Qual o tamanho da carteira de crédito ativa hoje?"],
         {"medidas": ["Carteira Ativa"]}),
    Caso("inadimplência PF", ["Qual a taxa de inadimplência de pessoa física?"],
         {"medidas": ["Taxa de Inadimplência PF"]}),
    Caso("continuação para PJ",
         ["Qual a taxa de inadimplência de pessoa física?", "E de pessoa jurídica?"],
         {"medidas": ["Taxa de Inadimplência PJ"]}),
    Caso("variação anual", ["Quanto a taxa de inadimplência subiu em relação a um ano antes?"],
         {"medidas": ["Taxa de Inadimplência Δpp a/a"]}),
    Caso("competência histórica", ["Qual era a taxa de inadimplência em dezembro de 2020?"],
         {"medidas": [TAXA], "filtros": {"competencia": "2020-12"}}),
    Caso("filtro por UF", ["Qual a taxa de inadimplência em São Paulo?"],
         {"medidas": [TAXA], "filtros": {"uf": "São Paulo"}}),
    Caso("ranking de UF", ["Qual UF tem a maior taxa de inadimplência?"],
         {"medidas": [TAXA], "agrupar_por": "uf", "limite": 1}),
    Caso("ranking de região", ["Qual região tem a menor taxa de inadimplência?"],
         {"medidas": [TAXA], "agrupar_por": "regiao", "descendente": False, "limite": 1}),
    Caso("ranking de modalidade", ["Qual modalidade de crédito tem a maior carteira?"],
         {"medidas": ["Carteira Ativa"], "agrupar_por": "modalidade", "limite": 1}),
    Caso("referência do BCB", ["Qual a taxa de inadimplência oficial do Banco Central?"],
         {"medidas": ["Inadimplência BCB (SGS 21082)"]}),
    Caso("macro", ["Qual a Selic meta mais recente?"],
         {"medidas": ["Selic Meta (SGS)"]}),
    Caso("recusa: banco", ["Qual banco tem a maior inadimplência?"], deve_recusar=True),
    Caso("recusa: previsão", ["Qual será a taxa de inadimplência em 2027?"], deve_recusar=True),
    Caso("recusa: município", ["Qual a inadimplência em Campinas?"], deve_recusar=True),
    Caso("recusa: juros", ["Qual a taxa de juros média do cheque especial?"], deve_recusar=True),
]

MARCAS_DE_RECUSA = (
    "nao posso", "nao possuo",  # faltavam: reprovaram três recusas corretas na 1ª rodada
    "nao e possivel", "nao ha", "nao existe", "nao esta disponivel", "nao estao disponiveis",
    "nao dispoe", "nao consigo", "nao temos", "nao tenho", "nao possui", "nao contempla",
    "nao cobre", "nao permite", "nao inclui", "nao faz parte", "indisponivel", "fora do",
)

# Hífen colado a dígito não é sinal de menos: "2025-12" é uma competência,
# não "2025" e "-12" (falso "número sem lastro" em 9 respostas do benchmark).
_NUMERO = re.compile(r"(?:(?<!\d)-)?\d{1,3}(?:\.\d{3})+(?:,\d+)?|(?:(?<!\d)-)?\d+(?:,\d+)?")


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


def extrair_numeros(texto: str) -> list[tuple[float, int]]:
    """Números em formato brasileiro, com a quantidade de casas decimais
    escrita — é ela que define quanto arredondamento é aceitável."""
    numeros = []
    for bruto in _NUMERO.findall(texto):
        inteiro, _, decimal = bruto.replace(".", "").partition(",")
        numeros.append((float(f"{inteiro}.{decimal or 0}"), len(decimal)))
    return numeros


def e_irrelevante(valor: float, casas: int) -> bool:
    """Números que não são afirmações sobre o dado: anos, dias e meses de
    uma data, posições de ranking, quantidades pequenas ("as 5 UFs")."""
    if casas:
        return False
    return 0 <= valor <= 31 or 1990 <= valor <= 2100


def tem_lastro(valor: float, casas: int, lastro: set[float]) -> bool:
    """Arredondar um valor certificado é permitido; inventar, não."""
    return any(round(certo, casas) == round(valor, casas) for certo in lastro)


def lastro_da_conversa(resultados: list[consultas.Resultado]) -> set[float]:
    cat = catalogo.carregar()
    lastro: set[float] = set()
    # Números em nomes e descrições de medida são identificadores ("SGS
    # 21082", "SGS 433"), não afirmações sobre o dado — citar um não é
    # inventar. Descrições não podem conter valores de dado (o catálogo as
    # omite do prompt: ver catalogo._descricao_para_agente).
    for medida in cat.medidas.values():
        for texto in (medida.nome, medida.descricao):
            lastro.update(n for n, _ in extrair_numeros(texto))
    for resultado in resultados:
        for linha in resultado.linhas:
            for chave, valor in linha.items():
                medida = cat.medidas.get(chave)
                texto = formatar(valor, medida.unidade) if medida else str(valor)
                lastro.update(n for n, _ in extrair_numeros(texto))
                if isinstance(valor, (int, float)) and not isinstance(valor, bool):
                    lastro.add(float(valor))
    return lastro


def gabarito(caso: Caso) -> tuple[list[str], list[float]]:
    """Nomes e números que a resposta precisa conter, calculados agora."""
    assert caso.gabarito is not None
    resultado = consultas.consultar(**caso.gabarito)
    linha = resultado.linhas[0]
    medida = catalogo.carregar().medidas[resultado.medidas[0]]
    valor = formatar(linha[medida.nome], medida.unidade)
    nomes = [str(linha[resultado.corte])] if resultado.corte else []
    return nomes, [n for n, _ in extrair_numeros(valor)]


@dataclass
class Veredito:
    caso: str
    pergunta: str
    resposta: str = ""
    esperado: str = ""
    acertou: bool | None = None
    recusou: bool | None = None
    sem_lastro: list[str] = field(default_factory=list)
    consultas: list[str] = field(default_factory=list)
    # A cadeia de reserva pode responder com um modelo diferente a cada
    # caso; sem isto, um placar misturando modelos pareceria de um só.
    modelo: str = ""
    erro: str = ""

    @property
    def passou(self) -> bool:
        if self.erro:
            return False
        principal = self.recusou if self.acertou is None else self.acertou
        return bool(principal) and not self.sem_lastro


def avaliar(caso: Caso, agente_novo) -> Veredito:
    veredito = Veredito(caso=caso.nome, pergunta=caso.perguntas[-1])
    agente = agente_novo()
    da_conversa: list[consultas.Resultado] = []
    for pergunta in caso.perguntas:
        resposta = agente.perguntar(pergunta)
        da_conversa.extend(resposta.consultas)
        time.sleep(PAUSA_ENTRE_TURNOS)
    veredito.resposta = resposta.texto
    veredito.consultas = [r.dax for r in da_conversa]
    veredito.modelo = getattr(agente, "modelo_em_uso", "")

    lastro = lastro_da_conversa(da_conversa)
    veredito.sem_lastro = [
        f"{v:.{c}f}".replace(".", ",")
        for v, c in extrair_numeros(resposta.texto)
        if not e_irrelevante(v, c) and not tem_lastro(v, c, lastro)
    ]

    if caso.deve_recusar:
        veredito.recusou = any(m in _sem_acento(resposta.texto) for m in MARCAS_DE_RECUSA)
        veredito.esperado = "recusa"
        return veredito

    nomes, numeros = gabarito(caso)
    veredito.esperado = " / ".join([*nomes, *(str(n).replace(".", ",") for n in numeros)])
    escritos = extrair_numeros(resposta.texto)
    tem_nomes = all(_sem_acento(n) in _sem_acento(resposta.texto) for n in nomes)
    # Sem casa decimal só vale se o valor certo for inteiro: "15%" para a
    # Selic de 15,00 é correto, "7" para 7,44 não é.
    tem_numeros = all(
        any(
            (c >= 1 or certo == round(certo)) and round(certo, c) == round(v, c)
            for v, c in escritos
        )
        for certo in numeros
    )
    veredito.acertou = tem_nomes and tem_numeros
    return veredito


def main() -> int:
    """Uso: python -m agent.avaliacao [a_partir_do_caso] [--modelo NOME]

    O número opcional retoma a partir de um caso (contando de 1). A cota
    gratuita da API costuma acabar no meio da rodada; repetir os casos que
    já passaram só gasta a cota que falta para os outros.

    `--modelo` fixa um único modelo, sem cadeia de reserva. É o modo certo
    para medir: um placar em que cada caso foi respondido por um modelo
    diferente não mede modelo nenhum.
    """
    import argparse

    from .agente import Agente, ModelosIndisponiveis

    parser = argparse.ArgumentParser(prog="python -m agent.avaliacao")
    parser.add_argument("inicio", nargs="?", type=int, default=1)
    parser.add_argument("--ate", type=int, default=len(CASOS), help="último caso a rodar")
    parser.add_argument("--modelo", default=None)
    argumentos = parser.parse_args()
    inicio = argumentos.inicio
    fim = argumentos.ate
    modelo_fixo = argumentos.modelo

    def novo_agente() -> Agente:
        return Agente(modelo=modelo_fixo)
    vereditos: list[Veredito] = []
    for indice, caso in enumerate(CASOS, start=1):
        if indice < inicio:
            continue
        if indice > fim:
            break
        print(f"[{indice:>2}/{len(CASOS)}] {caso.nome} ...", end=" ", flush=True)
        veredito = None
        for tentativa in range(1, TENTATIVAS_POR_COTA + 1):
            try:
                veredito = avaliar(caso, novo_agente)
                break
            except ModelosIndisponiveis as erro:
                ultimo_erro = str(erro)
                if tentativa < TENTATIVAS_POR_COTA:
                    print(f"(sem cota, aguardando {ESPERA_POR_COTA}s)", end=" ", flush=True)
                    time.sleep(ESPERA_POR_COTA)
        if veredito is None:
            print("interrompido: nenhum modelo disponível mesmo após esperar.")
            vereditos.append(
                Veredito(caso=caso.nome, pergunta=caso.perguntas[-1], erro=ultimo_erro)
            )
            break
        vereditos.append(veredito)
        detalhe = f" (sem lastro: {', '.join(veredito.sem_lastro)})" if veredito.sem_lastro else ""
        print(("ok" if veredito.passou else "FALHOU") + f" [{veredito.modelo}]" + detalhe)

    executados = [v for v in vereditos if not v.erro]
    aprovados = sum(v.passou for v in executados)
    pedidos = fim - inicio + 1
    print(f"\n{aprovados}/{len(executados)} casos aprovados", end="")
    if len(executados) < pedidos:
        faltam = inicio + len(executados)
        sufixo = f" --modelo {modelo_fixo}" if modelo_fixo else ""
        print(
            f" ({pedidos - len(executados)} não executados — retome com: "
            f"python -m agent.avaliacao {faltam}{sufixo})",
            end="",
        )
    print()

    RESULTADOS.mkdir(exist_ok=True)
    quando = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d_%H%M")
    arquivo = RESULTADOS / f"{quando}.json"
    arquivo.write_text(
        json.dumps([asdict(v) | {"passou": v.passou} for v in vereditos], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Relatório completo, com as respostas para revisão: {arquivo}")
    return 0 if aprovados == pedidos else 1


if __name__ == "__main__":
    sys.exit(main())
