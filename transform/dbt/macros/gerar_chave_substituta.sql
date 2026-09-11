{#
    Gera uma chave substituta estável a partir das colunas da chave
    natural.

    Centraliza a lógica que antes estava duplicada em dim_modalidade e
    dim_segmento — qualquer ajuste (função de hash, separador, tratamento
    de nulos) passa a ser feito em um único lugar.

    Decisões embutidas:
    - hash() do DuckDB (UBIGINT, 64 bits) em vez de md5() (VARCHAR 32):
      chaves inteiras são mais eficientes para dicionarização e comparação
      em VertiPaq/Direct Lake e para joins SQL.
    - coalesce(coluna, '') evita que um nulo em qualquer coluna produza
      chave nula.
    - separador '|' entre as colunas evita colisões por concatenação
      ambígua (sem ele, ('ab','c') e ('a','bc') gerariam a mesma chave).

    Uso:
        {{ gerar_chave_substituta(['modalidade', 'submodalidade']) }}
#}

{% macro gerar_chave_substituta(colunas) %}
    hash(
        {%- for coluna in colunas %}
        coalesce({{ coluna }}, ''){% if not loop.last %} || '|' ||{% endif %}
        {%- endfor %}
    )
{% endmacro %}	
