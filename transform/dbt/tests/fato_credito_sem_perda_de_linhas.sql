-- Teste customizado: garante que o INNER JOIN em fato_credito não
-- descartou nenhuma linha da origem.
--
-- O dbt considera o teste APROVADO quando esta consulta retorna ZERO
-- linhas. Portanto, retornamos uma linha apenas quando as contagens
-- divergem — sinalizando perda silenciosa de dados no join.

with contagem_origem as (
    select count(*) as total from {{ ref('stg_credito_uf_modalidade') }}
),
contagem_fato as (
    select count(*) as total from {{ ref('fato_credito') }}
)

select
    contagem_origem.total as linhas_na_origem,
    contagem_fato.total as linhas_no_fato,
    contagem_origem.total - contagem_fato.total as diferenca
from contagem_origem, contagem_fato
where contagem_origem.total != contagem_fato.total
