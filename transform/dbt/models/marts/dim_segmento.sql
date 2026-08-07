with combinacoes_unicas as (
    select distinct
        segmento,
        cliente,
        cnae_ocupacao,
        porte
    from {{ ref('stg_credito_uf_modalidade') }}
    where segmento is not null
)

select
    row_number() over (order by segmento, cliente, cnae_ocupacao, porte) as id_segmento,
    segmento,
    cliente,
    cnae_ocupacao,
    porte
from combinacoes_unicas
