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

    cat = Catalogo(medidas={n: Medida(nome=n, tabela="fato_credito") for n in MEDIDAS})
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


@pytest.mark.parametrize(
    ("medida", "valor", "esperado"),
    [
        ("Taxa de Inadimplência (SCR.data)", 0.041044414423335666, "4,10%"),
        ("Carteira Vencida Δ% a/a", 0.6310814128550438, "63,11%"),
        ("Taxa de Inadimplência Δpp a/a", 1.1134, "1,11 pp"),
        ("Carteira Ativa", 7444293999119.219, "R$ 7,44 Tri"),
        ("Carteira Ativa", 5119464780165.182, "R$ 5,12 Tri"),
        ("Número de Operações", 928619478, "928.619.478"),
        ("Carteira Ativa", None, "sem valor"),
    ],
)
def test_formatacao_segue_a_natureza_da_medida(medida, valor, esperado):
    assert ferramentas.formatar(valor, medida) == esperado


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


def test_ferramenta_registra_a_consulta_para_auditoria(modelo_falso):
    registro: list = []
    marca = ferramentas.execucao.set(registro)
    try:
        ferramentas.consultar_metricas(medidas=["Carteira Ativa"])
    finally:
        ferramentas.execucao.reset(marca)
    assert [r.dax for r in registro] == modelo_falso
