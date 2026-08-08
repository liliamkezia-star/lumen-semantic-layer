import duckdb

CAMINHO_BANCO = "lumen.duckdb"


def construir_silver_scr_data(conexao):
    """Cria silver.credito_uf_modalidade a partir de bronze.scr_data_raw.

    Mantém a granularidade total da fonte (ver ADR-004) — nenhuma
    agregação acontece aqui, apenas tratamento do valor sentinela -1 em
    numero_de_operacoes (ver observação no dicionário de dados) e CAST
    explícito de data_base.

    Extraído como função reutilizável para permitir testes de qualidade
    sobre dados sintéticos em memória (mesmo padrão de silver_sgs.py)."""
    conexao.execute("CREATE SCHEMA IF NOT EXISTS silver;")

    conexao.execute("""
        CREATE OR REPLACE TABLE silver.credito_uf_modalidade AS
        SELECT
            -- CAST explícito: não depender da inferência automática de
            -- tipo da camada Bronze. Garante DATE independentemente de
            -- como a fonte for lida (DuckDB read_csv hoje, Spark no
            -- Fabric a partir da Sprint 6). Sem isso, o join com
            -- dim_calendario em fato_credito dependeria de cast
            -- implícito, que pode falhar silenciosamente (gerando
            -- órfãos, não erro) se o formato da fonte variar.
            CAST(data_base AS DATE) AS data_base,
            uf,
            segmento,
            cliente,
            cnae_ocupacao,
            porte,
            modalidade,
            submodalidade,
            origem,
            indexador,
            -- -1 não é uma contagem válida; convertido para NULL.
            -- Causa raiz não confirmada na documentação oficial (ver
            -- observação no dicionário de dados).
            NULLIF(numero_de_operacoes, -1) AS numero_de_operacoes,
            carteira_a_vencer,
            carteira_vencida,
            carteira_ativa,
            carteira_inadimplencia,
            ativo_problematico,
            ano_arquivo,
            arquivo_origem,
            timestamp_coleta
        FROM bronze.scr_data_raw
    """)


if __name__ == "__main__":
    conexao = duckdb.connect(CAMINHO_BANCO)

    print("Processando silver.credito_uf_modalidade (pode levar alguns minutos)...")
    construir_silver_scr_data(conexao)

    total = conexao.execute(
        "SELECT COUNT(*) FROM silver.credito_uf_modalidade"
    ).fetchone()[0]
    print(f"Total de linhas em silver.credito_uf_modalidade: {total}")

    nulos_operacoes = conexao.execute(
        "SELECT COUNT(*) FROM silver.credito_uf_modalidade WHERE numero_de_operacoes IS NULL"
    ).fetchone()[0]
    print(f"Linhas com numero_de_operacoes NULL (antes era -1): {nulos_operacoes}")

    tipo_data = conexao.execute("""
        SELECT data_type FROM information_schema.columns
        WHERE table_schema = 'silver'
          AND table_name = 'credito_uf_modalidade'
          AND column_name = 'data_base'
    """).fetchone()[0]
    print(f"Tipo de data_base: {tipo_data}")

    conexao.close()
