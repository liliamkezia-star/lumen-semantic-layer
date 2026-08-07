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
left join {{ ref('dim_modalidade') }} mod
    on mod.modalidade = base.modalidade
    and mod.submodalidade = base.submodalidade
    and mod.origem = base.origem
    and mod.indexador = base.indexador
left join {{ ref('dim_segmento') }} seg
    on seg.segmento = base.segmento
    and seg.cliente = base.cliente
    and seg.cnae_ocupacao = base.cnae_ocupacao
    and seg.porte = base.porte
