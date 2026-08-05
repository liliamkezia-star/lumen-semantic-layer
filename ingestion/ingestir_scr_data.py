import zipfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import requests

ANO_INICIAL = 2015
ANO_FINAL = 2025  # 2026 tratado separadamente por ser ano corrente/incompleto
CAMINHO_BANCO = "lumen.duckdb"
PASTA_TEMP = Path("ingestion/temp_scr")


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
    url = f"https://www.bcb.gov.br/pda/desig/scrdata_{ano}.zip"
    destino = PASTA_TEMP / f"scrdata_{ano}.zip"
    PASTA_TEMP.mkdir(parents=True, exist_ok=True)

    print(f"  Baixando {url} ...")
    resposta = requests.get(url, stream=True)
    resposta.raise_for_status()

    with open(destino, "wb") as arquivo:
        for pedaco in resposta.iter_content(chunk_size=8192):
            arquivo.write(pedaco)

    return destino, url


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
