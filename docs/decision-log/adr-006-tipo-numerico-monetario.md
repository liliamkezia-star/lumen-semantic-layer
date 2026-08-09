# ADR-006: Manutenção de DOUBLE (não DECIMAL) para colunas monetárias

## Status
Aceito

## Contexto
As colunas monetárias do SCR.data (`carteira_ativa`,
`carteira_inadimplencia`, `ativo_problematico`, `carteira_a_vencer`,
`carteira_vencida` e as 8 colunas de faixa de vencimento) são tipadas
como DOUBLE em toda a cadeia Bronze → Silver → Gold. O tipo vem da
inferência automática do `read_csv` do DuckDB na ingestão e é propagado
sem CAST nas camadas seguintes.

A convenção corporativa para dado financeiro é DECIMAL/NUMERIC com
precisão fixa, justamente porque ponto flutuante de dupla precisão não
representa valores decimais exatamente, e o erro se acumula em agregações.

## Medição realizada
Comparação direta de `SUM(carteira_ativa)` em DOUBLE versus o mesmo
cálculo com CAST para `DECIMAL(18,2)`, sobre as 34,4 milhões de linhas
da Silver:

| Cálculo | Resultado |
|---|---|
| SUM como DOUBLE | R$ 584.292.561.377.052,62 |
| SUM como DECIMAL(18,2) | R$ 584.292.561.377.055,48 |
| **Diferença absoluta** | **R$ 2,88** |
| **Diferença relativa** | **0,0000000000005%** |

## Decisão
Manter DOUBLE. Não converter as colunas monetárias para DECIMAL nesta
fase do projeto.

## Justificativa
- O erro medido (R$ 2,88 sobre R$ 584 trilhões) é ordens de magnitude
  menor que a menor unidade exibida em qualquer visualização do projeto,
  que apresenta valores em R$ milhões arredondados.
- Converter exigiria reprocessar 34,4 milhões de linhas em toda a cadeia,
  sem impacto observável em nenhum KPI.
- O erro é irrelevante frente à divergência metodológica de +2,9% a +4,5%
  já documentada na reconciliação com o SGS — são fenômenos de escalas
  incomparáveis, e o ponto flutuante não é causa daquela diferença.

## Alternativas consideradas
- **Converter para DECIMAL(18,2) na Silver**: rejeitado por custo de
  reprocessamento desproporcional ao ganho medido.
- **Converter apenas na Gold**: rejeitado — resolveria só parcialmente
  (agregações na Silver continuariam em DOUBLE) e criaria inconsistência
  de tipo entre camadas.

## Consequências
- Positivo: evita reprocessamento sem retorno prático.
- Atenção: se o projeto passar a exigir precisão ao centavo em alguma
  análise (ex: conciliação contábil linha a linha), esta decisão deve ser
  revisitada. O script de medição usado aqui pode ser reexecutado para
  reavaliar o erro sob os dados vigentes na ocasião.
- Atenção: a decisão vale para este projeto analítico. Em contexto
  transacional ou contábil, DECIMAL seria obrigatório.
