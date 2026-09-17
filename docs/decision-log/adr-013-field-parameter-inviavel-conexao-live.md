# ADR-013: Field parameter "Cliente" substituído por slicer — limitação de conexão live

## Status
Aceito

## Contexto
A auditoria externa (§07, §15) especifica que o corte "Cliente" (PF/PJ/
Todos) na Página 2 deve ser implementado como **field parameter**, não
como slicer comum — a justificativa dada é que um field parameter "muda
a pergunta", enquanto um slicer "só filtra o dado".

Ao tentar implementar isso, a documentação oficial do Power BI
(`power-bi-field-parameters`, seção "Known limitations") registra:

> "You can't create parameters in live connection data sources without a
> local model."

O modelo semântico do Lumen (`lumen_semantico`) é consumido pelo
`powerbi/lumen_dashboard.pbix` via **conexão live** com o Direct Lake
publicado no Fabric (decisão do ADR-009) — não existe um modelo local
importado dentro do `.pbix`. Isso é exatamente o cenário que a
documentação exclui. Confirmado que não há como contornar sem adicionar
um modelo local ao relatório (o que descaracterizaria a arquitetura
Direct Lake escolhida deliberadamente no ADR-009 para evitar duplicar os
34,4M de linhas).

## Decisão
Implementar "Cliente" como **slicer comum** em `dim_segmento[cliente]`
na Página 2, com valores PF / PJ / Todos, aplicando filtro cruzado sobre
a matriz, o scatter e o dumbbell por UF — mesmo mecanismo usado no
slicer de competência da Página 1.

Isso não é uma correção de bug como os ADRs anteriores desta sequência
(010-012): é uma peça do dossiê de design que se mostrou **tecnicamente
inviável** dada a arquitetura Direct Lake já decidida — não uma omissão
de implementação.

## Alternativas consideradas
- **Adicionar um modelo local/composto só para viabilizar o field
  parameter**: rejeitado. Contradiz a decisão arquitetural do ADR-009
  (Direct Lake, sem duplicar dados) por uma diferença puramente
  semântica de interação (parâmetro vs. slicer), que na prática entrega
  o mesmo resultado ao usuário final.
- **Abrir mão do corte por cliente**: rejeitado — o corte PF/PJ é central
  pra tese da Página 1 (inadimplência PF piora mais que PJ) e precisa
  continuar disponível na Página 2 para aprofundamento.

## Consequências
- Positivo: o comportamento para o usuário final é equivalente — ele
  ainda escolhe PF, PJ ou Todos e vê os visuais da página reagirem.
- Atenção: ao descrever esta página em entrevista ou documentação
  externa, a redação correta é "slicer de cliente", não "field
  parameter" — a auditoria original pedia o segundo, mas a arquitetura
  do projeto (Direct Lake, decidida antes e por um motivo melhor) torna
  isso inviável. Vale mencionar essa própria descoberta como exemplo de
  julgamento técnico: manter Direct Lake > usar field parameter.
