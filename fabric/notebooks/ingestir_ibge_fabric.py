import time
from datetime import datetime, timezone

import requests
from pyspark.sql import Row

TIMEOUT_SEGUNDOS = 30
MAX_TENTATIVAS = 4

URL_LOCALIDADES = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
URL_POPULACAO = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/-11/"
    "variaveis/9324?localidades=N3[all]"
)


def buscar_com_retry(url, nome_fonte):
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            resposta = requests.get(url, timeout=TIMEOUT_SEGUNDOS)
            resposta.raise_for_status()
            return resposta
        except requests.exceptions.HTTPError as erro:
            status = erro.response.status_code if erro.response is not None else None
            if status is not None and 400 <= status < 500:
                print(f"{nome_fonte}: erro {status} (problema na requisição, não em retry): {erro}")
                raise
            espera = 2 ** (tentativa - 1)
            print(f"{nome_fonte}: tentativa {tentativa} falhou (erro {status}), esperando {espera}s...")
            time.sleep(espera)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as erro:
            espera = 2 ** (tentativa - 1)
            print(f"{nome_fonte}: tentativa {tentativa} falhou ({erro}), esperando {espera}s...")
            time.sleep(espera)
    raise RuntimeError(f"{nome_fonte}: falhou após {MAX_TENTATIVAS} tentativas")


def validar_schema_localidades(dados):
    if not isinstance(dados, list) or len(dados) == 0:
        raise ValueError("Localidades: resposta vazia ou não é lista")
    primeiro = dados[0]
    chaves_esperadas = {"id", "sigla", "nome", "regiao"}
    if chaves_esperadas - set(primeiro.keys()):
        raise ValueError(f"Localidades: schema mudou! Faltando: {chaves_esperadas - set(primeiro.keys())}")
    if "id" not in primeiro["regiao"] or "nome" not in primeiro["regiao"]:
        raise ValueError("Localidades: schema de 'regiao' mudou")


def validar_schema_populacao(dados):
    if not isinstance(dados, list) or len(dados) == 0:
        raise ValueError("População: resposta vazia ou formato inesperado")
    try:
        primeiro_resultado = dados[0]["resultados"][0]
        primeira_serie = primeiro_resultado["series"][0]
        _ = primeira_serie["localidade"]["id"]
        _ = primeira_serie["localidade"]["nome"]
        _ = primeira_serie["serie"]
    except (KeyError, IndexError) as erro:
        raise ValueError(f"População: schema mudou! Estrutura inesperada: {erro}") from erro


def buscar_localidades():
    resposta = buscar_com_retry(URL_LOCALIDADES, "Localidades")
    dados = resposta.json()
    validar_schema_localidades(dados)
    print(f"Localidades: {len(dados)} estados encontrados")
    return dados, URL_LOCALIDADES


def buscar_populacao():
    resposta = buscar_com_retry(URL_POPULACAO, "População")
    dados = resposta.json()
    validar_schema_populacao(dados)
    print("População: dados recebidos")
    return dados, URL_POPULACAO


def montar_linhas_localidades(dados, url):
    timestamp_coleta = datetime.now(timezone.utc).isoformat()
    linhas = []
    for estado in dados:
        linhas.append(Row(
            id_uf=estado["id"],
            sigla_uf=estado["sigla"],
            nome_uf=estado["nome"],
            id_regiao=estado["regiao"]["id"],
            nome_regiao=estado["regiao"]["nome"],
            url_fonte=url,
            timestamp_coleta=timestamp_coleta,
        ))
    return linhas


def montar_linhas_populacao(dados, url):
    timestamp_coleta = datetime.now(timezone.utc).isoformat()
    linhas = []
    for item in dados:
        for resultado in item["resultados"]:
            for serie in resultado["series"]:
                localidade = serie["localidade"]
                for ano, valor in serie["serie"].items():
                    linhas.append(Row(
                        id_uf=localidade["id"],
                        nome_uf=localidade["nome"],
                        ano=ano,
                        populacao_estimada=valor,
                        url_fonte=url,
                        timestamp_coleta=timestamp_coleta,
                    ))
    return linhas


dados_localidades, url_loc = buscar_localidades()
linhas_localidades = montar_linhas_localidades(dados_localidades, url_loc)

dados_populacao, url_pop = buscar_populacao()
linhas_populacao = montar_linhas_populacao(dados_populacao, url_pop)

print(f"Linhas de localidades: {len(linhas_localidades)}")
print(f"Linhas de população: {len(linhas_populacao)}")

spark.sql("CREATE SCHEMA IF NOT EXISTS bronze")

df_localidades = spark.createDataFrame(linhas_localidades)
df_localidades.write.format("delta").mode("append").saveAsTable("bronze.ibge_localidades_raw")

df_populacao = spark.createDataFrame(linhas_populacao)
df_populacao.write.format("delta").mode("append").saveAsTable("bronze.ibge_populacao_raw")

total_localidades = spark.sql("SELECT COUNT(*) AS total FROM bronze.ibge_localidades_raw").collect()[0]["total"]
total_populacao = spark.sql("SELECT COUNT(*) AS total FROM bronze.ibge_populacao_raw").collect()[0]["total"]
print(f"Total na tabela localidades: {total_localidades}")
print(f"Total na tabela populacao: {total_populacao}")
