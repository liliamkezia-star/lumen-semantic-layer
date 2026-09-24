# A IA não errou o número. Errou a fonte — e citou.

Perguntei a um modelo de linguagem qual era a taxa de inadimplência do
crédito brasileiro no fim de 2024. Ele tinha acesso direto às tabelas,
podia escrever o SQL que quisesse, e respondeu assim:

> "No fim de 2024, a taxa de inadimplência total era de 3,08% da
> carteira.
> **Fonte:** SCR.data (via série `inadimplencia_total`)."

Número redondo, período certo, fonte citada. E errado.

O valor do SCR.data é **2,99%**. O 3,08% existe — é a série oficial do
Banco Central, que mede um recorte diferente. O modelo foi buscar a
tabela vizinha, encontrou algo com nome parecido, e atribuiu o resultado
à fonte que eu tinha pedido. Sem hesitar, com citação.

Esse é o erro que me interessa. Não o erro que quebra: o que passa.

---

## A pergunta que eu queria responder

Passei alguns meses construindo o **Lumen**: uma camada semântica
certificada sobre dados públicos de crédito do Brasil, no Microsoft
Fabric, com dashboard em Power BI e um agente analítico que responde
perguntas em português.

A tese por trás é a de sempre em governança de dados: se "inadimplência"
tiver uma definição única, versionada e testada, quem consome o dado
erra menos. Só que, com IA no meio, essa tese virou marketing. Todo
fornecedor diz que a camada semântica resolve alucinação. Quase ninguém
mostra o número.

Então decidi tentar me provar errada.

A pergunta ficou assim: **um agente preso a métricas certificadas acerta
mais do que o mesmo modelo escrevendo SQL livre sobre as mesmas
tabelas?**

Repare nos controles. *Mesmo modelo* — não um modelo caro contra um
modelo pequeno. *Mesmas tabelas* — não um agente com dados melhores. A
única variável é a governança.

## Como construir um teste que pode te desmentir

Um benchmark feito por quem construiu a solução tem um problema óbvio de
viés, e nenhuma boa intenção resolve isso. O que resolve é amarrar as
próprias mãos antes de começar.

**Sessenta perguntas, seis categorias.** Consulta direta, filtros,
rankings, e três categorias que são pegadinhas de propósito:
semiaditividade (um saldo não se soma ao longo do tempo), macro e
deflacionamento (crescimento nominal não é crescimento real), e
perguntas que **devem ser recusadas** — previsão do futuro, corte que
não existe, dado que a base não tem.

**Gabarito verificado por dois caminhos independentes.** Cada resposta
esperada foi calculada de duas formas: SQL escrito à mão direto na
camada Gold, e a medida certificada no modelo semântico. Onde os dois
divergissem, eu não teria gabarito — teria um bug. Divergiram em zero
das 50 perguntas numéricas.

**Critérios de correção fechados antes de rodar.** O que conta como
acerto, o que conta como recusa legítima, quantos algarismos
significativos valem. Tudo escrito antes de ver qualquer resposta,
porque critério escrito depois é critério escrito para o resultado que
você quer.

**E o registro de toda alteração posterior.** Mexi no gabarito depois de
fixado? Está lá, com data e motivo. Treze perguntas ambíguas foram
reescritas para dizer "segundo o SCR.data", porque sem isso o baseline
seria punido por uma escolha defensável. Quatro descrições erradas na
documentação das tabelas foram corrigidas — documentação que **o
baseline lê**, e que o penalizava injustamente.

**A primeira rodada inteira foi invalidada.** Tinha três bugs de
infraestrutura, todos do meu lado: o token de acesso expirava no meio da
execução, as descrições das medidas vazavam valores para o prompt (o
agente citou um número sem consultar, porque o número estava na
descrição), e o corretor lia "2025-12" como o número negativo -12. Os
três distorciam o placar. A rodada está no repositório, marcada como
inválida, porque apagar teria sido mais limpo e menos honesto.

## O resultado

Mesmo modelo nas duas pontas, 60 perguntas, 120 respostas:

| Categoria | Agente governado | Text-to-SQL |
|---|---|---|
| Consulta direta | 10/10 | 9/10 |
| Filtros e cortes | 9/10 | 9/10 |
| Rankings e comparações | 10/10 | 10/10 |
| **Semiaditividade** | **10/10** | **7/10** |
| **Macro e deflacionamento** | **10/10** | **8/10** |
| Fora de escopo (recusar) | 10/10 | 10/10 |
| **Total** | **59/60** | **53/60** |

**A diferença não está no básico.** Em consulta direta e em ranking, os
dois vão bem — e tem que ser assim. Se a camada certificada fosse
necessária para responder "qual era a carteira em dezembro", ela seria
burocracia. A distância abre exatamente onde a modelagem importa.

Duas coisas que eu esperava e não aconteceram:

**A governança não custou tempo.** Latência mediana de 21 s no agente
contra 24 s no text-to-SQL. O agente é mais rápido porque não fica
explorando o schema: ele escolhe de uma lista.

**Recusar não foi problema para nenhum dos dois** — 10/10 nas duas
pontas na categoria de perguntas impossíveis. Essa é uma boa notícia
sobre os modelos atuais, e eu esperava o contrário.

