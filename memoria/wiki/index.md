# Índice da wiki

Catálogo de páginas. Atualizar a cada alteração.

## Síntese
- [[estado-do-projeto]] – feito, pendente, próximo passo, riscos. **Ler primeiro.**
- [[ferramentas-maximo]] – plano dos automation scripts (7), o que fica em
  `analysis/` ou no LLM, decisões (histórico, bloco comum, campos `cci_*`).

## Entidades
- [[itambe-cimentos]] – cliente piloto, homologação, chave MAXADMIN temporária.
- [[mas-mcp-server]] – servidor MCP do MAS 9.2, ferramentas expostas, notas do SDK.
  BMXAA10147E: usuário da chave precisa estar em EN (2 ocorrências). Cliente sem
  descrição de parâmetro.

## Conceitos
- [[allowlist-somente-leitura]] – única barreira contra escrita; nomes exatos,
  descrições próprias para o LLM e filtro de argumentos implementados.
- [[chave-api-por-usuario]] – decisão de arquitetura e exceção atual (MAXADMIN).
  Observação sobre idioma do usuário.
- [[automation-scripts-como-ferramentas]] – regras, como registrar, lições do OAS e
  do runtime Jython; `QUERYWORKORDERS` **funcionando via MCP** (2026-10-29).

## Fontes
- [[doc-mcp-server]] – doc IBM do MCP Server: registro de ferramenta, flags, auth.
- [[guia-automation-scripts]] – IBM Autoscripting Guide: variáveis, REST, segurança.
  Errata: sem `isLoggingEnabled` no MAS 9.2.
