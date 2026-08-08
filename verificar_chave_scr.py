import duckdb

con = duckdb.connect("lumen.duckdb", read_only=True)

print("Verificando se as 10 colunas de dimensão formam chave única...")

resultado = con.execute("""
    select count(*) from (
        select
            data_base, uf, segmento, cliente, cnae_ocupacao, porte,
            modalidade, submodalidade, origem, indexador,
            count(*) as qtd
        from silver.credito_uf_modalidade
        group by 1,2,3,4,5,6,7,8,9,10
        having count(*) > 1
    )
""").fetchone()[0]

print(f"Combinações que aparecem mais de uma vez: {resultado}")

if resultado > 0:
    print("\nExemplos:")
    exemplos = con.execute("""
        select
            data_base, uf, modalidade, submodalidade, count(*) as qtd
        from silver.credito_uf_modalidade
        group by data_base, uf, segmento, cliente, cnae_ocupacao, porte,
                 modalidade, submodalidade, origem, indexador
        having count(*) > 1
        limit 5
    """).fetchall()
    for linha in exemplos:
        print(linha)

con.close()
