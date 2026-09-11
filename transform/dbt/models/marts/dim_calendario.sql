-- Portável entre DuckDB e Spark (Fabric): usa dbt_utils.date_spine em vez
-- de generate_series (específico do DuckDB), e monta id_data/ano_mes por
-- aritmética (EXTRACT + LPAD) em vez de strftime (também específico do
-- DuckDB, sem equivalente direto em Spark SQL).
with datas_geradas as (
    {{ dbt_utils.date_spine(
        datepart="day",
        start_date="cast('2015-01-01' as date)",
        end_date="cast('2026-12-31' as date)"
    ) }}
)
select
    cast(
        cast(extract(year from date_day) as string)
        || lpad(cast(extract(month from date_day) as string), 2, '0')
        || lpad(cast(extract(day from date_day) as string), 2, '0')
        as integer
    ) as id_data,
    cast(date_day as date) as data,
    extract(year from date_day) as ano,
    extract(month from date_day) as mes,
    extract(quarter from date_day) as trimestre,
    extract(day from date_day) as dia,
    case extract(month from date_day)
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
    cast(extract(year from date_day) as string)
        || '-' || lpad(cast(extract(month from date_day) as string), 2, '0') as ano_mes,
    case
        when extract(month from date_day) in (1, 2, 3) then 'T1'
        when extract(month from date_day) in (4, 5, 6) then 'T2'
        when extract(month from date_day) in (7, 8, 9) then 'T3'
        else 'T4'
    end as trimestre_label
from datas_geradas
