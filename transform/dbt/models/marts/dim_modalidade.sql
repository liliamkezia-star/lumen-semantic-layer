-- Chave substituta gerada por hash da chave natural, não por row_number().
-- row_number() produz IDs instáveis: como esta dimensão é reconstruída
-- integralmente a cada dbt run, uma nova combinação inserida no meio da
-- ordenação alfabética deslocaria os IDs de todas as combinações
-- seguintes. Isso não quebra o fato (reconstruído no mesmo run, rejuntado
-- por chave natural), mas quebraria qualquer artefato fora do dbt que
-- grave o ID por valor — catálogo do agente (S7), tabelas de ML (S9),
-- benchmark (S12). O hash garante que a mesma combinação sempre produza
-- o mesmo ID.

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
    md5(
        coalesce(modalidade, '')
        || '|' || coalesce(submodalidade, '')
        || '|' || coalesce(origem, '')
        || '|' || coalesce(indexador, '')
    ) as id_modalidade,
    modalidade,
    submodalidade,
    origem,
    indexador
from combinacoes_unicas
