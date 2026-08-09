-- Chave substituta gerada por hash da chave natural, não por row_number().
-- Ver justificativa completa em dim_modalidade.sql: IDs sequenciais são
-- instáveis em dimensões reconstruídas integralmente a cada execução.

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
    md5(
        coalesce(segmento, '')
        || '|' || coalesce(cliente, '')
        || '|' || coalesce(cnae_ocupacao, '')
        || '|' || coalesce(porte, '')
    ) as id_segmento,
    segmento,
    cliente,
    cnae_ocupacao,
    porte
from combinacoes_unicas
