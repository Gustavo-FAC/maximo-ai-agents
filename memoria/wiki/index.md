# Índice da wiki

Catálogo de páginas. Atualizar a cada alteração.

## Síntese
- [[estado-do-projeto]] – feito, pendente, próximo passo, riscos. **Ler primeiro.**
- [[ferramentas-maximo]] – plano dos automation scripts, o que fica em
  `analysis/` ou no LLM, decisões (histórico, bloco comum, campos `cci_*`,
  `QUERYJOBPLANS`, histórico de status em 2 scripts, site explícito,
  `QUERYASSETDOWNTIME`, ficha técnica `include_specs` no `QUERYASSETS`, descrição
  longa da OS no `QUERYWORKORDERS`, `QUERYPMS` e campo do cliente `modalidade`).
- [[prompts-de-teste]] – 40 perguntas (33-40 em `tests/evals/`): 32 para OS e ativos via MCP (filtros,
  `text`, hierarquia, limites, segurança) e 8 de gerente para o agente `analise-os`;
  base para `tests/evals/`.
- [[perguntas-consultor]] – 22 dúvidas abertas ao consultor funcional (guia + achados
  nos dados), priorizadas pelo que bloqueiam; doc para enviar com coluna Resposta.

## Entidades
- [[itambe-cimentos]] – cliente piloto, homologação, chave MAXADMIN temporária;
  dados: sem classe de falha, corretiva `CO`, OS sem tipo, OS de checklist, status
  próprios (CONCL, APROG, POSEXEC...) e worktype `MS` a classificar; planos
  com status ATIVO (sinônimo) e 203 planos de nível sistema; quase sem registro de
  paradas (ASSETSTATUS) na homologação; sem material planejado (WPMATERIAL vazio),
  5241 baixas/devoluções em 366 dias.
- [[mas-mcp-server]] – servidor MCP do MAS 9.2, ferramentas expostas, notas do SDK.
  BMXAA10147E: usuário da chave precisa estar em EN (várias ocorrências). Cliente sem
  descrição de parâmetro. Resposta parece filtrada pelo response schema instalado;
  `apischema` só aceita estrutura de objeto; `apikey` no log do pod.

## Conceitos
- [[assistente-geral-roteador]] – 2º agente: roteador com `handoff` para os
  especialistas, resposta direta sem dados, histórico só com perguntas e respostas finais. Teste simulado no Claude Code (9 perguntas) em 2026-11-13.
- [[agente-sem-chave-de-api]] – 3 camadas para desenvolver o agente sem LLM por API:
  ferramentas (pytest), grafo com modelo falso, Claude Code como LLM (servidor
  `analises` + subagente `analise-os` gerado da receita). Teste com 6 perguntas de
  gerente (2026-11-06) e reteste: números batem com a CLI, recusas certas; pendentes:
  escala de prioridade; desvios de resposta corrigidos (regras 10 e 11).
- [[allowlist-somente-leitura]] – única barreira contra escrita; `DORMANT_TOOLS`; nomes exatos,
  descrições próprias para o LLM e filtro de argumentos implementados.
- [[chave-api-por-usuario]] – decisão de arquitetura e exceção atual (MAXADMIN).
  Observação sobre idioma do usuário.
- [[automation-scripts-como-ferramentas]] – regras, como registrar, lições do OAS e
  do runtime Jython; `QUERYWORKORDERS` **funcionando via MCP** (2026-10-29); objeto
  filho (JOBTASK) só pelo dono; site explícito para usar índice (`QUERYWOSTATUS`).

## Fontes
- [[guia-levantamento-fase1]] – guia da Itambé preenchido (2026-11-16): 17 perguntas
  do gerente e cobertura, status × backlog, atraso (início previsto, 7 dias),
  prioridades 1-4 com prazo, tipos preventivos, `MODALIDADE`, indicadores e 10
  dúvidas para o consultor.
- [[doc-mcp-server]] – doc IBM do MCP Server: registro de ferramenta, flags, auth.
- [[guia-automation-scripts]] – IBM Autoscripting Guide: variáveis, REST, segurança.
  Errata: sem `isLoggingEnabled` no MAS 9.2.
