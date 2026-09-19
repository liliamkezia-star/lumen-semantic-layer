"""Testes do registro persistente de interações do agente."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from agent import agente, catalogo, registro
from agent.catalogo import Catalogo
from agent.consultas import Resultado


@pytest.fixture
def agente_offline(monkeypatch, tmp_path):
    """Agente real, com o modelo de linguagem e o Fabric substituídos."""
    monkeypatch.setattr(registro, "PASTA", tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "chave-de-teste")
    monkeypatch.setattr(catalogo, "carregar", lambda: Catalogo())
    return agente.Agente(modelo="modelo-de-teste")


def linhas_gravadas(pasta: Path) -> list[dict]:
    arquivos = list(pasta.glob("*.jsonl"))
    assert len(arquivos) == 1
    return [json.loads(linha) for linha in arquivos[0].read_text(encoding="utf-8").splitlines()]


def test_resposta_e_gravada_com_consulta_e_latencia(agente_offline, monkeypatch, tmp_path):
    consulta = Resultado(linhas=[{"x": 1}], dax="EVALUATE ROW(...)", medidas=["Carteira Ativa"])

    def responder(pergunta):
        agente.ferramentas.execucao.get().append(consulta)
        return SimpleNamespace(text="A carteira é R$ 7,44 Tri.")

    monkeypatch.setattr(agente_offline, "_tentar", responder)
    agente_offline.perguntar("Qual a carteira?")

    [linha] = linhas_gravadas(tmp_path)
    assert linha["pergunta"] == "Qual a carteira?"
    assert linha["modelo"] == "modelo-de-teste"
    assert linha["resposta"] == "A carteira é R$ 7,44 Tri."
    assert linha["consultas"] == [
        {"medidas": ["Carteira Ativa"], "corte": None, "linhas": 1, "dax": "EVALUATE ROW(...)"}
    ]
    assert linha["latencia_s"] >= 0
    assert linha["erro"] == ""


def test_falha_tambem_e_gravada_e_o_erro_propaga(agente_offline, monkeypatch, tmp_path):
    def falhar(pergunta):
        raise agente.ModelosIndisponiveis("cota esgotada")

    monkeypatch.setattr(agente_offline, "_tentar", falhar)
    with pytest.raises(agente.ModelosIndisponiveis):
        agente_offline.perguntar("Qual a taxa?")

    [linha] = linhas_gravadas(tmp_path)
    assert linha["pergunta"] == "Qual a taxa?"
    assert linha["erro"] == "ModelosIndisponiveis: cota esgotada"
    assert linha["resposta"] == ""


def test_perguntas_do_mesmo_dia_vao_para_o_mesmo_arquivo(agente_offline, monkeypatch, tmp_path):
    monkeypatch.setattr(agente_offline, "_tentar", lambda p: SimpleNamespace(text="ok"))
    agente_offline.perguntar("primeira")
    agente_offline.perguntar("segunda")
    assert [linha["pergunta"] for linha in linhas_gravadas(tmp_path)] == ["primeira", "segunda"]
