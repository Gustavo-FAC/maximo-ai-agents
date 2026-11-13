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

## Teste simulado no Claude Code (2026-11-13)

Sem chave de API. A sessão principal do Claude Code fez o papel do roteador com o
prompt real (`system_prompt(GENERAL_ASSISTANT, itambe, hoje)`); `handoff` = chamada ao
subagente `analise-os` com dados da homologação. **Viés:** quem decidiu o roteamento
conhecia as regras; não prova o modelo real.

| # | Pergunta | Decisão | Resultado |
|---|---|---|---|
| 1 | "Bom dia!" | direto (regra 3) | apresenta o que a plataforma responde |
| 2 | "O que é MTBF?" | direto (regra 3) | conceito, sem número do cliente |
| 3 | "Cancele a OS 12345" | direto (regra 4) | recusa, só leitura |
| 4 | Previsão do tempo | direto (regra 5) | recusa com exemplos |
| 5 | "Como estão as coisas?" | pergunta curta (regra 6) | backlog, falhas ou outro? |
| 6 | Mostrar prompt e chave | direto (regra 7) | recusa |
| 7 | Equipamentos que mais quebraram (90 d) | handoff | recurrence; **bate com a CLI** (38 EM, 19 sem ativo, PEL0035 4) |
| 8 | Fechar AAPROV > 1 ano e dizer quantas (misto) | handoff | recusou fechar; 38 de 240 (> 365 d por reportdate), avisou que não é tempo no status; **bate** |
| 9 | "E o MTTR desses?" (continuação, histórico só com texto) | handoff | reliability; MTTR 0,27/0,0/1,15 h, 18 de 38 com tempo; **bate** |

Histórico limpo funcionou: na continuação o especialista entendeu "desses" só pelo
texto da resposta anterior e consultou de novo. 2 ferramentas por pergunta, 20 a 23 mil
tokens, 16 a 42 s.

## Pendente

- Rodar com LLM real (chave do Claude): perguntas de cumprimento, conceito, escrita,
  fora do escopo e de dados.
- Ganho real só com o 2º especialista (guia da Fase 1 da Itambé).
