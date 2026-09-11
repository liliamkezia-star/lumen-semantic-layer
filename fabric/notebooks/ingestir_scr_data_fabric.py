import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
from pyspark.sql.functions import col, lit, regexp_replace

ANO_INICIAL = 2015
ANO_FINAL = 2025

PASTA_TEMP_LOCAL = Path("/tmp/scr_data")
CAMINHO_LAKEHOUSE_FILES = "Files/scr_data_tmp"

TIMEOUT_CONEXAO = 10
TIMEOUT_LEITURA = 60
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

COLUNAS_DECIMAIS = {
    "a_vencer_ate_90_dias", "a_vencer_de_91_ate_360_dias",
    "a_vencer_de_361_ate_1080_dias", "a_vencer_de_1081_ate_1800_dias",
    "a_vencer_de_1801_ate_5400_dias", "a_vencer_acima_de_5400_dias",
    "carteira_a_vencer", "vencido_de_15_ate_90_dias", "vencido_acima_de_90_dias",
    "carteira_vencida", "carteira_ativa", "carteira_inadimplencia",
    "ativo_problematico",
}
COLUNA_INTEIRA = "numero_de_operacoes"


def baixar_zip_do_ano(ano):
    url = f"https://www.bcb.gov.br/pda/desig/scrdata_{ano}.zip"
    destino = PASTA_TEMP_LOCAL / f"scrdata_{ano}.zip"
    PASTA_TEMP_LOCAL.mkdir(parents=True, exist_ok=True)

    for tentativa in range(1, MAX_TENTATIVAS_DOWNLOAD + 1):
        try:
            print(f"Baixando {url} (tentativa {tentativa})...")
            resposta = requests.get(url, stream=True, timeout=(TIMEOUT_CONEXAO, TIMEOUT_LEITURA))
            resposta.raise_for_status()
            with open(destino, "wb") as arquivo:
                arquivo.writelines(resposta.iter_content(chunk_size=8192))
            return destino, url
        except requests.exceptions.HTTPError as erro:
            status = erro.response.status_code if erro.response is not None else None
            if destino.exists():
                destino.unlink()
            if status is not None and 400 <= status < 500:
                print(f"Ano {ano}: erro {status} (arquivo indisponível na fonte, sem retry)")
                raise
            print(f"Falha no download (tentativa {tentativa}, erro {status})")
            if tentativa == MAX_TENTATIVAS_DOWNLOAD:
                raise RuntimeError(f"Download do ano {ano} falhou após {MAX_TENTATIVAS_DOWNLOAD} tentativas") from erro
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as erro:
            if destino.exists():
                destino.unlink()
            print(f"Falha no download (tentativa {tentativa}): {erro}")
            if tentativa == MAX_TENTATIVAS_DOWNLOAD:
                raise RuntimeError(f"Download do ano {ano} falhou após {MAX_TENTATIVAS_DOWNLOAD} tentativas") from erro

    raise RuntimeError(f"Download do ano {ano} falhou de forma inesperada")


def validar_schema_csv(caminho_csv, nome_arquivo):
    with open(caminho_csv, encoding="utf-8-sig") as f:
        cabecalho = f.readline().strip()
    colunas_reais = set(cabecalho.split(";"))
    faltando = COLUNAS_ESPERADAS - colunas_reais
    if faltando:
        raise ValueError(f"{nome_arquivo}: schema mudou! Colunas faltando: {faltando}")


def ano_ja_carregado(ano):
    existe_tabela = spark.sql("SHOW TABLES IN bronze").filter("tableName = 'scr_data_raw'").count() > 0
    if not existe_tabela:
        return False
    total = spark.sql(f"SELECT COUNT(*) AS total FROM bronze.scr_data_raw WHERE ano_arquivo = {ano}").collect()[0]["total"]
    return total > 0


def processar_ano(ano):
    if ano_ja_carregado(ano):
        print(f"Ano {ano}: já carregado anteriormente, pulando.")
        return

    print(f"Ano {ano}: iniciando...")
    caminho_zip, url_fonte = baixar_zip_do_ano(ano)

    with zipfile.ZipFile(caminho_zip) as z:
        nomes_arquivos = sorted(z.namelist())

        for nome_arquivo in nomes_arquivos:
            z.extract(nome_arquivo, PASTA_TEMP_LOCAL)
            caminho_csv_local = PASTA_TEMP_LOCAL / nome_arquivo
            validar_schema_csv(caminho_csv_local, nome_arquivo)
            timestamp_coleta = datetime.now(timezone.utc).isoformat()

            caminho_lakehouse = f"{CAMINHO_LAKEHOUSE_FILES}/{nome_arquivo}"
            notebookutils.fs.cp(f"file:{caminho_csv_local}", caminho_lakehouse, True)

            df = spark.read.csv(
                caminho_lakehouse, sep=";", header=True, encoding="UTF-8"
            )

            for coluna in COLUNAS_DECIMAIS:
                df = df.withColumn(coluna, regexp_replace(col(coluna), ",", ".").cast("double"))
            df = df.withColumn(COLUNA_INTEIRA, col(COLUNA_INTEIRA).cast("int"))

            df = (
                df.withColumn("ano_arquivo", lit(ano).cast("int"))
                .withColumn("arquivo_origem", lit(nome_arquivo))
                .withColumn("url_fonte", lit(url_fonte))
                .withColumn("timestamp_coleta", lit(timestamp_coleta))
            )

            df.write.format("delta").mode("append").saveAsTable("bronze.scr_data_raw")

            linhas = spark.sql(
                f"SELECT COUNT(*) AS total FROM bronze.scr_data_raw WHERE arquivo_origem = '{nome_arquivo}'"
            ).collect()[0]["total"]
            print(f"{nome_arquivo}: {linhas} linhas inseridas")

            caminho_csv_local.unlink()
            notebookutils.fs.rm(caminho_lakehouse, True)

    caminho_zip.unlink()
    print(f"Ano {ano}: concluído.")


spark.sql("CREATE SCHEMA IF NOT EXISTS bronze")

for ano in range(ANO_INICIAL, ANO_FINAL + 1):
    processar_ano(ano)

total_geral = spark.sql("SELECT COUNT(*) AS total FROM bronze.scr_data_raw").collect()[0]["total"]
print(f"TOTAL GERAL na tabela bronze.scr_data_raw: {total_geral}")
