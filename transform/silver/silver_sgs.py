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
            -- Documenta explicitamente a unidade de cada série, evitando
            -- ambiguidade silenciosa (ex: taxa diária vs. taxa anual).
            CASE nome_serie
                WHEN 'selic_diaria' THEN '% ao dia'
                WHEN 'selic_meta' THEN '% ao ano'
                WHEN 'ipca_mensal' THEN '% no mês'
                WHEN 'saldo_credito_total' THEN 'R$ milhões'
                WHEN 'credito_pib' THEN '% do PIB'
                WHEN 'inadimplencia_total' THEN '% da carteira'
                WHEN 'spread_medio_total' THEN 'pontos percentuais'
                WHEN 'concessoes_pf_total' THEN 'R$ milhões'
                WHEN 'concessoes_pj_total' THEN 'R$ milhões'
                WHEN 'endividamento_familias' THEN '% da renda acumulada 12m'
                ELSE 'não documentado'
            END AS unidade_valor,
            -- Nome corrigido: este é o timestamp da coleta MAIS RECENTE
            -- (não da primeira/original), já que filtramos numero_linha = 1
            -- ordenado por timestamp_coleta DESC.
            timestamp_coleta AS timestamp_ultima_coleta
        FROM dados_mais_recentes
        WHERE numero_linha = 1
    """)

    total = conexao.execute(
        "SELECT COUNT(*) FROM silver.serie_credito_mensal"
    ).fetchone()[0]
    print(f"Total de linhas em silver.serie_credito_mensal: {total}")

    amostra = conexao.execute("""
        SELECT nome_serie, data_referencia, valor, unidade_valor
        FROM silver.serie_credito_mensal
        WHERE nome_serie = 'selic_meta'
        ORDER BY data_referencia
        LIMIT 5
    """).fetchall()
    print("\nAmostra (selic_meta):")
    for linha in amostra:
        print(linha)

    conexao.close()
