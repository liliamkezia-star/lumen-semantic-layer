# ADR-017: RLS fora do escopo da v1.0 — segurança por linha conflita com o acesso do agente

## Status
Aceito

## Contexto

A Sprint 7 do plano original ("AI-readiness") reunia cinco itens
independentes: sinônimos nos objetos do modelo, descrições em todos os
objetos, colunas técnicas ocultas, um gate de Best Practice Analyzer na
CI, e **RLS** (segurança em nível de linha).

A sprint foi pulada na execução, e o README passou meses marcando-a como
"adiada — RLS conflita com o agente". Isso é uma anotação, não uma
decisão: não diz qual é o conflito, não separa o item bloqueado dos
quatro que não têm bloqueio nenhum, e não registra o que teria que ser
investigado para destravar. Este ADR existe para transformar a anotação
em decisão.

### Qual é o conflito, exatamente

Não é que "RLS não funciona em Direct Lake". É mais específico, e vem de
uma decisão anterior.

O agente consulta o modelo semântico pelo endpoint `executeQueries` da
API REST do Power BI. Como registrado no ADR-015, essa API **recusa
entidade de serviço em modelo com SSO, por design**, e um modelo Direct
Lake nasce com SSO ligado. A solução adotada foi ligar o
`lumen_semantico` a uma conexão de nuvem com **identidade fixa** (o SPN
`lumen-dbt-fabric`), com SSO desabilitado.

RLS filtra linhas pela identidade efetiva de quem consulta. Mas todas as
consultas do agente chegam ao modelo como **o mesmo service principal**,
independentemente de quem fez a pergunta. Implementar RLS hoje
produziria uma de duas coisas, ambas ruins:

- Se o SPN cair numa função de RLS, **todo mundo que usar o agente vê o
  mesmo recorte** — o do serviço. A garantia que justifica o RLS
  desaparece, e fica a aparência dela, que é pior que nada.
- Se o SPN não cair em nenhuma função, o modelo pode simplesmente
  recusar a consulta, derrubando o agente inteiro.

Ou seja: o conflito não é técnico-teórico, é uma consequência direta do
caminho de autenticação que o agente precisou usar para existir.

### O que da Sprint 7 já existe, por outro motivo

Dois dos cinco itens acabaram entregues — não pela Sprint 7, mas porque
o agente precisava deles para funcionar:

- **Catálogo exportado para consumo programático**: `agent/catalogo.py`
  lê o modelo via `INFO.VIEW.MEASURES()` e monta o catálogo que o agente
  enxerga.
- **Objetos técnicos fora do catálogo**: a mesma consulta filtra
  `NOT [IsHidden]`, e a curadoria do catálogo remove medidas de
  dashboard, medidas de texto e descrições que carregam valores.

**Não verificado:** se *todos* os objetos do modelo — tabelas e colunas,
não só medidas — têm descrição e estão corretamente ocultos. O agente
não precisou disso, então nunca foi auditado.

**Não existe:** sinônimos e gate de BPA na CI (o `ci.yml` atual não roda
Best Practice Analyzer).

## Decisão

1. **RLS fica fora do escopo da v1.0**, e a razão é o conflito acima —
   não falta de tempo.
2. **Os outros quatro itens da Sprint 7 não estão bloqueados** e passam
   a ser backlog explícito, não sprint adiada. Sinônimos e BPA na CI são
   baratos e independentes do agente; a auditoria de descrições e
   objetos ocultos é trabalho de conferência.
3. **O README deixa de dizer "Sprint 7 adiada"** e passa a apontar para
   este ADR, para que a distinção entre "bloqueado" e "não feito" fique
   visível a quem lê o repositório.

## Alternativas consideradas

- **Implementar RLS assim mesmo, aceitando que o agente veja tudo**:
  rejeitado. Um modelo com RLS configurado e um caminho de acesso que o
  contorna é pior que um modelo sem RLS: cria a impressão de controle
  onde não há. Segurança que só parece segurança é um passivo.
- **Trocar o caminho de acesso do agente para SSO por usuário**:
  rejeitado para a v1.0. Desfaria a decisão do ADR-015, que só foi
  tomada porque `executeQueries` recusa SPN em modelo com SSO — e o
  agente deixaria de poder rodar sem uma sessão interativa de usuário,
  o que inviabiliza a demonstração e qualquer execução automatizada,
  inclusive o benchmark.
- **Restringir o agente por catálogo em vez de por linha**: é o que já
  acontece, e vale registrar que **não substitui RLS**. O catálogo
  limita *quais métricas e cortes* existem, igual para todo mundo; RLS
  limita *quais linhas* cada pessoa vê. São controles diferentes, e o
  primeiro não cobre o segundo.
- **Abandonar a Sprint 7 inteira**: rejeitado. Quatro dos cinco itens
  não têm relação com o bloqueio, e jogá-los fora junto seria deixar
  dívida por associação.

## O que investigar se a S7 for retomada

Aberto, e honestamente não testado neste projeto:

- O `executeQueries` aceita identidade efetiva (`impersonatedUserName`)
  nesta combinação — Direct Lake, conexão de identidade fixa, SPN? Se
  aceitar, RLS volta a ser possível sem desfazer o ADR-015, e este ADR
  deve ser revisitado. **Não presumir que funciona: a mesma classe de
  suposição já custou uma investigação inteira de 401 no ADR-015.**
- Qual licenciamento a impersonação exige, e se ele sobrevive à decisão
  de capacity que vence em 24/10/2026 (ver `docs/finops.md`).

## Consequências

- Positivo: a distinção entre "decidimos não fazer" e "não deu tempo"
  fica registrada, com a razão técnica e com o caminho de volta.
- Positivo: quatro itens saem de uma sprint congelada e viram backlog
  acionável, que pode ser feito a qualquer momento sem depender do
  destravamento do RLS.
- Negativo, e é o custo real: **o Lumen não tem segurança em nível de
  linha.** Enquanto for um projeto sobre dados públicos agregados, isso
  não é um problema. No dia em que a mesma arquitetura for apontada para
  dado sensível ou segmentado por cliente, este ADR **bloqueia** o uso —
  e é para isso que ele está escrito.
- Atenção: qualquer proposta futura de "colocar o agente em cima de
  dados internos" tem que passar por aqui antes. O caminho de acesso por
  identidade fixa é adequado a dado público; não é adequado a dado com
  recorte por usuário.
