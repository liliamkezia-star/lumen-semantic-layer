-- Chave substituta gerada por hash da chave natural, não por row_number().
-- row_number() produz IDs instáveis: como esta dimensão é reconstruída
-- integralmente a cada dbt run, uma nova combinação inserida no meio da
-- ordenação alfabética deslocaria os IDs de todas as combinações
-- seguintes. Isso não quebra o fato (reconstruído no mesmo run, rejuntado
-- por chave natural), mas quebraria qualquer artefato fora do dbt que
-- grave o ID por valor — catálogo do agente (S7), tabelas de ML (S9),
-- benchmark (S12).
--
-- Usa hash() (UBIGINT) em vez de md5() (VARCHAR 32): chaves inteiras são
-- significativamente mais eficientes para dicionarização e comparação em
-- VertiPaq/Direct Lake — a camada que a Sprint 6 constrói sobre este
-- modelo — e para joins em qualquer motor SQL. Com apenas centenas de
-- combinações, a probabilidade de colisão em 64 bits é desprezível, e o
-- teste unique no schema.yml a detectaria.

with combinacoes_unicas as (
    select distinct
        modalidade,
        submodalidade,
        origem,
        indexador
    from {{ ref('stg_credito_uf_modalidade') }}
    where modalidade is not null
)

select
    {{ gerar_chave_substituta(['modalidade', 'submodalidade', 'origem', 'indexador']) }} as id_modalidade,
    modalidade,
    submodalidade,
    origem,
    indexador
from combinacoes_unicas
