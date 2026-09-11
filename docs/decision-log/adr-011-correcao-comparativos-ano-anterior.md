# ADR-011: Correção das medidas de comparativo ano a ano e dos títulos dinâmicos

## Status
Aceito

## Contexto
Durante a implementação do Bloco 2 do plano de dashboard (aplicar o tema
v2 e construir a página 1), validei ao vivo, sem filtro de página, as
medidas de título dinâmico criadas no ADR-010. O resultado expôs um
segundo bug do mesmo gênero do que motivou aquele ADR:

```
Título · Visão Geral = "Carteira cresce 00% com a qualidade estável"
```

O valor esperado (validado por consulta direta ao `lumen.duckdb` e
registrado na auditoria externa) é "Carteira cresce +11,3%, mas a
qualidade piora 2,7x mais rápido".

**Causa raiz — mesma classe de erro do ADR-010.** As medidas de
comparativo ano a ano (`Carteira Ativa AA`, `Ativo Problemático AA`,
`Carteira Vencida AA`) usavam:

```dax
Carteira Ativa AA =
CALCULATE ( [Carteira Ativa], SAMEPERIODLASTYEAR ( dim_calendario[data] ) )
```

`dim_calendario` é gerada por `dbt_utils.date_spine` até 2026-12-31,
além do fim real dos dados (`fato_credito` termina em dez/2025). Sem
filtro de página, o contexto de avaliação de `dim_calendario[data]` é a
tabela inteira. `SAMEPERIODLASTYEAR` desloca esse intervalo completo em
1 ano — mas como o intervalo já é maior que a janela real de dados, o
intervalo deslocado ainda cobre a mesma última competência com dado
(dez/2025), e `LASTNONBLANKVALUE` (dentro de `[Carteira Ativa]`) devolve
o mesmo valor de novo. Validado: `[Carteira Ativa AA]` = `[Carteira
Ativa]` byte a byte, logo `Δ% a/a` = 0% para todas as três medidas, e
`Velocidade da Deterioração` = `DIVIDE(0%, 0%)` = vazio.

O ADR-010 já havia corrigido esse padrão para `MAX(dim_calendario[data])`
(medida `Última Competência com Crédito`, com `CROSSFILTER(..., BOTH)`).
Mas o comparativo ano a ano usa `SAMEPERIODLASTYEAR`, uma função
diferente, e não herdou a correção — cada função de time intelligence
precisa ser auditada separadamente contra o mesmo defeito estrutural do
calendário.

**Segundo problema, independente — format string com vírgula.**
`FORMAT()` usa **ponto** como marcador de casa decimal na sintaxe do
format string, sempre, independente do locale do relatório; o locale só
decide qual símbolo visual substitui esse marcador na renderização. As
medidas de título usavam vírgula (`"+0,0%"`, `"0,0"`), que o motor lê
como separador de milhar, não como marcador decimal. Resultado: mesmo
depois de corrigido o Δ% a/a, o título saía como "+11%" e "03x" em vez
de "+11,3%" e "2,7x" — um bug de formatação, não de cálculo, mas que
teria chegado à página 1 sem aviso porque nenhum erro é lançado.

## Decisão
1. Ancorar todos os comparativos ano a ano em
   `[Última Competência com Crédito]` em vez de `SAMEPERIODLASTYEAR`:
   ```dax
   VAR _DataAtual = [Última Competência com Crédito]
   VAR _DataAA = EDATE ( _DataAtual, -12 )
   RETURN
       CALCULATE (
           [Carteira Ativa],
           REMOVEFILTERS ( dim_calendario ),
           dim_calendario[data] = _DataAA
       )
   ```
   Aplicado a `Carteira Ativa AA`, `Ativo Problemático AA`,
   `Carteira Vencida AA`, `Taxa de Inadimplência Δpp a/a` e
   `Taxa de Ativo Problemático Δpp a/a`. `REMOVEFILTERS(dim_calendario)`
   remove apenas o filtro de data (preserva UF/modalidade/segmento se a
   página tiver outros filtros); a data exata substitui a ambiguidade do
   intervalo completo.
2. Corrigir os format strings de vírgula para ponto em
   `Título · Visão Geral` e `Título · Diagnóstico`.
3. Também retroportar para `Competência Selecionada`,
   `Inadimplência BCB (SGS 21082)` e `Defasagem SCR vs SGS (meses)` o
   uso de `[Última Competência com Crédito]` no lugar de
   `MAX(dim_calendario[data])` direto — essas três já tinham sido
   corrigidas ao vivo no modelo durante o ADR-010, mas a correção nunca
   havia sido escrita de volta em `powerbi/medidas_certificadas_v2.dax`.
   O arquivo em disco estava, portanto, desatualizado em relação ao
   modelo publicado — uma dívida de consistência corrigida aqui.
