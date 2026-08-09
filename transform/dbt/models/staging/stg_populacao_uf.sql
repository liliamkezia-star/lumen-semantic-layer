select
    id_uf,
    nome_uf,
    ano,
    populacao_estimada,
    timestamp_ultima_coleta
from {{ source('silver', 'populacao_uf') }}
