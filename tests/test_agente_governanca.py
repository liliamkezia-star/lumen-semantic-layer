"""Testes bloqueantes da fronteira de governança do agente (ADR-015).

Rodam sem Fabric e sem LLM: o catálogo e a execução de DAX são
substituídos por versões falsas. O que se testa é o contrato que torna o
agente "governado" — o que ele recusa, o DAX que monta e como apresenta
os valores. Uma regressão aqui é uma regressão de governança, não de
estilo.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from agent import catalogo, consultas, ferramentas
from agent.catalogo import (
    Catalogo,
    CorteDesconhecido,
    Medida,
    MedidaDesconhecida,
    ValorDesconhecido,
)

MEDIDAS = [
    "Carteira Ativa",
    "Taxa de Inadimplência (SCR.data)",
    "Taxa de Inadimplência PF",
    "Taxa de Inadimplência Δpp a/a",
    "Carteira Vencida Δ% a/a",
    "Número de Operações",
]

VALORES = {
    "uf": ("Maranhão", "São Paulo", 'Estado "com aspas"'),
    "cliente": ("PF", "PJ"),
    "ano": (2024, 2025),
}


@pytest.fixture
def modelo_falso(monkeypatch):
    """Substitui o modelo semântico: devolve o DAX executado para inspeção."""
    executados: list[str] = []

    def executar(dax: str):
        executados.append(dax)
        return [{"[Carteira Ativa]": 7444293999119.219}]

    def valores(corte: str):
        if corte not in catalogo.CORTES:
            raise CorteDesconhecido(corte)
        return VALORES.get(corte, ())

    cat = Catalogo(
        medidas={
            n: Medida(nome=n, tabela="fato_credito", unidade=catalogo.UNIDADES[n])
            for n in MEDIDAS
        }
    )
    monkeypatch.setattr(catalogo, "carregar", lambda: cat)
    monkeypatch.setattr(catalogo, "valores_do_corte", valores)
    monkeypatch.setattr(consultas, "executar_dax", executar)
    return executados


# --- recusas: o núcleo da governança ------------------------------------


def test_medida_fora_do_catalogo_e_recusada_sem_executar(modelo_falso):
    with pytest.raises(MedidaDesconhecida):
        consultas.consultar(["SUM(fato_credito[carteira_ativa])"])
    assert modelo_falso == []


def test_corte_inexistente_e_recusado(modelo_falso):
    with pytest.raises(CorteDesconhecido):
        consultas.consultar(["Carteira Ativa"], filtros={"banco": "Itaú"})
    assert modelo_falso == []


def test_valor_inexistente_e_recusado(modelo_falso):
    with pytest.raises(ValorDesconhecido):
        consultas.consultar(["Carteira Ativa"], filtros={"uf": "Narnia"})
    assert modelo_falso == []


def test_tentativa_de_injecao_no_valor_e_recusada(modelo_falso):
    """Um valor só chega ao DAX se for idêntico a um que existe no modelo."""
    with pytest.raises(ValorDesconhecido):
        consultas.consultar(
            ["Carteira Ativa"], filtros={"uf": 'X"} ), EVALUATE fato_credito //'}
        )
    assert modelo_falso == []


def test_agrupamento_por_corte_inexistente_e_recusado(modelo_falso):
    with pytest.raises(CorteDesconhecido):
        consultas.consultar(["Carteira Ativa"], agrupar_por="banco")


def test_ordenar_por_medida_nao_consultada_e_recusado(modelo_falso):
    with pytest.raises(ValueError, match="não está entre as medidas"):
        consultas.consultar(
            ["Carteira Ativa"], agrupar_por="uf", ordenar_por="Número de Operações"
        )


def test_sugestoes_ignoram_acento_e_aceitam_pf(modelo_falso):
    with pytest.raises(MedidaDesconhecida) as erro:
        consultas.consultar(["inadimplencia PF"])
    assert erro.value.sugestoes[0] == "Taxa de Inadimplência PF"


# --- DAX montado de forma determinística --------------------------------


def test_consulta_simples_monta_row(modelo_falso):
    consultas.consultar(["Carteira Ativa"])
    assert modelo_falso == ['EVALUATE ROW ( "Carteira Ativa", [Carteira Ativa] )']


def test_filtro_monta_calculatetable_com_valor_validado(modelo_falso):
    consultas.consultar(["Carteira Ativa"], filtros={"cliente": "PF"})
    assert modelo_falso[0] == (
        'EVALUATE CALCULATETABLE ( ROW ( "Carteira Ativa", [Carteira Ativa] ), '
        'FILTER ( ALL ( dim_segmento[cliente] ), dim_segmento[cliente] IN { "PF" } ) )'
    )


def test_numero_enviado_como_texto_vira_literal_numerico(modelo_falso):
    consultas.consultar(["Carteira Ativa"], filtros={"ano": "2025"})
    assert "dim_calendario[ano] IN { 2025 }" in modelo_falso[0]


def test_aspas_em_valor_valido_sao_escapadas(modelo_falso):
    consultas.consultar(["Carteira Ativa"], filtros={"uf": 'Estado "com aspas"'})
    assert '{ "Estado ""com aspas""" }' in modelo_falso[0]


