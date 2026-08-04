# Contrato de dados — Fonte SGS (Banco Central do Brasil)

## Visão geral
API pública do Banco Central (Sistema Gerenciador de Séries Temporais) para
consulta de indicadores econômicos e de crédito, sem necessidade de autenticação.

## Endpoint

https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_serie}/dados?formato=json&dataInicial={dd/mm/aaaa}&dataFinal={dd/mm/aaaa}

## Limites conhecidos
- Séries de periodicidade **diária** exigem `dataInicial` e `dataFinal`
  explícitos, com janela máxima de **10 anos** por chamada.
- Séries **mensais** parecem não ter essa restrição (a confirmar com testes
  na Sprint 2).
- Sem autenticação, sem rate limit documentado publicamente (monitorar).

## Séries mapeadas para os KPIs do projeto

| Indicador | Código | Frequência | Uso no projeto |
|---|---|---|---|
| Selic (diária) | 11 | diária | referência de ciclo de juros |
| Selic (meta) | 432 | por reunião Copom | anotações de ciclo no dashboard |
| IPCA (variação mensal %) | 433 | mensal | inflação, deflacionamento de valores |
| Saldo total de crédito (R$ milhões) | 20539 | mensal | KPI de estoque de crédito |
| Crédito/PIB (%) | 20622 | mensal | KPI de endividamento agregado |
| Inadimplência da carteira - Total | 21082 | mensal | KPI principal de risco |
| Spread médio total | 20783 | mensal | KPI de custo de crédito |
| Concessões de crédito - PF - Total | 20633 | mensal | KPI de novas operações (PF) |
| Concessões de crédito - PJ - Total | 20632 | mensal | KPI de novas operações (PJ) |
| Endividamento das famílias (renda 12m) | 29037 | mensal | KPI de endividamento PF |

## Campos retornados pela API
- `data` (string, formato dd/mm/aaaa)
- `valor` (string, precisa ser convertido para número — vem sempre como texto)

## Observações de qualidade (a validar na Sprint 4 - Silver)
- A Selic diária (série 11) vem como taxa diária (ex: 0.052531), não como
  percentual anual — precisa de conversão/documentação clara.
- O campo `valor` sempre vem como string, mesmo sendo numérico.
