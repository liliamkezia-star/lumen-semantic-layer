import zipfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import requests

ANO_INICIAL = 2015
ANO_FINAL = 2025  # 2026 tratado separadamente por ser ano corrente/incompleto
CAMINHO_BANCO = "lumen.duckdb"
PASTA_TEMP = Path("ingestion/temp_scr")

TIMEOUT_CONEXAO = 10  # segundos para estabelecer a conexão
TIMEOUT_LEITURA = 60  # segundos entre pedaços recebidos (arquivo grande)
MAX_TENTATIVAS_DOWNLOAD = 3

COLUNAS_ESPERADAS = {
    "data_base", "uf", "segmento", "cliente", "cnae_ocupacao", "porte",
    "modalidade", "submodalidade", "origem", "indexador",
    "numero_de_operacoes", "a_vencer_ate_90_dias", "a_vencer_de_91_ate_360_dias",
    "a_vencer_de_361_ate_1080_dias", "a_vencer_de_1081_ate_1800_dias",
    "a_vencer_de_1801_ate_5400_dias", "a_vencer_acima_de_5400_dias",
    "carteira_a_vencer", "vencido_de_15_ate_90_dias", "vencido_acima_de_90_dias",
    "carteira_vencida", "carteira_ativa", "carteira_inadimplencia",
    "ativo_problematico",
}


def validar_schema_csv(conexao, caminho_csv, nome_arquivo):
    """Lê apenas o cabeçalho do CSV (sem carregar os dados) e confere se
    as colunas esperadas estão presentes, antes de processar o arquivo
    inteiro. Evita gastar tempo/memória processando um arquivo com
    estrutura já sabidamente incompatível."""
    colunas_reais = conexao.sql(f"""
        SELECT * FROM read_csv(
            '{caminho_csv.as_posix()}', delim=';', decimal_separator=','
        )
        LIMIT 0
    """).columns
    colunas_reais = set(colunas_reais)

    faltando = COLUNAS_ESPERADAS - colunas_reais
    if faltando:
        raise ValueError(
            f"{nome_arquivo}: schema mudou! Colunas faltando: {faltando}"
        )


def ano_ja_carregado(conexao, ano):
    existe_tabela = conexao.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = 'bronze' AND table_name = 'scr_data_raw'
    """).fetchone()[0]

    if existe_tabela == 0:
        return False

    total = conexao.execute(
        "SELECT COUNT(*) FROM bronze.scr_data_raw WHERE ano_arquivo = ?", [ano]
    ).fetchone()[0]
    return total > 0


def baixar_zip_do_ano(ano):
    """Baixa o ZIP do ano com timeout e retry. Se a conexão cair no meio
    do download, o arquivo parcial é descartado antes de tentar de novo,
    evitando processar um ZIP corrompido/incompleto."""
    url = f"https://www.bcb.gov.br/pda/desig/scrdata_{ano}.zip"
    destino = PASTA_TEMP / f"scrdata_{ano}.zip"
    PASTA_TEMP.mkdir(parents=True, exist_ok=True)

    for tentativa in range(1, MAX_TENTATIVAS_DOWNLOAD + 1):
        try:
            print(f"  Baixando {url} (tentativa {tentativa})...")
            resposta = requests.get(
                url, stream=True, timeout=(TIMEOUT_CONEXAO, TIMEOUT_LEITURA)
            )
            resposta.raise_for_status()

            with open(destino, "wb") as arquivo:
                arquivo.writelines(resposta.iter_content(chunk_size=8192))

            return destino, url

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as erro:
            print(f"  Falha no download (tentativa {tentativa}): {erro}")
            if destino.exists():
                destino.unlink()  # descarta arquivo parcial/corrompido

            if tentativa == MAX_TENTATIVAS_DOWNLOAD:
                raise RuntimeError(
                    f"Download do ano {ano} falhou após {MAX_TENTATIVAS_DOWNLOAD} tentativas"
                ) from erro

    raise RuntimeError(f"Download do ano {ano} falhou de forma inesperada")


def processar_ano(conexao, ano):
    if ano_ja_carregado(conexao, ano):
        print(f"Ano {ano}: já carregado anteriormente, pulando.")
        return

    print(f"Ano {ano}: iniciando...")
    caminho_zip, url_fonte = baixar_zip_do_ano(ano)

    with zipfile.ZipFile(caminho_zip) as z:
        nomes_arquivos = sorted(z.namelist())

        for nome_arquivo in nomes_arquivos:
            z.extract(nome_arquivo, PASTA_TEMP)
            caminho_csv = PASTA_TEMP / nome_arquivo
            validar_schema_csv(conexao, caminho_csv, nome_arquivo)
            timestamp_coleta = datetime.now(timezone.utc).isoformat()

            existe_tabela = conexao.execute("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_schema = 'bronze' AND table_name = 'scr_data_raw'
            """).fetchone()[0]

            if existe_tabela == 0:
                conexao.execute(f"""
                    CREATE TABLE bronze.scr_data_raw AS
                    SELECT *,
                        CAST('{ano}' AS INTEGER) AS ano_arquivo,
                        CAST('{nome_arquivo}' AS VARCHAR) AS arquivo_origem,
                        CAST('{url_fonte}' AS VARCHAR) AS url_fonte,
                        CAST('{timestamp_coleta}' AS VARCHAR) AS timestamp_coleta
                    FROM read_csv('{caminho_csv.as_posix()}', delim=';', decimal_separator=',')
                    LIMIT 0
                """)

            conexao.execute(f"""
                INSERT INTO bronze.scr_data_raw
                SELECT *,
                    {ano} AS ano_arquivo,
                    '{nome_arquivo}' AS arquivo_origem,
                    '{url_fonte}' AS url_fonte,
                    '{timestamp_coleta}' AS timestamp_coleta
                FROM read_csv('{caminho_csv.as_posix()}', delim=';', decimal_separator=',')
            """)

            linhas = conexao.execute(
                "SELECT COUNT(*) FROM bronze.scr_data_raw WHERE arquivo_origem = ?",
                [nome_arquivo],
            ).fetchone()[0]
            print(f"    {nome_arquivo}: {linhas} linhas inseridas")

            caminho_csv.unlink()  # apaga o CSV extraído para economizar espaço em disco

    caminho_zip.unlink()  # apaga o zip do ano, já processado
    print(f"Ano {ano}: concluído.\n")


if __name__ == "__main__":
    conexao = duckdb.connect(CAMINHO_BANCO)
    conexao.execute("CREATE SCHEMA IF NOT EXISTS bronze;")

    for ano in range(ANO_INICIAL, ANO_FINAL + 1):
        processar_ano(conexao, ano)

    total_geral = conexao.execute(
        "SELECT COUNT(*) FROM bronze.scr_data_raw"
    ).fetchone()[0]
    print(f"\nTOTAL GERAL na tabela bronze.scr_data_raw: {total_geral}")

    conexao.close()
