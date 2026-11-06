"""Grafo LangGraph do agente: modelo -> ferramentas -> modelo, com limite de rodadas.

O modelo é qualquer ``BaseChatModel`` (gateway em ``llm/``, ou modelo falso nos
testes). Ferramentas só da receita, executadas pela ``Toolbox`` (allowlist e
``clean_arguments``). Na rodada-limite o modelo recebe um aviso para responder com o
que já tem; se ainda pedir ferramenta, a resposta vira texto sem chamadas.
"""

import datetime
import json
from typing import Annotated, TypedDict

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from maximo_agents.agents.recipes import MAX_TOOL_ROUNDS, Recipe, system_prompt
from maximo_agents.agents.tools import Toolbox
from maximo_agents.analysis.config import ClientConfig

LIMIT_NOTE = (
    "Limite de rodadas de ferramentas atingido. Responda agora ao gerente com o que já "
    "tem, sem chamar ferramentas, e diga o que ficou faltando."
)
LIMIT_FALLBACK = (
    "Não consegui concluir dentro do limite de consultas. Refaça a pergunta com um "
    "período ou filtro mais específico."
)


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    tool_rounds: int


def build_agent_graph(
    model: BaseChatModel,
    toolbox: Toolbox,
    recipe: Recipe,
    config: ClientConfig,
    today: datetime.date | None = None,
    checkpointer=None,
):
    system = SystemMessage(system_prompt(recipe, config, today or toolbox.context.today))
    bound = model.bind_tools(toolbox.definitions())

    async def call_model(state: AgentState) -> dict:
        messages = [system, *state["messages"]]
        limited = state.get("tool_rounds", 0) >= MAX_TOOL_ROUNDS
        if limited:
            messages.append(HumanMessage(LIMIT_NOTE))
        response = await bound.ainvoke(messages)
        if limited and response.tool_calls:
            # Sem chamadas pendentes: o histórico continua válido para a próxima pergunta.
            response = AIMessage(content=response.text or LIMIT_FALLBACK)
        return {"messages": [response]}

    async def run_tools(state: AgentState) -> dict:
        results = []
        for call in state["messages"][-1].tool_calls:
            data = await toolbox.run(call["name"], call["args"])
            failed = isinstance(data, dict) and "error" in data
            results.append(
                ToolMessage(
                    content=json.dumps(data, ensure_ascii=False, default=str),
                    tool_call_id=call["id"],
                    name=call["name"],
                    status="error" if failed else "success",
                )
            )
        return {"messages": results, "tool_rounds": state.get("tool_rounds", 0) + 1}

    def route(state: AgentState) -> str:
        last = state["messages"][-1]
        return "tools" if isinstance(last, AIMessage) and last.tool_calls else END

    graph = StateGraph(AgentState)
    graph.add_node("model", call_model)
    graph.add_node("tools", run_tools)
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", route, ["tools", END])
    graph.add_edge("tools", "model")
    return graph.compile(checkpointer=checkpointer)


async def ask(graph, question: str, config: dict | None = None) -> str:
    """Uma pergunta do gerente; devolve o texto da resposta final.

    Com checkpointer, ``config={"configurable": {"thread_id": ...}}`` mantém a conversa.
    O contador de rodadas recomeça a cada pergunta.
    """
    state = await graph.ainvoke(
        {"messages": [HumanMessage(question)], "tool_rounds": 0}, config=config
    )
    return state["messages"][-1].text
