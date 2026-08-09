# Lumen — Camada Semântica "AI-Ready" + Agente Analítico Governado

> 🚧 Projeto em desenvolvimento. Sprints 1-5 concluídas (fase de engenharia
> de dados). Sprint 6 (modelo semântico) em andamento.

## Visão

O Lumen é um projeto de engenharia de dados e BI que constrói uma camada
semântica certificada sobre dados públicos de crédito e indicadores
econômicos do Brasil (Banco Central, IBGE), com um agente analítico
governado capaz de responder perguntas em linguagem natural com base em
métricas certificadas — sem gerar SQL/DAX livre.

## Status atual

- **Concluído:** Sprints 1-5 — ingestão, camada Silver e star schema (Gold)
- **Em andamento:** Sprint 6 — modelo semântico e migração para Microsoft Fabric
- **Última atualização:** agosto de 2026

### O que já existe

| Camada | Conteúdo |
|---|---|
| Bronze | 3 fontes ingeridas, append-only, com validação de schema e retry |
| Silver | 5 tabelas limpas, tipadas e deduplicadas |
| Gold | Star schema com 4 dimensões e 2 fatos (~34,4M linhas no fato principal) |

**Qualidade:** 20 testes pytest + 21 testes dbt, todos rodando no CI a cada PR.

**Validação:** reconciliação do total agregado do SCR.data com a série
oficial do BCB realizada — convergência com divergência metodológica
documentada (ver `docs/data-dictionary.md`).

## Stack atual

Python, DuckDB, dbt, GitHub Actions. Microsoft Fabric e Power BI serão
incorporados a partir da Sprint 6 (ver ADR-001 para o plano de migração).

## Decisões técnicas (ADRs)

As decisões de arquitetura são documentadas em `docs/decision-log/`
conforme acontecem no desenvolvimento real — não como uma lista fixa
predefinida.

- **ADR-001**: Execução local com DuckDB nas Sprints 1-5, com plano
  explícito de migração para Microsoft Fabric na Sprint 6
- **ADR-002**: Ingestão do SCR.data via download de ZIP anual (não OData,
  como originalmente planejado)
- **ADR-003**: Correção arquitetural — camada Bronze deve ser append-only
  (identificado em revisão de código por colega sênior)
- **ADR-004**: Correção arquitetural — camada Silver mantém granularidade
  total da fonte; agregação fica para a Gold
- **ADR-005**: Adoção incremental de type hints a partir da Sprint 6

## Estrutura do projeto

common/ → utilitários compartilhados (logging estruturado)
ingestion/ → scripts de ingestão (Bronze) e contratos de dados
transform/silver/ → scripts de transformação (Silver)
transform/dbt/ → projeto dbt (staging + star schema Gold)
tests/ → testes de qualidade (pytest) e utilitários de CI
docs/ → dicionário de dados, ADRs, arquitetura

## Fontes de dados

- **SGS (Banco Central)**: séries temporais de Selic, IPCA, crédito nacional
- **SCR.data (Banco Central)**: crédito por UF, modalidade e segmento
  (~34,4 milhões de linhas, 2015-2025)
- **IBGE**: localidades e população por UF

Detalhes completos em `docs/data-dictionary.md` e `ingestion/contracts/`.

## Como reproduzir

Instruções completas de setup serão adicionadas ao final da fase de
engenharia de dados. Resumo atual:

```bash
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt

python ingestion/ingestir_sgs.py
python ingestion/ingestir_scr_data.py   # ~2GB de download, leva tempo
python ingestion/ingestir_ibge.py

python transform/silver/silver_sgs.py
python transform/silver/silver_scr_data.py
python transform/silver/silver_ibge.py

cd transform/dbt && dbt build
```
