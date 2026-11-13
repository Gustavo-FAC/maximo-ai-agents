import asyncio
import datetime

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from maximo_agents.agents.recipes import (
    GENERAL_ASSISTANT,
    HANDOFF_TOOL,
    RECIPES,
    WORK_ORDER_ANALYSIS,
)
from maximo_agents.agents.router import (
    ROUTER_FALLBACK,
    ask_assistant,
    build_assistant_graph,
    handoff_definition,
)
from maximo_agents.analysis.config import load_client_config
from maximo_agents.analysis.fetch import WORK_ORDER_TOOL

CONFIG = load_client_config("itambe")
TODAY = datetime.date(2026, 11, 13)
SPECIALIST = WORK_ORDER_ANALYSIS.name


class ScriptedModel(GenericFakeChatModel):
    """Modelo falso: devolve as mensagens do roteiro e grava o que recebeu."""

    binds: list = []
    received: list = []

    def bind_tools(self, tools, **kwargs):
        self.binds.append([t["name"] for t in tools])
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.received.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def scripted(*messages):
    return ScriptedModel(messages=iter(messages), binds=[], received=[])


def call(name, args, call_id):
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def handoff(agent=SPECIALIST, call_id="h1"):
    return AIMessage(content="", tool_calls=[call(HANDOFF_TOOL, {"agent": agent}, call_id)])


class FakeMaximo:
    def __init__(self):
        self.calls = []

    async def __call__(self, name, arguments):
        self.calls.append((name, arguments))
        return {"total": 3, "items": [{"wonum": "1", "siteid": "FABRICA"}], "has_more": False}


def assistant(router_script, specialist_script=(), checkpointer=None):
    router = scripted(*router_script)
    specialist = scripted(*specialist_script)
    maximo = FakeMaximo()
    graph = build_assistant_graph(
        specialist,
        maximo,
        CONFIG,
        today=TODAY,
        checkpointer=checkpointer,
        router_model=router,
    )
    return graph, router, specialist, maximo


def run(coro):
    return asyncio.run(coro)


def test_handoff_runs_the_specialist():
    graph, router, specialist, maximo = assistant(
        [handoff()],
        [
            AIMessage(content="", tool_calls=[call(WORK_ORDER_TOOL, {"wonums": "1"}, "c1")]),
            AIMessage(content="A OS 1 está aberta."),
        ],
    )
    state = run(graph.ainvoke({"messages": [HumanMessage("Como está a OS 1?")]}))

    assert state["messages"][-1].text == "A OS 1 está aberta."
    assert maximo.calls == [(WORK_ORDER_TOOL, {"wonums": "1"})]
    # O roteador só tem o handoff; o especialista, as ferramentas da receita.
    assert router.binds == [[HANDOFF_TOOL]]
    assert specialist.binds == [list(WORK_ORDER_ANALYSIS.tools)]
    router_system = router.received[0][0]
    assert isinstance(router_system, SystemMessage)
    assert "Assistente Geral" in router_system.content
    assert "Hoje é 2026-11-13." in router_system.content
    specialist_system = specialist.received[0][0]
    assert "agente de Análise de OS" in specialist_system.content
    assert "Hoje é 2026-11-13." in specialist_system.content
    # Conversa guardada: pergunta e resposta final, sem handoff nem ferramentas.
    assert [type(m) for m in state["messages"]] == [HumanMessage, AIMessage]
    assert state["messages"][-1].name == SPECIALIST
    assert not state["messages"][-1].tool_calls


def test_direct_answer_does_not_touch_maximo():
    graph, router, specialist, maximo = assistant(
        [AIMessage(content="Posso responder sobre backlog, falhas, MTBF e material.")]
    )
    answer = run(ask_assistant(graph, "O que você faz?"))
    assert answer == "Posso responder sobre backlog, falhas, MTBF e material."
    assert maximo.calls == []
    assert specialist.received == []
    assert len(router.received) == 1


def test_invalid_handoff_falls_back():
    graph, _, specialist, maximo = assistant(
        [
            AIMessage(
                content="",
                tool_calls=[
                    call(HANDOFF_TOOL, {"agent": "inexistente"}, "h1"),
                    call(WORK_ORDER_TOOL, {"wonums": "1"}, "h2"),
                ],
            )
        ]
    )
    assert run(ask_assistant(graph, "OS 1")) == ROUTER_FALLBACK
    assert maximo.calls == []
    assert specialist.received == []


def test_conversation_keeps_only_questions_and_answers():
    graph, router, specialist, maximo = assistant(
        [handoff(call_id="h1"), AIMessage(content="De nada."), handoff(call_id="h2")],
        [
            AIMessage(content="", tool_calls=[call(WORK_ORDER_TOOL, {"wonums": "1"}, "a")]),
            AIMessage(content="primeira"),
            AIMessage(content="", tool_calls=[call(WORK_ORDER_TOOL, {"wonums": "2"}, "b")]),
            AIMessage(content="segunda"),
        ],
        checkpointer=InMemorySaver(),
    )
    thread = {"configurable": {"thread_id": "gerente-1"}}
    assert run(ask_assistant(graph, "pergunta 1", thread)) == "primeira"
    assert run(ask_assistant(graph, "obrigado", thread)) == "De nada."
    assert run(ask_assistant(graph, "pergunta 2", thread)) == "segunda"
    assert len(maximo.calls) == 2

    # O especialista recebe a conversa limpa, sem repetir nem trazer ferramentas antigas.
    second_turn = [m for m in specialist.received[2] if not isinstance(m, SystemMessage)]
    assert [m.text for m in second_turn] == [
        "pergunta 1",
        "primeira",
        "obrigado",
        "De nada.",
        "pergunta 2",
    ]
    assert not any(isinstance(m, ToolMessage) for m in second_turn)
    # O roteador também nunca vê chamadas de ferramenta.
    last_router = router.received[-1]
    assert not any(isinstance(m, ToolMessage) for m in last_router)
    assert not any(getattr(m, "tool_calls", None) for m in last_router)


def test_shared_model_for_router_and_specialist():
    model = scripted(handoff(), AIMessage(content="Backlog: 3 OS."))
    graph = build_assistant_graph(model, FakeMaximo(), CONFIG, today=TODAY)
    assert run(ask_assistant(graph, "Como está o backlog?")) == "Backlog: 3 OS."


def test_router_prompt_and_handoff_cover_every_specialist():
    enum = handoff_definition(tuple(RECIPES.values()))["input_schema"]["properties"]["agent"]
    assert enum["enum"] == list(RECIPES)
    for recipe in RECIPES.values():
        assert recipe.name in GENERAL_ASSISTANT.instructions
    assert GENERAL_ASSISTANT.name not in RECIPES  # não vira subagente do Claude Code
    assert GENERAL_ASSISTANT.tools == ()
