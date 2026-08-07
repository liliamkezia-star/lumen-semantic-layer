"""Testes de qualidade bloqueantes para silver.localidade e
silver.populacao_uf.
"""

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "transform" / "silver"))
from silver_ibge import construir_silver_ibge

DADOS_LOCALIDADES = [
    (25, "PB", "Paraíba", 2, "Nordeste", "url-teste", "2024-01-01T00:00:00+00:00"),
    # Coleta duplicada de propósito, timestamp mais recente
    (25, "PB", "Paraíba", 2, "Nordeste", "url-teste", "2024-01-02T00:00:00+00:00"),
    (35, "SP", "São Paulo", 3, "Sudeste", "url-teste", "2024-01-01T00:00:00+00:00"),
]

DADOS_POPULACAO = [
    (25, "Paraíba", "2020", "4039277", "url-teste", "2024-01-01T00:00:00+00:00"),
    (25, "Paraíba", "2021", "4059905", "url-teste", "2024-01-01T00:00:00+00:00"),
    (35, "São Paulo", "2020", "46289333", "url-teste", "2024-01-01T00:00:00+00:00"),
]


@pytest.fixture
def conexao():
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze;")

    con.execute("""
        CREATE TABLE bronze.ibge_localidades_raw (
            id_uf INTEGER, sigla_uf VARCHAR, nome_uf VARCHAR,
            id_regiao INTEGER, nome_regiao VARCHAR,
            url_fonte VARCHAR, timestamp_coleta VARCHAR
        );
    """)
    con.executemany(
        "INSERT INTO bronze.ibge_localidades_raw VALUES (?, ?, ?, ?, ?, ?, ?)",
        DADOS_LOCALIDADES,
    )

    con.execute("""
        CREATE TABLE bronze.ibge_populacao_raw (
            id_uf INTEGER, nome_uf VARCHAR, ano VARCHAR,
            populacao_estimada VARCHAR,
            url_fonte VARCHAR, timestamp_coleta VARCHAR
        );
    """)
    con.executemany(
        "INSERT INTO bronze.ibge_populacao_raw VALUES (?, ?, ?, ?, ?, ?)",
        DADOS_POPULACAO,
    )

    construir_silver_ibge(con)

    yield con
    con.close()


def test_localidade_sem_duplicatas(conexao):
    """Cada UF deve aparecer apenas uma vez em silver.localidade, mesmo
    quando a Bronze tem múltiplas coletas da mesma UF."""
    resultado = conexao.execute("""
        SELECT id_uf, COUNT(*) as qtd FROM silver.localidade
        GROUP BY id_uf HAVING COUNT(*) > 1
    """).fetchall()
    assert len(resultado) == 0, f"Duplicatas encontradas: {resultado}"


def test_localidade_mantem_coleta_mais_recente(conexao):
    """PB teve duas coletas (timestamps diferentes) — a Silver deve
    manter a mais recente (02/01), não a mais antiga (01/01)."""
    resultado = conexao.execute("""
        SELECT timestamp_ultima_coleta FROM silver.localidade
        WHERE sigla_uf = 'PB'
    """).fetchone()[0]
    assert resultado == "2024-01-02T00:00:00+00:00", (
        f"Esperava manter a coleta mais recente, encontrado: {resultado}"
    )


def test_populacao_tipos_convertidos(conexao):
    """ano e populacao_estimada devem ser numéricos na Silver, não
    mais texto como estavam na Bronze."""
    resultado = conexao.execute("""
        SELECT ano, populacao_estimada FROM silver.populacao_uf
        WHERE id_uf = 25 AND ano = 2020
    """).fetchone()
    ano, populacao = resultado
    assert isinstance(ano, int), f"ano deveria ser int, é {type(ano)}"
    assert isinstance(populacao, int), f"populacao_estimada deveria ser int, é {type(populacao)}"
    assert populacao == 4039277


def test_populacao_sem_duplicatas_por_uf_e_ano(conexao):
    """Não deve haver mais de uma linha por (id_uf, ano)."""
    resultado = conexao.execute("""
        SELECT id_uf, ano, COUNT(*) as qtd FROM silver.populacao_uf
        GROUP BY id_uf, ano HAVING COUNT(*) > 1
    """).fetchall()
    assert len(resultado) == 0, f"Duplicatas encontradas: {resultado}"
