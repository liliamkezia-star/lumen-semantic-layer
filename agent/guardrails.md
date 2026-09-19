# Guardrails do agente analítico

Políticas que tornam o agente *governado*, onde cada uma está
implementada e como é verificada. Decisão de arquitetura: ADR-015.

## 1. O modelo de linguagem nunca escreve consulta

| Política | Onde | Verificação |
|---|---|---|
| O LLM escolhe medida, corte e valor de listas fechadas; o DAX é montado por código | `consultas.py` é o único módulo que monta DAX | `tests/test_agente_governanca.py` confere o DAX exato de cada tipo de pergunta |
| Só as 40 medidas de negócio são expostas, cada uma com unidade declarada | `catalogo.UNIDADES` | teste de curadoria: peças de dashboard ficam de fora |
| Medida nova no modelo não é exposta até alguém decidir | `Catalogo.nao_classificadas` | teste com medida fictícia "criada ontem" |
| Valor de filtro só chega ao DAX se for idêntico a um valor existente no modelo | `catalogo.validar_valor` | teste de tentativa de injeção; sabotar a validação faz 3 testes falharem |
| Escolha inválida volta para o modelo como texto, com as opções válidas | `ferramentas.consultar_metricas` | testes de recusa de medida, corte e valor |

## 2. Número só com lastro

| Política | Onde | Verificação |
|---|---|---|
| Todo número da resposta vem de consulta feita nesta conversa | prompt do sistema em `agente.py` | `avaliacao.py` mede lastro em cada caso |
| Valor já consultado nesta conversa pode ser citado de novo; valor novo exige consulta | idem | teste: número nunca consultado continua reprovando |
| A formatação (%, pp, R$ Bi/Tri) é feita pelo código, não pelo modelo | `ferramentas.formatar` | teste com os valores reais de dez/2025 |

A regra de lastro foi relaxada depois de uma falha na avaliação; o
motivo está registrado no ADR-015 ("Ajuste da regra de lastro").

## 3. Recusa

- Pergunta fora do catálogo é recusada, com o que dá para responder de
  perto. Aproximar um número "mesmo assim" conta como falha.
- Previsão, dado por instituição financeira e dado por município não
  existem no catálogo e são recusados.
- Nunca afirmar causalidade entre as séries macro (SGS) e o crédito (SCR).
- Dado certificado e leitura aparecem separados, e a leitura é rotulada
  como interpretação.

Verificação: 4/4 recusas corretas na avaliação de 2026-09-18.

## 4. Limites

| Limite | Valor | Onde |
|---|---|---|
| Linhas por consulta agrupada | 500 | `consultas.LIMITE_MAXIMO` |
| Valores listados de um corte | 60 | `ferramentas.listar_valores` |
| Chamadas de ferramenta por pergunta | 8 | `maximum_remote_calls` em `agente.py` |
| Timeout por chamada ao LLM | 90 s, uma tentativa por modelo | `agente.py` |
| Timeout por consulta ao modelo semântico | 120 s | `fabric.executar_dax` |

## 5. Acesso e rastreabilidade

- Demonstração com senha (`LUMEN_SENHA_DEMO`); sem senha configurada o
  app não abre.
- Um agente por sessão: conversas de pessoas diferentes não se misturam.
- Cada interação é gravada em `agent/interacoes/` (pergunta, modelo,
  DAX executado, resposta, latência, erro), fora do git.
- A interface mostra o DAX de cada consulta e o modelo que respondeu.
- O modelo semântico é lido com uma identidade fixa (SPN, sem SSO). Não
  há RLS: toda pessoa com acesso à demo vê o mesmo dado, que é público.

## O que não está garantido

- A **leitura** é texto do modelo. O lastro dos números é verificado; a
  qualidade da interpretação, não.
- A recusa é verificada na avaliação por expressões ("não posso", "não
  há"...). Uma recusa escrita de forma incomum pode ser mal classificada.
- A disponibilidade depende da cota gratuita da API; sem cota, o app
  avisa e não responde.
- Adicionar RLS ao modelo quebraria o agente: a API `executeQueries`
  recusa entidade de serviço em modelo com RLS (ADR-015).
