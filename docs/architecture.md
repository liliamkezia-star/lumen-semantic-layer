# Arquitetura — Projeto Lumen

## Visão geral

O Lumen segue uma arquitetura medallion (Bronze → Silver → Gold), com
execução local via DuckDB nas Sprints 1-5, migrando para Microsoft Fabric
a partir da Sprint 6 (ver ADR-001).

## Fluxo de dados

Fontes externas Bronze Silver Gold
───────────────── ────── ────── ────
API SGS (BCB) ──▶ sgs_series_raw ──▶ indicador_macro ─┐
──▶ serie_credito_mensal ─┤
SCR.data ZIP (BCB) ──▶ scr_data_raw ──▶ credito_uf_modalidade ─┤──▶ star schema (dbt)
API IBGE ──▶ ibge_*_raw ──▶ localidade, │ 4 dimensões + 2 fatos
populacao_uf ─┘

## Princípios arquiteturais

- **Bronze é append-only** (ADR-003): nenhum dado histórico é apagado;
  cada execução soma uma nova coleta, identificada por timestamp.
- **Silver preserva granularidade da fonte** (ADR-004): nenhuma agregação
  acontece antes da Gold; limpeza e tipagem apenas.
- **Gold é modelada como star schema**, construída via dbt, com chaves
  substitutas (surrogate keys) e integridade referencial testada.
- **Toda decisão de arquitetura é documentada como ADR** em
  `docs/decision-log/`, incluindo correções feitas ao longo do
  desenvolvimento.

## Stack técnica

| Camada | Tecnologia (atual) | Tecnologia (Sprint 6+) |
|---|---|---|
| Armazenamento | DuckDB (arquivo local) | Microsoft Fabric (Lakehouse) |
| Transformação | Python + SQL | dbt (mantido) |
| Orquestração | Execução manual | Fabric Data Pipelines |
| Modelo semântico | — | Power BI / Direct Lake |
| CI/CD | GitHub Actions | GitHub Actions (mantido) |

## Qualidade de dados

- Testes bloqueantes via pytest (dados sintéticos, rodam no CI)
- Testes declarativos via dbt (unique, not_null, relationships, sobre
  dados reais)
- Validação de schema em todos os scripts de ingestão

## Decisões de arquitetura

Ver `docs/decision-log/` para o histórico completo de ADRs.
