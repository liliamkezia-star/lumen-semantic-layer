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

# Tipos que espelham o que o DuckDB infere ao ler o CSV real do SCR.data.
# data_base é DATE (não VARCHAR) porque a fonte usa formato ISO e o
# read_csv detecta isso automaticamente — o teste precisa refletir a
# realidade do banco, não uma suposição.
COLUNAS_INTEIRAS = {"numero_de_operacoes", "ano_arquivo"}
COLUNAS_DATA = {"data_base"}
COLUNAS_TEXTO = {
    "uf", "segmento", "cliente", "cnae_ocupacao", "porte", "modalidade",
    "submodalidade", "origem", "indexador", "arquivo_origem", "timestamp_coleta",
}


def tipo_da_coluna(nome):
    if nome in COLUNAS_INTEIRAS:
        return "INTEGER"
    if nome in COLUNAS_DATA:
        return "DATE"
    if nome in COLUNAS_TEXTO:
        return "VARCHAR"
    return "DOUBLE"


DADOS_SINTETICOS = [
    # Linha normal, numero_de_operacoes válido
    ("2024-01-31", "PB", "Livre", "PF", "Comércio", "N/A", "Cartão de crédito",
     "Rotativo", "Sem destinação específica", "Prefixado", 150,
     1000.0, 500.0, 0.0, 0.0, 0.0, 0.0, 1500.0, 0.0, 0.0, 0.0, 1500.0, 50.0, 20.0,
     2024, "scrdata_202401.csv", "url-teste"),
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

    colunas_sql = ", ".join(f"{c} {tipo_da_coluna(c)}" for c in COLUNAS_BRONZE)
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


def test_data_base_e_tipo_date(conexao):
    """data_base deve ser DATE na Silver, garantido por CAST explícito —
    não por inferência automática da camada anterior. Sem isso, o join
    com dim_calendario em fato_credito dependeria de cast implícito, que
    pode se comportar de forma diferente após a migração para Fabric
    (Spark infere tipos de forma distinta do DuckDB)."""
    tipo = conexao.execute("""
        SELECT data_type FROM information_schema.columns
        WHERE table_schema = 'silver'
          AND table_name = 'credito_uf_modalidade'
          AND column_name = 'data_base'
    """).fetchone()[0]
    assert tipo == "DATE", f"data_base deveria ser DATE, é {tipo}"


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
