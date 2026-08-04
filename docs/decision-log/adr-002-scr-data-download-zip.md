# ADR-002: Ingestão do SCR.data via download de arquivo ZIP anual (não OData)

## Status
Aceito

## Contexto
O cronograma original previa consumir os dados de crédito por UF/modalidade
através do protocolo OData do Banco Central (parâmetros $filter, $select,
$skip/$top). Ao pesquisar a fonte real (SCR.data - Sistema de Informações
de Créditos), constatou-se que esse dataset específico não é distribuído
via OData: é disponibilizado como arquivo .ZIP com dados mensais agregados
de todo um ano, para download direto.

URL: https://www.bcb.gov.br/pda/desig/scrdata_{ANO}.zip
Tamanho aproximado por ano: ~168MB (testado com o ano de 2024)

## Decisão
A ingestão dessa fonte será feita por download do arquivo ZIP de cada ano
necessário, extração do(s) CSV(s) internos, e carga para a camada Bronze
em DuckDB — em vez de chamadas paginadas via OData.

## Alternativas consideradas
- Usar OData como planejado originalmente: descartado, pois o dataset
  específico do SCR.data não oferece esse protocolo (confirmado na
  documentação oficial do portal de dados abertos).

## Consequências
- Positivo: mecanismo de ingestão mais simples de implementar (download +
  leitura de CSV) do que paginação OData.
- Atenção: arquivos grandes (~168MB compactado por ano) exigem cuidado com
  uso de memória — não carregar tudo de uma vez ingenuamente.
- Decisão de escopo: será processado o período de 2015 até o presente
  (não o histórico completo desde 2012), para manter consistência com o
  período já coletado das séries SGS na Sprint 2 (que começam em 2015,
  com séries diárias ajustadas a partir de 2016 por limite da própria
  API). Cruzar fontes com períodos diferentes geraria lacunas ao comparar
  indicadores no dashboard final.
- O processamento será feito ano a ano (não todos simultaneamente em
  memória), dado o volume de cada arquivo (~150-200MB compactado).
