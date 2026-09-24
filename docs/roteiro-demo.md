# Roteiro de demonstração — 3 minutos

Para apresentar o Lumen a quem nunca viu. Três minutos é pouco: cabe
**uma** ideia. A ideia é esta — *a camada certificada não deixa a IA
errar bonito*.

O roteiro é escrito para ser executado ao vivo, com um plano B para cada
coisa que pode falhar.

---

## Antes de abrir a boca (5 minutos de preparação)

Nada aqui é opcional. A demo tem um inimigo real: **a latência do
agente, de 15 a 55 segundos por resposta**. Vinte segundos de silêncio
numa demo de três minutos é um terço da demo.

1. **Suba o agente e faça uma pergunta qualquer** para aquecer conexão e
   token: `streamlit run agent/app.py`. A primeira pergunta do dia é
   sempre a mais lenta.
2. **Deixe a pergunta da demo já digitada** na caixa, sem enviar.
3. **Abra o dashboard antes**, na Página 1, e confira que os visuais
   carregaram.
4. **Deixe aberta, numa aba atrás, a resposta do text-to-SQL** que você
   vai mostrar no bloco 4 — em `evaluation/resultados/rodada2.jsonl`,
   pergunta `D04`. Não rode o baseline ao vivo: são mais 20 segundos e
   ele pode acertar dessa vez.
5. **Confira a cota** da API. Sem cota, não há demo ao vivo.

> As abas do relatório aparecem como "Página 1" e "Página 2", não
> "Visão Geral" e "Onde". Ou você renomeia antes, ou não chama pelo nome
> na hora — tropeçar no próprio nome custa credibilidade barata.

---

## Bloco 1 — O problema (0:00 – 0:25)

**Mostrar:** nada ainda, ou só a capa.

> "Todo mundo está colocando IA em cima dos dados. O problema não é a IA
> não responder — é ela responder bonito e errado. Ela pega a tabela
> vizinha, soma o que não se soma, e devolve um número redondo com ar de
> certeza. Ninguém pega isso numa reunião.
>
> O Lumen é uma tentativa de resposta: dados públicos de crédito do
> Brasil, uma camada de métricas certificadas, e uma IA que só pode usar
> essa camada."

## Bloco 2 — O dashboard (0:25 – 1:00)

**Mostrar:** Página 1, e um clique de drill-through na Ficha de Segmento.

> "Isto é o dashboard, rodando direto sobre o modelo semântico no
> Fabric. Cada número aqui é uma medida certificada — 'inadimplência'
> tem **uma** definição, e é esta.
>
> [clique no drill-through] E isso vale no detalhe também: o mesmo
> conceito, o mesmo cálculo, em qualquer corte."

Não explique arquitetura. Ninguém pediu.

## Bloco 3 — O agente, ao vivo (1:00 – 2:00)

**Mostrar:** a interface do agente. Pergunta já digitada:

> *Segundo o SCR.data, qual era a taxa de inadimplência no fim de 2024?*

Envie e **fale durante a espera** — este texto tem a duração certa:

> "Enquanto ele responde: o modelo de linguagem aqui **não escreve
> consulta nenhuma**. Ele escolhe, de uma lista fechada, qual medida
> certificada usar e quais cortes aplicar. Quem monta a consulta é o
> código. Se ele pedir uma medida que não existe, o pedido é recusado
> antes de virar consulta."

Quando a resposta aparecer, leia o essencial:

> "**2,99%**, competência dezembro de 2024. E repare: ele diz de onde
> veio o número."

Se quiser mostrar a recusa (só se houver folga), pergunte
*"qual a taxa de inadimplência por faixa de idade?"* — ele responde que
não existe esse corte e lista os que existem. **Recusar é a
funcionalidade**, não a falha.

## Bloco 4 — O confronto (2:00 – 2:40)

**Mostrar:** a resposta do text-to-SQL que você deixou aberta.

> "Agora a mesma pergunta, para o **mesmo modelo de IA**, sobre as
> **mesmas tabelas**, só que livre para escrever SQL."

Leia a resposta dele em voz alta, incluindo a última linha:

> *"No fim de 2024, a taxa de inadimplência total era de 3,08% da
> carteira. Fonte: SCR.data (via série `inadimplencia_total`)."*

Pause. Então:

> "3,08% contra 2,99%. Ele foi buscar a série oficial do Banco Central,
> que mede outra coisa, e **atribuiu o número ao SCR.data** — com
> citação da fonte. Está errado, e está errado com confiança.
>
> Isso não foi sorte minha: em 60 perguntas, esse mesmo erro aparece
> cinco vezes. Placar final: **59 contra 53**. E a diferença não está no
> básico — nas perguntas diretas os dois vão bem. Ela está nas
> pegadinhas: 10 a 7."

## Bloco 5 — Fechamento (2:40 – 3:00)

> "O agente também erra — perdeu um filtro numa pergunta, e o erro está
> publicado no repositório, com o número errado escrito.
>
> A diferença é o tipo de erro. Errar um filtro alguém percebe. Errar a
> fonte e dizer o nome da fonte errada, não.
>
> Está tudo público: gabarito, metodologia, as 120 respostas e o custo
> — que foi zero."

---

## Planos B

| Se | Faça |
|---|---|
| A cota da API acabou | Pule o bloco 3 ao vivo e mostre a resposta gravada do agente para D04, lado a lado com a do baseline. A demo perde graça, não perde argumento |
| O agente demora demais | Continue falando: o texto do bloco 3 pode ser esticado com "ele escolhe a medida, valida contra o catálogo, e só então monta a consulta" |
| O Fabric está fora do ar | Demo inteira pelas respostas gravadas e pelo relatório. Diga que a capacity é de trial — é verdade e é uma das decisões pendentes |
| Perguntarem "quanto custou?" | "Zero. Roda em capacity de trial e API gratuita — e o gargalo do projeto nunca foi dinheiro, foi cota" |
| Perguntarem "e com um modelo melhor?" | "Não sei, e está escrito que não sei. O teste foi com um modelo aberto e gratuito; generalizar exigiria nova rodada" |

## Perguntas que vão vir

- **"Por que não deixar a IA escrever SQL e pronto?"** — É exatamente o
  que o baseline faz. Ele perde 53 a 59, e cinco dos sete erros dele são
  fonte trocada.
- **"Isso não engessa o analista?"** — Engessa, de propósito, no agente.
  O analista continua com SQL e DAX livres; quem fica preso à camada
  certificada é a IA que responde para quem não vai conferir.
- **"E se a pergunta não couber no catálogo?"** — Ele recusa e diz o que
  tem. É a categoria F do benchmark: 10 de 10.
