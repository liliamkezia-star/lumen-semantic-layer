# Benchmark: agente governado × text-to-SQL

Rodada `rodada2` · modelo `gemma-4-26b-a4b-it` nas duas abordagens · gabarito verificado em 2026-09-18 · critérios em [METODOLOGIA.md](METODOLOGIA.md).

## Acurácia por categoria

| Categoria | Agente | Baseline |
|---|---|---|
| A — Consulta direta | 10/10 | 9/10 |
| B — Filtros e cortes | 9/10 | 9/10 |
| C — Rankings e comparações | 10/10 | 10/10 |
| D — Semiaditividade (pegadinha) | 10/10 | 7/10 |
| E — Macro e deflacionamento (pegadinha) | 10/10 | 8/10 |
| F — Fora de escopo (recusar) | 10/10 | 10/10 |
| **Total** | **59/60** | **53/60** |

## Outros indicadores

| Indicador | Agente | Baseline |
|---|---|---|
| Recusas indevidas (pergunta respondível) | 0 | 1 |
| Latência mediana | 21 s | 24 s |
| Números sem lastro (só o agente tem o conceito) | 3 | — |

A latência acima é tempo de modelo: os 160 s de espera impostos pelo teto de tokens por minuto da cota gratuita estão descontados (ver METODOLOGIA.md).

## Erros, um a um

**agente** — 1 erro(s)

- `B09` Qual era a carteira de empréstimos a pessoas jurídicas em dezembro de 2025?
  - esperado: R$ 1,11 Tri — filtro perdido: respondeu PJ inteiro, sem a modalidade

**baseline** — 7 erro(s)

- `A02` Segundo o SCR.data, qual era a taxa de inadimplência do crédito em dezembro de 2025?
  - esperado: 4,10% — fonte trocada: usou a série do BCB e atribuiu ao SCR
- `B06` Segundo o SCR.data, qual era a taxa de inadimplência em dezembro de 2020?
  - esperado: 2,05% — fonte trocada: usou a série do BCB e atribuiu ao SCR
- `D04` Segundo o SCR.data, qual era a taxa de inadimplência no fim de 2024?
  - esperado: 2,99% — fonte trocada: usou a série do BCB e atribuiu ao SCR
- `D07` Segundo o SCR.data, em quantos pontos percentuais a taxa de inadimplência variou entre dezembro de 2024 e dezembro de 2025?
  - esperado: 1,11 pp — fonte trocada: variação calculada sobre a série do BCB
- `D10` Segundo o SCR.data, qual foi a taxa de inadimplência ao fim de cada trimestre de 2025?
  - esperado: 3,74%, 3,99%, 4,10%, 3,41% — fonte trocada: série do BCB nos quatro trimestres
- `E09` Qual foi o volume de concessões de crédito a pessoas físicas em dezembro de 2025?
  - esperado: R$ 407,48 Bi — recusa indevida: procurou concessões só na tabela de crédito
- `E10` Segundo o SCR.data e descontada a inflação, quanto a carteira de crédito ativa cresceu entre dezembro de 2020 e dezembro de 2021?
  - esperado: 5,69% — arredondamento: método certo, 5,68% contra 5,69%

## Reprodutibilidade

A rodada 1 foi invalidada por três bugs de infraestrutura (ver METODOLOGIA.md), mas as 84 respostas que ela alcançou servem para medir estabilidade. Nas perguntas que as duas rodadas têm em comum:

- **Baseline: nenhuma divergência entre as rodadas.** Os erros de fonte trocada se repetem pergunta a pergunta — são sistemáticos, não ruído de amostragem.
- **Agente: 6 divergências**, assim explicadas:
  - `B10`: errou na rodada 1 (submodalidade trocada) e acertou na 2 — variação do modelo
  - `D08`: rodada 1 falhou por token vencido (bug de infraestrutura, corrigido)
  - `D09`: rodada 1 falhou por token vencido (bug de infraestrutura, corrigido)
  - `D10`: rodada 1 falhou por token vencido (bug de infraestrutura, corrigido)
  - `E01`: rodada 1 falhou por token vencido (bug de infraestrutura, corrigido)
  - `E02`: rodada 1 falhou por token vencido (bug de infraestrutura, corrigido)

Descontada a infraestrutura, o agente variou em 1 das 42 perguntas comparáveis. O placar não deve ser lido como exato até a segunda casa; deve ser lido como uma diferença grande o bastante para não ser explicada por essa variação.

## Números sem lastro no agente

- `D07`: 1,11 — diferença entre dois valores certificados que o próprio agente consultou
- `E01`: 433 — falso positivo: 433 é o código da série SGS, que vem da descrição da medida
- `E03`: 33,3 — razão entre dois valores certificados que o próprio agente consultou

Nenhum dos três é um número inventado. O detector é deliberadamente severo: ele acusa qualquer número da resposta que não tenha saído de uma consulta, inclusive conta feita pelo agente sobre valores que ele mesmo consultou.