def test_ranking_monta_topn_ordenado(modelo_falso):
    consultas.consultar(["Taxa de Inadimplência (SCR.data)"], agrupar_por="uf", limite=5)
    dax = modelo_falso[0]
    assert dax.startswith("EVALUATE TOPN ( 5, SUMMARIZECOLUMNS ( dim_uf[nome_uf]")
    assert dax.endswith("ORDER BY [Taxa de Inadimplência (SCR.data)] DESC")


def test_limite_e_teto_de_seguranca(modelo_falso):
    consultas.consultar(["Carteira Ativa"], agrupar_por="uf", limite=10_000)
    assert f"TOPN ( {consultas.LIMITE_MAXIMO}," in modelo_falso[0]


# --- apresentação: o modelo de linguagem não decide a escala ------------


# Valores reais de dez/2025, com o resultado conferido contra o dashboard.
@pytest.mark.parametrize(
    ("medida", "valor", "esperado"),
    [
        ("Taxa de Inadimplência (SCR.data)", 0.041044414423335666, "4,10%"),
        ("Inadimplência BCB (SGS 21082)", 0.042, "4,20%"),
        ("% Carteira do Total (Modalidade)", 0.3476, "34,76%"),
        ("Carteira Vencida Δ% a/a", 0.6310814128550438, "63,11%"),
        ("Taxa de Inadimplência Δpp a/a", 1.113421393995244, "1,11 pp"),
        ("Divergência vs BCB (pp)", -0.09555855766643362, "-0,10 pp"),
        ("Divergência SCR vs SGS (Saldo) %", 4.313890002225459, "4,31%"),
        ("Crédito/PIB (SGS)", 56.02, "56,02%"),
        ("Carteira Ativa", 7444293999119.219, "R$ 7,44 Tri"),
        ("Carteira Vencida Δ Absoluto a/a", 89972408924.41003, "R$ 89,97 Bi"),
        ("SCR (R$ mi)", 7444294.0, "R$ 7,44 Tri"),
        ("Concessões PF (SGS)", 407477.0, "R$ 407,48 Bi"),
        ("Número de Operações", 928619478, "928.619.478"),
        ("Defasagem SCR vs SGS (meses)", 7, "7 meses"),
        ("Última Competência com Crédito", "2025-12-31T00:00:00", "31/12/2025"),
        ("Carteira Ativa", None, "sem valor"),
        # Deflacionamento (ADR-016), valores conferidos em SQL independente
        ("IPCA 12 Meses (SGS)", 0.042644, "4,26%"),
        ("Carteira Ativa Δ% a/a Real", 0.067459, "6,75%"),
        ("Carteira Ativa Real (R$ da Última Competência)", 5597036846992.1, "R$ 5,60 Tri"),
    ],
)
def test_formatacao_segue_a_unidade_declarada(medida, valor, esperado):
    assert ferramentas.formatar(valor, catalogo.UNIDADES[medida]) == esperado


def test_toda_unidade_declarada_tem_formatacao_propria():
    """Unidade com erro de digitação cairia silenciosamente no genérico."""
    conhecidas = {
        "fracao", "percentual", "pp", "reais", "reais_milhoes",
        "contagem", "meses", "data", "numero",
    }
    assert set(catalogo.UNIDADES.values()) <= conhecidas


# --- curadoria: o agente vê medida de negócio, não peça de dashboard ----


def test_catalogo_expoe_so_o_declarado_e_sinaliza_medida_nova(monkeypatch):
    no_modelo = [
        "Carteira Ativa",
        "Título · Diagnóstico",
        "Taxa de Inadimplência PF (Texto)",
        "Taxa de Inadimplência (dez/2024)",
        "Valor (Contexto Macro)",
        "Medida Criada Ontem",
    ]
    monkeypatch.setattr(
        catalogo,
        "executar_dax",
        lambda _: [{"[Name]": n, "[Table]": "fato_credito"} for n in no_modelo],
    )
    catalogo.carregar.cache_clear()
    try:
        cat = catalogo.carregar()
    finally:
        catalogo.carregar.cache_clear()
    assert list(cat.medidas) == ["Carteira Ativa"]
    assert cat.nao_classificadas == ["Medida Criada Ontem"]


