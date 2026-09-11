# ADR-009: Modelo semântico Direct Lake publicado sobre a Gold do Fabric

## Status
Aceito

## Contexto
Com a migração para o Fabric concluída (ADR-008), o objetivo central da
Sprint 6 — o modelo semântico — ainda não existia: ao contrário do que se
esperava, o Fabric **não cria automaticamente** um semantic model padrão
ao criar um Lakehouse (`GET /v1/workspaces/{id}/semanticModels` retornava
lista vazia mesmo após Bronze/Silver/Gold populados).

## Decisão
Construir o semantic model **programaticamente** via ferramentas de
modelagem TOM/XMLA (`powerbi-modeling-mcp`), em vez de recriar manualmente
pelo portal do Power BI, e publicá-lo em modo **Direct Lake** diretamente
sobre as tabelas `gold.*` do Lakehouse — sem cópia de dados (Direct Lake
lê os arquivos Delta diretamente do OneLake).

Modelo `lumen_semantico`, no workspace `lumen-dev`:
- **6 tabelas** Direct Lake: `dim_calendario`, `dim_modalidade`,
  `dim_segmento`, `dim_uf`, `fato_credito`, `fato_indicador_macro` —
  mapeadas via `EntityName` + `SchemaName: "gold"` + uma expressão M
  compartilhada (`DatabaseQuery`) apontando para o endpoint SQL do
  Lakehouse.
- **5 relacionamentos**, replicando exatamente as FKs do star schema já
  validado no dbt (`fato_credito` → 4 dimensões; `fato_indicador_macro` →
  `dim_calendario`).
- `dim_calendario` marcada como tabela de data, habilitando funções de
  time intelligence (DATESYTD, SAMEPERIODLASTYEAR etc.) sem trabalho
  adicional.
- **7 medidas DAX certificadas** em `fato_credito`: Carteira Ativa Total,
  Carteira Inadimplência Total, Carteira a Vencer Total, Carteira Vencida
  Total, Ativo Problemático Total, Número de Operações, Taxa de
  Inadimplência (`DIVIDE`). Estas são as primeiras métricas certificadas
  do projeto — a base sobre a qual o agente analítico (Sprint 7+, ver
  ADR-005) vai operar sem gerar SQL/DAX livre.

Validado com consulta DAX real contra o modelo publicado:
`[Carteira Ativa Total]` = R$ 584,27 trilhões e `COUNTROWS(fato_credito)`
= 34.461.970 — consistente com os totais já validados na Gold (ADR-008).

## Detalhes técnicos e armadilhas encontradas
- O segundo parâmetro de `Sql.Database(...)` na expressão `DatabaseQuery`
  precisa ser o **ID do SQL analytics endpoint**
  (`sqlEndpointProperties.id` na API do Lakehouse), não o ID do próprio
  item Lakehouse — usar o ID errado resulta em erro
  `DM_InvalidRequest_DatamartNotFound`, uma mensagem enganosa (não é um
  Datamart, é um Lakehouse).
- Colunas de tabelas em modo Direct Lake **não aceitam `IsKey`** — o
  motor gerencia a chave automaticamente via uma coluna `RowNumber`
  interna. `IsKey` só é válido em tabelas DirectQuery.
- Após criar as tabelas, é necessário um **Refresh** explícito (reframe)
  antes de qualquer consulta funcionar — sem isso, as partições ficam em
  `state: NoData`.
- O refresh pode falhar transitoriamente com "não é possível acessar a
  tabela Delta de origem" logo após a Gold ser (re)criada via dbt: existe
  um pequeno atraso entre a escrita Spark/Delta e a sincronização do
  catálogo do endpoint SQL. Mitigação: forçar a sincronização via
  `POST /v1/workspaces/{id}/sqlEndpoints/{id}/refreshMetadata` antes de
  tentar o refresh do modelo de novo.
- As ferramentas de modelagem TOM exigem uma autenticação **interativa**
  própria (popup de login no navegador), independente do Service
  Principal configurado para o dbt (ADR-008) — são dois mecanismos de
  auth diferentes para dois clientes diferentes (XMLA endpoint vs. API
  REST do Fabric).

## Alternativas consideradas
- **Criar o modelo manualmente pelo portal do Power BI** (Lakehouse →
  "Novo modelo semântico" → selecionar tabelas): descartado — mais lento
  sob o prazo de capacity, e não versionável/reproduzível como o
  processo programático via TMDL/XMLA.
- **Modo Import em vez de Direct Lake**: descartado — duplicaria os
  34,4M linhas em memória do modelo, contrariando o propósito do Direct
  Lake (consulta direta ao Delta Lake sem cópia) e o motivo original de
  se adotar Fabric nesta sprint.

## Consequências
- Positivo: modelo semântico versionável e reproduzível — pode ser
  recriado do zero via as mesmas chamadas de ferramenta, documentadas
  aqui.
- Positivo: nenhuma duplicação de dados (Direct Lake), consistente com o
  volume de 34,4M linhas do fato principal.
- Atenção: as 7 medidas atuais são um conjunto inicial — o catálogo de
  métricas certificadas deve crescer conforme o agente analítico (Sprint
  7+) definir suas necessidades reais de consulta.
- Atenção: Direct Lake tem um limite de "frames" de reprocessamento por
  período de tempo por capacity — relevante ao planejar a frequência de
  reprocessamento da Gold nas próximas sprints.
