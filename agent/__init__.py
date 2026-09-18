"""Agente analítico governado do Lumen (Sprint 8, ADR-015)."""

from dotenv import load_dotenv

from .consultas import Resultado, consultar, descrever_catalogo

# Credenciais (ANTHROPIC_API_KEY, e opcionalmente as do Fabric) vêm de um
# .env na raiz do repositório, que o .gitignore já cobre.
load_dotenv()

__all__ = ["Resultado", "consultar", "descrever_catalogo"]