def test_descricao_com_valor_ou_data_nao_chega_ao_prompt(monkeypatch):
    """No benchmark, o agente citou 4,10% tirado de uma descrição de medida,
    sem consultar. Valor em descrição é cola — e envelhece."""
    descricoes = {
        "Carteira Ativa": "Saldo semiaditivo; dez/2025: R$ 7,44 Tri.",
        "Taxa de Inadimplência PF": "Taxa de PF, 5,15% no último mês.",
        "Carteira Vencida": "Saldo vencido, com dado até 2025-12.",
        "% Carteira do Total (Modalidade)": "Base do corte de materialidade (≥1%).",
    }
    monkeypatch.setattr(
        catalogo,
        "executar_dax",
        lambda _: [
            {"[Name]": n, "[Table]": "fato_credito", "[Description]": d}
            for n, d in descricoes.items()
        ],
    )
    catalogo.carregar.cache_clear()
    try:
        cat = catalogo.carregar()
    finally:
        catalogo.carregar.cache_clear()
    assert cat.descricoes_omitidas == ["Carteira Ativa", "Carteira Vencida", "Taxa de Inadimplência PF"]
    assert cat.medidas["Carteira Ativa"].descricao == ""
    assert cat.medidas["% Carteira do Total (Modalidade)"].descricao.endswith("(≥1%).")


def test_medida_declarada_mas_removida_do_modelo_some_do_agente(monkeypatch):
    monkeypatch.setattr(
        catalogo,
        "executar_dax",
        lambda _: [{"[Name]": "Carteira Ativa", "[Table]": "fato_credito"}],
    )
    catalogo.carregar.cache_clear()
    try:
        cat = catalogo.carregar()
    finally:
        catalogo.carregar.cache_clear()
    assert "Taxa de Inadimplência PF" not in cat.medidas


# --- ferramentas: erro de escolha volta para o modelo se corrigir -------


def test_ferramenta_devolve_recusa_como_texto(modelo_falso):
    resposta = ferramentas.consultar_metricas(medidas=["Medida Inventada"])
    assert resposta.startswith("Consulta recusada:")


def test_ferramenta_aceita_medida_solta_em_vez_de_lista(modelo_falso):
    resposta = json.loads(ferramentas.consultar_metricas(medidas="Carteira Ativa"))
    assert resposta["linhas"][0]["Carteira Ativa"] == "R$ 7,44 Tri"


def test_ferramenta_rejeita_filtro_que_nao_e_json(modelo_falso):
    resposta = ferramentas.consultar_metricas(
        medidas=["Carteira Ativa"], filtros_json="cliente=PF"
    )
    assert "não é JSON válido" in resposta
    assert modelo_falso == []


@pytest.mark.parametrize("ferramenta", ferramentas.DISPONIVEIS)
def test_anotacoes_das_ferramentas_sao_tipos_reais(ferramenta):
    """O SDK valida os argumentos contra as anotações; anotação em texto
    (efeito de `from __future__ import annotations`) quebra a chamada."""
    for nome, anotacao in ferramenta.__annotations__.items():
        assert not isinstance(anotacao, str), f"{ferramenta.__name__}.{nome}"


def test_ferramentas_executam_pelo_caminho_do_sdk(modelo_falso):
    """Chama a ferramenta como o SDK do Gemini chama na execução automática.

    Os demais testes chamam a função direto e não pegaram o bug que fez a
    ferramenta nunca executar nos primeiros testes com o modelo. Usa uma
    função interna do SDK de propósito: é ela que roda em produção.
    """
    from google.genai import _extra_utils

    resposta = _extra_utils.invoke_function_from_dict_args(
        {"medidas": ["Carteira Ativa"], "filtros_json": '{"cliente": "PF"}'},
        ferramentas.consultar_metricas,
    )
    assert json.loads(resposta)["linhas"][0]["Carteira Ativa"] == "R$ 7,44 Tri"


def test_ferramenta_registra_a_consulta_para_auditoria(modelo_falso):
    registro: list = []
    marca = ferramentas.execucao.set(registro)
    try:
        ferramentas.consultar_metricas(medidas=["Carteira Ativa"])
    finally:
        ferramentas.execucao.reset(marca)
    assert [r.dax for r in registro] == modelo_falso
