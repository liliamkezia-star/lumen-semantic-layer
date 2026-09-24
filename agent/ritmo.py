"""Espaçamento entre as chamadas de ferramenta, para caber na cota gratuita.

O nível gratuito do Gemma limita **tokens de entrada por minuto** (16.000
no `gemma-4-26b`), e não só requisições por dia. Uma única pergunta pode
estourar esse teto sozinha: cada chamada com ferramenta reenvia a
conversa inteira, então um resultado gordo — um catálogo de séries com
17 mil caracteres, no caso que motivou este módulo — encarece todas as
chamadas seguintes. Esperar e repetir a pergunta não adianta: o estouro
se repete dentro do minuto seguinte, de forma determinística.

A saída é espaçar as chamadas **dentro** da pergunta. Isso não muda
nenhuma resposta: muda só o relógio. Por isso o tempo dormido é
contabilizado à parte — quem mede latência desconta essa espera e
continua medindo tempo de modelo, não tempo de cota.

Desligado por padrão. O benchmark liga via `LUMEN_PAUSA_FERRAMENTA`
(segundos), para que as duas abordagens corram sob a mesma regra.

O acumulador é um float de módulo, não um ContextVar: quem dorme é a
ferramenta, quem lê é o runner, e escrita feita dentro do contexto da
ferramenta não volta para o contexto de quem chamou.
"""

import os
import time

VARIAVEL = "LUMEN_PAUSA_FERRAMENTA"

_dormido = 0.0


def pausa() -> float:
    """Segundos de espera configurados. 0 (padrão) desliga o espaçamento."""
    try:
        return max(float(os.getenv(VARIAVEL, "0")), 0.0)
    except ValueError:
        return 0.0


def zerar() -> None:
    global _dormido
    _dormido = 0.0


def dormido() -> float:
    """Total já dormido por causa da cota desde o último `zerar()`."""
    return _dormido


def espacar() -> None:
    """Chamada no início de cada ferramenta, entre duas chamadas ao modelo."""
    global _dormido
    segundos = pausa()
    if not segundos:
        return
    time.sleep(segundos)
    _dormido += segundos
