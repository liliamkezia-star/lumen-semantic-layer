import duckdb

CAMINHO_BANCO = "lumen.duckdb"

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


def montar_case_unidade():
    """Monta a expressão CASE WHEN para a coluna de unidade a partir do
    dicionário UNIDADES, evitando repetir a lista em duas queries."""
    linhas_case = [
        f"WHEN '{serie}' THEN '{unidade}'" for serie, unidade in UNIDADES.items()
    ]
    return "CASE nome_serie\n" + "\n".join(linhas_case) + "\nELSE 'não documentado'\nEND"


def criar_cte_deduplicada():
    """CTE compartilhada: converte tipos e mantém apenas a coleta mais
    recente de cada (nome_serie, data_referencia), via ROW_NUMBER."""
    return """
        SELECT
            nome_serie,
            codigo_serie,
            STRPTIME(data_referencia, '%d/%m/%Y')::DATE AS data_referencia,
            CAST(valor AS DOUBLE) AS valor,
            timestamp_coleta,
            ROW_NUMBER() OVER (
                PARTITION BY nome_serie, data_referencia
                ORDER BY timestamp_coleta DESC
            ) AS numero_linha
        FROM bronze.sgs_series_raw
    """


if __name__ == "__main__":
    conexao = duckdb.connect(CAMINHO_BANCO)
    conexao.execute("CREATE SCHEMA IF NOT EXISTS silver;")

    cte = criar_cte_deduplicada()
    case_unidade = montar_case_unidade()
    lista_macro = ", ".join(f"'{s}'" for s in SERIES_INDICADOR_MACRO)

    # Tabela 1: indicador_macro (Selic, IPCA — indicadores macroeconômicos
    # nacionais, sem relação direta com o volume de crédito)
    conexao.execute(f"""
        CREATE OR REPLACE TABLE silver.indicador_macro AS
        WITH dados_mais_recentes AS ({cte})
        SELECT
            nome_serie,
            codigo_serie,
            data_referencia,
            valor,
            {case_unidade} AS unidade_valor,
            timestamp_coleta AS timestamp_ultima_coleta
        FROM dados_mais_recentes
        WHERE numero_linha = 1
          AND nome_serie IN ({lista_macro})
    """)

    # Tabela 2: serie_credito_mensal (indicadores derivados diretamente
    # do mercado de crédito nacional: saldo, concessões, inadimplência etc.)
    conexao.execute(f"""
        CREATE OR REPLACE TABLE silver.serie_credito_mensal AS
        WITH dados_mais_recentes AS ({cte})
        SELECT
            nome_serie,
            codigo_serie,
            data_referencia,
            valor,
            {case_unidade} AS unidade_valor,
            timestamp_coleta AS timestamp_ultima_coleta
        FROM dados_mais_recentes
        WHERE numero_linha = 1
          AND nome_serie NOT IN ({lista_macro})
    """)

    total_macro = conexao.execute(
        "SELECT COUNT(*) FROM silver.indicador_macro"
    ).fetchone()[0]
    total_credito = conexao.execute(
        "SELECT COUNT(*) FROM silver.serie_credito_mensal"
    ).fetchone()[0]

    print(f"Total em silver.indicador_macro: {total_macro}")
    print(f"Total em silver.serie_credito_mensal: {total_credito}")

    series_macro = conexao.execute(
        "SELECT DISTINCT nome_serie FROM silver.indicador_macro"
    ).fetchall()
    series_credito = conexao.execute(
        "SELECT DISTINCT nome_serie FROM silver.serie_credito_mensal"
    ).fetchall()

    print("\nSéries em indicador_macro:", [s[0] for s in series_macro])
    print("Séries em serie_credito_mensal:", [s[0] for s in series_credito])

    conexao.close()
