# ADR-016: Medidas deflacionadas pelo IPCA, criadas antes do gabarito

## Status
Aceito

## Contexto
O plano da Sprint 11 pede um gabarito de 60 perguntas com "pegadinhas
de semiaditividade e deflacionamento", para comparar o agente com um
baseline text-to-SQL na Sprint 12.

Ao preparar o gabarito, o catálogo do agente não tinha nenhuma medida
deflacionada. A série de IPCA existe na Gold (`ipca_mensal`, SGS 433,
variação mensal em %, jan/2015 a jul/2026), mas o agente só vê medidas
certificadas, então uma pergunta como "quanto a carteira cresceu em
termos reais?" seria recusada — enquanto o baseline, com acesso direto à
Gold, tentaria calcular.

## Decisão
Criar e certificar três medidas no modelo semântico **antes** de
escrever e congelar o gabarito:

- `IPCA 12 Meses (SGS)` — inflação acumulada nos 12 meses até a
  competência: produto de (1 + variação mensal), nunca a soma.
- `Carteira Ativa Δ% a/a Real` — (1 + crescimento nominal) / (1 + IPCA
  12 meses) − 1.
- `Carteira Ativa Real (R$ da Última Competência)` — carteira de
  qualquer competência a preços da última competência com crédito.

As três seguem a regra do projeto: ancoradas em
`[Última Competência com Crédito]`, nunca em data literal (ADR-010, 011,
014).

## Validação
Cada medida foi comparada com um cálculo independente, em SQL escrito à
mão sobre a Gold via SQL endpoint — caminho que não passa pelo DAX:

| Medida | SQL | DAX |
|---|---|---|
| IPCA acumulado em 2025 | 4,2644% | 4,2644% |
| Crescimento real da carteira em 2025 | 6,7459% | 6,7459% |
| Carteira de dez/2020 a preços de dez/2025 | R$ 5.597,04 Bi | R$ 5.597,04 Bi |

Os dois caminhos batem até a sexta casa decimal.

## O risco que este ADR existe para registrar
Criar uma medida porque uma pergunta de prova vai existir tem cara de
"estudar para a prova": o agente passaria a acertar justamente o que o
benchmark cobra. Três fatos limitam esse risco:

1. A ordem está registrada: as medidas foram criadas **antes** de o
   gabarito ser escrito. Nenhuma pergunta de deflacionamento existia
   quando elas foram definidas.
2. Deflacionamento é parte do escopo original da camada semântica — o
   próprio plano o cita como pegadinha que a camada deve resolver. A
   medida preenche uma lacuna conhecida do catálogo, não uma pergunta.
3. É exatamente o tipo de cálculo que a tese do projeto diz que um LLM
   erra sozinho (somar variações mensais em vez de multiplicar, esquecer
   de alinhar a base de preços). Uma camada semântica sem essa medida
   não estaria testando a tese; estaria testando uma lacuna.

A alternativa — deixar o catálogo como estava e o agente recusar essas
perguntas — foi considerada honesta, mas mediria uma falta de medida,
não o valor da camada semântica.

## Achado no caminho: catálogo versionado divergente do modelo
Ao olhar as medidas SGS existentes para seguir o mesmo padrão, o
arquivo `powerbi/medidas_certificadas_v2.dax` mostrou a `Selic Meta
(SGS)` sem âncora de data, enquanto o modelo ao vivo devolvia o valor
certo. Uma comparação das 73 medidas do modelo contra o arquivo achou
exatamente seis divergindo — as seis medidas SGS da página Contexto
Macro, corrigidas ao vivo na Sprint 8 e nunca trazidas para o arquivo.
Foram trazidas neste mesmo trabalho.

Essa conferência não pode ir para a CI: a API `executeQueries`, a única
que a CI alcança, devolve as expressões DAX como nulas. Continua sendo
uma verificação manual, pelo endpoint XMLA.

## Consequências
- O agente passa a ter 43 medidas; o gabarito da Sprint 11 pode incluir
  perguntas de valor real com resposta certificada.
- A Selic meta é média mensal de uma série diária: num mês em que o
  Copom mudou a meta, o valor fica entre a antiga e a nova. Perguntas do
  gabarito sobre a Selic precisam dizer "média do mês" ou escolher meses
  sem mudança, para não haver duas respostas certas.
