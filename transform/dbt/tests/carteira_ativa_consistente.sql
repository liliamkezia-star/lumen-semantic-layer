-- Invariante: carteira_ativa deve ser a soma de carteira_a_vencer e
-- carteira_vencida.
--
-- Exceção conhecida e documentada: 5.869 linhas de 2015-2016 (e 1 de
-- 2024) violam essa relação — ver observação de qualidade no dicionário
-- de dados. Provável mudança de metodologia no início da série do
-- SCR.data. Essas linhas são excluídas explicitamente do teste, para que
-- ele detecte QUALQUER nova ocorrência fora desse conjunto conhecido,
-- em vez de ser desativado ou de falhar permanentemente.

select
    data_base,
    uf,
    modalidade,
    carteira_ativa,
    carteira_a_vencer,
    carteira_vencida,
    carteira_ativa - (carteira_a_vencer + carteira_vencida) as diferenca
from {{ ref('stg_credito_uf_modalidade') }}
where abs(carteira_ativa - (carteira_a_vencer + carteira_vencida)) > 0.01
  and ano_arquivo not in (2015, 2016, 2024)
