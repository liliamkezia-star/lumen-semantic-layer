# FinOps: o que o Lumen custou

Este documento responde a uma pergunta só: **quanto foi desembolsado para
construir e operar o Lumen até a Sprint 12** — e onde o custo apareceria
se o projeto saísse do laboratório.

Desembolso direto até aqui: **R$ 0**. Isso não é sorte; é resultado de
três decisões registradas no decision-log, cada uma com um custo técnico
que o projeto aceitou em troca. A parte honesta deste documento é a que
lista esses custos técnicos e os prazos que já estão correndo.

## As quatro frentes onde o custo aparece

| Frente | Situação hoje | Pago? |
|---|---|---|
| Capacity do Fabric (computação) | Trial de 60 dias, desde 25/08/2026 | Não |
| Armazenamento (OneLake / Lakehouse) | Incluído na capacity | Não |
| API do modelo de linguagem (agente e benchmark) | Nível gratuito do Google (Gemini / Gemma) | Não |
| Licença de Power BI para consumo do relatório | Workspace na capacity de trial | Não |

## O que foi consumido de fato

Números medidos nos próprios registros do projeto, não estimados:

- **Agente**: 158 perguntas registradas em `agent/interacoes/` (fora do
  git, porque guarda perguntas de quem usa), das quais 56 terminaram em
  erro — a maioria esmagadora por cota esgotada, não por falha de código.
- **Benchmark**: 84 respostas na rodada 1 (invalidada, mantida como
  registro) e 120 na rodada 2, sempre 1 agente + 1 baseline por pergunta.
- **Tempo de modelo**: cerca de 1,5 h somando a latência de todas as
  respostas do benchmark.
- **dbt/Fabric**: as execuções da pipeline rodam em minutos sobre uma
  base que cabe folgadamente na capacity de trial; nenhuma execução foi
  barrada por falta de capacity desde a migração.

O gargalo real nunca foi dinheiro: foi **cota por minuto e por dia** do
nível gratuito. O `gemma-4-26b-a4b-it` entrega da ordem de 85 respostas
por dia, e foi isso — não o custo — que espalhou o benchmark por três
dias. Um benchmark de 120 respostas em um nível pago levaria minutos.

## As decisões que seguraram o custo em zero

1. **Capacity de trial em vez da F2 paga** (ADR-008). A F2 comprada com
   crédito do Azure rodava notebooks avulsos, mas não sustentava uma
   sessão Livy viva durante um `dbt run` completo. Com o trial liberado
   no mesmo dia, o workspace foi realocado e a F2 foi pausada. Custo
   técnico: o projeto passou a depender de um recurso com prazo.
2. **Gemini/Gemma no nível gratuito em vez de uma API paga** (ADR-015).
   A troca custou um arquivo — o adaptador de provedor —, porque a
   governança do agente não depende do modelo. Custo técnico: o agente
   depende de cota, e a arquitetura precisou de uma cadeia de reservas
   entre modelos para degradar sem quebrar.
3. **DuckDB local nas Sprints 1–5** (ADR-001). Enquanto o trial do
   Fabric estava bloqueado, o pipeline inteiro foi desenvolvido e
   testado localmente. Custo técnico: `dim_calendario` teve que ser
   reescrito para ser portável entre engines na hora da migração.

## Prazos que já estão correndo

Estes são os riscos financeiros reais do projeto — nenhum deles é uma
conta a pagar hoje, e todos viram uma se a data passar sem decisão:

- **Capacity de trial**: expira 60 dias após 25/08/2026. Quando expirar,
  a escolha é entre uma capacity paga maior e uma nova extensão. A F2 já
  foi testada e é insuficiente para sessões Livy sustentadas, então a
  cotação relevante começa em F4/F8 — e precisa ser feita na calculadora
  da Azure, com a região e o modelo de reserva reais, não estimada aqui.
- **Client secret do SPN**: expira 90 dias após a criação. Não custa
  dinheiro, mas derruba a pipeline e o agente no dia em que vencer.
- **Nível gratuito do modelo**: é política de fornecedor e pode mudar sem
  aviso. A mitigação já está no código (cadeia de reservas); a decisão de
  pagar só se justifica se o agente sair da demonstração.

## O que precisa ser cotado antes de produção

Deliberadamente sem números inventados — o que segue é a lista de
unidades a cotar, não uma previsão:

| Item | Unidade de cobrança | Onde cotar |
|---|---|---|
| Capacity Fabric (F4/F8) | CU-hora, com ou sem reserva anual | Calculadora de preços da Azure |
| Licença Power BI por consumidor | Pro/PPU por usuário/mês, ou capacity F64+ que dispensa Pro para leitura | Preços do Power BI |
| API do modelo | Tokens de entrada e saída, por milhão | Preços do provedor escolhido |

Para o agente, a unidade a projetar é **perguntas por dia × tokens por
pergunta**. O catálogo certificado enviado no prompt é o maior
componente fixo de entrada, e é justamente o que a curadoria do
`agent/catalogo.py` mantém enxuto: medidas de dashboard, medidas de
texto e descrições com valor embutido ficam de fora. Cortar catálogo é,
literalmente, cortar conta.
