"""Tela do duelo: a mesma pergunta para as duas abordagens, lado a lado.

Rodar com:  streamlit run evaluation/app_duelo.py

É a versão apresentável do `python -m evaluation.duelo`. Mesma ideia: o
benchmark inteiro produz um número, e esta tela mostra o número
acontecendo. A parte que convence não é a resposta — é a consulta que
cada lado rodou, mostrada embaixo dela.

Roda ao vivo e consome cota: duas respostas por pergunta.
"""

from __future__ import annotations

import hmac
import json
import os
import sys
import time
from pathlib import Path

# O streamlit põe a pasta do script no sys.path, não a raiz do projeto —
# sem isto, `from agent import ...` quebra dependendo de onde se roda.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from agent import ritmo  # noqa: E402
from agent.agente import Agente, ChaveAusente, ModelosIndisponiveis  # noqa: E402
from agent.fabric import ErroFabric  # noqa: E402
from evaluation.baseline_text2sql import MODELO, BaselineTextToSql  # noqa: E402
from evaluation.corretor import corrigir  # noqa: E402

GABARITO = Path(__file__).parent / "gabarito_congelado.json"
PAUSA_FERRAMENTA = 20  # s — ver agent/ritmo.py

load_dotenv()
# O teto da cota gratuita é de tokens de entrada por minuto, e uma
# pergunta com várias consultas o estoura sozinha.
os.environ.setdefault(ritmo.VARIAVEL, str(PAUSA_FERRAMENTA))

st.set_page_config(page_title="Lumen · Agente × SQL livre", layout="wide")

# Fonte um pouco maior: esta tela existe para ser gravada, e o vídeo é
# assistido no celular.
st.markdown(
    """
    <style>
      .stMarkdown p, .stMarkdown li { font-size: 1.05rem; }
      div[data-testid="stExpander"] summary p { font-size: .95rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _exigir_senha() -> None:
    """Mesma porta da demonstração do agente: a tela lê o modelo
    semântico com a identidade do SPN e não pode ficar aberta."""
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


@st.cache_data
def _gabarito() -> list[dict]:
    return json.loads(GABARITO.read_text(encoding="utf-8"))["perguntas"]


def _esperado(questao: dict) -> str:
    esperado = questao["esperado"]
    if esperado.get("recusa"):
        return "recusar a pergunta"
    return " · ".join(esperado.get("texto") or esperado.get("nomes") or ["?"])


st.title("Agente governado × text-to-SQL livre")
st.caption(
    "A mesma pergunta, o mesmo modelo, as mesmas tabelas. De um lado, um agente "
    "que só pode usar medidas certificadas. Do outro, o mesmo modelo escrevendo "
    "SQL direto na Gold. A consulta de cada lado aparece embaixo da resposta."
)

questoes = _gabarito()
rotulos = {f"{q['id']} · {q['pergunta']}": q for q in questoes}

escolha = st.selectbox(
    "Pergunta do gabarito",
    list(rotulos),
    index=list(rotulos).index(
        next(r for r in rotulos if r.startswith("D04"))
    ),
    help="As 60 perguntas do gabarito congelado, com resposta verificada por dois caminhos.",
)
questao = rotulos[escolha]

col_botao, col_certo = st.columns([1, 3])
with col_botao:
    perguntar = st.button("Perguntar aos dois", type="primary", width="stretch")
with col_certo:
    st.markdown(f"**Resposta certa:** `{_esperado(questao)}`")

st.divider()


def _executar(construtor, pergunta: str) -> tuple[str, list[str], float] | None:
    """Devolve texto, consultas e o tempo de modelo — sem a espera da cota."""
    ritmo.zerar()
    inicio = time.monotonic()
    try:
        resposta = construtor().perguntar(pergunta)
    except ChaveAusente as erro:
        st.error(str(erro))
        return None
    except ErroFabric as erro:
        st.error(f"Falha ao consultar o modelo semântico: {erro}")
        return None
    except ModelosIndisponiveis:
        st.warning(
            "Cota da API gratuita esgotada neste minuto. Espere um ou dois "
            "minutos e pergunte de novo."
        )
        return None
    latencia = time.monotonic() - inicio - ritmo.dormido()
    consultas = [getattr(c, "dax", c) for c in resposta.consultas]
    return resposta.texto, consultas, latencia


def _mostrar(titulo: str, legenda: str, resultado, rotulo_consulta: str) -> None:
    st.subheader(titulo)
    st.caption(legenda)
    if resultado is None:
        return
    texto, consultas, latencia = resultado

    nota = corrigir(questao, texto)
    if nota.acertou:
        st.success("Acertou")
    else:
        faltou = ", ".join(nota.faltou) if nota.faltou else _esperado(questao)
        st.error(f"Errou — esperado: {faltou}")

    st.markdown(texto)
    st.caption(f"{latencia:.0f} s")

    if consultas:
        for i, consulta in enumerate(consultas, 1):
            sufixo = f" ({i} de {len(consultas)})" if len(consultas) > 1 else ""
            with st.expander(rotulo_consulta + sufixo, expanded=True):
                # Sem quebra de linha, a consulta sai cortada na horizontal —
                # e o que fica fora da tela some do vídeo. É justamente a
                # parte que precisa ser lida.
                st.code(str(consulta).strip(), language="sql", wrap_lines=True)
    else:
        st.caption("Nenhuma consulta: respondeu sem ir ao banco.")


esquerda, direita = st.columns(2, gap="large")

if perguntar:
    with esquerda:
        with st.spinner("Agente consultando o modelo semântico..."):
            resultado_agente = _executar(lambda: Agente(modelo=MODELO), questao["pergunta"])
        _mostrar(
            "Agente governado",
            "Escolhe medidas de um catálogo fechado; o DAX é montado por código.",
            resultado_agente,
            "DAX montado pelo código",
        )
    with direita:
        with st.spinner("Text-to-SQL escrevendo a consulta..."):
            resultado_baseline = _executar(
                lambda: BaselineTextToSql(modelo=MODELO), questao["pergunta"]
            )
        _mostrar(
            "Text-to-SQL livre",
            "Mesmo modelo, escrevendo SQL direto sobre as tabelas da Gold.",
            resultado_baseline,
            "SQL escrito pelo modelo",
        )
else:
    with esquerda:
        st.subheader("Agente governado")
        st.caption("Escolhe medidas de um catálogo fechado; o DAX é montado por código.")
    with direita:
        st.subheader("Text-to-SQL livre")
        st.caption("Mesmo modelo, escrevendo SQL direto sobre as tabelas da Gold.")
    st.info(
        f"Escolha uma pergunta e clique em **Perguntar aos dois**. "
        f"Os dois lados usam `{MODELO}`. Cada execução consome duas respostas da "
        "cota gratuita, e leva de 20 a 60 segundos por lado."
    )
