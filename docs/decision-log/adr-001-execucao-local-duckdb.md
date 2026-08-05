# ADR-001: Execução local com DuckDB nas Sprints 1-5 (em vez de Microsoft Fabric)

## Status
Aceito

## Contexto
O plano original do projeto previa usar o Microsoft Fabric desde a Sprint 1,
incluindo workspaces dev/prod e capacity ativa. Ao tentar ativar o trial
gratuito de 60 dias do Fabric, a ativação foi recusada pela Microsoft com a
mensagem "Avaliação do Fabric indisponível para sua conta" — uma restrição
comum em tenants Microsoft Entra ID recém-criados, que pode levar semanas
para ser liberada automaticamente.

## Decisão
Nas Sprints 1 a 5 (ingestão, Bronze, Silver, Gold), o projeto será executado
localmente usando Python e DuckDB, conforme já sugerido no documento de
sugestões estratégicas do projeto. O Fabric será retomado a partir da
Sprint 6, quando a funcionalidade Direct Lake se torna estritamente necessária.

## Alternativas consideradas
- **Aguardar a liberação do trial do Fabric**: descartado por não ter prazo
  garantido, o que travaria o cronograma sem necessidade.
- **Criar capacity paga via crédito gratuito do Azure ($200/30 dias)**:
  descartado para esta fase por ter prazo curto e fixo (30 dias), que seria
  melhor aproveitado a partir da Sprint 6, quando o Fabric é indispensável.

## Consequências
- Positivo: nenhum custo ou prazo de trial é consumido antes de ser
  necessário; ambiente 100% local facilita testes rápidos e sem dependência
  de internet ou capacity ativa.
- Atenção: o pipeline de ingestão e transformação precisará ser adaptado
  (ou reescrito) ao migrar de DuckDB local para o Fabric na Sprint 6.
- Atenção: o checklist original da Sprint 1 (workspaces Fabric, deploy via
  fabric-cicd) é adiado para a Sprint 6.

## Plano de migração para a Sprint 6

A migração de DuckDB local para Microsoft Fabric ocorrerá integralmente na
Sprint 6, com os seguintes passos explícitos:

1. Reativar a tentativa de trial do Fabric (60 dias) ou, se ainda
   indisponível para o tenant, ativar capacity paga via crédito Azure
   (30 dias), conforme avaliado no momento.
2. Recriar os workspaces lumen-dev e lumen-prd (adiados desde a Sprint 1).
3. Adaptar os scripts de ingestão (SGS, SCR.data, IBGE) para rodar como
   Notebooks Fabric / Data Pipelines, substituindo a execução local.
4. Reprocessar o histórico completo (Bronze e Silver) dentro do ambiente
   Fabric — os dados já processados localmente não serão migrados
   diretamente; serão recarregados a partir das fontes originais, seguindo
   os mesmos scripts adaptados.
5. Validar que os totais reprocessados no Fabric batem com os totais
   obtidos localmente (ex: 34,4M linhas no SCR.data, 7.263 linhas no SGS),
   como checagem de integridade da migração.
6. Somente após essa validação, a Gold (Sprint 5, já concluída antes da
   migração) e o Modelo Semântico (Sprint 6) passam a operar sobre dados
   Fabric, não mais sobre o arquivo lumen.duckdb local.

Esse plano garante que a transição não é apenas "trocar a tecnologia", mas
uma migração validada, com paridade de dados confirmada antes de descartar
a base local.
