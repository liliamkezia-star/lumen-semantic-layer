select
    id_uf,
    sigla_uf,
    nome_uf,
    id_regiao,
    nome_regiao
from {{ ref('stg_localidade') }}
