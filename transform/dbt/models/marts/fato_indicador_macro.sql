with indicadores as (
    select
        nome_serie,
        codigo_serie,
        data_referencia,
        valor,
        unidade_valor,
        granularidade
    from {{ ref('stg_indicador_macro') }}

    union all

    select
        nome_serie,
        codigo_serie,
        data_referencia,
        valor,
        unidade_valor,
        granularidade
    from {{ ref('stg_serie_credito_mensal') }}
)

select
    cal.id_data,
    indicadores.nome_serie,
    indicadores.codigo_serie,
    indicadores.valor,
    indicadores.unidade_valor,
    indicadores.granularidade
from indicadores
left join {{ ref('dim_calendario') }} cal
    on cal.data = indicadores.data_referencia

