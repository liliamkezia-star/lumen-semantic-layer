# Lumen

**Camada semântica certificada sobre dados públicos de crédito do Brasil, com um agente analítico que não pode inventar métrica.**

Pipeline em arquitetura medalhão no Microsoft Fabric, modelo semântico Direct Lake, dashboard Power BI de 5 páginas e um agente que responde perguntas em português usando **só** medidas certificadas — o modelo de linguagem escolhe de listas fechadas, e quem monta a consulta é o código.

---

## O resultado

A tese de que uma camada certificada reduz erro de IA costuma ser afirmada e raramente medida. Aqui ela foi medida, com o **mesmo modelo** nos dois lados e sobre as **mesmas tabelas**:

| | Agente governado | Text-to-SQL livre |
|---|---|---|
| **Acertos em 60 perguntas** | **59/60** | **53/60** |
| Semiaditividade (pegadinha) | 10/10 | 7/10 |
| Recusas indevidas | 0 | 1 |
| Latência mediana | 21 s | 24 s |

**A diferença não está no básico.** Em consulta direta e ranking os dois vão bem. Ela abre nas pegadinhas — e **5 dos 7 erros do text-to-SQL são o mesmo erro**: a pergunta pede o dado do SCR.data, ele consulta a série oficial do Banco Central e apresenta o número como se fosse do SCR, citando a fonte errada.

Número real, ordem de grandeza certa, fonte citada. Nenhum detector de alucinação pega isso.

