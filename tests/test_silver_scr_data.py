"""Testes de qualidade bloqueantes para silver.credito_uf_modalidade.

Roda sobre um banco DuckDB em memória com dados sintéticos, sem depender
do arquivo real lumen.duckdb (que tem ~34 milhões de linhas — pesado
demais para rodar no CI a cada PR).
"""

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "transform" / "silver"))
from silver_scr_data import construir_silver_scr_data

COLUNAS_BRONZE = [
    "data_base", "uf", "segmento", "cliente", "cnae_ocupacao", "porte",
    "modalidade", "submodalidade", "origem", "indexador",
    "numero_de_operacoes", "a_vencer_ate_90_dias", "a_vencer_de_91_ate_360_dias",
    "a_vencer_de_361_ate_1080_dias", "a_vencer_de_1081_ate_1800_dias",
    "a_vencer_de_1801_ate_5400_dias", "a_vencer_acima_de_5400_dias",
    "carteira_a_vencer", "vencido_de_15_ate_90_dias", "vencido_acima_de_90_dias",
    "carteira_vencida", "carteira_ativa", "carteira_inadimplencia",
    "ativo_problematico", "ano_arquivo", "arquivo_origem", "timestamp_coleta",
]

DADOS_SINTETICOS = [
    # Linha normal, numero_de_operacoes válido
    ("2024-01-31", "PB", "Livre", "PF", "Comércio", "N/A", "Cartão de crédito",
     "Rotativo", "Sem destinação específica", "Prefixado", 150,
     1000.0, 500.0, 0.0, 0.0, 0.0, 0.0, 1500.0, 0.0, 0.0, 0.0, 1500.0, 50.0, 20.0,
     2024, "scrdata_202401.csv", "url-teste", ),
    # Linha com o valor sentinela -1 (deveria virar NULL na Silver)
    ("2024-01-31", "PB", "Livre", "PJ", "Indústria", "Médio", "Capital de giro",
     "N/A", "Sem destinação específica", "Prefixado", -1,
     2000.0, 1000.0, 0.0, 0.0, 0.0, 0.0, 3000.0, 0.0, 0.0, 0.0, 3000.0, 100.0, 40.0,
     2024, "scrdata_202401.csv", "url-teste"),
]


@pytest.fixture
def conexao():
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze;")

    colunas_sql = ", ".join(
        f"{c} {'INTEGER' if c in ('numero_de_operacoes', 'ano_arquivo') else 'VARCHAR' if c in ('data_base', 'uf', 'segmento', 'cliente', 'cnae_ocupacao', 'porte', 'modalidade', 'submodalidade', 'origem', 'indexador', 'arquivo_origem', 'timestamp_coleta') else 'DOUBLE'}"
        for c in COLUNAS_BRONZE
    )
    con.execute(f"CREATE TABLE bronze.scr_data_raw ({colunas_sql});")

    placeholders = ", ".join(["?"] * len(COLUNAS_BRONZE))
    con.executemany(
        f"INSERT INTO bronze.scr_data_raw VALUES ({placeholders})",
        DADOS_SINTETICOS,
    )

    construir_silver_scr_data(con)

    yield con
    con.close()


def test_valor_sentinela_convertido_para_null(conexao):
    """A linha com numero_de_operacoes = -1 na Bronze deve virar NULL
    na Silver, não permanecer como -1 (que não é uma contagem válida)."""
    resultado = conexao.execute("""
        SELECT COUNT(*) FROM silver.credito_uf_modalidade
        WHERE numero_de_operacoes = -1
    """).fetchone()[0]
    assert resultado == 0, "Ainda existem linhas com numero_de_operacoes = -1 na Silver"


def test_valor_valido_preservado(conexao):
    """A linha com numero_de_operacoes = 150 (válida) deve permanecer
    intacta, não deve ser afetada pelo tratamento do -1."""
    resultado = conexao.execute("""
        SELECT numero_de_operacoes FROM silver.credito_uf_modalidade
        WHERE uf = 'PB' AND cliente = 'PF'
    """).fetchone()[0]
    assert resultado == 150, f"Esperava 150, encontrado {resultado}"


def test_granularidade_preservada(conexao):
    """A Silver não deve agregar linhas (ver ADR-004) — o número de
    linhas na Silver deve ser igual ao número de linhas na Bronze."""
    total_bronze = conexao.execute(
        "SELECT COUNT(*) FROM bronze.scr_data_raw"
    ).fetchone()[0]
    total_silver = conexao.execute(
        "SELECT COUNT(*) FROM silver.credito_uf_modalidade"
    ).fetchone()[0]
    assert total_bronze == total_silver, (
        f"Silver deveria ter o mesmo número de linhas da Bronze "
        f"(bronze={total_bronze}, silver={total_silver}) — ver ADR-004"
    )


def test_colunas_dimensao_preservadas(conexao):
    """Confirma que nenhuma coluna de dimensão foi descartada (ver
    ADR-004: agregação prematura foi identificada e revertida)."""
    colunas = set(conexao.sql(
        "SELECT * FROM silver.credito_uf_modalidade LIMIT 0"
    ).columns)
    colunas_esperadas = {"cnae_ocupacao", "porte", "submodalidade", "origem", "indexador"}
    faltando = colunas_esperadas - colunas
    assert not faltando, f"Colunas de dimensão perdidas: {faltando}"
