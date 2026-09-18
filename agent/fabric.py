"""Transporte: autenticação e execução de DAX contra o modelo semântico.

Esta camada não sabe nada sobre governança — ela só executa o DAX que
recebe. Quem garante que o DAX é legítimo é `consultas.py`, que é o
único lugar do projeto autorizado a montá-lo. Nada fora dali deve
chamar `executar_dax` com uma string vinda do modelo de linguagem.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import requests
import yaml

ESCOPO = "https://analysis.windows.net/powerbi/api/.default"
API = "https://api.powerbi.com/v1.0/myorg"
WORKSPACE = os.getenv("LUMEN_WORKSPACE", "lumen-dev")
MODELO = os.getenv("LUMEN_MODELO", "lumen_semantico")
PROFILES = Path.home() / ".dbt" / "profiles.yml"


class ErroFabric(RuntimeError):
    """Falha de autenticação, permissão ou execução no lado do Fabric."""


def _credenciais() -> dict[str, str]:
    """Lê o SPN das variáveis de ambiente ou, na ausência delas, do
    profiles.yml do dbt — a mesma identidade do ADR-008, nunca uma nova.
    """
    do_ambiente = {
        "tenant_id": os.getenv("FABRIC_TENANT_ID"),
        "client_id": os.getenv("FABRIC_CLIENT_ID"),
        "client_secret": os.getenv("FABRIC_CLIENT_SECRET"),
    }
    if all(do_ambiente.values()):
        return do_ambiente  # type: ignore[return-value]

    if not PROFILES.exists():
        raise ErroFabric(
            "Sem credenciais: defina FABRIC_TENANT_ID, FABRIC_CLIENT_ID e "
            f"FABRIC_CLIENT_SECRET, ou mantenha o {PROFILES} do dbt."
        )
    perfil = yaml.safe_load(PROFILES.read_text(encoding="utf-8"))
    fabric = perfil["lumen"]["outputs"]["fabric"]
    return {
        "tenant_id": fabric["tenant_id"],
        "client_id": fabric["client_id"],
        "client_secret": fabric["client_secret"],
    }


@lru_cache(maxsize=1)
def _token() -> str:
    cred = _credenciais()
    resposta = requests.post(
        f"https://login.microsoftonline.com/{cred['tenant_id']}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": cred["client_id"],
            "client_secret": cred["client_secret"],
            "scope": ESCOPO,
        },
        timeout=30,
    )
    if not resposta.ok:
        raise ErroFabric(
            "Falha ao obter token do Entra ID. Se o secret do SPN venceu "
            "(ver ADR-008), renove-o no App Registration. "
            f"Detalhe: {resposta.text[:300]}"
        )
    return resposta.json()["access_token"]


def _cabecalhos() -> dict[str, str]:
    return {"Authorization": f"Bearer {_token()}"}


@lru_cache(maxsize=1)
def _ids() -> tuple[str, str]:
    """Resolve workspace e modelo por nome, para não fixar GUIDs no código."""
    grupos = requests.get(f"{API}/groups", headers=_cabecalhos(), timeout=30)
    if not grupos.ok:
        raise ErroFabric(f"Não consegui listar workspaces: {grupos.text[:200]}")
    workspace = next(
        (g["id"] for g in grupos.json()["value"] if g["name"] == WORKSPACE), None
    )
    if workspace is None:
        raise ErroFabric(f"Workspace '{WORKSPACE}' não encontrado para este SPN.")

    modelos = requests.get(
        f"{API}/groups/{workspace}/datasets", headers=_cabecalhos(), timeout=30
    )
    modelo = next(
        (d["id"] for d in modelos.json()["value"] if d["name"] == MODELO), None
    )
    if modelo is None:
        raise ErroFabric(f"Modelo semântico '{MODELO}' não encontrado no workspace.")
    return workspace, modelo


def executar_dax(consulta: str) -> list[dict[str, Any]]:
    """Executa uma consulta DAX e devolve as linhas como dicionários."""
    workspace, modelo = _ids()
    resposta = requests.post(
        f"{API}/groups/{workspace}/datasets/{modelo}/executeQueries",
        headers=_cabecalhos(),
        json={"queries": [{"query": consulta}], "serializerSettings": {"includeNulls": True}},
        timeout=120,
    )
    if resposta.status_code == 401:
        raise ErroFabric(
            "401 no executeQueries. A causa conhecida é a conexão do modelo "
            "voltar a usar SSO — entidade de serviço não é suportada nesse "
            "modo (ver ADR-015). Verifique o vínculo do modelo com a conexão "
            "de identidade fixa."
        )
    if not resposta.ok:
        raise ErroFabric(f"HTTP {resposta.status_code}: {resposta.text[:400]}")

    resultado = resposta.json()["results"][0]
    if "error" in resultado and resultado["error"]:
        raise ErroFabric(f"DAX rejeitado pelo modelo: {resultado['error']}")
    return resultado["tables"][0]["rows"]
