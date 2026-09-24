"""Validação do SQL escrito pelo modelo no baseline text-to-SQL.

O baseline executa SQL que o próprio LLM escreveu. Antes de rodar, cada
consulta é analisada sintaticamente (sqlglot, dialeto T-SQL do SQL
endpoint do Fabric) — não por busca de palavras no texto, que um nome de
coluna ou um comentário engana. Só passa uma instrução única, de leitura,
sobre tabelas do schema `gold`.

O SQL endpoint de um Lakehouse já é somente leitura para as tabelas Delta;
esta validação é a segunda camada, e a que dá uma mensagem de erro útil
para o modelo se corrigir.
"""

import sqlglot
from sqlglot import exp

SCHEMA_PERMITIDO = "gold"
PROIBIDOS = (
    exp.Insert, exp.Update, exp.Delete, exp.Merge, exp.Drop, exp.Create,
    exp.Alter, exp.Command, exp.Into,
)


class SqlRecusado(ValueError):
    pass


def validar_sql(consulta: str) -> str:
    """Devolve a consulta se for uma leitura permitida; senão, levanta
    SqlRecusado com o motivo."""
    try:
        instrucoes = [i for i in sqlglot.parse(consulta, read="tsql") if i is not None]
    except sqlglot.errors.ParseError as erro:
        raise SqlRecusado(f"SQL inválido: {erro}") from erro

    if len(instrucoes) != 1:
        raise SqlRecusado("Envie exatamente uma instrução SQL por consulta.")
    arvore = instrucoes[0]

    if not isinstance(arvore, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise SqlRecusado("Só consultas de leitura (SELECT) são permitidas.")
    for proibido in PROIBIDOS:
        if arvore.find(proibido) is not None:
            raise SqlRecusado("Só consultas de leitura (SELECT) são permitidas.")

    ctes = {cte.alias_or_name.lower() for cte in arvore.find_all(exp.CTE)}
    for tabela in arvore.find_all(exp.Table):
        if tabela.name.lower() in ctes and not tabela.db:
            continue
        if tabela.db.lower() != SCHEMA_PERMITIDO:
            nome = ".".join(p for p in (tabela.db, tabela.name) if p)
            raise SqlRecusado(
                f"Tabela fora do schema permitido: {nome}. "
                f"Use as tabelas {SCHEMA_PERMITIDO}.fato_* e {SCHEMA_PERMITIDO}.dim_*."
            )
    return consulta
