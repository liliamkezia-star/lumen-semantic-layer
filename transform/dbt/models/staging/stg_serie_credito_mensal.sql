select
    nome_serie,
    codigo_serie,
    data_referencia,
    valor,
    unidade_valor,
    granularidade,
    timestamp_ultima_coleta
from {{ source('silver', 'serie_credito_mensal') }}
