"""Testes da renovação do token do Entra ID usado para consultar o modelo."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from agent import fabric


@pytest.fixture
def relogio(monkeypatch):
    agora = {"t": 1_000_000.0}
    pedidos = []

    def pedir():
        pedidos.append(agora["t"])
        return {"access_token": f"token-{len(pedidos)}", "expires_in": 3600}

    monkeypatch.setattr(fabric.time, "time", lambda: agora["t"])
    monkeypatch.setattr(fabric, "_pedir_token", pedir)
    monkeypatch.setattr(fabric, "_cache_token", {})
    return agora, pedidos


def test_token_e_reaproveitado_enquanto_valido(relogio):
    agora, pedidos = relogio
    assert fabric._token() == "token-1"
    agora["t"] += 1800
    assert fabric._token() == "token-1"
    assert len(pedidos) == 1


def test_token_e_renovado_antes_de_vencer(relogio):
    """A primeira versão guardava o token para sempre; uma rodada de mais
    de uma hora passava a falhar com 'token expirado'."""
    agora, pedidos = relogio
    fabric._token()
    agora["t"] += 3600 - fabric.MARGEM_RENOVACAO_S + 1
    assert fabric._token() == "token-2"
    assert len(pedidos) == 2