4. Renomear, no arquivo, `Taxa de Inadimplência` para
   `Taxa de Inadimplência (SCR.data)`, espelhando o rename já aplicado
   ao vivo no modelo (P2 do dossiê de auditoria).

## Validação
Consulta DAX sem filtro de página, após a correção:

| Medida | Valor | Referência da auditoria |
|---|---|---|
| `Carteira Ativa Δ% a/a` | 11,30% | +11,3% |
| `Ativo Problemático Δ% a/a` | 30,98% | +31,0% |
| `Velocidade da Deterioração` | 2,74x | 2,74x (31,0 ÷ 11,3) |
| `Taxa de Inadimplência Δpp a/a` | 1,11 pp | +1,11 pp |
| `Taxa de Ativo Problemático Δpp a/a` | 1,15 pp | +1,15 pp |
| `Carteira Vencida Δ% a/a` | — | +63,0% (usado no título de diagnóstico) |
| `Título · Visão Geral` | "Carteira cresce +11,3%, mas a qualidade piora 2,7x mais rápido" | — |
| `Título · Diagnóstico` | "Onde a alta de +63,1% na carteira vencida está concentrada" | — |

Também validado **com** filtro de página (`dim_calendario[ano] = 2022`):
`Carteira Ativa` = R$ 5,51 Tri (bate com a auditoria), `Carteira Ativa AA`
desloca corretamente para dez/2021 — confirma que a correção funciona
tanto filtrada quanto sem filtro, os dois casos de uso reais da página 1
e do agente analítico.

## Adendo — separador decimal ainda errado após a correção acima
Depois de aplicar a correção de formato (vírgula → ponto nos format
strings), o valor passou a ter a magnitude certa, mas o **símbolo**
ainda saía errado: `"+11.3%"` em vez de `"+11,3%"`. Testado, nessa
ordem:
1. **Configuração regional do arquivo** no Power BI Desktop (Arquivo ›
   Opções › Arquivo Atual › Configurações Regionais → Português
   (Brasil)) — sem efeito. Essa configuração afeta modelos importados
   localmente; numa conexão live/Direct Lake, a avaliação DAX acontece
   no servidor, fora do alcance dessa configuração do arquivo.
2. **Propriedade `Language` do banco** no Fabric — testado
   `database_operations.Update` de `1033` (en-US) para `1046` (pt-BR).
   Sem efeito no `FORMAT()`: uma consulta DAX direta ao modelo
   continuou devolvendo `"+11.3%"` mesmo depois da mudança. Essa
   propriedade aparentemente só afeta legendas/metadados de tradução,
   não a locale de avaliação de `FORMAT()`. (A propriedade foi mantida
   em `1046` de qualquer forma — mais correta para um projeto de dados
   brasileiro, mesmo não resolvendo este sintoma específico.)
3. **Causa real**: a locale de avaliação de `FORMAT()` vem da conexão
   do cliente (Locale Identifier na connection string), não do modelo
   nem do arquivo do relatório — e isso está fora do nosso controle
   direto pelas ferramentas disponíveis.

**Correção final**: envolver o resultado de `FORMAT()` em
`SUBSTITUTE ( ..., ".", "," )`, forçando a vírgula no texto final
independente de qualquer negociação de locale. Aplicado em
`Título · Visão Geral` e `Título · Diagnóstico`. Validado:
`"Carteira cresce +11,3%, mas a qualidade piora 2,7x mais rápido"`.

## Alternativas consideradas
- **Filtrar `dim_calendario` na fonte para não passar de dez/2025**:
  resolveria este sintoma, mas quebraria qualquer necessidade futura de
  calendário futuro (ex. metas por competência ainda não publicada) e
  não protege contra o mesmo erro se a Gold for recarregada com uma
  competência nova sem atualizar o filtro. Rejeitada — a correção deve
  estar na medida, não escondida na modelagem da dimensão.
- **`DATEADD` no lugar de `SAMEPERIODLASTYEAR`**: mesma classe de
  problema, porque ambas dependem do contexto de filtro visível sobre
  `dim_calendario[data]` para saber "de onde" deslocar.

## Consequências
- Positivo: o título da página 1 — o elemento mais visível de todo o
  Bloco 2 — agora reflete os números reais com ou sem filtro de
  competência, condição que o agente analítico da Sprint 7+ também
  precisa.
- Positivo: `powerbi/medidas_certificadas_v2.dax` volta a ser fonte da
  verdade fiel ao modelo publicado — a divergência entre arquivo e
  modelo ao vivo, sinalizada como dívida pendente após o ADR-010, está
  resolvida.
- Atenção: qualquer nova medida de time intelligence sobre
  `dim_calendario[data]` (`DATEADD`, `PARALLELPERIOD`,
  `TOTALYTD`, etc.) deve ser auditada contra este mesmo defeito antes de
  ser certificada — o calendário seguirá maior que a janela real de
  dados enquanto for gerado por `date_spine` a partir de uma data-fim
  fixa.
