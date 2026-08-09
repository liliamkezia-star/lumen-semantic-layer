# dbt — Camada Gold do Projeto Lumen

Projeto dbt responsável por transformar as tabelas da camada Silver em um
star schema pronto para consumo analítico (camada Gold).

Para o contexto geral do projeto, ver o [README principal](../../README.md)
e a [documentação de arquitetura](../../docs/architecture.md).

## Estrutura


models/
├── staging/ → uma view por tabela Silver (camada de abstração)
└── marts/ → star schema: 4 dimensões + 2 fatos
macros/
└── generate_schema_name.sql → usa o schema customizado sem prefixo
tests/
└── fato_credito_sem_perda_de_linhas.sql → teste customizado de integridade

## Modelos

### Staging (views, schema `staging`)
Camada fina sobre a Silver, sem transformação relevante. Existe para
isolar os marts de mudanças de nome/estrutura nas tabelas de origem.

- `stg_indicador_macro`, `stg_serie_credito_mensal` — séries do SGS
- `stg_credito_uf_modalidade` — SCR.data (~34,4M linhas)
- `stg_localidade`, `stg_populacao_uf` — IBGE

### Marts (tabelas, schema `gold`)

**Dimensões**
- `dim_calendario` — gerada via `generate_series`, 2015 a 2026, diária
- `dim_uf` — 27 UFs, derivada do IBGE
- `dim_modalidade` — 491 combinações de modalidade/submodalidade/origem/indexador
- `dim_segmento` — 1.372 combinações de segmento/cliente/CNAE/porte

**Fatos**
- `fato_credito` — operações de crédito, granularidade original da fonte
- `fato_indicador_macro` — indicadores nacionais (SGS)

## Decisões de modelagem

- **Chaves substitutas por hash MD5** da chave natural, não sequenciais —
  garante que o mesmo registro sempre receba o mesmo ID entre execuções
  (dimensões são reconstruídas integralmente a cada run).
- **INNER JOIN** nas dimensões derivadas do próprio fato (modalidade,
  segmento); **LEFT JOIN** nas de fonte independente (UF, calendário),
  onde a ausência de match é informação a investigar.
- **Nenhuma agregação** — a granularidade original é preservada desde a
  Silver (ver ADR-004).

## Como executar

Requer um profile `lumen` configurado (ver `~/.dbt/profiles.yml`), com
targets `dev` (banco local completo) e `ci` (banco sintético).

```bash
dbt build              # roda modelos + testes no target dev
dbt build --target ci  # roda no banco sintético (usado pelo CI)
dbt docs generate      # gera documentação e lineage
dbt docs serve         # abre a documentação no navegador
```

## Testes

21 testes no total: `unique` e `not_null` nas chaves, `relationships`
entre fatos e dimensões, e um teste customizado que garante que nenhuma
linha se perdeu no join do fato.