## A anatomia do erro que interessa

Dos sete erros do text-to-SQL, **cinco são o mesmo erro**: a pergunta
pede o dado do SCR.data, ele consulta a série oficial do Banco Central e
apresenta o número como sendo do SCR.

Não é aleatório. Reproduz. Nas 84 perguntas que as duas rodadas têm em
comum, o baseline **não divergiu em nenhuma**: os erros dele são
sistemáticos, não ruído de amostragem.

E é o pior tipo de erro possível, por três motivos:

1. **O número é real.** Não é alucinação, é uma célula que existe no
   banco. Nenhum detector de invenção pega.
2. **A ordem de grandeza está certa.** 3,08% contra 2,99% não acende
   alarme nenhum. Se tivesse respondido 47%, alguém perguntaria.
3. **Vem com fonte.** A citação da fonte errada aumenta a confiança em
   vez de diminuir.

Esse número entra num slide, o slide entra numa reunião, e ninguém tem
como saber. É esse erro que a camada certificada impede — não porque a
IA fique mais inteligente, mas porque a pergunta "qual medida usar" foi
respondida antes, por uma pessoa, e versionada.

## O que o agente faz de diferente (e é menos mágico do que parece)

```
pergunta → o modelo escolhe, de listas fechadas, uma medida certificada
           e os cortes → validação contra o catálogo → o código monta a
           consulta → executa → resposta formatada
```

O ponto inteiro está numa frase: **o modelo de linguagem nunca escreve
consulta**. Ele preenche um formulário. Medida, de uma lista de nomes
exatos. Corte, de uma lista. Valor do filtro, de uma lista. Se pedir
algo que não está na lista, o pedido é recusado antes de virar consulta,
e ele recebe de volta as opções válidas.

Isso troca uma classe de erro por outra. O agente não pode errar a
fonte, porque não escolhe fonte. Mas pode errar o formulário — e errou:
numa pergunta sobre "empréstimos a pessoas jurídicas", perdeu o filtro
de modalidade e respondeu a carteira PJ inteira, R$ 2,92 Tri no lugar de
R$ 1,11 Tri.

Errou feio. Mas errou de um jeito que alguém pega: o número está quase
três vezes maior do que devia. É a diferença entre um erro que grita e
um erro que sussurra.

Tem um detalhe pequeno que gosto de mostrar. Perguntando a carteira
total, o text-to-SQL respondeu `R$ 7.444.293.999.119,03`. Correto, e
ilegível. O agente respondeu `R$ 7,44 Tri` — porque a unidade de cada
medida é declarada no catálogo, e formatar não fica a cargo do modelo.
Deixar um LLM decidir se 0,041 é "4,1%" ou "0,04%" é convidar o erro
para entrar.

## O que isto não prova

Um modelo só, aberto e gratuito. Não se generaliza para modelos de ponta
sem nova rodada — é plausível que um modelo maior erre menos a fonte, e
eu não testei.

As perguntas foram escritas por quem construiu a camada. Mitiguei com a
verificação independente e com a categoria de consulta direta, onde o
baseline deveria ir bem (e foi, 9/10). Mitiguei. Não eliminei.

E há variação entre execuções: o agente divergiu em 1 das 42 perguntas
comparáveis entre as duas rodadas. O placar vale como ordem de grandeza,
não como número exato até a segunda casa.

## O custo, e o gargalo de verdade

O projeto inteiro: **R$ 0 de desembolso.** Capacity de trial do Fabric,
API de IA no nível gratuito.

O gargalo nunca foi dinheiro — foi cota. O nível gratuito entrega cerca
de 85 respostas por dia, o que espalhou 120 respostas por três dias.

E a cota deu a melhor lição de engenharia do projeto. As cinco últimas
respostas falhavam com erro 429 de forma determinística, mesmo esperando
minutos entre tentativas. O diagnóstico óbvio — "acabou a cota diária" —
estava errado. O erro cru dizia outra coisa: o teto era de **tokens de
entrada por minuto**. Como cada chamada de ferramenta reenvia a conversa
inteira, uma única pergunta estourava o teto sozinha quando alguma
consulta devolvia muito texto. Uma delas trouxe 17 mil caracteres de
catálogo.

Esperar e repetir nunca ia funcionar. A correção foi espaçar as chamadas
*dentro* da pergunta — e, para não contaminar a métrica, descontar essa
espera do tempo medido. Levei duas tentativas erradas até parar de
adivinhar e ler a mensagem de erro inteira.

## Fechando

Não acho que este resultado encerre a discussão. Acho que ele mostra o
que perguntar.

A pergunta útil não é "a IA alucina?". É **"que tipo de erro ela comete,
e alguém consegue perceber?"**. Um agente que erra alto e evidente é
menos perigoso que um que erra dois pontos percentuais e cita a fonte.

A camada semântica não deixa a IA mais inteligente. Ela tira do modelo a
decisão que ele toma pior: qual número é o número.

---

*O projeto inteiro é público — pipeline, modelo semântico, dashboard,
agente, as 60 perguntas do gabarito, a metodologia, as 120 respostas
(inclusive a rodada invalidada) e o relatório de erros.*
