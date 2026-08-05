# ADR-004: Silver mantém granularidade total, agregação fica para a Gold

## Status
Aceito

## Contexto
Ao planejar a tabela Silver do SCR.data (34,4 milhões de linhas), foi
inicialmente proposto agregar os dados já na Silver, para o grão final
"competência × UF × modalidade × segmento" definido no cronograma para a
camada Gold. Essa proposta foi questionada e identificada como
conceitualmente incorreta: mistura a responsabilidade da Silver (limpeza,
tipagem, deduplicação, mesma granularidade da fonte) com a responsabilidade
da Gold (agregação para o grão de consumo analítico).

Agregar prematuramente na Silver também é irreversível: uma vez resumido,
o detalhe original (por CNAE, porte, submodalidade etc.) não pode ser
recuperado se uma análise futura precisar dele.

## Decisão
A Silver do SCR.data mantém a granularidade original da fonte (mesma
granularidade da Bronze), aplicando apenas: tipagem correta, deduplicação
por chave natural (quando aplicável) e padronização de códigos/unidades.
A agregação para o grão "competência × UF × modalidade × segmento" será
realizada exclusivamente na camada Gold (Sprint 5), conforme o
planejamento original do projeto.

## Alternativas consideradas
- Agregar já na Silver (rejeitado: mistura responsabilidade de camadas,
  perde informação de forma irreversível, contraria o princípio de que
  a Silver deve refletir a fonte de forma confiável, não resumida).

## Consequências
- Positivo: mantém flexibilidade para análises futuras que exijam maior
  detalhe (ex: por porte de empresa, por CNAE).
- Positivo: separação clara de responsabilidade entre Silver e Gold,
  alinhada com o princípio da arquitetura medallion.
- Atenção: a Silver do SCR.data será uma tabela grande (~34,4M linhas),
  exigindo cuidado com performance de consultas até a agregação na Gold.
