spark.sql("CREATE SCHEMA IF NOT EXISTS silver")

spark.sql("""
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

spark.sql("""
    CREATE OR REPLACE TABLE silver.populacao_uf AS
    WITH dados_mais_recentes AS (
        SELECT
            id_uf,
            nome_uf,
            CAST(ano AS INT) AS ano,
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

total_localidade = spark.sql("SELECT COUNT(*) AS total FROM silver.localidade").collect()[0]["total"]
total_populacao = spark.sql("SELECT COUNT(*) AS total FROM silver.populacao_uf").collect()[0]["total"]
print(f"Total em silver.localidade: {total_localidade}")
print(f"Total em silver.populacao_uf: {total_populacao}")
