"""Testes do corretor do benchmark: os critérios de METODOLOGIA.md."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from evaluation.corretor import contem_valor, corrigir

CARTEIRA = 7444293999119.219


@pytest.mark.parametrize(
    "texto",
    [
        "A carteira era de R$ 7,44 Tri.",
        "A carteira era de R$ 7,44 trilhões.",
        "A carteira somava R$ 7,4 trilhões.",
        "R$ 7.444,29 bilhões",
        "R$ 7.444.293.999.119,22",
        "cerca de 7.444.294 milhões de reais",
    ],
)
def test_o_mesmo_valor_escrito_de_jeitos_diferentes_e_aceito(texto):
    assert contem_valor(texto, CARTEIRA, "reais")


@pytest.mark.parametrize(
    "texto",
    [
        "R$ 7 trilhões",  # sem decimal, e o valor certo não é inteiro
        "R$ 7,14 trilhões",  # é o saldo do SGS, não a carteira do SCR
        "R$ 89,3 trilhões",  # soma dos 12 meses: a pegadinha da semiaditividade
    ],
)
def test_valor_errado_ou_impreciso_demais_e_reprovado(texto):
    assert not contem_valor(texto, CARTEIRA, "reais")


def test_sem_decimal_vale_com_tres_algarismos_significativos():
    vencida = 232541033339.08
    assert contem_valor("R$ 233 bilhões", vencida, "reais")
    assert not contem_valor("R$ 232 bilhões", vencida, "reais")  # arredondou errado
    assert contem_valor("928,6 milhões", 928619478, "contagem")
    assert not contem_valor("928 milhões", 928619478, "contagem")  # 928,6 arredonda para 929


def test_taxa_exige_percentual():
    assert contem_valor("a taxa era 4,10%", 0.041044, "fracao")
    assert contem_valor("a taxa era 4,1 %", 0.041044, "fracao")
    assert not contem_valor("a taxa era 0,041", 0.041044, "fracao")


def test_variacao_de_taxa_exige_pontos_percentuais():
    assert contem_valor("subiu 1,11 pp", 1.1134, "pp")
    assert contem_valor("subiu 1,1 ponto percentual", 1.1134, "pp")
    assert contem_valor("alta de 1,11 p.p.", 1.1134, "pp")
    assert not contem_valor("subiu 1,11%", 1.1134, "pp")


def test_percentual_ja_em_percentual_nao_e_multiplicado():
    assert contem_valor("Selic de 15%", 15.0, "percentual")
    assert contem_valor("crédito/PIB de 56,02%", 56.02, "percentual")


def test_serie_em_milhoes_aceita_bilhoes():
    assert contem_valor("R$ 407,48 bilhões", 407477.0, "reais_milhoes")
    assert contem_valor("R$ 407.477 milhões", 407477.0, "reais_milhoes")


def test_contagem_aceita_escala():
    assert contem_valor("928.619.478 operações", 928619478, "contagem")
    assert contem_valor("928,6 milhões de operações", 928619478, "contagem")


def _pergunta(tipo, brutos=(), texto=(), nomes=(), unidade="fracao"):
    return {
        "tipo": tipo,
        "unidade": unidade,
        "esperado": {"brutos": list(brutos), "texto": list(texto), "nomes": list(nomes)},
    }


def test_ranking_exige_todos_os_nomes_e_o_valor_do_primeiro():
    p = _pergunta("ranking", [0.0756, 0.0719], ["7,56%", "7,19%"], ["Maranhão", "Tocantins"])
    assert corrigir(p, "Maranhão (7,56%) e Tocantins (7,19%)").acertou
    assert corrigir(p, "Maranhao lidera com 7,6%, seguido de Tocantins").acertou
    assert not corrigir(p, "Maranhão, com 7,56%").acertou


def test_valores_exige_todos():
    p = _pergunta("valores", [0.0515, 0.0249], ["5,15%", "2,49%"])
    assert corrigir(p, "PF 5,15% e PJ 2,49%").acertou
    assert not corrigir(p, "PF 5,15%").acertou


def test_recusa_e_recusa_indevida():
    recusa = _pergunta("recusa")
    assert corrigir(recusa, "Não há dados por instituição individual.").acertou
    assert not corrigir(recusa, "O Banco do Brasil tem 3,2%.").acertou

    respondivel = _pergunta("valor", [0.041], ["4,10%"])
    nota = corrigir(respondivel, "Não é possível responder com os dados disponíveis.")
    assert not nota.acertou and nota.recusa_indevida
