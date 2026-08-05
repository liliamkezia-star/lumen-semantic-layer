import duckdb

CAMINHO_BANCO = "lumen.duckdb"

if __name__ == "__main__":
    conexao = duckdb.connect(CAMINHO_BANCO)
    conexao.execute("CREATE SCHEMA IF NOT EXISTS silver;")

    conexao.execute("""
        CREATE OR REPLACE TABLE silver.serie_credito_mensal AS
        WITH dados_mais_recentes AS (
            SELECT
                nome_serie,
                codigo_serie,
                -- Converte texto dd/mm/aaaa para tipo DATE de verdade
                STRPTIME(data_referencia, '%d/%m/%Y')::DATE AS data_referencia,
                -- Converte texto com vírgula/ponto decimal para número
                CAST(valor AS DOUBLE) AS valor,
                timestamp_coleta,
                ROW_NUMBER() OVER (
                    PARTITION BY nome_serie, data_referencia
                    ORDER BY timestamp_coleta DESC
                ) AS numero_linha
            FROM bronze.sgs_series_raw
        )
        SELECT
            nome_serie,
            codigo_serie,
            data_referencia,
            valor,
            timestamp_coleta AS timestamp_coleta_original
        FROM dados_mais_recentes
        WHERE numero_linha = 1
    """)

    total = conexao.execute(
        "SELECT COUNT(*) FROM silver.serie_credito_mensal"
    ).fetchone()[0]
    print(f"Total de linhas em silver.serie_credito_mensal: {total}")

    amostra = conexao.execute("""
        SELECT nome_serie, data_referencia, valor
        FROM silver.serie_credito_mensal
        WHERE nome_serie = 'selic_meta'
        ORDER BY data_referencia
        LIMIT 5
    """).fetchall()
    print("\nAmostra (selic_meta):")
    for linha in amostra:
        print(linha)

    conexao.close()
