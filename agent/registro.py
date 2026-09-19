"""Registro persistente de cada interação com o agente.

Uma linha JSON por pergunta, em um arquivo por dia. Guarda o que é
preciso para auditar uma resposta depois: a pergunta, o modelo que
respondeu, as consultas DAX executadas (a "interpretação" que o agente
fez da pergunta), a resposta, a latência — e o erro, quando houve. As
falhas são registradas também: é nelas que o log mais serve.

A pasta fica fora do git: guarda perguntas de quem usa o agente.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PASTA = Path(os.getenv("LUMEN_PASTA_REGISTRO", Path(__file__).parent / "interacoes"))
FUSO = ZoneInfo("America/Sao_Paulo")


def registrar(
    pergunta: str,
    modelo: str,
    latencia_s: float,
    resposta: str = "",
    consultas: list[Any] | None = None,
    erro: str = "",
) -> Path:
    agora = datetime.now(FUSO)
    linha = {
        "quando": agora.isoformat(timespec="seconds"),
        "pergunta": pergunta,
        "modelo": modelo,
        "latencia_s": round(latencia_s, 2),
        "consultas": [
            {"medidas": c.medidas, "corte": c.corte, "linhas": len(c.linhas), "dax": c.dax}
            for c in consultas or []
        ],
        "resposta": resposta,
        "erro": erro,
    }
    PASTA.mkdir(parents=True, exist_ok=True)
    arquivo = PASTA / f"{agora:%Y-%m-%d}.jsonl"
    with arquivo.open("a", encoding="utf-8") as saida:
        saida.write(json.dumps(linha, ensure_ascii=False) + "\n")
    return arquivo
