SERIES_INDICADOR_MACRO = {"selic_diaria", "selic_meta", "ipca_mensal"}

UNIDADES = {
    "selic_diaria": "% ao dia",
    "selic_meta": "% ao ano",
    "ipca_mensal": "% no mês",
    "saldo_credito_total": "R$ milhões",
    "credito_pib": "% do PIB",
    "inadimplencia_total": "% da carteira",
    "spread_medio_total": "pontos percentuais",
    "concessoes_pf_total": "R$ milhões",
    "concessoes_pj_total": "R$ milhões",
    "endividamento_familias": "% da renda acumulada 12m",
}

GRANULARIDADE = {
    "selic_diaria": "diária",
    "selic_meta": "diária",
    "ipca_mensal": "mensal",
    "saldo_credito_total": "mensal",
    "credito_pib": "mensal",
    "inadimplencia_total": "mensal",
    "spread_medio_total": "mensal",
    "concessoes_pf_total": "mensal",
    "concessoes_pj_total": "mensal",
    "endividamento_familias": "mensal",
}


def montar_case_unidade():
    linhas_case = [f"WHEN '{serie}' THEN '{unidade}'" for serie, unidade in UNIDADES.items()]
    return "CASE nome_serie\n" + "\n".join(linhas_case) + "\nELSE 'não documentado'\nEND"


def montar_case_granularidade():
    linhas_case = [f"WHEN '{serie}' THEN '{gran}'" for serie, gran in GRANULARIDADE.items()]
    return "CASE nome_serie\n" + "\n".join(linhas_case) + "\nELSE 'não documentado'\nEND"


def criar_cte_deduplicada():
    return """
        SELECT
            nome_serie,
            codigo_serie,
            to_date(data_referencia, 'dd/MM/yyyy') AS data_referencia,
            CAST(valor AS DOUBLE) AS valor,
            timestamp_coleta,
            ROW_NUMBER() OVER (
                PARTITION BY nome_serie, data_referencia
                ORDER BY timestamp_coleta DESC
            ) AS numero_linha
        FROM bronze.sgs_series_raw
    """


spark.sql("CREATE SCHEMA IF NOT EXISTS silver")

cte = criar_cte_deduplicada()
case_unidade = montar_case_unidade()
case_granularidade = montar_case_granularidade()
lista_macro = ", ".join(f"'{s}'" for s in SERIES_INDICADOR_MACRO)

spark.sql(f"""
    CREATE OR REPLACE TABLE silver.indicador_macro AS
    WITH dados_mais_recentes AS ({cte})
    SELECT
        nome_serie,
        codigo_serie,
        data_referencia,
        valor,
        {case_unidade} AS unidade_valor,
        {case_granularidade} AS granularidade,
        timestamp_coleta AS timestamp_ultima_coleta
    FROM dados_mais_recentes
    WHERE numero_linha = 1
      AND nome_serie IN ({lista_macro})
""")

spark.sql(f"""
    CREATE OR REPLACE TABLE silver.serie_credito_mensal AS
    WITH dados_mais_recentes AS ({cte})
    SELECT
        nome_serie,
        codigo_serie,
        data_referencia,
        valor,
        {case_unidade} AS unidade_valor,
        {case_granularidade} AS granularidade,
        timestamp_coleta AS timestamp_ultima_coleta
    FROM dados_mais_recentes
    WHERE numero_linha = 1
      AND nome_serie NOT IN ({lista_macro})
""")

total_macro = spark.sql("SELECT COUNT(*) AS total FROM silver.indicador_macro").collect()[0]["total"]
total_credito = spark.sql("SELECT COUNT(*) AS total FROM silver.serie_credito_mensal").collect()[0]["total"]
print(f"Total em silver.indicador_macro: {total_macro}")
print(f"Total em silver.serie_credito_mensal: {total_credito}")
