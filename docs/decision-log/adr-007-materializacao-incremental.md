# ADR-007: Materialização full-refresh na fase local, incremental avaliada na Sprint 6

## Status
Aceito (com revisão programada para a Sprint 6)

## Contexto
Todos os modelos de `marts/` são materializados como `table`, sem
`materialized='incremental'`, `unique_key` ou `partition_by`. Cada
execução do dbt reconstrói `fato_credito` (34,4 milhões de linhas)
integralmente.

Na execução local em DuckDB isso leva cerca de 35 segundos — não é
gargalo observável. Mas é uma decisão de design que precisa ser
consciente antes da Sprint 6, por dois motivos:

- O custo do full refresh cresce linearmente com o histórico: cada ano
  novo adiciona ~3,7M linhas.
- Direct Lake se beneficia de particionamento (tipicamente por
  ano/competência) para pruning eficiente de arquivos.

## Decisão
Manter `materialized='table'` (full refresh) durante a fase local
(Sprints 1-5). A avaliação de materialização incremental e
particionamento fica explicitamente para a Sprint 6, como parte da
migração para o Microsoft Fabric.

## Justificativa
- **A estratégia correta depende da plataforma-alvo, não do DuckDB.** A
  sintaxe de particionamento, o comportamento do `merge` incremental e as
  preferências reais do Direct Lake são específicos do Fabric.
  Implementar agora em DuckDB provavelmente exigiria reescrever depois.
- **Full refresh é mais simples e mais seguro.** Reconstrói sempre a
  partir do estado atual da fonte, sem risco de estado parcial
  inconsistente. Incremental introduz uma classe de falha que não existe
  hoje: linhas que deveriam ser atualizadas e não foram.
- **A deduplicação por `timestamp_ultima_coleta` complica o incremental.**
  Uma recoleta pode revisar dados de competências antigas — uma
  estratégia ingênua de "processar apenas o que é novo" perderia essas
  revisões silenciosamente. Isso exige lógica cuidadosa que vale
  desenhar já conhecendo a plataforma final.
- **Não há dor a resolver hoje.** 35 segundos de rebuild não impacta o
  fluxo de trabalho nem o CI (que roda sobre banco sintético).

## Alternativas consideradas
- **Implementar incremental agora em DuckDB**: rejeitado por antecipar
  complexidade sem ganho mensurável e com risco de retrabalho na
  migração.
- **Não documentar e decidir depois**: rejeitado — sem registro, a
  ausência de estratégia incremental pareceria omissão em vez de escolha.

## Consequências
- Positivo: mantém o pipeline simples e determinístico durante a fase de
  construção do modelo dimensional.
- Atenção: **gatilho de revisão** — ao migrar para o Fabric na Sprint 6,
  avaliar explicitamente: (a) `materialized='incremental'` com
  `unique_key` composta pelas 4 FKs, (b) particionamento por
  `ano_arquivo` ou por competência, (c) como tratar revisões de
  competências antigas sem perder atualizações.
- Atenção: se o histórico for expandido para antes de 2015 (hoje limitado
  por alinhamento com o SGS — ver ADR-002), o custo do full refresh
  aumenta proporcionalmente, antecipando a necessidade dessa revisão.
