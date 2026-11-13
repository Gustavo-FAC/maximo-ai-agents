"""Assistente Geral: grafo roteador sobre os agentes especialistas.

O roteador vê a conversa e faz uma de duas coisas:

- chama ``handoff`` com o nome de um especialista: o especialista (grafo de
  ``graph.py``, com as ferramentas da receita dele) responde à pergunta;
- responde ele mesmo, sem dados do Maximo (cumprimento, o que a plataforma faz,
  conceito geral, recusa de escrita ou de assunto fora da manutenção).

A conversa guardada tem só perguntas do gerente e respostas finais. A chamada de
``handoff`` e as chamadas de ferramenta do especialista ficam fora do histórico: um
modelo nunca vê chamadas de ferramentas que não tem.
"""

import datetime
from typing import Annotated, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command

from maximo_agents.agents.graph import build_agent_graph
from maximo_agents.agents.recipes import (
    GENERAL_ASSISTANT,
    HANDOFF_TOOL,
    RECIPES,
    Recipe,
    system_prompt,
)
from maximo_agents.agents.tools import CallTool, Toolbox
from maximo_agents.analysis.config import ClientConfig

ROUTER_NODE = "router"
ROUTER_FALLBACK = "Não entendi a pergunta. Pode reformular?"


class AssistantState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def handoff_definition(specialists: tuple[Recipe, ...]) -> dict:
    return {
        "name": HANDOFF_TOOL,
        "description": (
            "Hand the manager's question to a specialist agent, which queries the client's "
            "Maximo (read only) and answers. Use it for any question that needs Maximo data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent": {
                    "type": "string",
                    "enum": [r.name for r in specialists],
                    "description": "Specialist that answers the question.",
                }
            },
            "required": ["agent"],
            "additionalProperties": False,
        },
    }


def chosen_specialist(response: AIMessage, names: set[str]) -> str | None:
    """Especialista pedido no ``handoff``; None se o pedido for inválido."""
    for call in response.tool_calls:
        if call["name"] == HANDOFF_TOOL and (call.get("args") or {}).get("agent") in names:
            return call["args"]["agent"]
    return None


def build_assistant_graph(
    model: BaseChatModel,
    call_tool: CallTool,
    config: ClientConfig,
    today: datetime.date | None = None,
    checkpointer=None,
    router_model: BaseChatModel | None = None,
    specialists: tuple[Recipe, ...] = tuple(RECIPES.values()),
):
    """Grafo do Assistente Geral.

    ``model`` responde nos especialistas; ``router_model`` (padrão: o mesmo) decide o
    encaminhamento. ``call_tool`` é a sessão MCP do Maximo do gerente.
    """
    today = today or datetime.date.today()
    names = {r.name for r in specialists}
    system = SystemMessage(system_prompt(GENERAL_ASSISTANT, config, today))
    router = (router_model or model).bind_tools([handoff_definition(specialists)])

    subgraphs = {
        recipe.name: build_agent_graph(
            model,
            Toolbox(call_tool, config, recipe.tools, today=today),
            recipe,
            config,
            today=today,
            # Sem estado próprio entre perguntas: a conversa vem do roteador.
            checkpointer=False,
        )
        for recipe in specialists
    }

    async def route(state: AssistantState) -> Command:
        response = await router.ainvoke([system, *state["messages"]])
        if not response.tool_calls:
            return Command(goto=END, update={"messages": [AIMessage(content=response.text)]})
        name = chosen_specialist(response, names)
        if name is None:
            return Command(goto=END, update={"messages": [AIMessage(content=ROUTER_FALLBACK)]})
        return Command(goto=name)

    def specialist_node(name: str):
        subgraph = subgraphs[name]

        async def run(state: AssistantState) -> dict:
            result = await subgraph.ainvoke({"messages": state["messages"], "tool_rounds": 0})
            answer = result["messages"][-1]
            return {"messages": [AIMessage(content=answer.text, name=name)]}

        return run

    graph = StateGraph(AssistantState)
    graph.add_node(ROUTER_NODE, route, destinations=(*subgraphs, END))
    for name in subgraphs:
        graph.add_node(name, specialist_node(name))
        graph.add_edge(name, END)
    graph.add_edge(START, ROUTER_NODE)
    return graph.compile(checkpointer=checkpointer)


async def ask_assistant(graph, question: str, config: dict | None = None) -> str:
    """Uma pergunta do gerente ao Assistente Geral; devolve o texto da resposta final.

    Com checkpointer, ``config={"configurable": {"thread_id": ...}}`` mantém a conversa.
    """
    state = await graph.ainvoke({"messages": [HumanMessage(question)]}, config=config)
    return state["messages"][-1].text
