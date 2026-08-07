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
    row_number() over (order by modalidade, submodalidade) as id_modalidade,
    modalidade,
    submodalidade,
    origem,
    indexador
from combinacoes_unicas
