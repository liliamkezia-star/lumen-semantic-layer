"""O agente: um LLM com ferramentas restritas ao catálogo certificado.

Este é o único arquivo do pacote que conhece o provedor de modelo. Toda
a governança — catálogo, validação, montagem do DAX — vive em
`consultas.py` e `ferramentas.py`, que não sabem qual modelo está do
outro lado. Trocar de provedor é reescrever este arquivo, e nada mais.

Provedor atual: Google Gemini (ver ADR-015).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from google import genai
from google.genai import errors, types

from . import catalogo, consultas, ferramentas, registro

# Versões fixadas de propósito, em vez do alias `gemini-flash-latest`: um
# modelo que muda sozinho embaixo do projeto tornaria a avaliação do
# agente irreprodutível. Trocar de versão passa a ser decisão explícita.
#
# A lista é uma cadeia de reserva, não uma preferência estética: no nível
# gratuito da API, 503 por alta demanda é rotina e não erro — medido neste
# projeto, modelos alternam entre disponível e indisponível em questão de
# segundos. Cair para o próximo é o comportamento correto; falhar na cara
# de quem perguntou não é.
#
# Os Gemma 4 (modelos abertos do Google, servidos pela mesma API) têm cota
# gratuita separada dos Gemini Flash e suportam ferramentas — medido: com a
# cota dos Flash esgotada, o gemma-4-26b-a4b-it respondeu o ranking de UF
# certo, com o DAX certo. Mais lentos (~40s por pergunta), mas é o que
# mantém o projeto sem custo.
MODELO = os.getenv("LUMEN_MODELO_LLM", "gemini-3.6-flash")
RESERVAS = [
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3.1-flash-lite",
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
]


class ChaveAusente(RuntimeError):
    pass


@dataclass
class Resposta:
    texto: str
    consultas: list[consultas.Resultado] = field(default_factory=list)


def _instrucoes() -> str:
    cat = catalogo.carregar()
    medidas = [
        f"- {m.nome}" + (f" — {m.descricao}" if m.descricao else "")
        for m in sorted(cat.medidas.values(), key=lambda m: m.nome)
    ]
    return f"""Você é o agente analítico do Lumen, uma camada semântica certificada \
sobre dados públicos de crédito do Banco Central (SCR.data e SGS) e do IBGE.

Responda em português do Brasil.

REGRA CENTRAL, INEGOCIÁVEL: todo número que você escrever tem que ter vindo de uma \
chamada a `consultar_metricas` feita nesta conversa. Você não sabe nenhum valor de \
cor. Se não consultou, não afirma — nem que o número pareça óbvio. Um valor que você \
já trouxe de uma consulta em pergunta anterior desta conversa pode ser citado de novo \
(por exemplo, para comparar); qualquer valor novo exige consulta.

Se a pergunta não puder ser respondida com as medidas e cortes disponíveis, diga isso \
claramente e mostre o que dá para responder de perto. Recusar bem faz parte do \
trabalho; inventar uma aproximação, não.

Separe sempre duas coisas na resposta:
1. O dado certificado: os números, sempre dizendo a que corte e competência se referem.
2. A leitura: sua interpretação, quando fizer sentido oferecer uma. Deixe explícito \
que é leitura, não medição.

Nunca afirme causalidade entre as séries macroeconômicas do SGS e os dados de crédito \
do SCR. Elas são apresentadas lado a lado; a relação é leitura do analista.

Os valores chegam das ferramentas já formatados pela definição certificada da medida \
(percentual, escala em Bi/Tri). Use-os como vieram, sem reconverter.

Se uma consulta for recusada, a mensagem traz as opções válidas — corrija a escolha e \
tente de novo, em vez de desistir ou improvisar.

CORTES DISPONÍVEIS para filtrar ou agrupar:
{', '.join(sorted(catalogo.CORTES))}

