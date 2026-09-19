# ADR-015: Arquitetura do agente analítico governado (Sprint 8)

## Status
Aceito — caminho de execução validado ponta a ponta em 2026-09-18

## Contexto
O README do projeto promete, desde a Sprint 1, um "agente analítico
governado capaz de responder perguntas em linguagem natural com base em
métricas certificadas — **sem gerar SQL/DAX livre**". As Sprints 1-7
entregaram a metade de dados dessa promessa (Bronze/Silver/Gold, modelo
semântico Direct Lake, catálogo de medidas certificadas, dashboard). O
agente em si nunca foi iniciado: não existe código, nem ADR, e o
`docs/architecture.md` termina o fluxo no modelo semântico.

A restrição central não é técnica, é de governança. Um agente que
escreve DAX/SQL livre contra a Gold é fácil de construir e é exatamente
o que este projeto **não** quer: ele recalcula métricas por conta
própria, diverge do catálogo certificado, e reintroduz em linguagem
natural os mesmos erros que as ADR-010, 011 e 014 documentam ter
acontecido quando uma medida é escrita sem âncora. Se o agente pode
inventar a métrica, toda a camada semântica vira decoração.

## Decisão

### 1. O modelo escolhe medidas, não escreve consultas
O LLM recebe ferramentas cujos parâmetros são **restritos ao catálogo
certificado**. Ele nunca emite DAX; ele escolhe:

- uma medida, validada contra a lista de medidas certificadas do
  `lumen_semantico` (obtida do próprio modelo, não de uma cópia que
  pode divergir — mesmo princípio de sincronia do
  `powerbi/medidas_certificadas_v2.dax`);
- filtros, validados contra colunas e valores reais das dimensões
  (`dim_calendario`, `dim_modalidade`, `dim_uf`, `dim_segmento`);
- opcionalmente uma dimensão de agrupamento, para comparação e ranking.

Código Python determinístico monta a consulta DAX a partir desses
parâmetros validados e a executa. Medida fora do catálogo, coluna
inexistente ou valor de filtro inválido retornam erro com a lista de
opções válidas — o agente corrige a escolha, não a sintaxe.

Consequência prática: o conjunto de perguntas respondíveis é exatamente
o conjunto de combinações medida × corte que a camada semântica
certifica. Isso é a definição de "governado" neste projeto.

### 2. Execução via API REST, reusando o SPN do ADR-008
As consultas vão para o endpoint `executeQueries` da API REST do Power
BI, autenticadas com o mesmo Service Principal (`lumen-dbt-fabric`) já
usado pelo dbt desde o ADR-008 — sem criar um segundo caminho de
autenticação.

**Pré-requisito de tenant a validar antes de escrever código**: assim
como o ADR-008 precisou da configuração "Entidades de serviço podem
chamar APIs públicas do Fabric", o `executeQueries` depende da
configuração de locatário que libera a API de consultas a entidades de
serviço. Historicamente essa classe de configuração foi a causa raiz de
404/403 silenciosos neste tenant — validar com uma consulta trivial
(`EVALUATE ROW("teste", 1)`) é o primeiro passo da implementação, antes
de qualquer outra coisa.

**Resultado da validação (ver seção Validação abaixo): o caminho REST
exige desligar o SSO da conexão do modelo.** A API recusa entidade de
serviço em modelo com SSO por design, e Direct Lake nasce com SSO. O
modelo `lumen_semantico` passa a ser ligado a uma conexão de nuvem com
identidade fixa (o próprio SPN `lumen-dbt-fabric`), com SSO desabilitado.

### 3. Interpretação é permitida, mas sempre ancorada
O agente pode comparar períodos, ranquear cortes e escrever uma leitura
do resultado. A regra que separa dado de opinião: **todo número que
aparece na resposta tem que ter vindo de uma consulta executada naquela
conversa**, nunca da memória do modelo. A resposta exibe o dado
certificado e a leitura em blocos visualmente distintos.

