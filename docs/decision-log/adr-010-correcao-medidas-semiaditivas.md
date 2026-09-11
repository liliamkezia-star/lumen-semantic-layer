# ADR-010: Correção das medidas certificadas — tratamento semi-aditivo e catálogo v2

## Status
Aceito

## Contexto
Uma auditoria completa do repositório e do modelo semântico publicado
(lendo o código-fonte, os 9 ADRs anteriores e rodando consultas de
verificação contra `lumen.duckdb` e contra o modelo `lumen_semantico`
no Fabric) identificou que as 7 medidas certificadas registradas no
ADR-009 usavam `SUM()` direto sobre colunas de **saldo** —
`carteira_ativa`, `carteira_vencida`, `carteira_a_vencer`,
`carteira_inadimplencia`, `ativo_problematico` e `numero_de_operacoes`.

O `docs/data-dictionary.md` já classificava essas colunas como
**semi-aditivas**: podem ser somadas entre UF/modalidade/segmento dentro
da mesma competência, mas nunca ao longo do tempo. As medidas da v1
violavam essa regra. O próprio ADR-009 registra o sintoma sem
identificá-lo como bug: `[Carteira Ativa Total]` validado em
R$ 584,27 trilhões — a soma das 132 competências (jan/2015–dez/2025),
não o saldo real. O saldo real em dez/2025 é **R$ 7,44 trilhões**
(ordem de grandeza compatível com o mercado de crédito brasileiro; o
valor da v1 era ~48× o PIB do Brasil).

O risco não é apenas de exibição no dashboard (onde normalmente há
filtro de competência) — é o **agente analítico da Sprint 7+**, que
responde em linguagem natural sobre estas medidas certificadas.
Perguntado "qual o saldo total de crédito?" sem um filtro de período
explícito na pergunta, o agente responderia 584 trilhões com a mesma
confiança de uma resposta correta.

## Decisão
Substituir todas as medidas de saldo por uma versão que usa
`LASTNONBLANKVALUE` sobre `dim_calendario[data]`, garantindo que o
resultado seja sempre o saldo da **última competência dentro do
contexto de filtro** — nunca a soma de múltiplas competências. Isso é
o padrão correto para medidas semi-aditivas (contas de balanço, saldos
de estoque), documentado pela comunidade SQLBI.

Medidas renomeadas (removido o sufixo "Total", alinhando ao catálogo
`powerbi/medidas_certificadas_v2.dax`):
- `Carteira Ativa Total` → `Carteira Ativa`
- `Carteira Inadimplência Total` → `Carteira Inadimplência`
- `Carteira a Vencer Total` → `Carteira a Vencer`
- `Carteira Vencida Total` → `Carteira Vencida`
- `Ativo Problemático Total` → `Ativo Problemático`
- `Número de Operações`: mesmo nome, mesma correção (também é
  semi-aditiva — contagem de contratos vigentes na competência, não
  novas operações originadas)

Medidas novas adicionadas ao catálogo:
- **`Cobertura Nº de Operações`**: 26,3% das linhas de dez/2025
  (81.700 de 310.419) têm `numero_de_operacoes` nulo (sentinela `-1`
  na fonte). `SUM` ignora nulo silenciosamente, subestimando o total
  sem avisar. Esta medida expõe a cobertura e deve acompanhar o número
  sempre que ele for exibido.
- **`Inadimplência BCB (SGS 21082)`** e **`Divergência vs BCB (pp)`**:
  a taxa de inadimplência calculada do SCR.data (4,10% em dez/2025)
  convive no mesmo modelo com a série oficial do BCB via
  `fato_indicador_macro` (4,20% na mesma competência). As duas
  convergem — validação forte — mas sem rótulo de origem, a primeira
  reação de um leitor familiarizado com os dados de crédito é
  "esse número está errado". A referência do BCB também substitui a
  meta/orçamento que não existe em nenhuma tabela do projeto.
- **`Defasagem SCR vs SGS (meses)`**: `fato_credito` termina em
  dez/2025; as séries mensais do SGS avançam além disso. Cruzar os
  dois fatos no mesmo eixo temporal sem tratar essa defasagem produz
  uma queda visual falsa no fim da série de crédito.
- **`Aviso Decomposição 2015-2016`**: 5.869 linhas (99,98% concentradas
  em 2015–2016) onde `carteira_ativa` ≠ `carteira_a_vencer` +
  `carteira_vencida`. Aviso a exibir junto de qualquer visual que
  decomponha a carteira em suas partes.
- **`Velocidade da Deterioração`**, **`Título · Visão Geral`**,
  **`Subtítulo · Fonte e Competência`**, **`Título · Diagnóstico`**:
  títulos e o insight da página deixam de ser texto fixo e passam a
  ser calculados por medida — não ficam desatualizados quando a Gold
  for recarregada com uma nova competência.
- **`Última Competência com Crédito`**: medida auxiliar necessária
  porque o relacionamento `fato_credito` → `dim_calendario` é
  `OneDirection`. Sem um `CROSSFILTER(..., BOTH)` explícito,
  `MAX(dim_calendario[data])` sem filtro de página retorna o fim do
  calendário completo (`dim_calendario` foi gerado até 2026-12-31,
  além do fim real dos dados), não o fim real dos dados de crédito —
  o mesmo tipo de armadilha que motivou esta correção, encontrada de
  novo ao validar as medidas de referência externa.

## Alternativas consideradas
- **Manter `SUM()` e resolver só com filtro obrigatório no relatório**:
  rejeitado — não protege o agente analítico, que pode ser questionado
  sem filtro de período explícito.
- **`MAX(dim_calendario[data])` para achar a última competência**:
  tentado e descartado durante a implementação desta correção — falha
  exatamente pelo mesmo motivo que a v1 falhava (calendário construído
  além do fim dos dados reais), exigindo o `CROSSFILTER` acima.

## Consequências
- Positivo: as medidas certificadas agora retornam valores plausíveis
  com ou sem filtro de competência aplicado — pré-requisito para o
  agente da Sprint 7+ não herdar o erro.
- Positivo: duas fontes de "inadimplência" no mesmo modelo passam a
  ser rotuladas e comparadas explicitamente, transformando uma
  ambiguidade em prova de rigor.
- Atenção: `Cobertura Nº de Operações` deve sempre acompanhar
  `[Número de Operações]` em qualquer visual — nunca exibir a
  contagem isolada.
- Atenção: nenhum visual deve cruzar `fato_credito` e
  `fato_indicador_macro` no mesmo eixo temporal sem tratar a defasagem
  (`Defasagem SCR vs SGS (meses)`).
- Atenção: catálogo completo versionado em
  `powerbi/medidas_certificadas_v2.dax`; tema correspondente em
  `powerbi/lumen_theme_v2.json` (ver ADR a seguir sobre o dashboard,
  quando a Sprint do dashboard for concluída).
