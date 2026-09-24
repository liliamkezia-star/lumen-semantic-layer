# Memorando executivo — Lumen v1.0

**Data:** 24 de setembro de 2026
**Assunto:** resultado do projeto e as duas decisões que vencem em 60 dias

---

## Em uma frase

O Lumen mostra, com número medido, que um agente de IA preso a métricas
certificadas erra menos que o mesmo modelo escrevendo SQL livre — e que
a diferença aparece exatamente nas perguntas em que um erro passaria
despercebido numa reunião.

## O que foi entregue

Uma camada analítica completa sobre dados públicos de crédito do Brasil
(SCR.data, Banco Central, IBGE), em produção no Microsoft Fabric:

- **Pipeline** em arquitetura medalhão, do arquivo bruto ao star schema,
  versionado e testado.
- **Modelo semântico** Direct Lake com medidas certificadas — a
  definição única de "inadimplência", "carteira ativa" e afins.
- **Dashboard** Power BI de 5 páginas sobre esse modelo.
- **Agente analítico** que responde perguntas em português consultando
  só as medidas certificadas. O modelo de linguagem escolhe de listas
  fechadas; quem monta a consulta é o código. Ele nunca escreve DAX.

Nove das doze sprints do plano. Duas ficaram de fora por decisão
registrada, uma não foi iniciada — e o README diz isso.

## O resultado que importa

Sessenta perguntas, gabarito conferido por dois caminhos independentes
antes de qualquer teste, critérios de correção fechados de antemão.
O mesmo modelo nos dois lados, sobre as mesmas tabelas:

| | Agente governado | Text-to-SQL |
|---|---|---|
| Acertos | **59/60** | **53/60** |
| Recusas indevidas | 0 | 1 |
| Latência mediana | 21 s | 24 s |

**A leitura que interessa não é o placar, é onde ele se forma.** Em
consulta direta e ranking, os dois vão bem. A distância abre nas
perguntas que exigem saber que um saldo não se soma ao longo do tempo e
que crescimento precisa descontar inflação: 10/10 contra 7/10.

E cinco dos sete erros do text-to-SQL são **o mesmo erro**: a pergunta
pede o dado do SCR.data, ele consulta a série oficial do Banco Central e
apresenta o número como se fosse do SCR. A resposta sai plausível,
redonda e com a fonte trocada. É o tipo de erro que ninguém pega na
reunião — e é precisamente o que a camada certificada impede.

O agente também erra: em uma pergunta perdeu um filtro e respondeu a
carteira de um segmento inteiro no lugar de uma modalidade. O erro está
publicado no relatório, com o número errado escrito.

A governança não cobrou o preço que se costuma temer: o agente foi
**mais rápido** que o text-to-SQL, não mais lento.

## O que custou

**R$ 0 de desembolso direto.** Infraestrutura em capacity de trial do
Fabric, modelo de linguagem em nível gratuito. O gargalo do projeto
nunca foi dinheiro — foi cota de API, que limitou o benchmark a cerca de
85 respostas por dia e o espalhou por três dias. Detalhe em
[`finops.md`](finops.md).

## O que precisa de decisão

Nenhum destes é uma conta a pagar hoje. Todos viram uma — ou uma parada
— se a data passar sem decisão:

| Prazo | O que vence | Consequência |
|---|---|---|
| **24/10/2026** (30 dias) | Capacity de trial do Fabric | Dashboard e agente param. A capacity paga mínima (F2) já foi testada e **não** sustenta o pipeline; a cotação real começa em F4/F8 |
| **23/11/2026** (60 dias) | Client secret do service principal | Pipeline e agente perdem acesso. Renovação leva minutos, mas tem que ser feita |
| Sem data | Política de nível gratuito do fornecedor de IA | Muda sem aviso. Já mitigado no código por uma cadeia de modelos de reserva |

## Recomendação

1. **Decidir a capacity nos próximos 30 dias**, com cotação real de F4 ou
   F8 — é a única decisão com custo e prazo curto.
2. **Renovar o secret do SPN antes de 23/11**, independente do resto.
3. **Não tratar o agente como produto ainda.** Ele foi medido com um
   modelo aberto e gratuito, e as perguntas do teste foram escritas por
   quem construiu a camada. O número é forte, mas não se generaliza sem
   nova rodada.
4. **Se houver continuidade**, as duas frentes com maior retorno são as
   sprints que ficaram em aberto: AI-readiness (que exige resolver o
   conflito entre segurança por linha e o acesso do agente) e previsão
   explicável de inadimplência.

---

Relatório completo do benchmark, erro a erro:
[`../evaluation/resultados/rodada2.md`](../evaluation/resultados/rodada2.md).
Critérios e registro de toda alteração:
[`../evaluation/METODOLOGIA.md`](../evaluation/METODOLOGIA.md).
