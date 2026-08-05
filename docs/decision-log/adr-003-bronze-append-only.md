# ADR-003: Correção de arquitetura — Bronze deve ser append-only, não delete+insert

## Status
Aceito

## Contexto
O script de ingestão da Sprint 2 (ingestion/ingestir_sgs.py) implementava
idempotência usando o padrão "DELETE FROM tabela" seguido de "INSERT" a
cada execução. Essa abordagem, embora evite duplicação de linhas, viola o
princípio fundamental da camada Bronze em arquiteturas medallion: dados
brutos devem ser append-only (somente adicionados, nunca apagados ou
sobrescritos), preservando o histórico completo de coletas — inclusive
quando a fonte original revisa valores publicados anteriormente.

Essa inconsistência foi identificada em revisão de código por um colega
sênior de dados.

O script de ingestão da Sprint 3 (ingestion/ingestir_scr_data.py) já
seguia o padrão correto (apenas INSERT, com controle de idempotência por
ano já carregado, sem apagar dados existentes) — o problema estava
isolado no script da Sprint 2.

## Decisão
A camada Bronze passa a seguir estritamente o padrão append-only:
- Nenhum script de ingestão pode conter DELETE ou TRUNCATE na Bronze.
- Cada execução adiciona uma nova "safra" de dados, identificada por
  timestamp_coleta.
- Execuções repetidas no mesmo período podem gerar múltiplas versões do
  mesmo dado de referência (mesma data_referencia, timestamps de coleta
  diferentes) — isso é esperado e correto, não é duplicação indevida.
- A responsabilidade de resolver "qual é a versão mais atual de cada
  dado" passa a ser da camada Silver (Sprint 4), usando uma janela
  (ROW_NUMBER() OVER PARTITION BY chave ORDER BY timestamp_coleta DESC)
  para selecionar apenas o registro mais recente por chave.

## Alternativas consideradas
- Manter delete+insert (rejeitado: destrói histórico de coletas,
  inviabiliza auditoria de revisões da fonte).
- Historização completa com SCD Tipo 2 (valido_de/valido_ate): rejeitado
  por ora, por complexidade desproporcional ao estágio atual do projeto;
  pode ser revisitado futuramente se a auditoria de mudanças se tornar
  requisito explícito.

## Consequências
- Positivo: Bronze passa a refletir corretamente o princípio de dados
  brutos imutáveis; histórico de coletas é preservado.
- Positivo: alinhamento entre os scripts da Sprint 2 e Sprint 3, que
  antes seguiam padrões inconsistentes entre si.
- Atenção: a camada Silver precisa implementar a lógica de "pegar só a
  versão mais recente" — isso deve ser adicionado ao escopo da Sprint 4.
- Atenção: o volume da tabela bronze.sgs_series_raw crescerá a cada
  execução do script (aceitável, dado o volume pequeno dessa fonte).
