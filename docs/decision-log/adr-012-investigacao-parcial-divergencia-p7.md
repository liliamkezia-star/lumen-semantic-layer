# ADR-012: Investigação parcial da divergência P7 (linhas local vs Fabric)

## Status
Aceito — investigação parcial, causa raiz não totalmente confirmada

## Contexto
O ADR-009 registrou `COUNTROWS(fato_credito)` = 34.461.970 no modelo
publicado no Fabric, contra 34.461.901 no `lumen.duckdb` local — uma
diferença agregada de 69 linhas, nunca investigada a fundo (P7 na
auditoria externa de 2026-09-07).

Ao construir a página de Notas Metodológicas (Sprint 7), a reconciliação
SCR × SGS foi recalculada **ao vivo** contra o modelo Fabric (em vez de
copiar os números estáticos do `docs/data-dictionary.md`). O valor de
mar/2025 divergiu: **R$ 6.781.116 mi (Fabric, ao vivo)** contra
**R$ 6.790.705 mi (local, `tests/reconciliar_totais.py`)** — uma
diferença de ~R$ 9.589 mi, não explicada pela reconciliação original
(que roda inteiramente sobre o local).

## Investigação
1. **Hipótese descartada — transformação dbt (Silver→Gold) local**:
   comparado `silver.credito_uf_modalidade` com `gold.fato_credito`,
   ambos no `lumen.duckdb` local, para mar/2025. Resultado idêntico nos
   dois: 317.740 linhas, R$ 6.790.705 mi. A transformação dbt local está
   correta — o problema não está aqui.
2. **Contagem de linhas Fabric vs local, mar/2025**: Fabric tem
   **317.087** linhas (via DAX `COUNTROWS(fato_credito)` filtrado à
   competência); local tem **317.740**. Diferença de **653 linhas**,
   concentrada nesta única competência — muito maior que a diferença
   agregada de 69 linhas registrada no ADR-009, o que indica que a
   diferença agregada provavelmente mistura meses com mais linhas no
   Fabric e meses com menos, se cancelando parcialmente no total.
3. **Hipótese descartada — atraso de sincronização**: todas as 317.740
   linhas locais de mar/2025 têm `timestamp_ultima_coleta` em
   **2026-08-05**, 20 dias antes da migração para o Fabric
   (2026-08-25, ver ADR-008). Os dados já existiam localmente a tempo de
   entrar na migração — não é uma coleta local mais recente que o Fabric
   nunca recebeu.

## Decisão
Registrar o achado com o que foi confirmado e o que não foi, em vez de
adivinhar uma causa. Hipótese mais provável, **não confirmada**: perda de
linhas durante o reprocessamento Bronze→Silver→Gold no Fabric (notebooks
PySpark do ADR-008) especificamente para mar/2025 — mas isso exigiria
inspecionar os logs de execução dos notebooks no portal do Fabric, fora
do escopo desta sessão (que trabalha via TOM/XMLA e consultas DAX, sem
acesso a logs de notebook).

Exibir essa investigação na página de Notas Metodológicas do dashboard
(P5), com o texto: causa raiz não confirmada, duas hipóteses descartadas,
uma hipótese pendente de verificação nos logs do Fabric.

## Alternativas consideradas
- **Não investigar, só copiar o número estático do dicionário**: rejeitado
  — a página de notas existe justamente para expor rigor, e usar um
  número desatualizado quando o modelo ao vivo já mostra outro seria o
  oposto disso.
- **Investigar até o fim nesta sessão**: rejeitado por falta de acesso —
  os logs de execução dos notebooks Spark ficam no portal do Fabric, não
  são consultáveis via as ferramentas TOM/XMLA usadas neste projeto.

## Consequências
- Positivo: duas hipóteses plausíveis (atraso de sincronização, erro de
  transformação dbt) foram testadas e descartadas com evidência direta,
  não por suposição — reduz o espaço de causas possíveis para o mesmo
  reprocessamento Fabric-side já suspeitado, mas não confirmado, no
  ADR-008.
- Atenção: a diferença agregada de 69 linhas (ADR-009) provavelmente
  **subestima** a variação real mês a mês — pelo menos mar/2025 sozinho
  já difere em 653 linhas. Qualquer análise futura por competência
  individual (não só o agregado) deve considerar essa possibilidade.
- Pendência real: verificar os logs dos notebooks de reprocessamento do
  Fabric (workspace `lumen-dev`) para mar/2025, e considerar reprocessar
  essa competência (e possivelmente outras) se a causa for confirmada
  como perda de dados durante o Spark job.
