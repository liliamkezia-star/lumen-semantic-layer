import time
from datetime import datetime, timezone

import duckdb
import requests

SERIES_SGS = {
    "selic_diaria": 11,
    "selic_meta": 432,
    "ipca_mensal": 433,
    "saldo_credito_total": 20539,
    "credito_pib": 20622,
    "inadimplencia_total": 21082,
    "spread_medio_total": 20783,
    "concessoes_pf_total": 20633,
    "concessoes_pj_total": 20632,
    "endividamento_familias": 29037,
}

DATA_INICIAL_COMPLETA = "01/01/2015"
DATA_INICIAL_JANELA_10_ANOS = "05/08/2016"
DATA_FINAL = "04/08/2026"
CAMINHO_BANCO = "lumen.duckdb"
MAX_TENTATIVAS = 4


def chamar_api(codigo, data_inicial):
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
    parametros = {
        "formato": "json",
        "dataInicial": data_inicial,
        "dataFinal": DATA_FINAL,
    }
    resposta = requests.get(url, params=parametros)
    return resposta, url


def chamar_api_com_retry(codigo, data_inicial):
    """Tenta chamar a API várias vezes, esperando mais tempo a cada falha
    (backoff exponencial: 1s, 2s, 4s, 8s...)."""
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        resposta, url = chamar_api(codigo, data_inicial)

        if resposta.status_code == 200:
            try:
                resposta.json()
                return resposta, url
            except requests.exceptions.JSONDecodeError:
                pass

        if resposta.status_code == 406:
            return resposta, url

        espera = 2 ** (tentativa - 1)
        motivo = "JSON inválido" if resposta.status_code == 200 else f"status {resposta.status_code}"
        print(f"  tentativa {tentativa} falhou ({motivo}), esperando {espera}s...")
        time.sleep(espera)

    raise RuntimeError(f"Falhou após {MAX_TENTATIVAS} tentativas para código {codigo}")


def validar_schema_resposta(dados, nome_serie):
    """Verifica se a resposta da API mantém a estrutura esperada
    (lista de objetos com as chaves 'data' e 'valor'). Interrompe o
    processo se a fonte mudou o formato, em vez de inserir dado
    incompleto ou errado silenciosamente."""
    if not isinstance(dados, list):
        raise ValueError(
            f"{nome_serie}: esperava uma lista, recebeu {type(dados)}"
        )

    if len(dados) == 0:
        raise ValueError(f"{nome_serie}: resposta vazia, sem registros")

    primeiro_registro = dados[0]
    chaves_esperadas = {"data", "valor"}
    chaves_recebidas = set(primeiro_registro.keys())

    if chaves_recebidas != chaves_esperadas:
        raise ValueError(
            f"{nome_serie}: schema mudou! Esperado {chaves_esperadas}, "
            f"recebido {chaves_recebidas}"
        )


def buscar_serie(nome, codigo):
    resposta, url = chamar_api_com_retry(codigo, DATA_INICIAL_COMPLETA)

    if resposta.status_code == 406:
        print(f"{nome}: periodicidade diária detectada, ajustando janela...")
        resposta, url = chamar_api_com_retry(codigo, DATA_INICIAL_JANELA_10_ANOS)

    resposta.raise_for_status()
    dados = resposta.json()
    validar_schema_resposta(dados, nome)
    print(f"{nome} (código {codigo}): {len(dados)} registros")
    return dados, url


def montar_linhas(nome, codigo, dados, url):
    """Transforma a resposta da API em linhas prontas para inserir no banco,
    já incluindo os metadados de coleta. O timestamp_coleta é o que permite,
    na camada Silver, identificar a versão mais recente de cada dado sem
    que a Bronze precise apagar coletas anteriores."""
    timestamp_coleta = datetime.now(timezone.utc).isoformat()
    linhas = []
    for registro in dados:
        linhas.append({
            "nome_serie": nome,
            "codigo_serie": codigo,
            "data_referencia": registro["data"],
            "valor": registro["valor"],
            "url_fonte": url,
            "timestamp_coleta": timestamp_coleta,
        })
    return linhas


if __name__ == "__main__":
    todas_as_linhas = []

    for nome, codigo in SERIES_SGS.items():
        dados, url = buscar_serie(nome, codigo)
        todas_as_linhas.extend(montar_linhas(nome, codigo, dados, url))

    print(f"\nTotal de linhas a inserir: {len(todas_as_linhas)}")

    conexao = duckdb.connect(CAMINHO_BANCO)
    conexao.execute("CREATE SCHEMA IF NOT EXISTS bronze;")
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS bronze.sgs_series_raw (
            nome_serie VARCHAR,
            codigo_serie INTEGER,
            data_referencia VARCHAR,
            valor VARCHAR,
            url_fonte VARCHAR,
            timestamp_coleta VARCHAR
        );
    """)

    # Bronze é append-only: nunca apagamos dados existentes (ver ADR-003).
    conexao.executemany(
        """
        INSERT INTO bronze.sgs_series_raw
        VALUES ($nome_serie, $codigo_serie, $data_referencia, $valor, $url_fonte, $timestamp_coleta)
        """,
        todas_as_linhas,
    )

    total_na_tabela = conexao.execute(
        "SELECT COUNT(*) FROM bronze.sgs_series_raw"
    ).fetchone()[0]
    print(f"Total de linhas agora na tabela: {total_na_tabela}")

    conexao.close()
