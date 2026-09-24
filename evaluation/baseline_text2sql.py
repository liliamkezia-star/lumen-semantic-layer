"""Baseline text-to-SQL: o mesmo modelo do agente, escrevendo SQL na Gold.

É o contraponto do benchmark (Sprint 12). A única diferença para o agente
é a camada semântica: aqui o modelo recebe a documentação das tabelas
(gerada do `schema.yml` do dbt, a mesma que um analista consultaria) e
escreve a própria consulta. As regras gerais — não inventar número,
recusar o que não sabe, separar dado de leitura — são as mesmas do
agente, para a comparação isolar só a camada.

Cada consulta passa por `sql_seguro.validar_sql` antes de rodar.
"""

import contextvars
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import pyodbc
import yaml
from google import genai
from google.genai import errors, types

from agent import ritmo
from agent.agente import ChaveAusente, ModelosIndisponiveis
from evaluation.sql_gold import executar_sql
from evaluation.sql_seguro import SqlRecusado, validar_sql

MODELO = "gemma-4-26b-a4b-it"  # o mesmo fixado na avaliação do agente
LIMITE_LINHAS = 200
SCHEMA_DBT = Path(__file__).parent.parent / "transform" / "dbt" / "models" / "marts" / "schema.yml"

_executadas: contextvars.ContextVar[list[str]] = contextvars.ContextVar("executadas")


def consultar_sql(consulta: str) -> str:
    """Executa uma consulta SQL de leitura sobre as tabelas da Gold.

    Use para obter QUALQUER número. Nunca responda com um valor que não
    tenha vindo desta ferramenta.

    Args:
        consulta: uma única instrução SELECT em T-SQL (use TOP, não LIMIT),
            sobre as tabelas gold.fato_* e gold.dim_*.
    """
    ritmo.espacar()
    try:
        validar_sql(consulta)
    except SqlRecusado as erro:
        return f"Consulta recusada: {erro}"

    registro = _executadas.get(None)
    if registro is not None:
        registro.append(consulta)
    try:
        linhas = executar_sql(consulta, limite=LIMITE_LINHAS)
    except pyodbc.Error as erro:
        return f"Erro do banco: {str(erro)[:400]}"
    if not linhas:
        return "A consulta não retornou linhas."
    aviso = f" (cortado em {LIMITE_LINHAS} linhas)" if len(linhas) == LIMITE_LINHAS else ""
    return json.dumps({"linhas": linhas}, ensure_ascii=False, default=str) + aviso


def _documentacao_das_tabelas() -> str:
    """Documentação das tabelas da Gold, gerada do schema.yml do dbt."""
    modelos = yaml.safe_load(SCHEMA_DBT.read_text(encoding="utf-8"))["models"]
    partes = []
    for modelo in modelos:
        colunas = "\n".join(
            f"  - {c['name']}: {' '.join((c.get('description') or '').split())}"
            for c in modelo.get("columns", [])
        )
        descricao = " ".join((modelo.get("description") or "").split())
        partes.append(f"gold.{modelo['name']} — {descricao}\n{colunas}")
    return "\n\n".join(partes)


def _instrucoes() -> str:
    return f"""Você é um analista que responde perguntas sobre dados públicos de crédito \
do Banco Central (SCR.data e SGS) e do IBGE, consultando um banco SQL.

Responda em português do Brasil.

REGRA CENTRAL, INEGOCIÁVEL: todo número que você escrever tem que ter vindo de uma \
chamada a `consultar_sql` feita nesta conversa. Você não sabe nenhum valor de cor. \
Se não consultou, não afirma. Um valor que você já trouxe de uma consulta em pergunta \
anterior desta conversa pode ser citado de novo; qualquer valor novo exige consulta.

Se a pergunta não puder ser respondida com as tabelas disponíveis, diga isso \
claramente. Recusar bem faz parte do trabalho; inventar uma aproximação, não.

Separe o dado (os números, dizendo a que recorte e período se referem) da sua \
leitura, e deixe explícito que a leitura é interpretação. Nunca afirme causalidade \
entre as séries macroeconômicas do SGS e os dados de crédito do SCR.

O banco é o SQL endpoint do Microsoft Fabric (dialeto T-SQL): use TOP em vez de \
LIMIT e sempre o schema gold. Se uma consulta der erro, leia a mensagem e corrija.

TABELAS DISPONÍVEIS:

{_documentacao_das_tabelas()}"""


@dataclass
class RespostaBaseline:
    texto: str
    consultas: list[str] = field(default_factory=list)


class BaselineTextToSql:
    """Uma conversa com o baseline, com histórico de texto como o agente."""

    def __init__(self, modelo: str = MODELO) -> None:
        chave = os.getenv("GEMINI_API_KEY")
        if not chave:
            raise ChaveAusente("GEMINI_API_KEY não definida (ver README).")
        self.cliente = genai.Client(
            api_key=chave,
            http_options=types.HttpOptions(
                timeout=90_000, retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )
        self.modelo_em_uso = modelo
        self.configuracao = types.GenerateContentConfig(
            system_instruction=_instrucoes(),
            tools=[consultar_sql],
            temperature=0,
            # o mesmo teto do agente: comparação justa de "tentativas"
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                maximum_remote_calls=8
            ),
        )
        self.historico: list[types.Content] = []

    def perguntar(self, pergunta: str) -> RespostaBaseline:
        executadas: list[str] = []
        marca = _executadas.set(executadas)
        try:
            conversa = self.cliente.chats.create(
                model=self.modelo_em_uso, config=self.configuracao, history=list(self.historico)
            )
            try:
                resposta = conversa.send_message(pergunta)
            except errors.ServerError as erro:
                raise ModelosIndisponiveis(f"{self.modelo_em_uso}: {str(erro)[:80]}") from erro
            except errors.ClientError as erro:
                if erro.code != 429:
                    raise
                raise ModelosIndisponiveis(f"{self.modelo_em_uso}: cota esgotada") from erro
        finally:
            _executadas.reset(marca)

        texto = (resposta.text or "").strip()
        self.historico.extend(
            [
                types.Content(role="user", parts=[types.Part(text=pergunta)]),
                types.Content(role="model", parts=[types.Part(text=texto)]),
            ]
        )
        return RespostaBaseline(texto=texto, consultas=executadas)


def main() -> None:
    """Teste manual: python -m evaluation.baseline_text2sql "pergunta" """
    import sys

    from dotenv import load_dotenv

    load_dotenv()
    inicio = time.monotonic()
    resposta = BaselineTextToSql().perguntar(" ".join(sys.argv[1:]))
    print(resposta.texto)
    print(f"\n[{time.monotonic() - inicio:.0f} s]")
    for consulta in resposta.consultas:
        print("\nSQL:", consulta)


if __name__ == "__main__":
    main()
