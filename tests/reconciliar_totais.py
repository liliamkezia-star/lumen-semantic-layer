"""Reconciliação: compara o total agregado do SCR.data com o valor
oficial divulgado pelo Banco Central via SGS.

Duas fontes independentes do mesmo fenômeno (saldo de crédito no Brasil):
- SGS série 20539: valor consolidado publicado pelo BCB (R$ milhões)
- SCR.data: soma de carteira_ativa de todas as operações (R$)

Se os dois convergirem, é evidência de que a ingestão e a modelagem não
perderam nem duplicaram dados no caminho.
"""

import duckdb

CAMINHO_BANCO = "lumen.duckdb"

con = duckdb.connect(CAMINHO_BANCO, read_only=True)

print("Comparando saldo de crédito: SCR.data (agregado por nós) vs SGS (oficial BCB)\n")

resultado = con.execute("""
    with scr_agregado as (
        select
            date_trunc('month', data_base) as competencia,
            sum(carteira_ativa) as total_scr
        from silver.credito_uf_modalidade
        group by 1
    ),
    sgs_oficial as (
        select
            date_trunc('month', data_referencia) as competencia,
            valor as total_sgs_milhoes
        from silver.serie_credito_mensal
        where nome_serie = 'saldo_credito_total'
    )
    select
        strftime(scr.competencia, '%Y-%m') as competencia,
        round(scr.total_scr / 1000000, 0) as scr_em_milhoes,
        round(sgs.total_sgs_milhoes, 0) as sgs_em_milhoes,
        round((scr.total_scr / 1000000 - sgs.total_sgs_milhoes) / sgs.total_sgs_milhoes * 100, 2) as diferenca_percentual
    from scr_agregado scr
    inner join sgs_oficial sgs on sgs.competencia = scr.competencia
    order by scr.competencia desc
    limit 12
""").fetchall()

print(f"{'Competência':<12} {'SCR (R$ mi)':>15} {'SGS (R$ mi)':>15} {'Diferença':>12}")
print("-" * 58)
for linha in resultado:
    competencia, scr, sgs, diff = linha
    print(f"{competencia:<12} {scr:>15,.0f} {sgs:>15,.0f} {diff:>11.2f}%")

con.close()
