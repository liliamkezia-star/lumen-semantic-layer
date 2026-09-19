"""Interface do agente analítico governado do Lumen.

Rodar com:  streamlit run agent/app.py

A tela mostra, junto de cada resposta, as consultas DAX que foram
executadas para produzi-la. Isso não é recurso de depuração: é a prova
de que a resposta veio de medida certificada, e não de texto plausível.
"""

from __future__ import annotations

import hmac
import os
import time

import streamlit as st

from agent import catalogo
from agent.agente import MODELO, RESERVAS, Agente, ChaveAusente, ModelosIndisponiveis
from agent.fabric import ErroFabric

st.set_page_config(page_title="Lumen · Agente analítico", layout="wide")


def _exigir_senha() -> None:
    """Porta de entrada da demonstração.

    Sem senha configurada o app não abre: um app que lê o modelo semântico
    com a identidade do SPN não pode ficar aberto por esquecimento.
    """
    senha = os.getenv("LUMEN_SENHA_DEMO")
    if not senha:
        st.error(
            "Demonstração sem senha configurada. Defina LUMEN_SENHA_DEMO no .env "
            "da raiz do repositório e reinicie o app."
        )
        st.stop()
    if st.session_state.get("autenticado"):
        return
    with st.form("entrada"):
        tentativa = st.text_input("Senha da demonstração", type="password")
        if st.form_submit_button("Entrar"):
            if hmac.compare_digest(tentativa.encode(), senha.encode()):
                st.session_state.autenticado = True
                st.rerun()
            st.error("Senha incorreta.")
    st.stop()


_exigir_senha()


def _agente() -> Agente:
    """Um agente por sessão, não um para o processo inteiro: o agente
    guarda o histórico da conversa, e compartilhá-lo misturaria as
    conversas de pessoas diferentes."""
    if "agente" not in st.session_state:
        st.session_state.agente = Agente()
    return st.session_state.agente


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
    st.caption(
        f"Modelo preferido: `{MODELO}`, com {len(RESERVAS)} reservas gratuitas. "
        "Cada resposta indica o modelo que de fato respondeu."
    )
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
        if coluna.button(exemplo, width="stretch"):
            st.session_state.pergunta_pendente = exemplo
            st.rerun()

def _mostrar(mensagem: dict) -> None:
    st.markdown(mensagem["texto"])
    if mensagem.get("modelo"):
        # O modelo que de fato respondeu, não o preferido: a cadeia de
        # reserva pode ter caído para outro.
        st.caption(f"Respondido por `{mensagem['modelo']}` em {mensagem['latencia']:.0f} s")
    for consulta in mensagem.get("consultas", []):
        with st.expander(
            f"Consulta executada · {', '.join(consulta['medidas'])}", expanded=False
        ):
            st.code(consulta["dax"], language="sql")
            if consulta["linhas"]:
                st.dataframe(consulta["linhas"], width="stretch")


for mensagem in st.session_state.mensagens:
    with st.chat_message(mensagem["papel"]):
        _mostrar(mensagem)

pergunta = st.chat_input("Pergunte sobre crédito no Brasil") or st.session_state.pop(
    "pergunta_pendente", None
)

if pergunta:
    st.session_state.mensagens.append({"papel": "user", "texto": pergunta})
    with st.chat_message("user"):
        st.markdown(pergunta)

    with st.chat_message("assistant"):
        inicio = time.monotonic()
        try:
            with st.spinner("Consultando o modelo semântico..."):
                agente = _agente()
                resposta = agente.perguntar(pergunta)
        except ChaveAusente as erro:
            st.error(str(erro))
            st.stop()
        except ErroFabric as erro:
            st.error(f"Falha ao consultar o modelo semântico: {erro}")
            st.stop()
        except ModelosIndisponiveis:
            st.warning(
                "Nenhum modelo de linguagem disponível agora: a API gratuita limita "
                "requisições por minuto. Tente de novo em um ou dois minutos."
            )
            st.stop()

        nova = {
            "papel": "assistant",
            "texto": resposta.texto,
            "modelo": agente.modelo_em_uso,
            "latencia": time.monotonic() - inicio,
            "consultas": [
                {"medidas": c.medidas, "dax": c.dax, "linhas": c.linhas}
                for c in resposta.consultas
            ],
        }
        _mostrar(nova)

    st.session_state.mensagens.append(nova)
