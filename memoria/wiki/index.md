# Índice da wiki

Catálogo de páginas. Atualizar a cada alteração.

## Síntese
- [[estado-do-projeto]] – feito, pendente, próximo passo, riscos. **Ler primeiro.**
- [[ferramentas-maximo]] – plano dos automation scripts, o que fica em
  `analysis/` ou no LLM, decisões (histórico, bloco comum, campos `cci_*`,
  `QUERYJOBPLANS`, histórico de status em 2 scripts, site explícito,
  `QUERYASSETDOWNTIME`).
- [[prompts-de-teste]] – 32 perguntas para testar OS e ativos via MCP (filtros,
  `text`, hierarquia, limites, segurança); base para `tests/evals/`.

## Entidades
- [[itambe-cimentos]] – cliente piloto, homologação, chave MAXADMIN temporária;
  dados: sem classe de falha, corretiva `CO`, OS sem tipo, OS de checklist; planos
  com status ATIVO (sinônimo) e 203 planos de nível sistema; quase sem registro de
  paradas (ASSETSTATUS) na homologação; sem material planejado (WPMATERIAL vazio),
  5241 baixas/devoluções em 366 dias.
- [[mas-mcp-server]] – servidor MCP do MAS 9.2, ferramentas expostas, notas do SDK.
  BMXAA10147E: usuário da chave precisa estar em EN (2 ocorrências). Cliente sem
  descrição de parâmetro.

## Conceitos
- [[allowlist-somente-leitura]] – única barreira contra escrita; `DORMANT_TOOLS`; nomes exatos,
  descrições próprias para o LLM e filtro de argumentos implementados.
- [[chave-api-por-usuario]] – decisão de arquitetura e exceção atual (MAXADMIN).
  Observação sobre idioma do usuário.
- [[automation-scripts-como-ferramentas]] – regras, como registrar, lições do OAS e
  do runtime Jython; `QUERYWORKORDERS` **funcionando via MCP** (2026-10-29); objeto
  filho (JOBTASK) só pelo dono; site explícito para usar índice (`QUERYWOSTATUS`).

## Fontes
- [[doc-mcp-server]] – doc IBM do MCP Server: registro de ferramenta, flags, auth.
- [[guia-automation-scripts]] – IBM Autoscripting Guide: variáveis, REST, segurança.
  Errata: sem `isLoggingEnabled` no MAS 9.2.
