-- Chave substituta gerada por hash da chave natural, não por row_number().
-- Ver justificativa completa em dim_modalidade.sql: IDs sequenciais são
-- instáveis em dimensões reconstruídas integralmente a cada execução, e
-- hash() (UBIGINT) é preferível a md5() (VARCHAR) pelo custo de
-- dicionarização e join em VertiPaq/Direct Lake e em motores SQL.

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
    {{ gerar_chave_substituta(['segmento', 'cliente', 'cnae_ocupacao', 'porte']) }} as id_segmento,
    segmento,
    cliente,
    cnae_ocupacao,
    porte
from combinacoes_unicas
