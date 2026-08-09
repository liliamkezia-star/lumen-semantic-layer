-- Valida o grão declarado de fato_credito: uma linha por combinação de
-- (data × UF × modalidade × segmento).
--
-- Os testes de not_null e relationships garantem que cada FK aponta para
-- uma dimensão válida, mas não impedem que duas linhas tenham exatamente
-- as mesmas 4 chaves — o que indicaria violação de grão (ex: reexecução
-- de ingestão mal controlada, ou correção de fonte gerando duplicata).
--
-- As 4 FKs cobrem, somadas, as 10 colunas da chave natural da Silver:
-- calendário (1) + UF (1) + modalidade (4) + segmento (4).
--
-- O dbt aprova o teste quando esta consulta retorna zero linhas.

select
    id_data,
    id_uf,
    id_modalidade,
    id_segmento,
    count(*) as linhas_duplicadas
from {{ ref('fato_credito') }}
group by 1, 2, 3, 4
having count(*) > 1
