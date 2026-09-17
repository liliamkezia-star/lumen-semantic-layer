# ADR-014: Terceira ocorrência de data fixa em vez de âncora dinâmica

## Status
Aceito

## Contexto
Revisão externa do dashboard identificou que três medidas usadas no
dumbbell por modalidade da Página 1 tinham `DATE(2024,12,31)` e
`DATE(2025,12,31)` escritos literalmente no código:
`Taxa de Inadimplência (dez/2024)`, `Taxa de Inadimplência (dez/2025)` e
`Dumbbell · Elegivel (Materialidade)`.

Sintoma relatado: o título da página (`Título · Diagnóstico`, que usa
`[Carteira Vencida Δ% a/a]` — já ancorada em
`[Última Competência com Crédito]` desde o ADR-011) reage ao slicer de
competência; o dumbbell, alimentado pelas três medidas acima, não — ele
sempre mostra dez/2024 vs dez/2025, não importa o que o usuário
selecione. Quando a Gold receber uma competência nova (ex.: jan/2026),
o gráfico congelaria silenciosamente em dez/2025, sem nenhum aviso.

Esta é a **mesma classe de erro** do ADR-010 (medidas certificadas
somando competências no tempo) e do ADR-011 (comparativos ano a ano
herdando o fim do calendário gerado, não o fim real dos dados) — a
diferença é só onde a data fixa foi introduzida: aqui, direto como
literal `DATE(...)` em vez de uma função de time intelligence sem âncora.
Mesma causa raiz recorrente: qualquer medida que precise de "período
atual" ou "um ano antes" tem que passar por
`[Última Competência com Crédito]`, nunca por um valor fixo ou por uma
função de data sem âncora — e isso precisa ser conferido medida por
medida, não presumido a partir de uma correção anterior.

## Decisão
Trocar os três `DATE(2025,12,31)`/`DATE(2024,12,31)` por
`[Última Competência com Crédito]` e `EDATE(_Atual, -12)`, mesmo padrão
já estabelecido no ADR-011.

Os nomes das duas primeiras medidas (`Taxa de Inadimplência (dez/2024)`
e `(dez/2025)`) foram **mantidos**, não renomeados — apesar de o nome
sugerir uma data fixa que não existe mais no comportamento real. Isso é
uma dívida deliberada: renomear quebraria os campos já vinculados nos
visuais existentes (dumbbell da Página 1, tabela de reconciliação da
Página 5), exigindo re-trabalho manual no Power BI Desktop sem ganho de
correção — só de clareza de nome. Registrado aqui para não ser
confundido, no futuro, com um esquecimento.

## Validação
Consultado sem filtro (retorna dez/2024 e dez/2025, os valores reais
mais recentes) e com filtro `ano = 2022` (retorna dez/2021 e dez/2022
corretamente) — confirmado que as medidas agora seguem qualquer
competência selecionada, não só a mais recente.

## Consequências
- Positivo: dumbbell e título da Página 1 agora sempre respondem ao
  mesmo período, seja qual for o filtro ativo.
- Positivo: quando a Gold for recarregada com uma competência nova, o
  dumbbell avança sozinho — não precisa de outro ADR igual a este para
  cada novo mês.
- Atenção real, não resolvida por este ADR: **qualquer medida futura
  que use uma data literal (`DATE(...)`) para representar "a competência
  atual" ou "um período de referência" deve ser tratada como suspeita
  por padrão** — a auditoria e a própria autora já erraram esse padrão
  três vezes neste projeto (ADR-010, ADR-011, este). Antes de certificar
  uma medida nova, perguntar explicitamente: "isso ainda funciona depois
  que a Gold ganhar mais um mês de dado?"
- Nomes de medida desatualizados (`(dez/2024)`/`(dez/2025)`) permanecem
  como dívida cosmética — mencionar caso alguém audite o catálogo de
  novo e estranhe.
