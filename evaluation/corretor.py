"""Corretor do benchmark: aplica os critérios de METODOLOGIA.md.

Compara quantidades, não texto. O agente recebe os valores já formatados
("R$ 7,44 Tri"); o baseline recebe números crus do SQL e pode escrever o
mesmo valor de vários jeitos corretos — "R$ 7,44 trilhões", "R$ 7.444,29
bilhões", "7.444.293.999.119". Um corretor que comparasse texto
reprovaria o baseline por formato, não por erro.

Regras (da metodologia, fixadas antes de rodar):
- o número vale no nível de arredondamento em que foi escrito; sem casa
  decimal, só se tiver ao menos 3 algarismos significativos ou se o valor
  certo for inteiro;
- taxa exige "%"; variação de taxa exige "pp" ou "pontos percentuais" —
  0,041 no lugar de 4,1% é erro, e 1,11% no lugar de 1,11 pp também.
"""

import re
import unicodedata
from dataclasses import dataclass, field

# número em formato brasileiro, seguido opcionalmente de escala ou unidade
_QUANTIDADE = re.compile(
    r"(-?\d{1,3}(?:\.\d{3})+(?:,\d+)?|-?\d+(?:,\d+)?)\s*"
    r"(%|p\.?\s?p\.?|pontos? percentua(?:l|is)|trilh(?:ao|oes)|tri\b|bilh(?:ao|oes)|bi\b"
    r"|milh(?:ao|oes)|mi\b|mil\b)?",
    re.IGNORECASE,
)

ESCALAS = {"tri": 1e12, "trilh": 1e12, "bi": 1e9, "bilh": 1e9, "mi": 1e6, "milh": 1e6, "mil": 1e3}

MARCAS_DE_RECUSA = (
    "nao posso", "nao possuo", "nao e possivel", "nao ha", "nao existe", "nao esta disponivel",
    "nao estao disponiveis", "nao dispoe", "nao consigo", "nao temos", "nao tenho", "nao contem",
    "nao contempla", "nao cobre", "nao permite", "nao inclui", "nao faz parte", "indisponivel",
    "fora do", "nao ha dados", "sem dados",
)


def sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


@dataclass(frozen=True)
class Quantidade:
    mantissa: float
    casas: int
    marcador: str  # "", "%", "pp" ou a escala ("tri", "bi"...)


def ler_quantidades(texto: str) -> list[Quantidade]:
    quantidades = []
    for numero, sufixo in _QUANTIDADE.findall(sem_acento(texto)):
        inteiro, _, decimal = numero.replace(".", "").partition(",")
        sufixo = sufixo.lower().replace(" ", "").replace(".", "")
        if sufixo == "%":
            marcador = "%"
        elif sufixo.startswith(("pp", "ponto")):
            marcador = "pp"
        else:
            marcador = next((e for e in ESCALAS if sufixo.startswith(e)), "")
        quantidades.append(Quantidade(float(f"{inteiro}.{decimal or 0}"), len(decimal), marcador))
    return quantidades


def _multiplicadores(unidade: str, marcador: str) -> float | None:
    """Quanto vale 1 unidade escrita, na escala do valor bruto do gabarito.
    None = essa forma de escrever não serve para essa unidade."""
    if unidade == "fracao":
        return 0.01 if marcador == "%" else None
    if unidade == "percentual":
        return 1.0 if marcador == "%" else None
    if unidade == "pp":
        return 1.0 if marcador == "pp" else None
    if unidade in ("reais", "reais_milhoes", "contagem"):
        if marcador in ("%", "pp"):
            return None
        return ESCALAS.get(marcador, 1.0)
    return 1.0 if marcador == "" else None


def contem_valor(texto: str, certo: float, unidade: str) -> bool:
    if unidade == "reais_milhoes":  # o gabarito guarda a série do SGS em R$ milhões
        certo, unidade = certo * 1e6, "reais"
    for q in ler_quantidades(texto):
        escala = _multiplicadores(unidade, q.marcador)
        if escala is None:
            continue
        alvo = certo / escala
        algarismos = len(str(int(abs(q.mantissa))).lstrip("0"))
        if q.casas == 0 and alvo != round(alvo) and algarismos < 3:
            continue  # "R$ 7 trilhões" não vale para 7,44; "R$ 233 bilhões" vale
        if round(alvo, q.casas) == round(q.mantissa, q.casas):
            return True
    return False


def recusou(texto: str) -> bool:
    return any(m in sem_acento(texto) for m in MARCAS_DE_RECUSA)


@dataclass
class Nota:
    acertou: bool
    recusa_indevida: bool = False
    faltou: list[str] = field(default_factory=list)


def corrigir(pergunta: dict, texto: str) -> Nota:
    """Aplica o critério do tipo da pergunta (METODOLOGIA.md)."""
    tipo = pergunta["tipo"]
    esperado = pergunta["esperado"]
    if tipo == "recusa":
        return Nota(acertou=recusou(texto))

    unidade = pergunta["unidade"]
    faltou: list[str] = []
    if tipo in ("valor", "valores"):
        alvos = esperado["brutos"]
    else:  # ranking: todos os nomes e o valor do primeiro colocado
        alvos = esperado["brutos"][:1]
        faltou += [n for n in esperado["nomes"] if sem_acento(n) not in sem_acento(texto)]
    faltou += [
        t for b, t in zip(alvos, esperado["texto"], strict=False) if not contem_valor(texto, b, unidade)
    ]
    acertou = not faltou
    return Nota(acertou=acertou, recusa_indevida=not acertou and recusou(texto), faltou=faltou)
