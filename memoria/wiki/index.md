# Índice da wiki

Catálogo de páginas. Atualizar a cada alteração.

## Síntese
- [[estado-do-projeto]] – feito, pendente, próximo passo, riscos. **Ler primeiro.**

## Entidades
- [[itambe-cimentos]] – cliente piloto, homologação, chave MAXADMIN temporária.
- [[mas-mcp-server]] – servidor MCP do MAS 9.2, ferramentas expostas, notas do SDK.
  Observações: BMXAA10147E (idioma PT do usuário), cliente sem descrição de parâmetro.

## Conceitos
- [[allowlist-somente-leitura]] – única barreira contra escrita; não implementada.
  Requisitos novos: nome exato ASCII, descrição própria.
- [[chave-api-por-usuario]] – decisão de arquitetura e exceção atual (MAXADMIN).
  Observação sobre idioma do usuário.
- [[automation-scripts-como-ferramentas]] – regras, como registrar, lições do OAS e
  do runtime Jython; `QUERYWORKORDERS` **funcionando via MCP** (2026-10-29).

## Fontes
- [[doc-mcp-server]] – doc IBM do MCP Server: registro de ferramenta, flags, auth.
- [[guia-automation-scripts]] – IBM Autoscripting Guide: variáveis, REST, segurança.
  Errata: sem `isLoggingEnabled` no MAS 9.2.
