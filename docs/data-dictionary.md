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
