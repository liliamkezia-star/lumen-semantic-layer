# Dicionário de Dados — Projeto Lumen

## Camada Bronze

### bronze.sgs_series_raw
Dados brutos das séries temporais do Banco Central (SGS), coletados via API
pública, sem nenhum tratamento. Um registro por observação (data + valor)
de cada série.

**Fonte:** https://api.bcb.gov.br (ver contrato completo em
`ingestion/contracts/sgs.md`)

**Padrão de carga:** full refresh (apaga tudo e reinsere a cada execução) —
garante idempotência, adequado para o volume atual (~7.200 linhas).

| Coluna | Tipo | Descrição |
|---|---|---|
| nome_serie | VARCHAR | Nome amigável da série (ex: `selic_diaria`) |
| codigo_serie | INTEGER | Código oficial da série no SGS |
| data_referencia | VARCHAR | Data do dado, formato dd/mm/aaaa (ainda como texto — tratamento de tipo fica para a Silver) |
| valor | VARCHAR | Valor da observação (ainda como texto — conversão numérica fica para a Silver) |
| url_fonte | VARCHAR | URL exata usada na chamada à API, para rastreabilidade |
| timestamp_coleta | VARCHAR | Data/hora (UTC) em que o dado foi coletado |

**Observações de qualidade conhecidas (a tratar na Silver):**
- `valor` da Selic diária vem como taxa diária (ex: 0.052531), não anualizada
- Todos os campos vêm como texto, mesmo quando são números ou datas

### bronze.scr_data_raw
Dados brutos de operações de crédito por UF, modalidade, segmento e
cliente, do Sistema de Informações de Créditos (SCR.data) do Banco Central.

**Fonte:** ver `ingestion/contracts/olinda.md`
**Padrão de carga:** append-only, idempotência por ano (ADR-003)
**Volume:** ~34,4 milhões de linhas (2015-2025)

### bronze.ibge_localidades_raw
Cadastro de estados brasileiros (id, sigla, nome, região).

**Fonte:** API de Localidades do IBGE
**Volume:** 27 linhas

### bronze.ibge_populacao_raw
População estimada por UF e ano.

**Fonte:** API de Agregados do IBGE (SIDRA, tabela 6579)
**Observação de qualidade:** anos de 2022 e 2023 ausentes (pausa da fonte
durante o Censo 2022 — ver `ingestion/contracts/olinda.md`)
