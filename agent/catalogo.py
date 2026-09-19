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


# Medidas expostas ao agente e a unidade em que cada uma vem do modelo.
#
# Duas razões para a lista ser explícita:
#
# 1. O modelo semântico serve também ao dashboard, e metade das medidas
#    visíveis são peças de visual (títulos, rodapés, rótulos de ponta,
#    variantes em texto). Expostas ao agente, elas viram ruído ou erro —
#    `Valor (Contexto Macro)` sem o contexto do gráfico devolve uma média
#    sem sentido entre séries de unidades diferentes.
# 2. O `executeQueries` não devolve o FormatString das medidas (medido:
#    null nas 73), e deduzir a unidade pelo nome errou em oito medidas na
#    primeira versão — `SCR (R$ mi)` saía como "R$ 7,44 Mi" em vez de
#    R$ 7,44 Tri. A unidade tem que ser declarada, não adivinhada.
#
# A existência continua vindo do modelo ao vivo: uma medida listada aqui
# mas removida do `lumen_semantico` some do agente sem mudança de código.
UNIDADES: dict[str, str] = {
    # frações: 0,041 -> 4,10%
    "Taxa de Inadimplência (SCR.data)": "fracao",
    "Taxa de Inadimplência PF": "fracao",
    "Taxa de Inadimplência PJ": "fracao",
    "Taxa de Ativo Problemático": "fracao",
    "Taxa de Carteira Vencida": "fracao",
    "Inadimplência BCB (SGS 21082)": "fracao",
    "Cobertura Nº de Operações": "fracao",
    "% Carteira do Total (Modalidade)": "fracao",
    "Carteira Ativa Δ% a/a": "fracao",
    "Carteira Vencida Δ% a/a": "fracao",
    "Ativo Problemático Δ% a/a": "fracao",
    "IPCA 12 Meses (SGS)": "fracao",  # deflacionamento: ADR-016
    "Carteira Ativa Δ% a/a Real": "fracao",
    # já em pontos percentuais
    "Taxa de Inadimplência Δpp a/a": "pp",
    "Taxa de Inadimplência PF Δpp a/a": "pp",
    "Taxa de Inadimplência PJ Δpp a/a": "pp",
    "Taxa de Ativo Problemático Δpp a/a": "pp",
    "Divergência vs BCB (pp)": "pp",
    "Spread Médio (SGS)": "pp",
    # já em percentual: 56,02 -> 56,02%
    "Divergência SCR vs SGS (Saldo) %": "percentual",
    "Crédito/PIB (SGS)": "percentual",
    "Endividamento das Famílias (SGS)": "percentual",
    "Selic Meta (SGS)": "percentual",
    # reais
    "Carteira Ativa": "reais",
    "Carteira Ativa AA": "reais",
    "Carteira a Vencer": "reais",
    "Carteira Vencida": "reais",
    "Carteira Vencida AA": "reais",
    "Carteira Vencida Δ Absoluto a/a": "reais",
    "Carteira Inadimplência": "reais",
    "Ativo Problemático": "reais",
    "Ativo Problemático AA": "reais",
    "Carteira Ativa Real (R$ da Última Competência)": "reais",
    # séries em milhões de reais
    "SCR (R$ mi)": "reais_milhoes",
    "SGS (R$ mi)": "reais_milhoes",
    "Saldo Crédito BCB (SGS 20539)": "reais_milhoes",
    "Concessões PF (SGS)": "reais_milhoes",
    "Concessões PJ (SGS)": "reais_milhoes",
    # demais
    "Número de Operações": "contagem",
    "Linhas do Fato": "contagem",
    "Defasagem SCR vs SGS (meses)": "meses",
    "Última Competência com Crédito": "data",
    "Velocidade da Deterioração": "numero",
}

# Fora do agente de propósito, e não por esquecimento:
# - `Taxa de Inadimplência (dez/2024)` e `(dez/2025)`: o nome promete uma
#   data fixa que a medida não tem desde a ADR-014. Para o agente, a forma
#   correta é `Taxa de Inadimplência (SCR.data)` com filtro de competência.
# - `Valor (Contexto Macro)`: só tem sentido dentro do gráfico de pequenos
#   múltiplos, com a série já filtrada.
# - `Carteira (R$ Bi) · Matriz` e `Competência Selecionada`: duplicam
#   medidas expostas, em outra unidade ou em texto.
EXCLUIDAS = {
    "Taxa de Inadimplência (dez/2024)",
    "Taxa de Inadimplência (dez/2025)",
    "Valor (Contexto Macro)",
    "Aviso Decomposição 2015-2016",
    "Competência Selecionada",
}


def _e_peca_de_dashboard(nome: str) -> bool:
    """Convenção do modelo: ` · ` marca ajudante de visual e `(Texto)`
    marca variante já formatada para cartão."""
    return " · " in nome or "(Texto)" in nome or nome in EXCLUIDAS


@dataclass(frozen=True)
class Medida:
    nome: str
    tabela: str
    unidade: str = "numero"
    descricao: str = ""

    def referencia_dax(self) -> str:
        return f"[{self.nome}]"


@dataclass
class Catalogo:
    medidas: dict[str, Medida] = field(default_factory=dict)
    # Medidas que existem no modelo mas ninguém decidiu ainda se o agente
    # deve ver nem em que unidade apresentar. Ficam de fora até decisão.
    nao_classificadas: list[str] = field(default_factory=list)

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
    nao_classificadas = []
    for linha in linhas:
        nome = linha["[Name]"]
        if nome in UNIDADES:
            medidas[nome] = Medida(
                nome=nome,
                tabela=linha.get("[Table]") or "",
                unidade=UNIDADES[nome],
                descricao=linha.get("[Description]") or "",
            )
        elif not _e_peca_de_dashboard(nome):
            nao_classificadas.append(nome)
    return Catalogo(medidas=medidas, nao_classificadas=sorted(nao_classificadas))


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
