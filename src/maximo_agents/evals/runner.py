"""Roda casos de eval no grafo do agente e grava a conversa.

A conversa vem do ``astream`` com subgrafos: chamadas de ferramenta (nome,
argumentos), resultados (JSON das ``ToolMessage``), especialista escolhido pelo
Assistente Geral e a resposta final. Cada caso começa sem histórico.
"""

import datetime
import json
import time
from dataclasses import dataclass
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from maximo_agents.agents.graph import LIMIT_FALLBACK, build_agent_graph
from maximo_agents.agents.recipes import GENERAL_ASSISTANT, HANDOFF_TOOL, RECIPES
from maximo_agents.agents.router import build_assistant_graph
from maximo_agents.agents.tools import CallTool, Toolbox
from maximo_agents.analysis.config import ClientConfig
from maximo_agents.evals.cases import EvalCase
from maximo_agents.evals.checks import CheckResult, ToolCall, Transcript, check_case

MAX_ERROR_CHARS = 300


@dataclass
class CaseRun:
    case: EvalCase
    transcript: Transcript
    checks: list[CheckResult]
    seconds: float

    @property
    def passed(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.ok]


def build_graph(
    case: EvalCase,
    model: BaseChatModel,
    call_tool: CallTool,
    config: ClientConfig,
    today: datetime.date,
    router_model: BaseChatModel | None = None,
):
    if case.agent == GENERAL_ASSISTANT.name:
        return build_assistant_graph(
            model, call_tool, config, today=today, router_model=router_model
        )
    recipe = RECIPES[case.agent]
    toolbox = Toolbox(call_tool, config, recipe.tools, today=today)
    return build_agent_graph(model, toolbox, recipe, config, today=today)


def _result(content) -> object:
    try:
        return json.loads(content)
    except (TypeError, ValueError):
        return content


async def record(graph, question: str) -> Transcript:
    """Roda uma pergunta e devolve a conversa gravada."""
    transcript = Transcript(question=question)
    pending: dict[str, ToolCall] = {}
    final: AIMessage | None = None
    stream = graph.astream(
        {"messages": [HumanMessage(question)]}, stream_mode="updates", subgraphs=True
    )
    async for namespace, update in stream:
        for node, values in update.items():
            if not namespace and node in RECIPES:
                transcript.specialist = node
            messages = values.get("messages", []) if isinstance(values, dict) else []
            for message in messages:
                if isinstance(message, AIMessage):
                    for call in message.tool_calls:
                        if call["name"] == HANDOFF_TOOL:
                            continue
                        recorded = ToolCall(call["name"], dict(call.get("args") or {}))
                        pending[call["id"]] = recorded
                        transcript.calls.append(recorded)
                    if not namespace:
                        final = message
                elif isinstance(message, ToolMessage) and message.tool_call_id in pending:
                    pending[message.tool_call_id].result = _result(message.content)
    transcript.answer = final.text if final is not None else ""
    if transcript.answer == LIMIT_FALLBACK:
        transcript.error = "tool round limit reached"
    return transcript


async def run_case(
    case: EvalCase,
    model: BaseChatModel,
    call_tool: CallTool,
    config: ClientConfig,
    today: datetime.date,
    router_model: BaseChatModel | None = None,
) -> CaseRun:
    start = time.monotonic()
    try:
        graph = build_graph(case, model, call_tool, config, today, router_model)
        transcript = await record(graph, case.question)
    except Exception as e:  # o caso falha; os outros seguem
        transcript = Transcript(
            question=case.question, error=f"{type(e).__name__}: {e}"[:MAX_ERROR_CHARS]
        )
    checks = check_case(case, transcript, extra_sources=(today.isoformat(),))
    return CaseRun(case, transcript, checks, time.monotonic() - start)


def _call_summary(call: ToolCall) -> dict:
    summary: dict = {"name": call.name, "args": call.args}
    result = call.result
    if isinstance(result, dict):
        if "error" in result:
            summary["error"] = result["error"]
        elif "total" in result:
            summary["total"] = result["total"]
    return summary


def report(runs: list[CaseRun], today: datetime.date, model_name: str) -> dict:
    """Relatório em JSON. Tem respostas e argumentos com dados do cliente: fica fora do
    git (``tests/evals/reports/``)."""
    return {
        "today": today.isoformat(),
        "model": model_name,
        "passed": sum(r.passed for r in runs),
        "total": len(runs),
        "cases": [
            {
                "id": r.case.id,
                "agent": r.case.agent,
                "gap": r.case.gap,
                "passed": r.passed,
                "seconds": round(r.seconds, 1),
                "question": r.case.question,
                "specialist": r.transcript.specialist,
                "calls": [_call_summary(c) for c in r.transcript.calls],
                "answer": r.transcript.answer,
                "error": r.transcript.error,
                "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in r.checks],
            }
            for r in runs
        ],
    }


def write_report(data: dict, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = directory / f"eval-{stamp}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path