→ [Relatório completo, erro a erro](evaluation/resultados/rodada2.md) · [Metodologia e critérios](evaluation/METODOLOGIA.md) · [detalhes do benchmark](#o-benchmark)

![Página 1 do dashboard Lumen](docs/assets/dashboard-pagina1.png)

---

## O que existe

| Camada | Conteúdo |
|---|---|
| **Bronze** | 3 fontes ingeridas, append-only, com validação de schema e retry — no Lakehouse do Fabric |
| **Silver** | 5 tabelas limpas, tipadas e deduplicadas |
| **Gold** | Star schema com 4 dimensões e 2 fatos (~34,4M linhas no fato principal), em dbt sobre o Fabric via `dbt-fabricspark` |
| **Modelo semântico** | `lumen_semantico` em Direct Lake, com o catálogo de medidas versionado em [`powerbi/medidas_certificadas_v2.dax`](powerbi/medidas_certificadas_v2.dax) |
| **Dashboard** | 5 páginas em Power BI sobre o modelo semântico: visão geral, recorte geográfico, contexto macro, ficha de segmento (drill-through) e notas metodológicas |
| **Agente** | Perguntas em português respondidas com medidas certificadas, com interface Streamlit autenticada |
| **Benchmark** | 60 perguntas com gabarito verificado por dois caminhos independentes, e um baseline text-to-SQL para comparar |

**Stack:** Python, dbt, GitHub Actions, Microsoft Fabric (Lakehouse + Direct Lake), Power BI, Deneb/Vega-Lite, Streamlit e a API gratuita do Google (Gemini e Gemma). Execução local com DuckDB continua disponível como alvo de desenvolvimento e CI.

**Qualidade:** 132 testes pytest e 20 testes dbt, rodando na CI a cada PR. O total agregado do SCR.data foi reconciliado com a série oficial do BCB, com a divergência metodológica documentada em [`docs/data-dictionary.md`](docs/data-dictionary.md).

---

## Como o agente funciona

```
pergunta ──▶ LLM escolhe medida + cortes ──▶ validação contra o catálogo ──▶ DAX montado por código
                    ▲                              │ inválido: recusa com as opções válidas
                    └──── resultado formatado ◀────┴── executeQueries no lumen_semantico
```

O ponto inteiro cabe numa frase: **o modelo de linguagem nunca escreve consulta.** Ele preenche um formulário — medida, corte e valor, cada um de uma lista fechada. Pedido fora da lista é recusado antes de virar consulta, e ele recebe de volta as opções válidas.

Duas regras completam a governança:

- **Lastro.** Todo número que aparece na resposta tem que ter vindo de uma consulta executada naquela conversa, nunca da memória do modelo.
- **Formatação pelo catálogo.** A unidade de cada medida é declarada, então quem decide se `0,041` vira "4,10%" é o código. Deixar isso a cargo do LLM é convidar o erro para entrar.

Detalhes em [`agent/guardrails.md`](agent/guardrails.md) e [ADR-015](docs/decision-log/adr-015-arquitetura-agente-governado.md).

---

## O benchmark

Um benchmark feito por quem construiu a solução tem um problema óbvio de viés. O que resolve não é boa intenção, é amarrar as próprias mãos antes de começar:

- **Gabarito verificado por dois caminhos independentes** antes de qualquer rodada: SQL escrito à mão na Gold e a medida certificada. Divergiram em zero das 50 perguntas numéricas.
- **Critérios de correção fixados antes de rodar**, e toda alteração posterior registrada com data e motivo em [`METODOLOGIA.md`](evaluation/METODOLOGIA.md).
- **A primeira rodada inteira foi invalidada** por três bugs de infraestrutura meus — token vencido, descrição de medida vazando valor, e `2025-12` lido como `-12`. Ela continua no repositório, marcada como inválida, porque apagar teria sido mais limpo e menos honesto.
- **Todas as respostas erradas foram lidas uma a uma** antes de o placar ser aceito. Foi assim que um falso positivo do detector de lastro foi pego antes de virar resultado publicado.

### Acurácia por categoria

| Categoria | Agente | Text-to-SQL |
|---|---|---|
| A — Consulta direta | 10/10 | 9/10 |
| B — Filtros e cortes | 9/10 | 9/10 |
| C — Rankings e comparações | 10/10 | 10/10 |
| D — Semiaditividade (pegadinha) | **10/10** | **7/10** |
| E — Macro e deflacionamento (pegadinha) | **10/10** | **8/10** |
| F — Fora de escopo (deve recusar) | 10/10 | 10/10 |
| **Total** | **59/60** | **53/60** |

### O agente também erra

Em B09 ele perdeu o filtro de modalidade e respondeu a carteira PJ inteira (R$ 2,92 Tri) no lugar de empréstimos a PJ (R$ 1,11 Tri). Errar o filtro é diferente de errar a fonte — o número fica quase três vezes maior, e alguém percebe —, mas continua sendo errar.

### O que este número não prova

Um modelo só, aberto e gratuito: não se generaliza para modelos de ponta sem nova rodada. As perguntas foram escritas por quem construiu a camada, e o viés foi mitigado pela verificação independente e pela categoria A (onde o baseline deveria ir bem, e foi) — mitigado, não eliminado. E há variação entre execuções: nas 84 perguntas que as duas rodadas têm em comum, o baseline não divergiu em nenhuma, mas o agente divergiu em uma. O placar vale como diferença de ordem de grandeza, não como número exato.

---

## Três decisões de design que eu defendo

**1. Toda medida de "período atual" passa por uma única âncora dinâmica.** Nunca `MAX()`, `SAMEPERIODLASTYEAR()` ou data literal. `dim_calendario` é gerada por `dbt_utils.date_spine()` até 2026-12-31, bem além do fim real dos dados (dez/2025), e o relacionamento com `fato_credito` é OneDirection. Sem uma âncora que force `CROSSFILTER(..., BOTH)`, qualquer medida de "competência atual" escaneia o calendário inteiro e erra em silêncio. Essa classe de erro apareceu **quatro vezes** neste projeto ([ADR-010](docs/decision-log/adr-010-correcao-medidas-semiaditivas.md), [011](docs/decision-log/adr-011-correcao-comparativos-ano-anterior.md), [014](docs/decision-log/adr-014-terceira-ocorrencia-data-fixa.md)) até virar regra fixa, verificada medida a medida.

**2. Field parameter trocado por slicer comum, contra a recomendação literal da auditoria** ([ADR-013](docs/decision-log/adr-013-field-parameter-inviavel-conexao-live.md)). Field parameter exige modelo local, e modelo local é uma decisão que já havia sido rejeitada para não duplicar 34,4M de linhas. Prefiro manter a arquitetura Direct Lake com o trade-off documentado a violar uma decisão estrutural anterior por uma diferença semântica de interação.

**3. O painel duplo resolve o desalinhamento desligando o eixo Y, não compensando por pixel.** As duas séries têm rótulos de larguras diferentes ("R$ 8 Tri" contra "4%") e o Power BI calcula a área de plot de cada visual separadamente. Empurrar pixels quebraria a cada mudança de fonte, DPI ou resolução; desligar o eixo de valor resolve de um jeito que não depende de medida nenhuma em pixels.

---

## Como rodar

Crie um `.env` na raiz (fora do git):

```
GEMINI_API_KEY=...          # gratuita em https://aistudio.google.com/apikey
LUMEN_SENHA_DEMO=...        # senha de entrada da demonstração
```

As credenciais do Fabric vêm do `~/.dbt/profiles.yml` (o mesmo SPN do dbt) ou das variáveis `FABRIC_TENANT_ID`, `FABRIC_CLIENT_ID` e `FABRIC_CLIENT_SECRET`.

```bash
# agente
streamlit run agent/app.py

# o duelo entre as duas abordagens, lado a lado
streamlit run evaluation/app_duelo.py
python -m evaluation.duelo --id D04 --pausa

# avaliação e benchmark (consomem cota da API)
python -m agent.avaliacao --modelo gemma-4-26b-a4b-it
python -m evaluation.verificar_gabarito
python -m evaluation.benchmark --rodada minha_rodada
python -m evaluation.relatorio evaluation/resultados/minha_rodada.jsonl
```

### Sobre a cota gratuita

O teto que mais atrapalha não é o de requisições por dia, e sim o de **tokens de entrada por minuto**: como cada chamada com ferramenta reenvia a conversa inteira, uma única pergunta pode estourá-lo quando alguma consulta devolve muito texto. Por isso o benchmark espaça as chamadas ([`agent/ritmo.py`](agent/ritmo.py)) e desconta essa espera da latência medida. Com a cota esgotada, o agente cai para o próximo modelo da cadeia de reserva.

O custo do projeto está em [`docs/finops.md`](docs/finops.md): **R$ 0 de desembolso**.

---

## Reproduzir do zero

```bash
python -m venv .venv && source .venv/Scripts/activate
pip install -r requirements.txt

python ingestion/ingestir_sgs.py
python ingestion/ingestir_scr_data.py   # ~2 GB de download, leva tempo
python ingestion/ingestir_ibge.py

python transform/silver/silver_sgs.py
python transform/silver/silver_scr_data.py
python transform/silver/silver_ibge.py

cd transform/dbt && dbt build           # --target dev (DuckDB) ou --target fabric
```

---

## Estrutura

```
agent/              agente governado: catálogo, consulta, ferramentas, interface, guardrails
evaluation/         benchmark: gabarito das 60 perguntas, baseline text-to-SQL, corretor, relatórios
ingestion/          ingestão (Bronze), versão local em DuckDB
transform/silver/   transformação (Silver), versão local em DuckDB
transform/dbt/      projeto dbt: staging + star schema Gold, contra DuckDB ou Fabric
fabric/notebooks/   notebooks PySpark equivalentes, para rodar no Fabric
powerbi/            catálogo de medidas DAX, tema e specs Deneb do dashboard
docs/               dicionário de dados, arquitetura, ADRs, finops e material de lançamento
tests/              testes de qualidade (pytest) e utilitários de CI
common/             utilitários compartilhados
```

---

## Fontes de dados

- **SCR.data (Banco Central)** — crédito por UF, modalidade e segmento (~34,4 milhões de linhas, 2015–2025)
- **SGS (Banco Central)** — séries de Selic, IPCA e crédito nacional
- **IBGE** — localidades e população por UF

Detalhes em [`docs/data-dictionary.md`](docs/data-dictionary.md) e `ingestion/contracts/`.

---

## Decisões técnicas

As decisões de arquitetura são registradas em [`docs/decision-log/`](docs/decision-log/) conforme acontecem no desenvolvimento real, não como uma lista predefinida. Inclusive as investigações que não fecharam.

| ADR | Decisão |
|---|---|
| [001](docs/decision-log/adr-001-execucao-local-duckdb.md) | Execução local com DuckDB nas Sprints 1–5, com plano explícito de migração para o Fabric |
| [002](docs/decision-log/adr-002-scr-data-download-zip.md) | Ingestão do SCR.data por ZIP anual, não OData como planejado |
| [003](docs/decision-log/adr-003-bronze-append-only.md) | Correção: Bronze passa a ser append-only (apontado em revisão por colega sênior) |
| [004](docs/decision-log/adr-004-silver-mantem-granularidade.md) | Correção: Silver mantém a granularidade da fonte; agregação fica na Gold |
| [005](docs/decision-log/adr-005-type-hints.md) | Adoção incremental de type hints a partir da Sprint 6 |
| [006](docs/decision-log/adr-006-tipo-numerico-monetario.md) | DOUBLE em vez de DECIMAL para colunas monetárias |
| [007](docs/decision-log/adr-007-materializacao-incremental.md) | Full-refresh na fase local; incremental avaliado depois |
| [008](docs/decision-log/adr-008-migracao-fabric-concluida.md) | Migração para o Fabric concluída: SPN em vez de CLI, capacity de trial, calendário portável |
| [009](docs/decision-log/adr-009-modelo-semantico-direct-lake.md) | Modelo semântico Direct Lake publicado sobre a Gold |
| [010](docs/decision-log/adr-010-correcao-medidas-semiaditivas.md) | Medidas de saldo são semiaditivas: `LASTNONBLANKVALUE` no lugar de `SUM()` |
| [011](docs/decision-log/adr-011-correcao-comparativos-ano-anterior.md) | Comparativos ano a ano sem âncora herdavam o fim do calendário gerado |
| [012](docs/decision-log/adr-012-investigacao-parcial-divergencia-p7.md) | Divergência entre o modelo publicado e o DuckDB local — **causa raiz não confirmada**, registrada assim mesmo |
| [013](docs/decision-log/adr-013-field-parameter-inviavel-conexao-live.md) | Field parameter inviável em conexão live sem modelo local |
| [014](docs/decision-log/adr-014-terceira-ocorrencia-data-fixa.md) | Terceira ocorrência do padrão de data fixa em vez de âncora dinâmica |
| [015](docs/decision-log/adr-015-arquitetura-agente-governado.md) | Arquitetura do agente governado, e por que a conexão usa identidade fixa sem SSO |
| [016](docs/decision-log/adr-016-medidas-deflacionadas-antes-do-gabarito.md) | Medidas deflacionadas pelo IPCA criadas **antes** do gabarito, para a camada não ser ajustada em resposta ao teste |
| [017](docs/decision-log/adr-017-rls-fora-do-escopo-da-v1.md) | RLS fora do escopo da v1.0: o agente consulta com identidade fixa, então RLS filtraria pelo serviço e não por quem pergunta |

---

## Estado do projeto

**v1.0**, com 9 das 12 sprints do plano entregues.

| Sprint | Entrega | |
|---|---|---|
| 1–5 | Fundação, Bronze, Silver, Gold (star schema em dbt) | ✅ |
| 6 | Modelo semântico Direct Lake + medidas certificadas | ✅ |
| 7 | AI-readiness: sinônimos, BPA na CI, RLS | ⛔ RLS descartado com razão registrada ([ADR-017](docs/decision-log/adr-017-rls-fora-do-escopo-da-v1.md)); os outros itens viram backlog |
| 8 | Dashboard Power BI | ✅ |
| 9 | ML explicável: previsão de inadimplência e anomalias | ⬜ não iniciada |
| 10 | Agente analítico governado | ✅ |
| 11 | Gabarito de 60 perguntas + baseline text-to-SQL | ✅ |
| 12 | Benchmark e lançamento | ✅ |

**Fora de escopo por decisão, não por esquecimento:** faixa sombreada da defasagem SCR/SGS na página de contexto macro e layout mobile da primeira página.

**Sobre a numeração:** ADRs e commits anteriores a setembro de 2026 chamam o dashboard de "Sprint 7" e o agente de "Sprint 8". A numeração acima é a do plano original.

**Material de lançamento:** [memorando executivo](docs/memorando-executivo.md) · [artigo](docs/artigo.md) · [roteiro de demonstração](docs/roteiro-demo.md) · [finops](docs/finops.md)
