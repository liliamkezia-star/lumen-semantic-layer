from datetime import datetime, timezone

import duckdb
import requests

CAMINHO_BANCO = "lumen.duckdb"

URL_LOCALIDADES = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
URL_POPULACAO = (
    "https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/-11/"
    "variaveis/9324?localidades=N3[all]"
)


def buscar_localidades():
    resposta = requests.get(URL_LOCALIDADES)
    resposta.raise_for_status()
    dados = resposta.json()
    print(f"Localidades: {len(dados)} estados encontrados")
    return dados, URL_LOCALIDADES


def buscar_populacao():
    resposta = requests.get(URL_POPULACAO)
    resposta.raise_for_status()
    dados = resposta.json()
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
