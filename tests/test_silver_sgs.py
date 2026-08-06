"""Testes de qualidade bloqueantes para as tabelas Silver derivadas do SGS.

Roda inteiramente sobre um banco DuckDB em memória, com dados sintéticos
fabricados aqui mesmo — não depende do arquivo lumen.duckdb nem de
chamadas à API do Banco Central. Isso permite rodar os testes no CI
(GitHub Actions), sem precisar de dados reais no repositório.
"""

import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "transform" / "silver"))
from silver_sgs import construir_silver_sgs

DADOS_SINTETICOS = [
    # (nome_serie, codigo_serie, data_referencia, valor, url_fonte, timestamp_coleta)
    ("selic_diaria", 11, "01/01/2024", "0.05", "url-teste", "2024-01-02T00:00:00+00:00"),
    ("selic_meta", 432, "01/01/2024", "11.75", "url-teste", "2024-01-02T00:00:00+00:00"),
    ("ipca_mensal", 433, "01/01/2024", "0.42", "url-teste", "2024-01-02T00:00:00+00:00"),
    ("inadimplencia_total", 21082, "01/01/2024", "3.5", "url-teste", "2024-01-02T00:00:00+00:00"),
    ("saldo_credito_total", 20539, "01/01/2024", "5500000", "url-teste", "2024-01-02T00:00:00+00:00"),
    # Coleta duplicada de propósito: mesma série/data, timestamp mais recente
    # (testa se a deduplicação por ROW_NUMBER está funcionando)
    ("selic_meta", 432, "01/01/2024", "11.75", "url-teste", "2024-01-03T00:00:00+00:00"),
]


@pytest.fixture
def conexao():
    """Banco DuckDB em memória, populado com dados sintéticos e já
    processado pela função real construir_silver_sgs()."""
    con = duckdb.connect(":memory:")
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
    con.execute("""
        CREATE TABLE bronze.sgs_series_raw (
            nome_serie VARCHAR,
            codigo_serie INTEGER,
            data_referencia VARCHAR,
            valor VARCHAR,
            url_fonte VARCHAR,
            timestamp_coleta VARCHAR
        );
    """)
    con.executemany(
        "INSERT INTO bronze.sgs_series_raw VALUES (?, ?, ?, ?, ?, ?)",
        DADOS_SINTETICOS,
    )

    construir_silver_sgs(con)

    yield con
    con.close()


@pytest.mark.parametrize("tabela", ["silver.indicador_macro", "silver.serie_credito_mensal"])
def test_colunas_chave_sem_nulos(conexao, tabela):
    """Colunas-chave (nome_serie, data_referencia, valor) nunca devem
    ser nulas — um nulo aqui indica falha silenciosa na transformação."""
    resultado = conexao.execute(f"""
        SELECT COUNT(*) FROM {tabela}
        WHERE nome_serie IS NULL
           OR data_referencia IS NULL
           OR valor IS NULL
    """).fetchone()[0]
    assert resultado == 0, f"{tabela}: encontradas {resultado} linhas com colunas-chave nulas"


@pytest.mark.parametrize("tabela", ["silver.indicador_macro", "silver.serie_credito_mensal"])
def test_sem_duplicatas_por_serie_e_data(conexao, tabela):
    """Não deve haver mais de uma linha por (nome_serie, data_referencia)
    na Silver — a deduplicação via ROW_NUMBER deveria garantir isso."""
    resultado = conexao.execute(f"""
        SELECT nome_serie, data_referencia, COUNT(*) as qtd
        FROM {tabela}
        GROUP BY nome_serie, data_referencia
        HAVING COUNT(*) > 1
    """).fetchall()
    assert len(resultado) == 0, f"{tabela}: encontradas duplicatas: {resultado[:5]}"


@pytest.mark.parametrize("tabela", ["silver.indicador_macro", "silver.serie_credito_mensal"])
def test_unidade_valor_documentada(conexao, tabela):
    """Nenhuma série deveria ficar com unidade 'não documentado'."""
    resultado = conexao.execute(f"""
        SELECT COUNT(*) FROM {tabela} WHERE unidade_valor = 'não documentado'
    """).fetchone()[0]
    assert resultado == 0, f"{tabela}: {resultado} linhas sem unidade documentada"


def test_selic_diaria_valor_plausivel(conexao):
    """A Selic diária (% ao dia) nunca deveria ultrapassar 1% ao dia."""
    resultado = conexao.execute("""
        SELECT COUNT(*) FROM silver.indicador_macro
        WHERE nome_serie = 'selic_diaria' AND (valor < 0 OR valor > 1)
    """).fetchone()[0]
    assert resultado == 0, f"selic_diaria: {resultado} valores fora da faixa plausível [0, 1]"


def test_inadimplencia_valor_plausivel(conexao):
    """Inadimplência é um percentual — deveria estar sempre entre 0 e 100."""
    resultado = conexao.execute("""
        SELECT COUNT(*) FROM silver.serie_credito_mensal
        WHERE nome_serie = 'inadimplencia_total' AND (valor < 0 OR valor > 100)
    """).fetchone()[0]
    assert resultado == 0, f"inadimplencia_total: {resultado} valores fora da faixa [0, 100]"


def test_deduplicacao_mantem_apenas_coleta_mais_recente(conexao):
    """Verifica especificamente o caso de teste com coleta duplicada:
    selic_meta em 01/01/2024 tem duas coletas (timestamps diferentes);
    a Silver deve manter só uma linha, com o timestamp mais recente."""
    resultado = conexao.execute("""
        SELECT COUNT(*), MAX(timestamp_ultima_coleta)
        FROM silver.indicador_macro
        WHERE nome_serie = 'selic_meta'
    """).fetchone()

    quantidade, timestamp_mantido = resultado
    assert quantidade == 1, f"Esperava 1 linha para selic_meta, encontrou {quantidade}"
    assert timestamp_mantido == "2024-01-03T00:00:00+00:00", (
        f"Esperava manter a coleta mais recente (03/01), mantido: {timestamp_mantido}"
    )
