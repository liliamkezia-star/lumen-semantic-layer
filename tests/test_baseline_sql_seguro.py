"""Testes do validador de SQL do baseline text-to-SQL."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from evaluation.sql_seguro import SqlRecusado, validar_sql


@pytest.mark.parametrize(
    "consulta",
    [
        "SELECT SUM(carteira_ativa) FROM gold.fato_credito WHERE id_data = 20251231",
        """SELECT u.nome_uf, SUM(f.carteira_ativa) FROM gold.fato_credito f
           JOIN gold.dim_uf u ON u.id_uf = f.id_uf GROUP BY u.nome_uf""",
        """WITH base AS (SELECT id_data, SUM(carteira_ativa) AS c FROM gold.fato_credito GROUP BY id_data)
           SELECT TOP 5 * FROM base ORDER BY id_data DESC""",
        "SELECT (SELECT SUM(carteira_ativa) FROM gold.fato_credito WHERE id_data = 20251231) AS v",
    ],
)
def test_leituras_sobre_gold_sao_aceitas(consulta):
    assert validar_sql(consulta) == consulta


@pytest.mark.parametrize(
    ("consulta", "motivo"),
    [
        ("DROP TABLE gold.fato_credito", "leitura"),
        ("DELETE FROM gold.fato_credito", "leitura"),
        ("UPDATE gold.dim_uf SET nome_uf = 'x'", "leitura"),
        ("INSERT INTO gold.dim_uf VALUES (1)", "leitura"),
        ("SELECT * INTO gold.copia FROM gold.dim_uf", "leitura"),
        ("SELECT 1 FROM gold.dim_uf; DROP TABLE gold.dim_uf", "exatamente uma"),
        ("SELECT * FROM silver.credito_uf_modalidade", "fora do schema"),
        ("SELECT * FROM dim_uf", "fora do schema"),
        ("SELECT * FROM sys.tables", "fora do schema"),
        ("EXEC sp_who", "leitura"),
    ],
)
def test_escrita_multiplas_instrucoes_e_outros_schemas_sao_recusados(consulta, motivo):
    with pytest.raises(SqlRecusado, match=motivo):
        validar_sql(consulta)


def test_nome_de_coluna_com_palavra_proibida_nao_engana_o_validador():
    """Busca por palavra-chave recusaria isto; a análise sintática, não."""
    consulta = "SELECT COUNT(*) AS delete_count FROM gold.fato_credito"
    assert validar_sql(consulta) == consulta
