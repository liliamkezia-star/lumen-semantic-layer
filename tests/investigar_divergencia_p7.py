"""Investigação pontual do P7: por que mar/2025 recalculado no Fabric
(R$ 6.781.116 mi) difere do valor no dicionário/reconciliação local
(R$ 6.790.705 mi, vindo de silver.credito_uf_modalidade).

Testa a hipótese: a diferença já existe entre Silver e Gold DENTRO do
próprio banco local (problema de transformação dbt), ou só aparece
quando comparado ao Fabric (problema de ambiente/migração)?
"""

import duckdb

con = duckdb.connect("lumen.duckdb", read_only=True)

print("=== Linhas e soma por camada, mar/2025 ===\n")

resultado = con.execute("""
    with silver_mar25 as (
        select
            count(*) as linhas,
            sum(carteira_ativa) / 1000000 as total_mi
        from silver.credito_uf_modalidade
        where date_trunc('month', data_base) = '2025-03-01'
    ),
    gold_mar25 as (
        select
            count(*) as linhas,
            sum(f.carteira_ativa) / 1000000 as total_mi
        from gold.fato_credito f
        join gold.dim_calendario c on f.id_data = c.id_data
        where c.data = '2025-03-31'
    )
    select 'Silver' as camada, linhas, round(total_mi, 0) as total_mi from silver_mar25
    union all
    select 'Gold' as camada, linhas, round(total_mi, 0) as total_mi from gold_mar25
""").fetchall()

print(f"{'Camada':<10} {'Linhas':>10} {'Total (R$ mi)':>15}")
print("-" * 37)
for camada, linhas, total in resultado:
    print(f"{camada:<10} {linhas:>10,} {total:>15,.0f}")

print("\n=== Se Silver == Gold aqui: o problema está no Fabric (migração). ===")
print("=== Se Silver != Gold aqui: o problema está na transformação dbt.  ===")

con.close()
