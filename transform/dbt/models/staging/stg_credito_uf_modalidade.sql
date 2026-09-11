select
    data_base,
    uf,
    segmento,
    cliente,
    cnae_ocupacao,
    porte,
    modalidade,
    submodalidade,
    origem,
    indexador,
    -- CAST explícito para BIGINT: a coluna chega como INT32 desde a
    -- ingestão (Bronze), o que faz SUM() estourar ao agregar sobre os
    -- 34,4M linhas do fato (achado ao publicar o modelo semântico —
    -- ver ADR-009). BIGINT evita o overflow sem precisar reprocessar
    -- Bronze/Silver.
    CAST(numero_de_operacoes AS BIGINT) AS numero_de_operacoes,
    a_vencer_ate_90_dias,
    a_vencer_de_91_ate_360_dias,
    a_vencer_de_361_ate_1080_dias,
    a_vencer_de_1081_ate_1800_dias,
    a_vencer_de_1801_ate_5400_dias,
    a_vencer_acima_de_5400_dias,
    vencido_de_15_ate_90_dias,
    vencido_acima_de_90_dias,
    carteira_a_vencer,
    carteira_vencida,
    carteira_ativa,
    carteira_inadimplencia,
    ativo_problematico,
    ano_arquivo,
    arquivo_origem,
    timestamp_ultima_coleta
from {{ source('silver', 'credito_uf_modalidade') }}
