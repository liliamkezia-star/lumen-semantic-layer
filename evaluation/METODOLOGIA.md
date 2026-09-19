# Metodologia do benchmark: agente governado × text-to-SQL

Sprints 11–12 do plano. Este documento foi escrito e versionado **antes**
de qualquer rodada do benchmark: os critérios abaixo não podem ser
ajustados depois de ver os resultados. Se precisarem mudar, a mudança é
registrada aqui com data e motivo, e os resultados anteriores continuam
publicados.

## Pergunta que o experimento responde
Um LLM responde perguntas sobre crédito com mais exatidão quando escolhe
medidas de uma camada semântica certificada do que quando escreve SQL
direto sobre as tabelas?

A única variável é a camada semântica. Todo o resto é igual nas duas
abordagens: o mesmo modelo, as mesmas 60 perguntas, o mesmo dado.

## As duas abordagens

| | Agente governado | Baseline text-to-SQL |
|---|---|---|
| Modelo | `gemma-4-26b-a4b-it`, fixo | o mesmo |
| Acesso ao dado | só o modelo semântico, escolhendo medidas de um catálogo fechado | SQL livre sobre a Gold (`gold.fato_*`, `gold.dim_*`), via SQL endpoint |
| O que o modelo recebe | catálogo de medidas e cortes | schema das tabelas, com descrição das colunas |
| Quem escreve a consulta | código determinístico | o modelo |

O modelo é aberto e gratuito, não de ponta (custo zero de API, decisão
registrada no ADR-015). O resultado mede o ganho da camada semântica
**para esse modelo**.

## O gabarito
`gabarito.yaml`: 60 perguntas, 6 categorias × 10.

| Categoria | O que testa |
|---|---|
| A | Consulta direta — uma métrica, uma competência |
| B | Filtros e cortes — UF, região, modalidade, cliente, competência histórica |
| C | Rankings e comparações |
| D | **Semiaditividade** — carteira é estoque; variação de taxa é em pontos percentuais |
| E | **Macro e deflacionamento** — inflação acumulada é produto, não soma; séries diárias |
| F | Fora de escopo — o dado não existe; a resposta certa é recusar |

### Verificação independente
Cada resposta das categorias A–E foi calculada por **dois caminhos que
não compartilham código**: SQL escrito à mão sobre a Gold, e a medida
certificada da camada semântica. O gabarito só é congelado se os dois
baterem (tolerância relativa de 10⁻⁶, para diferenças de ordem de soma
em ponto flutuante). `python -m evaluation.verificar_gabarito` refaz a
verificação e trava o congelamento em qualquer divergência.

Primeira verificação, 2026-09-18: 50/50 perguntas numéricas batem pelos
dois caminhos. Três valores também conferem com fontes públicas: IPCA
2024 = 4,83%, IPCA 2025 = 4,26%, e o mínimo da taxa de inadimplência em
dez/2020 = 2,05%.

Para a categoria F, foi verificado por SQL que o dado realmente não
existe (Maranhão em jan/2026, carteira em 2014, Selic meta em dez/2026:
zero linhas; o SCR termina em 31/12/2025).

### Congelamento
As perguntas citam competências explícitas ("dezembro de 2025"), para o
gabarito não mudar quando a Gold ganhar uma competência nova. As
respostas congeladas ficam em `gabarito_congelado.json`, com a data de
verificação.

## Critérios de acerto (definidos antes de rodar)
Os mesmos para as duas abordagens.

| Tipo | Acerta quando |
|---|---|
| `valor` | a resposta contém o número certo no nível de arredondamento em que foi escrito. Sem casa decimal, só vale com ao menos 3 algarismos significativos ou se o valor certo for inteiro ("R$ 7 trilhões" não vale para R$ 7,44 Tri; "R$ 233 bilhões" vale para R$ 232,54 Bi). Escalas escritas por extenso contam: "R$ 7,44 trilhões", "R$ 7.444,29 bilhões" e o valor completo são a mesma resposta |
| `valores` | todos os números esperados aparecem, pelo mesmo critério |
| `ranking` | todos os nomes esperados aparecem, e o valor do primeiro colocado, pelo critério de `valor` |
| `recusa` | a resposta não afirma nenhum número sobre o dado pedido e sinaliza que ele não está disponível |

