"""Catálogo do que é perguntável: medidas certificadas e cortes válidos.

Lido do modelo semântico ao vivo, nunca de uma cópia local — se uma
medida for corrigida ou removida no `lumen_semantico`, o agente enxerga
a mudança na execução seguinte, sem alteração de código. É a mesma
razão pela qual o dashboard consome medidas certificadas em vez de
recalcular: existe uma definição só.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from .fabric import executar_dax


def _sem_acento(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")

# Cortes expostos ao agente. É deliberadamente uma curadoria, não um
# espelho de todas as colunas do modelo: cada entrada aqui é um eixo que
# faz sentido em uma pergunta de negócio. Acrescentar um corte é uma
# decisão consciente, não um efeito colateral de mudança no schema.
CORTES: dict[str, tuple[str, str]] = {
    "competencia": ("dim_calendario", "ano_mes"),
    "ano": ("dim_calendario", "ano"),
    "trimestre": ("dim_calendario", "trimestre_label"),
    "modalidade": ("dim_modalidade", "modalidade"),
    "submodalidade": ("dim_modalidade", "submodalidade"),
    "origem": ("dim_modalidade", "origem"),
    "indexador": ("dim_modalidade", "indexador"),
    "uf": ("dim_uf", "nome_uf"),
    "sigla_uf": ("dim_uf", "sigla_uf"),
    "regiao": ("dim_uf", "nome_regiao"),
    "cliente": ("dim_segmento", "cliente"),
    "segmento": ("dim_segmento", "segmento"),
    "porte": ("dim_segmento", "porte"),
    "ocupacao": ("dim_segmento", "cnae_ocupacao"),
}


@dataclass(frozen=True)
class Medida:
    nome: str
    tabela: str
    descricao: str = ""
    formato: str = ""

    def referencia_dax(self) -> str:
        return f"[{self.nome}]"


@dataclass
class Catalogo:
    medidas: dict[str, Medida] = field(default_factory=dict)

    def nomes_de_medidas(self) -> list[str]:
        return sorted(self.medidas)

    def validar_medida(self, nome: str) -> Medida:
        if nome in self.medidas:
            return self.medidas[nome]
        raise MedidaDesconhecida(nome, self.sugerir_medidas(nome))

    def sugerir_medidas(self, procurado: str, limite: int = 8) -> list[str]:
        """Sugestões por subpalavra — o modelo erra o nome exato com
        frequência ('inadimplência PF' em vez de 'Taxa de Inadimplência PF')
        e uma lista de 73 nomes não cabe numa mensagem de erro útil.

        Compara sem acento e aceita termos de duas letras: são justamente
        'PF' e 'PJ' que separam as medidas mais parecidas do catálogo.
        """
        termos = [t for t in _sem_acento(procurado).split() if len(t) >= 2]
        pontuados = [
            (sum(t in _sem_acento(nome) for t in termos), nome) for nome in self.medidas
        ]
        melhores = [nome for pontos, nome in sorted(pontuados, reverse=True) if pontos]
        return melhores[:limite] or self.nomes_de_medidas()[:limite]


class MedidaDesconhecida(ValueError):
    def __init__(self, nome: str, sugestoes: list[str]) -> None:
        self.nome = nome
        self.sugestoes = sugestoes
        super().__init__(
            f"'{nome}' não é uma medida certificada. "
            f"Medidas parecidas: {', '.join(sugestoes)}."
        )


class CorteDesconhecido(ValueError):
    def __init__(self, corte: str) -> None:
        super().__init__(
            f"'{corte}' não é um corte disponível. "
            f"Cortes válidos: {', '.join(sorted(CORTES))}."
        )


class ValorDesconhecido(ValueError):
    def __init__(self, corte: str, valor: Any, disponiveis: list[Any]) -> None:
        amostra = ", ".join(str(v) for v in disponiveis[:10])
        reticencias = "..." if len(disponiveis) > 10 else ""
        super().__init__(
            f"'{valor}' não existe no corte '{corte}'. "
            f"Valores disponíveis: {amostra}{reticencias}"
        )


@lru_cache(maxsize=1)
def carregar() -> Catalogo:
    """Lê as medidas certificadas visíveis do modelo."""
    linhas = executar_dax("EVALUATE FILTER ( INFO.VIEW.MEASURES (), NOT [IsHidden] )")
    medidas = {}
    for linha in linhas:
        nome = linha["[Name]"]
        medidas[nome] = Medida(
            nome=nome,
            tabela=linha.get("[Table]") or "",
            descricao=linha.get("[Description]") or "",
            formato=linha.get("[FormatString]") or "",
        )
    return Catalogo(medidas=medidas)


@lru_cache(maxsize=32)
def valores_do_corte(corte: str) -> tuple[Any, ...]:
    """Valores existentes de um corte, lidos do modelo.

    São eles que validam o que o agente pede: um valor só chega ao DAX
    se for idêntico a um que já existe aqui. Isso substitui qualquer
    tentativa de sanitizar string — não há o que escapar se o conjunto
    de valores aceitos é fechado.
    """
    if corte not in CORTES:
        raise CorteDesconhecido(corte)
    tabela, coluna = CORTES[corte]
    linhas = executar_dax(
        f"EVALUATE FILTER ( VALUES ( {tabela}[{coluna}] ), "
        f"NOT ISBLANK ( {tabela}[{coluna}] ) ) ORDER BY {tabela}[{coluna}]"
    )
    chave = f"{tabela}[{coluna}]"
    return tuple(linha[chave] for linha in linhas)


def validar_valor(corte: str, valor: Any) -> Any:
    disponiveis = valores_do_corte(corte)
    if valor in disponiveis:
        return valor
    # O modelo costuma mandar número como texto ("2025" em vez de 2025).
    for candidato in disponiveis:
        if str(candidato) == str(valor):
            return candidato
    raise ValorDesconhecido(corte, valor, list(disponiveis))
