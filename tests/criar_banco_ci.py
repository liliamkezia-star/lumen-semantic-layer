"""Cria um banco DuckDB sintetico para o CI rodar dbt build.

O banco real (lumen.duckdb) tem ~34 milhoes de linhas e nunca e versionado
no repositorio. Este script monta um banco pequeno com a mesma ESTRUTURA
das camadas bronze e silver, permitindo que o dbt construa e teste o star
schema completo no CI sem depender de dados reais nem de chamadas as APIs.
"""

import duckdb

CAMINHO_BANCO_CI = "lumen_ci.duckdb"


def criar_silver_sintetica(con):
    con.execute("CREATE SCHEMA IF NOT EXISTS silver;")

    con.execute("""
        CREATE OR REPLACE TABLE silver.indicador_macro AS
        SELECT * FROM (VALUES
            ('selic_meta', 432, DATE '2024-01-01', 11.75, 'pct ao ano', 'diaria', '2024-01-02T00:00:00+00:00'),
            ('ipca_mensal', 433, DATE '2024-01-01', 0.42, 'pct no mes', 'mensal', '2024-01-02T00:00:00+00:00')
        ) AS t(nome_serie, codigo_serie, data_referencia, valor, unidade_valor, granularidade, timestamp_ultima_coleta);
    """)

    con.execute("""
        CREATE OR REPLACE TABLE silver.serie_credito_mensal AS
        SELECT * FROM (VALUES
            ('inadimplencia_total', 21082, DATE '2024-01-01', 3.5, 'pct da carteira', 'mensal', '2024-01-02T00:00:00+00:00'),
            ('saldo_credito_total', 20539, DATE '2024-01-01', 5500000.0, 'BRL milhoes', 'mensal', '2024-01-02T00:00:00+00:00')
        ) AS t(nome_serie, codigo_serie, data_referencia, valor, unidade_valor, granularidade, timestamp_ultima_coleta);
    """)

    con.execute("""
        CREATE OR REPLACE TABLE silver.credito_uf_modalidade AS
        SELECT * FROM (VALUES
            (DATE '2024-01-31', 'PB', 'Livre', 'PF', 'Comercio', 'N/A', 'Cartao de credito',
             'Rotativo', 'Sem destinacao especifica', 'Prefixado', 150,
             1500.0, 0.0, 1500.0, 50.0, 20.0, 2024, 'scrdata_202401.csv', '2024-01-02T00:00:00+00:00'),
            (DATE '2024-01-31', 'SP', 'Livre', 'PJ', 'Industria', 'Medio', 'Capital de giro',
             'N/A', 'Sem destinacao especifica', 'Prefixado', NULL,
             3000.0, 0.0, 3000.0, 100.0, 40.0, 2024, 'scrdata_202401.csv', '2024-01-02T00:00:00+00:00')
        ) AS t(data_base, uf, segmento, cliente, cnae_ocupacao, porte, modalidade,
               submodalidade, origem, indexador, numero_de_operacoes,
               carteira_a_vencer, carteira_vencida, carteira_ativa,
               carteira_inadimplencia, ativo_problematico, ano_arquivo,
               arquivo_origem, timestamp_ultima_coleta);
    """)

    con.execute("""
        CREATE OR REPLACE TABLE silver.localidade AS
        SELECT * FROM (VALUES
            (25, 'PB', 'Paraiba', 2, 'Nordeste', '2024-01-02T00:00:00+00:00'),
            (35, 'SP', 'Sao Paulo', 3, 'Sudeste', '2024-01-02T00:00:00+00:00')
        ) AS t(id_uf, sigla_uf, nome_uf, id_regiao, nome_regiao, timestamp_ultima_coleta);
    """)

    con.execute("""
        CREATE OR REPLACE TABLE silver.populacao_uf AS
        SELECT * FROM (VALUES
            (25, 'Paraiba', 2024, 4145040, '2024-01-02T00:00:00+00:00'),
            (35, 'Sao Paulo', 2024, 46289333, '2024-01-02T00:00:00+00:00')
        ) AS t(id_uf, nome_uf, ano, populacao_estimada, timestamp_ultima_coleta);
    """)


if __name__ == "__main__":
    con = duckdb.connect(CAMINHO_BANCO_CI)
    criar_silver_sintetica(con)

    for tabela in ["indicador_macro", "serie_credito_mensal",
                   "credito_uf_modalidade", "localidade", "populacao_uf"]:
        total = con.execute(f"SELECT COUNT(*) FROM silver.{tabela}").fetchone()[0]
        print(f"silver.{tabela}: {total} linhas")

    con.close()
    print(f"\nBanco sintetico criado em {CAMINHO_BANCO_CI}")
