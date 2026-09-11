"""P7, parte 2: será que o local tem linhas coletadas DEPOIS da migração
pro Fabric (25/08/2026), que o Fabric nunca recebeu porque foi uma
migração pontual (ADR-008), não uma sincronização contínua?
"""

import duckdb

con = duckdb.connect("lumen.duckdb", read_only=True)

print("=== timestamp_ultima_coleta das linhas de mar/2025 (Silver) ===\n")

resultado = con.execute("""
    select
        date_trunc('day', CAST(timestamp_ultima_coleta AS TIMESTAMP)) as dia_coleta,
        count(*) as linhas
    from silver.credito_uf_modalidade
    where date_trunc('month', data_base) = '2025-03-01'
    group by 1
    order by 1
""").fetchall()

print(f"{'Dia da coleta':<14} {'Linhas':>10}")
print("-" * 26)
for dia, linhas in resultado:
    print(f"{str(dia):<14} {linhas:>10,}")

print("\n(Migração para o Fabric ocorreu em 2026-08-25 — linhas coletadas")
print(" depois dessa data existem no local mas não foram para o Fabric)")

con.close()
