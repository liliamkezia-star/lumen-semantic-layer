"""Consulta SQL direta à Gold, pelo SQL endpoint do Lakehouse no Fabric.

Mesma identidade do dbt e do agente (SPN do ADR-008). Exige o driver
"ODBC Driver 18 for SQL Server", que aceita autenticação por entidade de
serviço.
"""

import os
from functools import lru_cache
from typing import Any

import pyodbc

from agent.fabric import _credenciais

SERVIDOR = os.getenv(
    "LUMEN_SQL_ENDPOINT",
    "cmvdgdohzmjexd4hmjjhdnunvm-bu3dkn66jvnu5hnwqck6b7qpwy.datawarehouse.fabric.microsoft.com",
)
BANCO = os.getenv("LUMEN_LAKEHOUSE", "lumen_lakehouse")


@lru_cache(maxsize=1)
def _conexao() -> pyodbc.Connection:
    cred = _credenciais()
    return pyodbc.connect(
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={SERVIDOR},1433;Database={BANCO};"
        "Encrypt=yes;TrustServerCertificate=no;"
        "Authentication=ActiveDirectoryServicePrincipal;"
        f"UID={cred['client_id']};PWD={cred['client_secret']};",
        timeout=60,
    )


def executar_sql(consulta: str) -> list[dict[str, Any]]:
    """Executa uma consulta e devolve as linhas como dicionários."""
    cursor = _conexao().cursor()
    cursor.execute(consulta)
    colunas = [c[0] for c in cursor.description]
    return [dict(zip(colunas, linha, strict=True)) for linha in cursor.fetchall()]
