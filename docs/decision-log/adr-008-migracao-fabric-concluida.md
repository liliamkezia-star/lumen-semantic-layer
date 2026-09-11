# ADR-008: Migração para Microsoft Fabric concluída — decisões técnicas da execução

## Status
Aceito

## Contexto
O ADR-001 definiu o plano de migração de DuckDB local para o Microsoft
Fabric na Sprint 6, mas não detalhava decisões de implementação de nível
mais baixo. A execução da migração, concluída em 25/08/2026 sob prazo
apertado (capacity paga com janela de 9 dias, ver contexto da Sprint 6),
levantou três decisões técnicas não previstas no plano original, que
ficam registradas aqui.

## Decisão 1: Autenticação do dbt via Service Principal, não Azure CLI

Ao configurar o adapter `dbt-fabricspark` para conectar o dbt ao Lakehouse
via Livy, a autenticação `CLI` (`az login`) falhou com
**AADSTS53003 — Access has been blocked by Conditional Access policies**,
bloqueando especificamente o aplicativo "Microsoft Azure CLI" (dispositivo
"Unregistered"). Este é um bloqueio diferente do 2FA original do ADR-001
(que era sobre elegibilidade de trial, não autenticação de app).

**Decisão**: usar autenticação **SPN (Service Principal)** — um App
Registration dedicado (`lumen-dbt-fabric`) com client secret, adicionado
como Contribuidor no workspace `lumen-dev`. Autenticação de aplicativo
(client credentials) não é tipicamente afetada por políticas de
Conditional Access voltadas a sign-in de usuário, e é o método oficialmente
recomendado para cenários de CI/CD — não é um workaround, é a alternativa
correta para automação.

**Pré-requisito de tenant**: a configuração "Entidades de serviço podem
chamar APIs públicas do Fabric" precisou estar habilitada no Portal de
Administração do Fabric (Configurações de locatário) — sem isso, o SPN
recebe 404 em qualquer chamada às APIs do Fabric, independente de
permissão no workspace.

## Decisão 2: Capacity de trial do Fabric em vez da capacity paga (F2)

A capacity paga via crédito Azure (SKU **F2**, a menor disponível) rodou
notebooks avulsos sem problema, mas não sustentou uma sessão Livy viva
durante um `dbt run` completo — sessões morriam repetidamente
(`livyState: dead`) mesmo com a capacity marcada como "Ativa" no portal.

No mesmo dia, o trial gratuito de 60 dias do Fabric — bloqueado desde a
Sprint 1 (causa raiz original do ADR-001) — foi liberado. Essa capacity de
trial é significativamente maior que F2.

**Decisão**: realocar o workspace `lumen-dev` para a capacity de trial, e
pausar a capacity F2 paga (sem uso pendente, evita consumo desnecessário
do crédito Azure de 30 dias).

## Decisão 3: `dim_calendario` reescrito para ser portável entre motores SQL

O model original usava `generate_series` (função de tabela) e `strftime`,
específicos do dialeto DuckDB, sem equivalente direto em Spark SQL —
falhou com `UNRESOLVED_ROUTINE` ao rodar no Fabric.

**Decisão**: substituir por `dbt_utils.date_spine()` (macro cross-database
do pacote `dbt-labs/dbt_utils`, adicionado via novo `packages.yml`) para
gerar a série de datas, e por aritmética simples (`EXTRACT` + `LPAD`) para
montar `id_data` e `ano_mes`, eliminando a dependência de `strftime`.
Também foi necessário trocar `CAST(... AS VARCHAR)` por
`CAST(... AS STRING)`, já que o Spark exige tamanho explícito para
`VARCHAR` (`VARCHAR(n)`), enquanto `STRING` funciona sem tamanho nos dois
motores.

Validado que o model portável continua passando 100% no target local
(`dev`, DuckDB) após a mudança — a portabilidade não é apenas para o
Fabric, é uma melhoria arquitetural que remove um vendor lock-in que já
existia no model.

## Alternativas consideradas
- **Replicar a Gold como Spark SQL puro num notebook, sem dbt**: rejeitado
  explicitamente — perderia os 21+ testes dbt (unique/not_null/
  relationships) e contrariaria a decisão já documentada em
  architecture.md de manter dbt na stack pós-Sprint 6. Cogitado
  brevemente como atalho sob pressão de prazo, mas descartado a pedido
  explícito do time: "não, vamos fazer tudo agora, do jeito certo."
- **Aguardar resolução do bloqueio de Conditional Access via admin**:
  descartado — SPN resolve sem depender de mudar política de segurança do
  tenant, e é o método correto de qualquer forma para automação.
- **Manter Jinja condicional (`{% if target.type == 'duckdb' %}`) em vez
  de reescrever `dim_calendario` de forma portável**: descartado — a
  versão portável via `dbt_utils` é mais simples e não duplica lógica por
  engine.

## Consequências
- Positivo: pipeline de dbt agora roda de forma idêntica (mesmo código)
  contra DuckDB local e Fabric, sem branches condicionais por engine.
- Positivo: dependência de Conditional Access do usuário é eliminada para
  automação — o SPN funciona independente de política de dispositivo.
- Atenção: o client secret do SPN expira (90 dias, conforme criado) — será
  necessário renovar e atualizar `~/.dbt/profiles.yml` antes do
  vencimento.
- Atenção: a capacity de trial expira em 60 dias a partir de 25/08/2026;
  ao expirar, será necessário reavaliar entre capacity paga maior (F4/F8)
  ou nova extensão de trial, considerando o requisito mínimo de recursos
  identificado (F2 é insuficiente para sessões Livy sustentadas).
- Atenção: `.venv-fabric/` (Python 3.12) é um ambiente separado do
  `.venv/` principal (Python 3.14), necessário porque `dbt-fabricspark`
  ainda não tem wheels pré-compiladas de sua dependência nativa
  (`pymsalruntime`) para Python 3.14. Reavaliar quando isso for resolvido
  upstream.