MEDIDAS CERTIFICADAS ({len(cat.medidas)} disponíveis):
{chr(10).join(medidas)}"""


class ModelosIndisponiveis(RuntimeError):
    pass


class Agente:
    """Uma conversa com o agente, mantendo o histórico entre perguntas."""

    def __init__(self, modelo: str | None = None) -> None:
        chave = os.getenv("GEMINI_API_KEY")
        if not chave:
            raise ChaveAusente(
                "GEMINI_API_KEY não definida. Crie um .env na raiz do "
                "repositório com GEMINI_API_KEY=... (chave gratuita em "
                "https://aistudio.google.com/apikey)."
            )
        # Uma tentativa por modelo: a cadeia de reserva já é a estratégia de
        # repetição. Com as repetições internas do SDK ligadas, um modelo
        # sobrecarregado segurava a resposta por mais de um minuto antes de a
        # cadeia chegar ao próximo (medido: 65 s numa pergunta simples).
        self.cliente = genai.Client(
            api_key=chave,
            http_options=types.HttpOptions(
                timeout=90_000, retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )
        self.modelos = [modelo or MODELO, *RESERVAS] if modelo is None else [modelo]
        self.modelo_em_uso = self.modelos[0]
        self.configuracao = types.GenerateContentConfig(
            system_instruction=_instrucoes(),
            tools=ferramentas.DISPONIVEIS,
            temperature=0,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                maximum_remote_calls=8
            ),
        )
        # Histórico só de texto, sem o tráfego de ferramentas: mantém o
        # contexto enxuto (a cota gratuita é por tokens por minuto). Números
        # das respostas anteriores podem ser citados de novo porque já vieram
        # de consulta certificada nesta conversa — ver ADR-015, seção
        # "Ajuste da regra de lastro".
        self.historico: list[types.Content] = []

    def perguntar(self, pergunta: str) -> Resposta:
        executadas: list[consultas.Resultado] = []
        marca = ferramentas.execucao.set(executadas)
        inicio = time.monotonic()
        try:
            resposta = self._tentar(pergunta)
        except Exception as erro:
            registro.registrar(
                pergunta, self.modelo_em_uso, time.monotonic() - inicio,
                consultas=executadas, erro=f"{type(erro).__name__}: {erro}",
            )
            raise
        finally:
            ferramentas.execucao.reset(marca)

        texto = (resposta.text or "").strip()
        self.historico.extend(
            [
                types.Content(role="user", parts=[types.Part(text=pergunta)]),
                types.Content(role="model", parts=[types.Part(text=texto)]),
            ]
        )
        registro.registrar(
            pergunta, self.modelo_em_uso, time.monotonic() - inicio,
            resposta=texto, consultas=executadas,
        )
        return Resposta(texto=texto, consultas=executadas)

    def _tentar(self, pergunta: str) -> types.GenerateContentResponse:
        """Percorre a cadeia de modelos até um responder."""
        recusas: list[str] = []
        for modelo in self._ordem_de_tentativa():
            conversa = self.cliente.chats.create(
                model=modelo, config=self.configuracao, history=list(self.historico)
            )
            try:
                resposta = conversa.send_message(pergunta)
            except errors.ServerError as erro:
                recusas.append(f"{modelo}: {str(erro)[:60]}")
                continue
            except errors.ClientError as erro:
                if erro.code != 429:  # cota estourada segue para o próximo
                    raise
                recusas.append(f"{modelo}: cota esgotada")
                continue
            self.modelo_em_uso = modelo
            return resposta
        raise ModelosIndisponiveis(
            "Nenhum modelo disponível no momento (a API gratuita do Gemini "
            "recusa por alta demanda em picos). Tentativas — "
            + "; ".join(recusas)
        )

    def _ordem_de_tentativa(self) -> list[str]:
        """Começa pelo último que funcionou, para não repetir a busca a
        cada pergunta enquanto o modelo preferido estiver sobrecarregado."""
        return [
            self.modelo_em_uso,
            *[m for m in self.modelos if m != self.modelo_em_uso],
        ]
