import sys
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from common.logging_config import configurar_logger

logger = configurar_logger(__name__)

CAMINHO_BANCO = "lumen.duckdb"


def construir_silver_scr_data(conexao) -> None:
    """Cria silver.credito_uf_modalidade a partir de bronze.scr_data_raw.

    Mantém a granularidade total da fonte (ver ADR-004) — nenhuma
    agregação acontece aqui. Aplica:
    - deduplicação por chave natural, mantendo apenas a coleta mais
      recente (ver ADR-003: a Silver é responsável por resolver qual é
      a versão atual de cada dado, não a Bronze)
    - CAST explícito de data_base para DATE
    - tratamento do valor sentinela -1 em numero_de_operacoes

    A chave natural (10 colunas de dimensão) foi verificada como única
    na fonte antes da implementação desta deduplicação.

    Extraído como função reutilizável para permitir testes de qualidade
    sobre dados sintéticos em memória (mesmo padrão de silver_sgs.py)."""
    conexao.execute("CREATE SCHEMA IF NOT EXISTS silver;")

    conexao.execute("""
        CREATE OR REPLACE TABLE silver.credito_uf_modalidade AS
        WITH dados_mais_recentes AS (
            SELECT
                -- CAST explícito: não depender da inferência automática
                -- de tipo da camada Bronze. Garante DATE independentemente
                -- de como a fonte for lida (DuckDB read_csv hoje, Spark
                -- no Fabric a partir da Sprint 6).
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
                timestamp_coleta,
                ROW_NUMBER() OVER (
                    PARTITION BY
                        data_base, uf, segmento, cliente, cnae_ocupacao,
                        porte, modalidade, submodalidade, origem, indexador
                    ORDER BY timestamp_coleta DESC
                ) AS numero_linha
            FROM bronze.scr_data_raw
        )
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
            numero_de_operacoes,
            carteira_a_vencer,
            carteira_vencida,
            carteira_ativa,
            carteira_inadimplencia,
            ativo_problematico,
            ano_arquivo,
            arquivo_origem,
            timestamp_coleta AS timestamp_ultima_coleta
        FROM dados_mais_recentes
        WHERE numero_linha = 1
    """)


if __name__ == "__main__":
    conexao = duckdb.connect(CAMINHO_BANCO)

    logger.info("Processando silver.credito_uf_modalidade (pode levar alguns minutos)...")
    construir_silver_scr_data(conexao)

    total = conexao.execute(
        "SELECT COUNT(*) FROM silver.credito_uf_modalidade"
    ).fetchone()[0]
    logger.info(f"Total de linhas em silver.credito_uf_modalidade: {total}")

    nulos_operacoes = conexao.execute(
        "SELECT COUNT(*) FROM silver.credito_uf_modalidade WHERE numero_de_operacoes IS NULL"
    ).fetchone()[0]
    logger.info(f"Linhas com numero_de_operacoes NULL (antes era -1): {nulos_operacoes}")

    tipo_data = conexao.execute("""
        SELECT data_type FROM information_schema.columns
        WHERE table_schema = 'silver'
          AND table_name = 'credito_uf_modalidade'
          AND column_name = 'data_base'
    """).fetchone()[0]
    logger.info(f"Tipo de data_base: {tipo_data}")

    conexao.close()
