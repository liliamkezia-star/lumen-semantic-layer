# Lumen — Camada Semântica "AI-Ready" + Agente Analítico Governado

> 🚧 Projeto em desenvolvimento. Sprints 1-7 concluídas (engenharia de
> dados, migração para Microsoft Fabric, modelo semântico e dashboard
> Power BI).

## Visão

O Lumen é um projeto de engenharia de dados e BI que constrói uma camada
semântica certificada sobre dados públicos de crédito e indicadores
econômicos do Brasil (Banco Central, IBGE), com um agente analítico
governado capaz de responder perguntas em linguagem natural com base em
métricas certificadas — sem gerar SQL/DAX livre.

## Status atual

- **Concluído:** Sprints 1-5 (ingestão, Silver, star schema Gold), Sprint 6
  (migração para Microsoft Fabric + modelo semântico Direct Lake) e Sprint 7
  (dashboard Power BI de 5 páginas, a partir de uma auditoria externa de
  design — `ADR-010` a `ADR-014`)
- **Deliberadamente fora de escopo:** faixa sombreada da defasagem SCR/SGS
  na Página 3 e layout mobile da Página 1 — cortes conscientes, não
  esquecimentos (ver seção [Dashboard](#dashboard))
- **Última atualização:** setembro de 2026

### O que já existe

| Camada | Conteúdo |
|---|---|
| Bronze | 3 fontes ingeridas, append-only, com validação de schema e retry — rodando no Fabric (Lakehouse) |
| Silver | 5 tabelas limpas, tipadas e deduplicadas — rodando no Fabric |
| Gold | Star schema com 4 dimensões e 2 fatos (~34,4M linhas no fato principal) — dbt rodando sobre o Fabric via `dbt-fabricspark` |
| Modelo semântico | `lumen_semantico`, Direct Lake, catálogo de medidas certificadas versionado em `powerbi/medidas_certificadas_v2.dax`, publicado no workspace `lumen-dev` |
| Dashboard | Power BI de 5 páginas sobre o modelo semântico — tema (`powerbi/lumen_theme_v2.json`), visuais Deneb versionados em `powerbi/deneb/` (ver seção [Dashboard](#dashboard)) |

**Qualidade:** 20 testes pytest + 23 testes dbt, todos passando tanto no
target local (DuckDB) quanto no Fabric.

**Validação:** reconciliação do total agregado do SCR.data com a série
oficial do BCB realizada — convergência com divergência metodológica
documentada (ver `docs/data-dictionary.md`).

## Stack atual

Python, dbt, GitHub Actions, Microsoft Fabric (Lakehouse + Direct Lake),
Power BI (Direct Lake + tema customizado) e Deneb/Vega-Lite para o único
visual não-nativo do dashboard. Execução local com DuckDB permanece
disponível como target de desenvolvimento/CI (ver ADR-001 e ADR-008 para
o histórico da migração).

## Dashboard

![Página 1 — Visão Geral do dashboard Lumen](docs/assets/dashboard-pagina1.png)

> A imagem acima é da Página 1 (Visão Geral). O relatório completo tem 5
> páginas — Visão Geral, Onde, Contexto Macro, Ficha de Segmento
> (drill-through) e Notas Metodológicas — e roda 100% sobre o modelo
> semântico Direct Lake (`powerbi/lumen_dashboard.pbix`), sem publicação
> pública (workspace `lumen-dev` é um ambiente de desenvolvimento).

### Três decisões de design que eu mais defendo

1. **Toda medida de "período atual" passa por uma única âncora dinâmica,
   nunca por `MAX()`, `SAMEPERIODLASTYEAR()` ou data literal.**
   `dim_calendario` é gerada por `dbt_utils.date_spine()` até 2026-12-31 —
   bem além do fim real dos dados (dez/2025) — e o relacionamento
   `fato_credito → dim_calendario` é OneDirection. Sem uma âncora que force
   `CROSSFILTER(..., BOTH)`, qualquer medida de "competência atual" escaneia
   o calendário inteiro e erra silenciosamente. Essa mesma classe de erro
   apareceu 4 vezes neste projeto (`ADR-010`, `ADR-011`, `ADR-014`, e de
   novo no aviso de decomposição 2015-2016) até virar regra fixa: toda
   medida nova passa por `[Última Competência com Crédito]`, sem exceção,
   verificada uma a uma antes de ser certificada.
2. **Field parameter trocado por slicer na Página 2 (`ADR-013`), contra a
   recomendação literal da auditoria.** A auditoria pedia field parameter
   para o corte de cliente (PF/PJ) porque "muda a pergunta" em vez de só
   filtrar. A documentação oficial do Power BI é explícita: não dá para
   criar parâmetros em fontes de conexão live sem modelo local — e um
   modelo local decisão que já rejeitei antes (`ADR-009`) para não duplicar
   34,4M de linhas. Prefiro manter a arquitetura Direct Lake e usar um
   slicer comum, com o trade-off documentado, a violar uma decisão
   estrutural anterior por uma diferença semântica de interação.
3. **O painel duplo da Página 1 resolve o desalinhamento desligando o eixo
   Y em vez de compensar por pixel.** As duas séries (carteira ativa e
   taxa de inadimplência) têm rótulos de eixo Y de larguras diferentes
   ("R$ 8 Tri" vs. "4%"), e o Power BI calcula a área de plot de cada
   visual de forma independente — sem alinhamento nativo entre eles. A
   correção óbvia seria empurrar um painel alguns pixels e redimensionar o
   outro, mas isso quebra a cada mudança de fonte, DPI ou resolução de
   tela. Desligar o eixo de valor (mantendo gridlines, rótulo de ponta e
   rótulo da linha de referência do BCB, que já dão a escala) resolve o
   alinhamento de um jeito que não depende de nenhuma medida em pixels.

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
- **ADR-006**: Manutenção de DOUBLE (não DECIMAL) para colunas monetárias
- **ADR-007**: Materialização full-refresh na fase local, incremental avaliada na Sprint 6
- **ADR-008**: Migração para Microsoft Fabric concluída — SPN em vez de CLI, capacity de trial, `dim_calendario` portável
- **ADR-009**: Modelo semântico Direct Lake publicado sobre a Gold do Fabric
- **ADR-010**: Correção das medidas certificadas de `SUM()` para
  `LASTNONBLANKVALUE` — as medidas de saldo são semiaditivas e não podem
  somar competências no tempo
- **ADR-011**: Correção dos comparativos ano a ano (`SAMEPERIODLASTYEAR`
  sem âncora herdava o fim do calendário gerado, não o fim real dos dados)
  e do separador decimal em medidas de texto
- **ADR-012**: Investigação parcial de uma divergência entre o modelo
  publicado no Fabric e o `lumen.duckdb` local para uma competência
  específica — causa raiz não totalmente confirmada, registrada com
  honestidade em vez de escondida
- **ADR-013**: Field parameter da Página 2 ("Cliente") substituído por
  slicer comum — parâmetros não podem ser criados em fontes de conexão
  live sem modelo local, o que descaracterizaria a arquitetura Direct Lake
- **ADR-014**: Terceira ocorrência do padrão de data fixa em vez de âncora
  dinâmica (medidas do dumbbell da Página 1) — mesma classe de erro do
  ADR-010/011, agora com literal `DATE(...)` em vez de time intelligence
  sem âncora

## Estrutura do projeto

common/ → utilitários compartilhados (logging estruturado)
ingestion/ → scripts de ingestão (Bronze) local, versão DuckDB
transform/silver/ → scripts de transformação (Silver) local, versão DuckDB
transform/dbt/ → projeto dbt (staging + star schema Gold) — roda contra
  DuckDB local (`--target dev`) ou Fabric (`--target fabric`)
fabric/notebooks/ → notebooks PySpark (Bronze + Silver) para rodar no
  Fabric — equivalentes aos scripts de ingestion/ e transform/silver/
tests/ → testes de qualidade (pytest) e utilitários de CI
docs/ → dicionário de dados, ADRs, arquitetura
powerbi/ → catálogo de medidas DAX, tema do relatório e specs Deneb
  (Vega-Lite) do dashboard da Sprint 7

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
