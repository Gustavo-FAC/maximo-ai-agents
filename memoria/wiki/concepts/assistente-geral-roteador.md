---
title: Assistente Geral (roteador)
type: concept
sources: []
related: [[agente-sem-chave-de-api]], [[allowlist-somente-leitura]], [[estado-do-projeto]]
created: 2026-11-13
updated: 2026-11-13
---

# Assistente Geral (roteador)

2º agente da arquitetura, porta de entrada do gerente. Código em
`src/maximo_agents/agents/router.py`; receita `GENERAL_ASSISTANT` em `recipes.py`.

## Como funciona

- Grafo LangGraph: nó `router` → nó do especialista (um por receita de `RECIPES`) ou fim.
- O roteador só tem a ferramenta `handoff(agent)` (enum com os especialistas). Nenhuma
  ferramenta do Maximo.
- Responde ele mesmo só o que não precisa de dados: cumprimento, o que a plataforma faz,
  conceito geral (MTBF, backlog), recusa de escrita pura e de assunto fora da manutenção.
  Pedido misto (escrita + consulta) vai para o especialista, que também recusa a escrita.
- `handoff` inválido (agente desconhecido, outra ferramenta) → `ROUTER_FALLBACK`
  ("Não entendi a pergunta. Pode reformular?"), sem tocar no Maximo.
- Especialista = grafo de `graph.py` como subgrafo, compilado com `checkpointer=False`:
  recebe a conversa limpa a cada pergunta, sem estado próprio.

## Decisão: histórico limpo

A conversa guardada (checkpointer do roteador) tem só perguntas do gerente e respostas
finais (`AIMessage` com `name` do especialista). A chamada de `handoff` e as chamadas de
ferramenta do especialista não entram. Motivos: nenhum modelo vê chamadas de ferramentas
que não tem (a API do Claude rejeita/estranha), e menos tokens. Custo: numa pergunta de
continuação o especialista não tem os dados brutos da pergunta anterior, só o texto da
resposta; consulta de novo se precisar.

## Modelos

`build_assistant_graph(model, call_tool, config, today, checkpointer, router_model)`:
`router_model` opcional permite modelo mais barato só para rotear (ex.: Haiku).

## Testes

`tests/unit/test_agent_router.py` (6, modelo falso): handoff, resposta direta sem
Maximo, handoff inválido, conversa de 3 turnos sem duplicar mensagens nem vazar
ferramentas, modelo único para roteador e especialista, enum = `RECIPES`.

Não vira subagente do Claude Code (subagente não chama subagente). Validar o roteamento
real precisa da chave do Claude.

## Pendente

- Rodar com LLM real (chave do Claude): perguntas de cumprimento, conceito, escrita,
  fora do escopo e de dados.
- Ganho real só com o 2º especialista (guia da Fase 1 da Itambé).
