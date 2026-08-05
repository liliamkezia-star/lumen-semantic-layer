import duckdb

con = duckdb.connect("lumen.duckdb")

resultado = con.execute("""
    SELECT nome_serie, data_referencia, valor, timestamp_coleta,
        ROW_NUMBER() OVER (
            PARTITION BY nome_serie, data_referencia
            ORDER BY timestamp_coleta DESC
        ) AS numero_linha
    FROM bronze.sgs_series_raw
    WHERE nome_serie = 'selic_meta' AND data_referencia = '05/08/2016'
""").fetchall()

for linha in resultado:
    print(linha)
