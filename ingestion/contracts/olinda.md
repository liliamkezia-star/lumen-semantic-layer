# Contrato de dados — SCR.data (Sistema de Informações de Créditos) e IBGE

## SCR.data — Crédito por UF, modalidade e segmento

**Nota:** apesar do nome do arquivo (herdado do planejamento original, que
previa o protocolo Olinda/OData), a fonte real é o SCR.data, distribuído
como arquivos ZIP anuais — ver ADR-002 para detalhes da mudança de rota.

**Fonte:** https://www.bcb.gov.br/pda/desig/scrdata_{ANO}.zip

**Período coletado:** 2015 a 2025 (alinhado com o período do SGS — ver ADR-002)

**Formato:** ZIP contendo 12 CSVs (um por mês), separador `;`, decimais
com vírgula.

**Volume:** ~34,4 milhões de linhas (2015-2025)

**Padrão de carga:** append-only, idempotência por ano já carregado
(ver ADR-003)

**Principais colunas:** data_base, uf, segmento, cliente (PF/PJ), cnae_ocupacao,
porte, modalidade, submodalidade, origem, indexador, numero_de_operacoes,
carteira_ativa, carteira_inadimplencia, ativo_problematico (e outras
colunas de faixas de vencimento)

---

## IBGE — Localidades e População

### Localidades
**Fonte:** https://servicodados.ibge.gov.br/api/v1/localidades/estados

**Volume:** 27 UFs (26 estados + Distrito Federal)

**Colunas:** id_uf, sigla_uf, nome_uf, id_regiao, nome_regiao

### População estimada por UF
**Fonte:** API de Agregados (SIDRA), tabela 6579, variável 9324
(População residente estimada), nível territorial N3 (Estados)

**Período coletado:** 2013-2021, 2024-2025

**Observação de qualidade importante:** faltam os anos de 2022 e 2023.
Isso é comportamento conhecido da fonte, não erro de coleta: o IBGE pausa
a publicação de estimativas intercensitárias em anos de Censo (2022) e
durante o reprocessamento pós-Censo. A ausência desses anos deve ser
tratada explicitamente na camada Silver (não preencher com estimativa
própria sem documentar).

**Colunas:** id_uf, nome_uf, ano, populacao_estimada