Isso não é uma concessão: é o mesmo padrão que o dashboard já usa na
medida `Insight · Concentração da Deterioração`, que interpreta ("a
deterioração está concentrada em X") em cima de valores certificados.

### 4. Stack
- **Modelo**: Google Gemini pela API gratuita, via o SDK `google-genai`,
  com execução automática de ferramentas. Cadeia de reserva:
  `gemini-3.6-flash` → outros Flash → `gemma-4-26b-a4b-it` →
  `gemma-4-31b-it`. Na avaliação e no benchmark, um modelo fixo
  (`gemma-4-26b-a4b-it`), sem reserva — ver seção Provedor.
- **Isolamento do provedor**: só `agent/agente.py` conhece o provedor.
  Catálogo, validação e montagem de DAX (`catalogo.py`, `consultas.py`,
  `ferramentas.py`) não sabem qual modelo está do outro lado.
- **Interface**: app Streamlit, com a lógica do agente isolada em um
  módulo Python reutilizável (a interface não pode ser o único lugar
  onde a regra de governança existe — os testes precisam chamar o mesmo
  caminho).

### Provedor: por que Gemini, e não Claude como na primeira versão
A primeira versão deste ADR previa `claude-opus-5`. A autora optou por
custo zero de API, e a troca custou um arquivo, porque a governança não
depende do provedor. No nível gratuito, os Gemini Flash esgotavam a cota
em ~3 perguntas; os Gemma 4 (modelos abertos do Google, na mesma API)
têm cota separada e suportam ferramentas, e viraram o modelo da
avaliação.

O limite que interrompia as rodadas é **por minuto**, não diário — a
cota voltava minutos depois. A avaliação espera a janela virar e repete
o caso, em vez de abortar.

Consequência para o benchmark do plano (Sprints 11–12): a comparação
agente × text-to-SQL será feita com um modelo aberto e gratuito, não com
um modelo de ponta. A comparação continua justa — o mesmo modelo nas
duas abordagens —, mas o resultado mede o ganho da camada semântica
*para esse modelo*, e o artigo precisa dizer isso.

## Alternativas consideradas
- **Text-to-DAX / text-to-SQL livre**: rejeitado. É a abordagem mais
  comum e a mais fácil de demonstrar, mas contradiz o motivo de existir
  do projeto. Uma métrica recalculada pelo modelo não passou por
  nenhuma das correções das ADR-010/011/014, e o usuário não tem como
  saber disso olhando a resposta.
- **Consultar a Gold diretamente (SQL no Lakehouse), pulando o modelo
  semântico**: rejeitado. As medidas certificadas são semiaditivas
  (`LASTNONBLANKVALUE`, ADR-010) e ancoradas em
  `[Última Competência com Crédito]`; reimplementar essa lógica em SQL
  criaria uma segunda definição da mesma métrica, que divergiria na
  primeira correção feita só de um lado.
- **XMLA via `pyadomd`**: mantido como alternativa, não como primeira
  escolha. Depende das bibliotecas cliente ADOMD.NET instaladas na
  máquina, o que atrapalha CI e portabilidade. Vira o plano B se o
  `executeQueries` esbarrar em limitação de entidade de serviço.
- **Agente sem interpretação, só devolvendo números**: considerado e
  rejeitado pela autora — entrega menos do que o dashboard já entrega
  hoje, o que tornaria o agente um retrocesso e não o próximo passo.

## Validação (2026-09-18): por que a identidade fixa é obrigatória
A primeira tentativa de consultar o modelo com o SPN falhou com
`401 PowerBINotAuthorizedException`. O diagnóstico, feito por
eliminação, vale registro porque **o sintoma parece permissão mal
configurada e não é** — perseguir permissão teria custado horas.

O que foi medido, não presumido:

| Verificação | Resultado |
|---|---|
| Listar datasets / metadados / fontes do dataset | 200 — token e acesso ao workspace OK |
| `GET datasets/{id}/users` e `POST executeQueries` | 401 |
| Papel do SPN no workspace | `Contributor` (confirmado via API) |
| RLS no modelo | ausente (`isEffectiveIdentityRequired: false`) |
| Configs de locatário | "Execute Queries REST API" e "Service principals can call Fabric public APIs" ambas habilitadas |

Com permissão, token e RLS descartados, a causa está na documentação da
própria API: *"regardless of the admin tenant setting, Service
Principals aren't supported for datasets with RLS [...] or datasets with
**SSO enabled**"* — combinado com o comportamento padrão do Direct Lake:
*"By default, Direct Lake uses SSO (Microsoft Entra ID) and uses the
identity of the current user querying the semantic model."*

Não é uma configuração faltando, é uma incompatibilidade por design
entre entidade de serviço e SSO nessa API.

**Alternativa considerada e rejeitada**: usar XMLA em vez de REST. O
XMLA não tem essa restrição e já estava comprovadamente funcionando na
máquina de desenvolvimento. Rejeitado porque exige as bibliotecas
ADOMD.NET instaladas em qualquer ambiente que rode o agente — o CI deste
projeto roda em Ubuntu no GitHub Actions, e a dependência nativa
quebraria a portabilidade que o resto do projeto mantém.

**Decisão**: ligar o modelo a uma conexão de nuvem com identidade fixa
(autenticação de Service Principal, o mesmo `lumen-dbt-fabric`) e SSO
desabilitado. O efeito colateral — quem consulta o modelo passa a usar a
permissão da identidade fixa, não a própria — é nulo neste projeto: não
há RLS, o dado é público do BCB e há uma única dona. É também o padrão
que a documentação recomenda para este caso de uso ("*use a
fixed-identity cloud connection for embedded or read-only consumer
scenarios where source-level access is scoped to a single service
account*").

**Resultado**: com a conexão de identidade fixa criada e efetivamente
vinculada ao modelo, o `executeQueries` passou a responder. Validado com
medidas certificadas reais, não com um teste sintético:

| Retorno | Valor |
|---|---|
| `[Última Competência com Crédito]` | 2025-12-31 |
| `[Carteira Ativa]` | 7.444.293.999.119,22 (R$ 7,44 Tri) |
| `[Taxa de Inadimplência (SCR.data)]` | 0,041044414 (4,10%) |

Os três batem com os valores validados no dashboard da Sprint 7, o que
confirma que o caminho REST devolve as medidas certificadas do modelo —
não um recálculo paralelo.

**Armadilha de diagnóstico registrada para o futuro**: entre criar a
conexão e vinculá-la ao modelo há dois passos distintos, e o 401 é
idêntico quando só o primeiro foi feito. Uma rodada inteira de
investigação foi gasta porque a conexão existia mas não estava
vinculada. A API não permite distinguir os dois estados — o
`Default.GetBoundGatewayDataSources` responde `DMTS_MonikerNotFoundError`
nos dois casos, porque Direct Lake não usa o mecanismo de moniker de
gateway. Verificar o vínculo pela tela do modelo, não pela API.

## Consequências
- Positivo: qualquer resposta do agente é rastreável até uma medida
  certificada e versionada — a mesma prova de rigor que a Página 5 do
  dashboard dá visualmente, agora em linguagem natural.
- Positivo: quando uma medida é corrigida no modelo (como as quatro
  ocorrências da armadilha do calendário), o agente passa a responder
  certo automaticamente, sem mudança de código.
- Custo real: perguntas fora do catálogo não têm resposta. O agente
  precisa recusar explicitamente e dizer o que **sabe** responder, em
  vez de improvisar — recusar bem é requisito de produto aqui, não caso
  de borda.
- Dependência nova: chave da API do Gemini (`GEMINI_API_KEY` no `.env`,
  fora do git), no nível gratuito.
- Dependência operacional herdada, agora com mais um consumidor: o
  client secret do SPN expira (90 dias a partir de 2026-08-25, conforme
  registrado no ADR-008). Até hoje o vencimento derrubaria só o `dbt`;
  a partir do agente, derruba também as respostas em produção. Renovar
  o secret passa a ser tarefa de manutenção com dois dependentes, não
  um.
- A avaliação do agente precisa existir desde o começo, no mesmo
  espírito de `tests/reconciliar_totais.py`: um conjunto de perguntas
  com resposta certa conhecida (ex.: inadimplência de dez/2025 = 4,10%,
  carteira ativa = R$ 7,44 Tri), para provar que ele não alucina em
  cima de métrica certificada. Sem isso não há como afirmar que o
  agente é governado — só que ele foi projetado para ser.

## Avaliação (2026-09-18)
`python -m agent.avaliacao --modelo gemma-4-26b-a4b-it`: 16 casos, com
gabarito calculado na hora pela camada certificada (não escrito à mão,
para não quebrar quando a Gold ganhar competência nova).

Resultado da primeira rodada completa: **15/16**.
- 12/12 perguntas factuais com o valor e o DAX certos (valor simples,
  filtro, competência histórica, rankings de UF/região/modalidade,
  referência do BCB, Selic).
- 4/4 recusas corretas (banco, previsão, município, juros), sem número
  inventado e com a alternativa mais próxima oferecida.
- 1 falha: o caso de continuação — ver seção abaixo.

Três recusas corretas foram inicialmente reprovadas pelo corretor, que
não reconhecia "não posso" e "não possuo". Erro do corretor, corrigido e
coberto por teste com as frases reais do agente.

## Ajuste da regra de lastro (feito depois de uma falha — registrado por isso)
A regra original mandava o agente **consultar de novo** qualquer número
numa pergunta de continuação, e o corretor exigia lastro só no turno
atual. No caso "e de PJ?", o agente consultou o PJ (2,49%) mas comparou
com os 5,15% de PF da pergunta anterior sem reconsultar. O número estava
certo — tinha vindo de consulta certificada um turno antes —, mas a regra
foi desobedecida.

A regra foi relaxada para: **valor já trazido por consulta nesta
conversa pode ser citado de novo; valor novo exige consulta**. O
corretor passou a aceitar lastro de qualquer consulta da conversa.

Este ajuste foi feito **depois** de o modelo falhar na regra antiga, o
que tem aparência de mover a trave para melhorar o placar. O argumento
precisa valer sem o placar: o risco que a regra existe para evitar é
citar número **não certificado**, e esse continua bloqueado — há teste
garantindo que um número nunca consultado em nenhum turno reprova.
Reconsultar um número já certificado na mesma conversa não aumenta a
exatidão; só gasta a cota que no nível gratuito é o recurso escasso.

Com a regra ajustada, o caso de continuação foi rodado de novo e passou:
o agente consultou o PJ (2,49%) e a competência, e citou os 5,15% de PF
da consulta feita na primeira pergunta da conversa. **Placar honesto:
15/16 pela regra original, 16/16 pela regra ajustada** — os dois números
ficam registrados, e não só o melhor.
