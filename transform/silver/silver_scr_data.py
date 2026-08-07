import duckdb

CAMINHO_BANCO = "lumen.duckdb"


def construir_silver_scr_data(conexao):
    """Cria silver.credito_uf_modalidade a partir de bronze.scr_data_raw.

    Mantém a granularidade total da fonte (ver ADR-004) — nenhuma
    agregação acontece aqui, apenas tratamento do valor sentinela -1 em
    numero_de_operacoes (ver observação no dicionário de dados).

    Extraído como função reutilizável para permitir testes de qualidade
    sobre dados sintéticos em memória (mesmo padrão de silver_sgs.py)."""
    conexao.execute("CREATE SCHEMA IF NOT EXISTS silver;")

    conexao.execute("""
        CREATE OR REPLACE TABLE silver.credito_uf_modalidade AS
        SELECT
            data_base,
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

    conexao.close()
