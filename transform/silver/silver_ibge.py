import duckdb

CAMINHO_BANCO = "lumen.duckdb"


def construir_silver_ibge(conexao):
    """Cria silver.localidade e silver.populacao_uf a partir da Bronze do
    IBGE, aplicando deduplicação por timestamp_coleta (mesmo padrão do
    SGS) e tipagem correta.

    Extraído como função reutilizável para testes com dados sintéticos."""
    conexao.execute("CREATE SCHEMA IF NOT EXISTS silver;")

    conexao.execute("""
        CREATE OR REPLACE TABLE silver.localidade AS
        WITH dados_mais_recentes AS (
            SELECT
                id_uf,
                sigla_uf,
                nome_uf,
                id_regiao,
                nome_regiao,
                timestamp_coleta,
                ROW_NUMBER() OVER (
                    PARTITION BY id_uf
                    ORDER BY timestamp_coleta DESC
                ) AS numero_linha
            FROM bronze.ibge_localidades_raw
        )
        SELECT id_uf, sigla_uf, nome_uf, id_regiao, nome_regiao,
               timestamp_coleta AS timestamp_ultima_coleta
        FROM dados_mais_recentes
        WHERE numero_linha = 1
    """)

    conexao.execute("""
        CREATE OR REPLACE TABLE silver.populacao_uf AS
        WITH dados_mais_recentes AS (
            SELECT
                id_uf,
                nome_uf,
                CAST(ano AS INTEGER) AS ano,
                CAST(populacao_estimada AS BIGINT) AS populacao_estimada,
                timestamp_coleta,
                ROW_NUMBER() OVER (
                    PARTITION BY id_uf, ano
                    ORDER BY timestamp_coleta DESC
                ) AS numero_linha
            FROM bronze.ibge_populacao_raw
        )
        SELECT id_uf, nome_uf, ano, populacao_estimada,
               timestamp_coleta AS timestamp_ultima_coleta
        FROM dados_mais_recentes
        WHERE numero_linha = 1
    """)


if __name__ == "__main__":
    conexao = duckdb.connect(CAMINHO_BANCO)
    construir_silver_ibge(conexao)

    total_localidade = conexao.execute(
        "SELECT COUNT(*) FROM silver.localidade"
    ).fetchone()[0]
    total_populacao = conexao.execute(
        "SELECT COUNT(*) FROM silver.populacao_uf"
    ).fetchone()[0]

    print(f"Total em silver.localidade: {total_localidade}")
    print(f"Total em silver.populacao_uf: {total_populacao}")

    anos_presentes = conexao.execute(
        "SELECT DISTINCT ano FROM silver.populacao_uf ORDER BY ano"
    ).fetchall()
    print("Anos presentes em populacao_uf:", [a[0] for a in anos_presentes])

    conexao.close()
