# Lumen — Camada Semântica "AI-Ready" + Agente Analítico Governado

> 🚧 Projeto em desenvolvimento. Sprint 4 (Silver) em andamento.

## Visão

O Lumen é um projeto de engenharia de dados e BI que constrói uma camada
semântica certificada sobre dados públicos de crédito e indicadores
econômicos do Brasil (Banco Central, IBGE), com um agente analítico
governado capaz de responder perguntas em linguagem natural com base em
métricas certificadas — sem gerar SQL/DAX livre.

## Status atual

- **Fase:** Sprint 4 — Silver (saneamento e qualidade)
- **Última atualização:** agosto de 2026

## Stack atual

Python, DuckDB, dbt (a partir da Sprint 5), Power BI (a partir da Sprint 6),
GitHub Actions. Microsoft Fabric será incorporado na Sprint 6 (ver ADR-001).

## Decisões técnicas (ADRs)

As decisões de arquitetura são documentadas em `docs/decision-log/` conforme
acontecem no desenvolvimento real — não como uma lista fixa predefinida.
Até o momento:

- **ADR-001**: Execução local com DuckDB nas Sprints 1-5, com plano
  explícito de migração para Microsoft Fabric na Sprint 6
- **ADR-002**: Ingestão do SCR.data via download de ZIP anual (não OData,
  como originalmente planejado)
- **ADR-003**: Correção arquitetural — camada Bronze deve ser append-only
  (identificado em revisão de código por colega sênior)
- **ADR-004**: Correção arquitetural — camada Silver mantém granularidade
  total da fonte; agregação fica para a Gold

## Estrutura do projeto

ingestion/ → scripts de ingestão (Bronze) e contratos de dados
transform/silver/ → scripts de transformação (Silver)
docs/ → dicionário de dados, ADRs, arquitetura

## Fontes de dados

- **SGS (Banco Central)**: séries temporais de Selic, IPCA, crédito nacional
- **SCR.data (Banco Central)**: crédito por UF, modalidade e segmento
  (~34,4 milhões de linhas, 2015-2025)
- **IBGE**: localidades e população por UF

Detalhes completos em `docs/data-dictionary.md` e `ingestion/contracts/`.

## Como reproduzir

Em construção — instruções completas de setup serão adicionadas ao final
da fase de engenharia de dados (Sprint 5).
