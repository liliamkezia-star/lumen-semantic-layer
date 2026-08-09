-- CAST explícito para DATE: generate_series do DuckDB retorna TIMESTAMP
-- quando o passo é um INTERVAL, mesmo com limites DATE. Sem o cast, o
-- join com fato_credito (cujo data_base é DATE explícito) dependeria de
-- conversão implícita, e o Power BI receberia uma coluna TIMESTAMP —
-- o recurso "Marcar como Tabela de Data" e boa parte das funções DAX de
-- time intelligence esperam DATE genuíno.
with datas_geradas as (
    select
        cast(generate_series as date) as data
    from generate_series(
        cast('2015-01-01' as date),
        cast('2026-12-31' as date),
        interval '1 day'
    )
)
select
    cast(strftime(data, '%Y%m%d') as integer) as id_data,
    data,
    extract(year from data) as ano,
    extract(month from data) as mes,
    extract(quarter from data) as trimestre,
    extract(day from data) as dia,
case extract(month from data)
        when 1 then 'Janeiro'
        when 2 then 'Fevereiro'
        when 3 then 'Março'
        when 4 then 'Abril'
        when 5 then 'Maio'
        when 6 then 'Junho'
        when 7 then 'Julho'
        when 8 then 'Agosto'
        when 9 then 'Setembro'
        when 10 then 'Outubro'
        when 11 then 'Novembro'
        when 12 then 'Dezembro'
    end as nome_mes,
    strftime(data, '%Y-%m') as ano_mes,
    case
        when extract(month from data) in (1, 2, 3) then 'T1'
        when extract(month from data) in (4, 5, 6) then 'T2'
        when extract(month from data) in (7, 8, 9) then 'T3'
        else 'T4'
    end as trimestre_label
from datas_geradas
