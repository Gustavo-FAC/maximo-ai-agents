"""Casos de eval: leitura e validação do arquivo TOML.

Formato (um ``[[cases]]`` por pergunta):

    [defaults]
    answer_none = ["(?i)analyze_"]   # vale para todos os casos
    grounded_numbers = true

    [[cases]]
    id = "p37-mtbf-moi0001"
    source = "prompts-de-teste 37"
    agent = "analise-os"              # ou "assistente-geral"
    question = "Qual o MTBF e o MTTR do MOI0001 no último ano?"
    gap = ""                          # ferramenta que falta (comportamento de hoje)
    [cases.expect]
    calls = [{ tool = "analyze_reliability", args = { assetnum = "MOI0001" } }]
    forbidden_args = [{ tool = "script_querypms", args = { status = "ACTIVE" } }]
    forbidden_tools = []
    no_tools = false
    specialist = "analise-os"         # só no assistente-geral; "none" = respondeu direto
    answer_all = ["(?i)mediana"]      # regex, todas precisam aparecer
    answer_any = []                   # regex, ao menos uma
    answer_none = []                  # regex, nenhuma (soma com defaults)
    grounded_numbers = true           # padrão vem de [defaults]

``tool`` aceita lista (qualquer uma serve). Valores de ``args``: texto comparado sem
diferença de maiúsculas; lista separada por vírgula comparada como conjunto; ``*`` =
qualquer valor; datas por marcador: ``{today}``, ``{yesterday}``, ``{week_start}``,
``{week_end}`` (semana do cliente), ``{month_start}``, ``{year_start}``.
"""

import datetime
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from maximo_agents.agents.recipes import GENERAL_ASSISTANT, RECIPES
from maximo_agents.agents.tools import ANALYSIS_TOOLS
from maximo_agents.mcp.allowlist import AGENT_TOOLS

DEFAULT_CASES = Path("tests/evals/cases.toml")
NO_SPECIALIST = "none"
AGENTS = (*RECIPES, GENERAL_ASSISTANT.name)

WEEKDAYS = {"monday": 0, "sunday": 6}
PLACEHOLDER = re.compile(r"\{(\w+)\}")

_EXPECT_KEYS = {
    "calls",
    "forbidden_args",
    "forbidden_tools",
    "no_tools",
    "specialist",
    "answer_all",
    "answer_any",
    "answer_none",
    "grounded_numbers",
}
_CASE_KEYS = {"id", "source", "agent", "question", "gap", "expect"}


class CaseError(ValueError):
    """Arquivo de casos inválido."""


