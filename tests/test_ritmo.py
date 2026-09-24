"""Testes do espaçamento de chamadas imposto pela cota gratuita.

O espaçamento existe para uma pergunta caber no teto de tokens por
minuto. Se ele ficar ligado por engano fora do benchmark, o agente fica
lento sem motivo; se o tempo dormido entrar na latência, o indicador do
benchmark mede cota em vez de modelo. Os dois riscos são testados aqui.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from agent import ritmo


@pytest.fixture(autouse=True)
def sem_dormir_de_verdade(monkeypatch):
    dormidas = []
    monkeypatch.setattr(ritmo.time, "sleep", dormidas.append)
    monkeypatch.delenv(ritmo.VARIAVEL, raising=False)
    ritmo.zerar()
    return dormidas


def test_desligado_por_padrao(sem_dormir_de_verdade):
    """Fora do benchmark o agente não pode ficar lento sem motivo."""
    ritmo.espacar()
    assert sem_dormir_de_verdade == []
    assert ritmo.dormido() == 0.0


def test_valor_invalido_na_variavel_nao_derruba_o_agente(monkeypatch):
    monkeypatch.setenv(ritmo.VARIAVEL, "vinte")
    assert ritmo.pausa() == 0.0


def test_valor_negativo_nao_vira_espera(monkeypatch):
    monkeypatch.setenv(ritmo.VARIAVEL, "-5")
    assert ritmo.pausa() == 0.0


def test_ligado_dorme_e_contabiliza(monkeypatch, sem_dormir_de_verdade):
    monkeypatch.setenv(ritmo.VARIAVEL, "20")
    ritmo.espacar()
    ritmo.espacar()
    assert sem_dormir_de_verdade == [20.0, 20.0]
    assert ritmo.dormido() == 40.0


def test_zerar_separa_uma_pergunta_da_seguinte(monkeypatch):
    """O runner desconta da latência o que dormiu naquela pergunta, só."""
    monkeypatch.setenv(ritmo.VARIAVEL, "20")
    ritmo.espacar()
    ritmo.zerar()
    assert ritmo.dormido() == 0.0
