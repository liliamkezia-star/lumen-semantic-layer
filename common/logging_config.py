"""Configuração centralizada de logging para os scripts do projeto.

Substitui o uso de print() por logging estruturado, com níveis e
timestamps — necessário para observabilidade quando os scripts migrarem
para Fabric Data Pipelines/Notebooks na Sprint 6, onde logs sem estrutura
dificultam diagnóstico e monitoramento.
"""

import logging
import sys


def configurar_logger(nome: str, nivel: int = logging.INFO) -> logging.Logger:
    """Devolve um logger configurado com formato padrão do projeto.

    Args:
        nome: identificador do módulo (normalmente __name__).
        nivel: nível mínimo de severidade a registrar.

    Returns:
        Logger pronto para uso, sem handlers duplicados em reimportação.
    """
    logger = logging.getLogger(nome)

    if logger.handlers:  # evita handlers duplicados ao reimportar o módulo
        return logger

    logger.setLevel(nivel)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)

    return logger
