"""Testes do corretor da avaliação do agente.

A avaliação em si consome cota do LLM e roda fora do pytest. O corretor,
não: um corretor com bug aprova resposta errada ou reprova resposta certa
sem dar sinal nenhum, então ele é testado com um agente falso.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from agent import avaliacao, catalogo
from agent.avaliacao import Caso, extrair_numeros, tem_lastro
from agent.catalogo import Catalogo, Medida
from agent.consultas import Resultado

TAXA = "Taxa de Inadimplência (SCR.data)"
SELIC = "Selic Meta (SGS)"

CONSULTA_TAXA = Resultado(linhas=[{TAXA: 0.041044414423335666}], dax="", medidas=[TAXA])
CONSULTA_RANKING = Resultado(
    linhas=[{"uf": "Maranhão", TAXA: 0.0756}], dax="", medidas=[TAXA], corte="uf"
)


@dataclass
class RespostaFalsa:
    texto: str
    consultas: list = field(default_factory=list)


def agente_que_responde(texto, consultas):
    class AgenteFalso:
        def perguntar(self, _pergunta):
            return RespostaFalsa(texto, consultas)

    return AgenteFalso


@pytest.fixture(autouse=True)
def sem_rede(monkeypatch):
    cat = Catalogo(
        medidas={
            n: Medida(nome=n, tabela="fato_credito", unidade=catalogo.UNIDADES[n])
            for n in (TAXA, SELIC, "Inadimplência BCB (SGS 21082)")
        }
    )
    monkeypatch.setattr(catalogo, "carregar", lambda: cat)
    monkeypatch.setattr(avaliacao.time, "sleep", lambda _: None)

    def gabarito_fixo(**argumentos):
        if argumentos.get("agrupar_por"):
            return CONSULTA_RANKING
        if argumentos["medidas"] == [SELIC]:
            return Resultado(linhas=[{SELIC: 15.0}], dax="", medidas=[SELIC])
        return CONSULTA_TAXA

    monkeypatch.setattr(avaliacao.consultas, "consultar", gabarito_fixo)


CASO_TAXA = Caso("taxa", ["Qual a taxa?"], {"medidas": [TAXA]})


def test_extrai_numeros_no_formato_brasileiro():
    assert extrair_numeros("R$ 2.588,2 Bi e 4,10%") == [(2588.2, 1), (4.10, 2)]


def test_competencia_com_hifen_nao_vira_numero_negativo():
    """ "2025-12" gerava um "-12" sem lastro em 9 respostas corretas."""
    assert extrair_numeros("competência 2025-12") == [(2025.0, 0), (12.0, 0)]
    assert extrair_numeros("variação de -0,10 pp") == [(-0.10, 2)]


def test_arredondar_valor_certificado_tem_lastro():
    assert tem_lastro(4.1, 1, {4.10})
    assert not tem_lastro(4.2, 1, {4.10})


def test_resposta_certa_arredondada_passa():
    v = avaliacao.avaliar(CASO_TAXA, agente_que_responde("A taxa é 4,1% em dez/2025.", [CONSULTA_TAXA]))
    assert v.passou, v


def test_valor_errado_reprova():
    v = avaliacao.avaliar(CASO_TAXA, agente_que_responde("A taxa é 3,9%.", [CONSULTA_TAXA]))
    assert v.acertou is False
    assert v.sem_lastro == ["3,9"]


def test_numero_principal_certo_com_secundario_inventado_reprova():
    """Acertar o principal não compensa inventar outro número."""
    texto = "A taxa é 4,10%, e em PF deve estar perto de 5,2%."
    v = avaliacao.avaliar(CASO_TAXA, agente_que_responde(texto, [CONSULTA_TAXA]))
    assert v.acertou is True
    assert v.sem_lastro == ["5,2"]
    assert not v.passou


def test_numero_certo_sem_consulta_reprova():
    """O valor certo de memória, sem consultar, também é falha de governança."""
    v = avaliacao.avaliar(CASO_TAXA, agente_que_responde("A taxa é 4,10%.", []))
    assert v.sem_lastro == ["4,10"]
    assert not v.passou


def test_inteiro_so_vale_quando_o_valor_certo_e_inteiro():
    caso_selic = Caso("selic", ["Selic?"], {"medidas": [SELIC]})
    consulta = Resultado(linhas=[{SELIC: 15.0}], dax="", medidas=[SELIC])
    assert avaliacao.avaliar(caso_selic, agente_que_responde("A Selic é 15%.", [consulta])).passou
    v = avaliacao.avaliar(CASO_TAXA, agente_que_responde("A taxa é de uns 4%.", [CONSULTA_TAXA]))
    assert v.acertou is False


def test_ranking_exige_o_nome_certo():
    caso = Caso("ranking", ["Qual UF?"], {"medidas": [TAXA], "agrupar_por": "uf", "limite": 1})
    certo = avaliacao.avaliar(caso, agente_que_responde("Maranhão, com 7,56%.", [CONSULTA_RANKING]))
    errado = avaliacao.avaliar(caso, agente_que_responde("Tocantins, com 7,56%.", [CONSULTA_RANKING]))
    assert certo.passou
    assert not errado.passou


def test_recusa_sem_numero_inventado_passa():
    caso = Caso("recusa", ["Qual banco?"], deve_recusar=True)
    texto = "Não há corte por instituição financeira no catálogo certificado."
    assert avaliacao.avaliar(caso, agente_que_responde(texto, [])).passou


@pytest.mark.parametrize(
    "texto",
    [
        # Recusas reais do agente (gemma-4-26b-a4b-it, 2026-09-18) que a
        # primeira versão do corretor reprovou por falta de marcador.
        "Não posso realizar previsões para o futuro, como a taxa para 2027.",
        "Não possuo dados detalhados por cidade (como Campinas).",
        'Não possuo uma medida de "taxa de juros média" por modalidade.',
    ],
)
def test_recusas_reais_do_agente_sao_reconhecidas(texto):
    caso = Caso("recusa", ["?"], deve_recusar=True)
    assert avaliacao.avaliar(caso, agente_que_responde(texto, [])).passou


def test_recusa_que_aproxima_um_numero_reprova():
    caso = Caso("recusa", ["Previsão 2027?"], deve_recusar=True)
    texto = "Não é possível prever, mas a tendência sugere algo perto de 5,3%."
    v = avaliacao.avaliar(caso, agente_que_responde(texto, []))
    assert v.recusou is True
    assert not v.passou


def test_resposta_que_nao_recusa_reprova():
    caso = Caso("recusa", ["Qual banco?"], deve_recusar=True)
    v = avaliacao.avaliar(caso, agente_que_responde("O Banco X lidera.", []))
    assert not v.passou


PF = "Taxa de Inadimplência PF"
PJ = "Taxa de Inadimplência PJ"


def agente_em_dois_turnos(primeiro, segundo):
    class AgenteFalso:
        def __init__(self):
            self.respostas = iter([primeiro, segundo])

        def perguntar(self, _pergunta):
            return next(self.respostas)

    return AgenteFalso


@pytest.fixture
def catalogo_pf_pj(monkeypatch):
    cat = Catalogo(
        medidas={n: Medida(nome=n, tabela="f", unidade="fracao") for n in (PF, PJ)}
    )
    monkeypatch.setattr(catalogo, "carregar", lambda: cat)
    monkeypatch.setattr(
        avaliacao.consultas,
        "consultar",
        lambda **_: Resultado(linhas=[{PJ: 0.0249}], dax="", medidas=[PJ]),
    )


CASO_CONTINUACAO = Caso("continuação", ["PF?", "E PJ?"], {"medidas": [PJ]})
CONSULTA_PF = Resultado(linhas=[{PF: 0.05145}], dax="pf", medidas=[PF])
CONSULTA_PJ = Resultado(linhas=[{PJ: 0.0249}], dax="pj", medidas=[PJ])


def test_numero_certificado_em_turno_anterior_tem_lastro(catalogo_pf_pj):
    """Regra ajustada em 2026-09-18 (ADR-015): citar de novo um valor já
    consultado nesta conversa é permitido."""
    agente = agente_em_dois_turnos(
        RespostaFalsa("PF é 5,15%.", [CONSULTA_PF]),
        RespostaFalsa("PJ é 2,49%, contra 5,15% em PF.", [CONSULTA_PJ]),
    )
    veredito = avaliacao.avaliar(CASO_CONTINUACAO, agente)
    assert veredito.passou, veredito
    assert veredito.consultas == ["pf", "pj"]


def test_numero_nunca_consultado_na_conversa_continua_reprovando(catalogo_pf_pj):
    """O ajuste não abre brecha: valor sem consulta em nenhum turno reprova."""
    agente = agente_em_dois_turnos(
        RespostaFalsa("PF é 5,15%.", [CONSULTA_PF]),
        RespostaFalsa("PJ é 2,49%, e a média do mercado é 3,80%.", [CONSULTA_PJ]),
    )
    veredito = avaliacao.avaliar(CASO_CONTINUACAO, agente)
    assert veredito.sem_lastro == ["3,80"]
    assert not veredito.passou


def test_codigo_de_serie_citado_nao_conta_como_inventado():
    v = avaliacao.avaliar(
        CASO_TAXA,
        agente_que_responde("A taxa é 4,10%, próxima da série SGS 21082.", [CONSULTA_TAXA]),
    )
    assert v.sem_lastro == []
