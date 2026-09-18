"""Interface do agente analítico governado do Lumen.

Rodar com:  streamlit run agent/app.py

A tela mostra, junto de cada resposta, as consultas DAX que foram
executadas para produzi-la. Isso não é recurso de depuração: é a prova
de que a resposta veio de medida certificada, e não de texto plausível.
"""

from __future__ import annotations

import streamlit as st

from agent import catalogo
from agent.agente import MODELO, Agente, ChaveAusente
from agent.fabric import ErroFabric

st.set_page_config(page_title="Lumen · Agente analítico", layout="wide")


@st.cache_resource
def _agente() -> Agente:
    return Agente()


@st.cache_data(ttl=3600)
def _resumo_do_catalogo() -> tuple[int, list[str]]:
    cat = catalogo.carregar()
    return len(cat.medidas), sorted(catalogo.CORTES)


st.title("Agente analítico do Lumen")
st.caption(
    "Perguntas em linguagem natural respondidas com as medidas certificadas do "
    "modelo semântico. O agente não escreve DAX: ele escolhe medidas e cortes de "
    "um catálogo fechado, e a consulta é montada de forma determinística."
)

with st.sidebar:
    st.subheader("O que dá para perguntar")
    try:
        total, cortes = _resumo_do_catalogo()
        st.metric("Medidas certificadas", total)
        st.write("**Cortes disponíveis**")
        st.write(", ".join(cortes))
    except ErroFabric as erro:
        st.error(f"Sem acesso ao modelo semântico: {erro}")
    st.divider()
    st.caption(f"Modelo: `{MODELO}`")
    st.caption("Fonte: SCR.data e SGS (Banco Central), IBGE")
    st.caption("Arquitetura: ADR-015")

EXEMPLOS = [
    "Qual a taxa de inadimplência mais recente?",
    "Quais as 5 UFs com maior inadimplência?",
    "Compare a inadimplência de PF e PJ",
    "Qual modalidade mais piorou no último ano?",
]

if "mensagens" not in st.session_state:
    st.session_state.mensagens = []

if not st.session_state.mensagens:
    st.write("**Exemplos para começar**")
    colunas = st.columns(len(EXEMPLOS))
    for coluna, exemplo in zip(colunas, EXEMPLOS, strict=True):
        if coluna.button(exemplo, use_container_width=True):
            st.session_state.pergunta_pendente = exemplo
            st.rerun()

for mensagem in st.session_state.mensagens:
    with st.chat_message(mensagem["papel"]):
        st.markdown(mensagem["texto"])
        for consulta in mensagem.get("consultas", []):
            with st.expander(
                f"Consulta executada · {', '.join(consulta['medidas'])}", expanded=False
            ):
                st.code(consulta["dax"], language="sql")
                if consulta["linhas"]:
                    st.dataframe(consulta["linhas"], use_container_width=True)

pergunta = st.chat_input("Pergunte sobre crédito no Brasil") or st.session_state.pop(
    "pergunta_pendente", None
)

if pergunta:
    st.session_state.mensagens.append({"papel": "user", "texto": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Consultando o modelo semântico..."):
                resposta = _agente().perguntar(pergunta)
        except ChaveAusente as erro:
            st.error(str(erro))
            st.stop()
        except ErroFabric as erro:
            st.error(f"Falha ao consultar o modelo semântico: {erro}")
            st.stop()

        st.markdown(resposta.texto)
        consultas_registradas = [
            {"medidas": c.medidas, "dax": c.dax, "linhas": c.linhas}
            for c in resposta.consultas
        ]
        for consulta in consultas_registradas:
            with st.expander(
                f"Consulta executada · {', '.join(consulta['medidas'])}", expanded=False
            ):
                st.code(consulta["dax"], language="sql")
                if consulta["linhas"]:
                    st.dataframe(consulta["linhas"], use_container_width=True)

    st.session_state.mensagens.append(
        {"papel": "assistant", "texto": resposta.texto, "consultas": consultas_registradas}
    )
