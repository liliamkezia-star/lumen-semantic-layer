# ADR-005: Adoção de type hints a partir da Sprint 6

## Status
Aceito

## Contexto
Nenhuma função em `ingestion/` ou `transform/silver/` possui anotações de
tipo. Isso não causa problemas no estado atual do projeto — os módulos são
pequenos, com contratos simples e cobertura de testes adequada.

A situação muda a partir da Sprint 9 (ML explicável) e especialmente da
Sprint 10 (agente analítico com function calling): bibliotecas de
orquestração de agentes tipicamente derivam o schema das ferramentas
diretamente das anotações de tipo das funções. Sem elas, o contrato
precisa ser escrito duas vezes (na assinatura e em um schema manual),
criando risco de divergência silenciosa entre os dois.

## Decisão
- Todo código novo escrito a partir da Sprint 6 deve incluir anotações de
  tipo em assinaturas de função (parâmetros e retorno).
- Código existente será anotado de forma incremental, quando for tocado
  por outro motivo — não haverá refatoração retroativa em massa.
- A verificação será feita via regras do `ruff` (já presente no projeto),
  evitando adicionar `mypy` como dependência nova nesta fase.

## Alternativas consideradas
- **Anotar todo o código retroativamente agora**: rejeitado por ser
  trabalho considerável com benefício baixo em código já estável, testado
  e que não será a interface principal do agente.
- **Adotar mypy imediatamente**: adiado. O ruff cobre a verificação
  básica de presença de anotações; mypy (verificação de consistência de
  tipos) pode ser adotado na Sprint 10, se o agente exigir garantias mais
  fortes.
- **Não adotar type hints**: rejeitado, pelo risco de duplicação de
  contrato descrito no contexto.

## Consequências
- Positivo: contratos entre módulos ficam explícitos e verificáveis antes
  da fase em que isso se torna crítico.
- Positivo: melhora o autocompletar e a detecção de erros em editores.
- Atenção: durante a transição, o projeto terá código anotado e não
  anotado convivendo — comportamento esperado e aceito.