@dataclass(frozen=True)
class ExpectedCall:
    tools: tuple[str, ...]
    args: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Expectation:
    calls: tuple[ExpectedCall, ...] = ()
    forbidden_args: tuple[ExpectedCall, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    no_tools: bool = False
    specialist: str | None = None
    answer_all: tuple[str, ...] = ()
    answer_any: tuple[str, ...] = ()
    answer_none: tuple[str, ...] = ()
    grounded_numbers: bool = True


@dataclass(frozen=True)
class EvalCase:
    id: str
    agent: str
    question: str
    expect: Expectation
    source: str = ""
    gap: str = ""


def tool_schema(name: str) -> dict:
    """Propriedades do schema de uma ferramenta de agente (análise ou script)."""
    if name in ANALYSIS_TOOLS:
        return ANALYSIS_TOOLS[name].input_schema["properties"]
    return {p: {"type": "string"} for p in AGENT_TOOLS[name].parameters}


def known_tools(agent: str) -> tuple[str, ...]:
    if agent == GENERAL_ASSISTANT.name:
        return tuple(dict.fromkeys(t for r in RECIPES.values() for t in r.tools))
    return RECIPES[agent].tools


def placeholder_dates(today: datetime.date, week_start: str) -> dict[str, str]:
    first_weekday = WEEKDAYS[week_start]
    week_begin = today - datetime.timedelta(days=(today.weekday() - first_weekday) % 7)
    values = {
        "today": today,
        "yesterday": today - datetime.timedelta(days=1),
        "week_start": week_begin,
        "week_end": week_begin + datetime.timedelta(days=6),
        "month_start": today.replace(day=1),
        "year_start": today.replace(month=1, day=1),
    }
    return {k: v.isoformat() for k, v in values.items()}


def resolve(value: str, dates: dict[str, str]) -> str:
    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in dates:
            raise CaseError(f"Unknown placeholder '{{{name}}}'.")
        return dates[name]

    return PLACEHOLDER.sub(replace, value)


def _strings(raw, where: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise CaseError(f"{where}: expected a list of strings.")
    return tuple(raw)


def _regexes(raw, where: str) -> tuple[str, ...]:
    patterns = _strings(raw, where)
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as e:
            raise CaseError(f"{where}: bad regex {pattern!r}: {e}") from e
    return patterns


def _calls(raw, where: str, tools: tuple[str, ...], dates: dict[str, str]):
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise CaseError(f"{where}: expected a list of {{tool, args}}.")
    result = []
    for item in raw:
        if not isinstance(item, dict) or set(item) - {"tool", "args"} or "tool" not in item:
            raise CaseError(f"{where}: each item needs 'tool' and optional 'args'.")
        names = (item["tool"],) if isinstance(item["tool"], str) else tuple(item["tool"])
        args = item.get("args", {})
        if not isinstance(args, dict):
            raise CaseError(f"{where}: 'args' must be a table.")
        for name in names:
            if name not in tools:
                raise CaseError(f"{where}: tool '{name}' is not available to this agent.")
            unknown = set(args) - set(tool_schema(name))
            if unknown:
                raise CaseError(f"{where}: unknown args for {name}: {sorted(unknown)}.")
        result.append(ExpectedCall(names, {k: resolve(str(v), dates) for k, v in args.items()}))
    return tuple(result)


def _case(raw: dict, defaults: dict, dates: dict[str, str]) -> EvalCase:
    case_id = raw.get("id")
    if not isinstance(case_id, str) or not case_id:
        raise CaseError("Every case needs an 'id'.")
    where = f"case {case_id}"
    unknown = set(raw) - _CASE_KEYS
    if unknown:
        raise CaseError(f"{where}: unknown keys {sorted(unknown)}.")
    agent = raw.get("agent", next(iter(RECIPES)))
    if agent not in AGENTS:
        raise CaseError(f"{where}: unknown agent '{agent}'.")
    question = raw.get("question")
    if not isinstance(question, str) or not question.strip():
        raise CaseError(f"{where}: 'question' is required.")

    expect = raw.get("expect", {})
    unknown = set(expect) - _EXPECT_KEYS
    if unknown:
        raise CaseError(f"{where}: unknown expect keys {sorted(unknown)}.")
    tools = known_tools(agent)
    specialist = expect.get("specialist")
    if specialist is not None:
        if agent != GENERAL_ASSISTANT.name:
            raise CaseError(f"{where}: 'specialist' only applies to {GENERAL_ASSISTANT.name}.")
        if specialist not in (*RECIPES, NO_SPECIALIST):
            raise CaseError(f"{where}: unknown specialist '{specialist}'.")
    forbidden_tools = _strings(expect.get("forbidden_tools"), f"{where} forbidden_tools")
    calls = _calls(expect.get("calls"), f"{where} calls", tools, dates)
    no_tools = bool(expect.get("no_tools", False))
    if no_tools and calls:
        raise CaseError(f"{where}: 'no_tools' contradicts 'calls'.")

    return EvalCase(
        id=case_id,
        agent=agent,
        question=question.strip(),
        source=raw.get("source", ""),
        gap=raw.get("gap", ""),
        expect=Expectation(
            calls=calls,
            forbidden_args=_calls(
                expect.get("forbidden_args"), f"{where} forbidden_args", tools, dates
            ),
            forbidden_tools=forbidden_tools,
            no_tools=no_tools,
            specialist=specialist,
            answer_all=_regexes(expect.get("answer_all"), f"{where} answer_all"),
            answer_any=_regexes(expect.get("answer_any"), f"{where} answer_any"),
            answer_none=(
                _regexes(defaults.get("answer_none"), "defaults answer_none")
                + _regexes(expect.get("answer_none"), f"{where} answer_none")
            ),
            grounded_numbers=bool(
                expect.get("grounded_numbers", defaults.get("grounded_numbers", True))
            ),
        ),
    )


def parse_cases(text: str, today: datetime.date, week_start: str) -> list[EvalCase]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise CaseError(f"Invalid TOML: {e}") from e
    dates = placeholder_dates(today, week_start)
    defaults = data.get("defaults", {})
    cases = [_case(raw, defaults, dates) for raw in data.get("cases", [])]
    ids = [c.id for c in cases]
    duplicated = sorted({i for i in ids if ids.count(i) > 1})
    if duplicated:
        raise CaseError(f"Duplicated case ids: {duplicated}.")
    return cases


def load_cases(path: Path, today: datetime.date, week_start: str) -> list[EvalCase]:
    return parse_cases(path.read_text(encoding="utf-8"), today, week_start)