Unidade: "4,1%" e "0,041" são o mesmo número, mas só o primeiro é aceito
para uma taxa — apresentar uma fração como percentual (ou o contrário) é
erro, porque é exatamente o tipo de erro que um usuário leva adiante.

Pergunta sem resposta por falha de infraestrutura (cota esgotada, erro
de rede) não conta como erro nem acerto: é repetida.

## O que é medido
- **Acurácia**, geral e por categoria, para cada abordagem.
- **Recusa correta** (categoria F) — e, separadamente, **recusas
  indevidas** nas categorias A–E (recusar pergunta respondível é erro).
- **Latência** por pergunta.
- **Lastro** (só no agente): se algum número da resposta não veio de
  consulta. Não entra na acurácia, porque o baseline não tem esse
  conceito; é reportado à parte.

## Decisões de gabarito que precisam ser conhecidas
- **"A carteira de 2024" = posição de dezembro de 2024.** É a convenção
  certificada da camada (saldos são semiaditivos, ADR-010). Uma resposta
  que some os 12 meses, ou faça a média, está errada por este critério.
  Isso é a pegadinha da categoria D, não uma ambiguidade escondida.
- **Selic meta = média do mês** (série diária). A única pergunta sobre a
  Selic (E05) diz "em média" e usa dezembro de 2025, mês sem mudança de
  meta, para não haver duas respostas razoáveis.
- **C05 (modalidade com maior inadimplência) = "Adiantamentos a
  depositantes", 66,80%.** É uma modalidade pequena; a resposta é
  correta pelo dado, e o dashboard aplica um corte de materialidade que
  o gabarito deliberadamente não aplica, porque a pergunta não pede.
- **Medidas deflacionadas foram criadas antes do gabarito** (ADR-016).

## Registro de alterações
Toda mudança no gabarito ou nos critérios fica aqui, com data e motivo.

**2026-09-18 — antes de qualquer rodada do benchmark.** Um teste de
fumaça do baseline (3 perguntas, sem medir nada) mostrou que 13
perguntas sobre agregados nacionais tinham duas respostas razoáveis: a
taxa calculada do SCR.data (4,10%) e a série oficial do BCB (4,20%); a
carteira do SCR (R$ 7,44 Tri) e o saldo do SGS (R$ 7,14 Tri). O baseline
respondeu com a série oficial, o que é defensável. As 13 passaram a
citar a fonte ("Segundo o SCR.data, ..."). A mudança diz o que está
sendo perguntado, não como calcular, e vale igual para as duas
abordagens. As respostas esperadas não mudaram.

No mesmo teste, foram corrigidas descrições erradas da documentação da
Gold (`schema.yml` do dbt), que o baseline recebe como referência: a
coluna `numero_de_operacoes` era descrita como aditiva no tempo (é
estoque), e `segmento` e `porte` tinham exemplos que não correspondiam
aos valores reais. Também foi documentada a convenção de data (crédito
no último dia do mês, séries SGS mensais no primeiro). Sem essas
correções, o baseline seria penalizado por seguir uma documentação
errada.

**2026-09-18 — antes de qualquer rodada do benchmark.** Os testes do
corretor mostraram que a regra "sem casa decimal só se o valor certo for
inteiro" reprovava respostas corretas e precisas escritas em outra
escala ("7.444.294 milhões" para a carteira de R$ 7,44 Tri). A regra
existia para barrar arredondamentos grosseiros como "R$ 7 trilhões".
Refinada para: sem casa decimal, vale com ao menos 3 algarismos
significativos. O corretor também passou a comparar quantidades em vez
de texto, porque o baseline recebe números crus do SQL e pode escrever o
mesmo valor em trilhões, bilhões ou por extenso.

## Limitações conhecidas
- Um modelo só, e aberto: o resultado não se generaliza para modelos de
  ponta sem nova rodada.
- A detecção de recusa é por expressões ("não posso", "não há"...). Uma
  recusa escrita de forma incomum pode ser mal classificada; todas as
  respostas ficam salvas para revisão humana.
- As perguntas foram escritas por quem construiu a camada semântica. O
  risco de viés a favor dela é real e mitigado — não eliminado — pela
  verificação independente e pela categoria A, onde o baseline deve ir
  bem.
