import asyncio
import datetime
import json

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from maximo_agents.agents.graph import LIMIT_FALLBACK, LIMIT_NOTE, ask, build_agent_graph
from maximo_agents.agents.recipes import MAX_TOOL_ROUNDS, WORK_ORDER_ANALYSIS
from maximo_agents.agents.tools import Toolbox
from maximo_agents.analysis.config import load_client_config
from maximo_agents.analysis.fetch import WORK_ORDER_TOOL

CONFIG = load_client_config("itambe")
TODAY = datetime.date(2026, 11, 6)


class ScriptedModel(GenericFakeChatModel):
    """Modelo falso: devolve as mensagens do roteiro e grava o que recebeu."""

    bound_tools: list = []
    received: list = []

    def bind_tools(self, tools, **kwargs):
        self.bound_tools = list(tools)
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.received.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def call(name, args, call_id):
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def tool_request(*calls):
    return AIMessage(content="", tool_calls=list(calls))


class FakeMaximo:
    def __init__(self):
        self.calls = []

    async def __call__(self, name, arguments):
        self.calls.append((name, arguments))
        return {"total": 3, "items": [{"wonum": "1", "siteid": "FABRICA"}], "has_more": False}


def agent(script, maximo=None, checkpointer=None):
    model = ScriptedModel(messages=iter(script))
    maximo = maximo or FakeMaximo()
    toolbox = Toolbox(maximo, CONFIG, WORK_ORDER_ANALYSIS.tools, today=TODAY)
    graph = build_agent_graph(
        model, toolbox, WORK_ORDER_ANALYSIS, CONFIG, checkpointer=checkpointer
    )
    return graph, model, maximo


def run(coro):
    return asyncio.run(coro)


def test_question_tool_answer():
    graph, model, maximo = agent(
        [
            tool_request(call(WORK_ORDER_TOOL, {"wonums": "1"}, "c1")),
            AIMessage(content="A OS 1 está aberta."),
        ]
    )
    answer = run(ask(graph, "Como está a OS 1?"))
    assert answer == "A OS 1 está aberta."
    assert maximo.calls == [(WORK_ORDER_TOOL, {"wonums": "1"})]

    assert [t["name"] for t in model.bound_tools] == list(WORK_ORDER_ANALYSIS.tools)
    first, second = model.received
    system = first[0]
    assert isinstance(system, SystemMessage)
    assert "Itambé Cimentos" in system.content
    assert "CO, EM" in system.content
    assert "Hoje é 2026-11-06." in system.content
    assert isinstance(first[1], HumanMessage)
    tool_message = second[-1]
    assert isinstance(tool_message, ToolMessage)
    assert tool_message.tool_call_id == "c1"
    assert tool_message.status == "success"
    assert json.loads(tool_message.content)["total"] == 3


def test_errors_go_back_to_the_model():
    graph, model, maximo = agent(
        [
            tool_request(call("analyze_material_usage", {"days": 9999}, "c1")),
            tool_request(call("changestatus", {"wonum": "1", "status": "CAN"}, "c2")),
            AIMessage(content="Não consegui."),
        ]
    )
    assert run(ask(graph, "Custo de material dos últimos 30 anos")) == "Não consegui."
    assert maximo.calls == []  # nada chegou ao Maximo
    errors = [m for m in model.received[-1] if isinstance(m, ToolMessage)]
    assert [m.status for m in errors] == ["error", "error"]
    assert json.loads(errors[0].content)["error"]["code"] == "invalid_argument"
    assert json.loads(errors[1].content)["error"]["code"] == "unknown_tool"


def test_several_calls_in_one_round():
    graph, _, maximo = agent(
        [
            tool_request(
                call(WORK_ORDER_TOOL, {"wonums": "1"}, "c1"),
                call(WORK_ORDER_TOOL, {"wonums": "2"}, "c2"),
            ),
            AIMessage(content="ok"),
        ]
    )
    state = run(graph.ainvoke({"messages": [HumanMessage("OS 1 e 2")], "tool_rounds": 0}))
    assert len(maximo.calls) == 2
    assert state["tool_rounds"] == 1


def test_tool_round_limit():
    looping = [
        tool_request(call(WORK_ORDER_TOOL, {"wonums": str(n)}, f"c{n}"))
        for n in range(MAX_TOOL_ROUNDS + 1)
    ]
    graph, model, maximo = agent(looping)
    state = run(graph.ainvoke({"messages": [HumanMessage("loop")], "tool_rounds": 0}))

    assert len(maximo.calls) == MAX_TOOL_ROUNDS
    assert state["tool_rounds"] == MAX_TOOL_ROUNDS
    assert model.received[-1][-1].content == LIMIT_NOTE
    final = state["messages"][-1]
    assert final.text == LIMIT_FALLBACK
    assert not final.tool_calls
    # O aviso não fica no histórico da conversa.
    assert all(m.content != LIMIT_NOTE for m in state["messages"])


def test_limit_keeps_text_the_model_wrote():
    script = [
        tool_request(call(WORK_ORDER_TOOL, {"wonums": str(n)}, f"c{n}"))
        for n in range(MAX_TOOL_ROUNDS)
    ]
    script.append(
        AIMessage(
            content="Resumo parcial.",
            tool_calls=[call(WORK_ORDER_TOOL, {"wonums": "9"}, "c9")],
        )
    )
    graph, _, _ = agent(script)
    assert run(ask(graph, "loop")) == "Resumo parcial."


def test_conversation_resets_round_counter():
    script = [
        tool_request(call(WORK_ORDER_TOOL, {"wonums": "1"}, "a")),
        AIMessage(content="primeira"),
        tool_request(call(WORK_ORDER_TOOL, {"wonums": "2"}, "b")),
        AIMessage(content="segunda"),
    ]
    graph, model, maximo = agent(script, checkpointer=InMemorySaver())
    thread = {"configurable": {"thread_id": "gerente-1"}}
    assert run(ask(graph, "pergunta 1", thread)) == "primeira"
    assert run(ask(graph, "pergunta 2", thread)) == "segunda"
    assert len(maximo.calls) == 2
    # A 2ª pergunta vê a conversa anterior.
    humans = [m.content for m in model.received[-1] if isinstance(m, HumanMessage)]
    assert humans == ["pergunta 1", "pergunta 2"]
