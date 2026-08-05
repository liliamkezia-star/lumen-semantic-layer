import time
from datetime import datetime, timezone

import duckdb
import requests

CAMINHO_BANCO = "lumen.duckdb"
TIMEOUT_SEGUNDOS = 30
MAX_TENTATIVAS = 4

URL_LOCALIDADES = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
URL_POPULACAO = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/-11/"
    "variaveis/9324?localidades=N3[all]"
)


def buscar_com_retry(url, nome_fonte):
    """Chama a URL com timeout e tenta novamente em caso de falha de
    rede, com espera crescente entre tentativas (backoff exponencial)."""
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        try:
            resposta = requests.get(url, timeout=TIMEOUT_SEGUNDOS)
            resposta.raise_for_status()
            return resposta
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as erro:
            espera = 2 ** (tentativa - 1)
            print(f"  {nome_fonte}: tentativa {tentativa} falhou ({erro}), esperando {espera}s...")
            time.sleep(espera)

    raise RuntimeError(f"{nome_fonte}: falhou após {MAX_TENTATIVAS} tentativas")


def validar_schema_localidades(dados):
    """Verifica se a resposta mantém a estrutura esperada: lista de
    estados, cada um com id, sigla, nome e um objeto regiao com id e nome."""
    if not isinstance(dados, list):
        raise TypeError(f"Localidades: esperava uma lista, recebeu {type(dados)}")

    if len(dados) == 0:
        raise ValueError("Localidades: resposta vazia")

    primeiro = dados[0]
    chaves_esperadas = {"id", "sigla", "nome", "regiao"}
    chaves_recebidas = set(primeiro.keys())

    if chaves_esperadas - chaves_recebidas:
        raise ValueError(
            f"Localidades: schema mudou! Faltando chaves: {chaves_esperadas - chaves_recebidas}"
        )

    if "id" not in primeiro["regiao"] or "nome" not in primeiro["regiao"]:
        raise ValueError("Localidades: schema de 'regiao' mudou")


def validar_schema_populacao(dados):
    """Verifica a estrutura aninhada da resposta de Agregados/SIDRA:
    lista de itens, cada um com 'resultados', cada resultado com 'series',
    cada série com 'localidade' e um dicionário 'serie' (ano -> valor)."""
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
        linhas.append({
            "id_uf": estado["id"],
            "sigla_uf": estado["sigla"],
            "nome_uf": estado["nome"],
            "id_regiao": estado["regiao"]["id"],
            "nome_regiao": estado["regiao"]["nome"],
            "url_fonte": url,
            "timestamp_coleta": timestamp_coleta,
        })
    return linhas


def montar_linhas_populacao(dados, url):
    """A resposta da API de Agregados vem em formato aninhado (série >
    resultado > série de anos > valor). Essa função desmonta essa estrutura
    em linhas simples: uma por UF, por ano."""
    timestamp_coleta = datetime.now(timezone.utc).isoformat()
    linhas = []

    for item in dados:
        for resultado in item["resultados"]:
            for serie in resultado["series"]:
                localidade = serie["localidade"]
                for ano, valor in serie["serie"].items():
                    linhas.append({
                        "id_uf": localidade["id"],
                        "nome_uf": localidade["nome"],
                        "ano": ano,
                        "populacao_estimada": valor,
                        "url_fonte": url,
                        "timestamp_coleta": timestamp_coleta,
                    })
    return linhas


if __name__ == "__main__":
    dados_localidades, url_loc = buscar_localidades()
    linhas_localidades = montar_linhas_localidades(dados_localidades, url_loc)

    dados_populacao, url_pop = buscar_populacao()
    linhas_populacao = montar_linhas_populacao(dados_populacao, url_pop)

    print(f"\nLinhas de localidades: {len(linhas_localidades)}")
    print(f"Linhas de população: {len(linhas_populacao)}")

    conexao = duckdb.connect(CAMINHO_BANCO)
    conexao.execute("CREATE SCHEMA IF NOT EXISTS bronze;")

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS bronze.ibge_localidades_raw (
            id_uf INTEGER,
            sigla_uf VARCHAR,
            nome_uf VARCHAR,
            id_regiao INTEGER,
            nome_regiao VARCHAR,
            url_fonte VARCHAR,
            timestamp_coleta VARCHAR
        );
    """)
    conexao.executemany(
        """
        INSERT INTO bronze.ibge_localidades_raw
        VALUES ($id_uf, $sigla_uf, $nome_uf, $id_regiao, $nome_regiao, $url_fonte, $timestamp_coleta)
        """,
        linhas_localidades,
    )

    conexao.execute("""
        CREATE TABLE IF NOT EXISTS bronze.ibge_populacao_raw (
            id_uf INTEGER,
            nome_uf VARCHAR,
            ano VARCHAR,
            populacao_estimada VARCHAR,
            url_fonte VARCHAR,
            timestamp_coleta VARCHAR
        );
    """)
    conexao.executemany(
        """
        INSERT INTO bronze.ibge_populacao_raw
        VALUES ($id_uf, $nome_uf, $ano, $populacao_estimada, $url_fonte, $timestamp_coleta)
        """,
        linhas_populacao,
    )

    total_localidades = conexao.execute(
        "SELECT COUNT(*) FROM bronze.ibge_localidades_raw"
    ).fetchone()[0]
    total_populacao = conexao.execute(
        "SELECT COUNT(*) FROM bronze.ibge_populacao_raw"
    ).fetchone()[0]

    print(f"\nTotal na tabela localidades: {total_localidades}")
    print(f"Total na tabela populacao: {total_populacao}")

    conexao.close()
