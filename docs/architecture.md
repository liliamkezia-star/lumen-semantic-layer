# Arquitetura — Projeto Lumen

## Visão geral

O Lumen segue uma arquitetura medallion (Bronze → Silver → Gold). Rodou
localmente via DuckDB nas Sprints 1-5, e migrou para o Microsoft Fabric na
Sprint 6 (ver ADR-001 e ADR-008), onde roda hoje. O target DuckDB local
permanece disponível para desenvolvimento e CI (`dbt --target dev`).

## Fluxo de dados

Fontes externas Bronze Silver Gold
───────────────── ────── ────── ────
API SGS (BCB) ──▶ sgs_series_raw ──▶ indicador_macro ─┐
──▶ serie_credito_mensal ─┤
SCR.data ZIP (BCB) ──▶ scr_data_raw ──▶ credito_uf_modalidade ─┤──▶ star schema (dbt) ──▶ modelo semântico
API IBGE ──▶ ibge_*_raw ──▶ localidade, │ 4 dimensões + 2 fatos    (Direct Lake,
populacao_uf ─┘                          lumen_semantico)

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

| Camada | Tecnologia (produção, desde Sprint 6) | Tecnologia (dev/CI local) |
|---|---|---|
| Armazenamento | Microsoft Fabric (Lakehouse, schemas habilitados) | DuckDB (arquivo local) |
| Ingestão/transformação | Notebooks PySpark (`fabric/notebooks/`) | Scripts Python (`ingestion/`, `transform/silver/`) |
| Gold | dbt via `dbt-fabricspark` (`--target fabric`) | dbt via `dbt-duckdb` (`--target dev`) |
| Modelo semântico | Power BI / Direct Lake (`lumen_semantico`) | — |
| Orquestração | Execução manual dos notebooks (pipelines Fabric ainda não adotados) | Execução manual |
| CI/CD | GitHub Actions (roda contra DuckDB sintético) | GitHub Actions |

Autenticação do dbt contra o Fabric usa Service Principal (não CLI
interativo) — ver ADR-008 para o motivo (Conditional Access bloqueava
login interativo do Azure CLI neste tenant).

## Qualidade de dados

- Testes bloqueantes via pytest (dados sintéticos, rodam no CI)
- Testes declarativos via dbt (unique, not_null, relationships, sobre
  dados reais)
- Validação de schema em todos os scripts de ingestão

## Decisões de arquitetura

Ver `docs/decision-log/` para o histórico completo de ADRs.
