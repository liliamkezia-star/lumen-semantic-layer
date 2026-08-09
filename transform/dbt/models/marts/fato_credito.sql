-- Estratégia de join deliberada:
--
-- INNER JOIN para dim_modalidade e dim_segmento — essas dimensões são
-- derivadas do PRÓPRIO fato (distinct das mesmas linhas), então toda
-- linha do fato tem match garantido por construção. O INNER expressa
-- essa invariante em vez de deixá-la implícita.
--
-- LEFT JOIN para dim_uf e dim_calendario — vêm de fontes independentes
-- (IBGE e geração de calendário). Uma ausência de match aqui é
-- informação legítima a investigar (ex: UF nova, data fora do intervalo
-- do calendário), não um bug esperado — e o teste relationships no
-- schema.yml captura isso explicitamente.
--
-- O INNER JOIN faria uma linha desaparecer silenciosamente caso o
-- casamento quebrasse; o teste de contagem em schema.yml
-- (fato_credito vs stg_credito_uf_modalidade) detecta essa perda.

with base as (
    select * from {{ ref('stg_credito_uf_modalidade') }}
)

select
    cal.id_data,
    uf.id_uf,
    mod.id_modalidade,
    seg.id_segmento,
    base.numero_de_operacoes,
    base.carteira_a_vencer,
    base.carteira_vencida,
    base.carteira_ativa,
    base.carteira_inadimplencia,
    base.ativo_problematico
from base
left join {{ ref('dim_calendario') }} cal
    on cal.data = base.data_base
left join {{ ref('dim_uf') }} uf
    on uf.sigla_uf = base.uf
inner join {{ ref('dim_modalidade') }} mod
    on mod.modalidade = base.modalidade
    and mod.submodalidade = base.submodalidade
    and mod.origem = base.origem
    and mod.indexador = base.indexador
inner join {{ ref('dim_segmento') }} seg
    on seg.segmento = base.segmento
    and seg.cliente = base.cliente
    and seg.cnae_ocupacao = base.cnae_ocupacao
    and seg.porte = base.porte
