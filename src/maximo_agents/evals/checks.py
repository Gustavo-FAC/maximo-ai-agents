"""Conferência de um caso de eval contra a conversa gravada (determinística).

Números: todo número da resposta precisa aparecer, com o arredondamento usado na
resposta, na pergunta, nos argumentos ou nos resultados das ferramentas (também
x100, para percentuais). Número que não vem de lá é conta ou invenção do LLM. Datas,
horas e números colados em letras (códigos como MOI0001) ficam de fora; inteiros até
``SMALL_INTEGER`` também (meses, "top 5", enumerações), para não dar falso alarme.
"""

import bisect
import json
import re
from dataclasses import dataclass, field

from maximo_agents.evals.cases import NO_SPECIALIST, EvalCase, ExpectedCall, tool_schema

SMALL_INTEGER = 12

_DATES = re.compile(
    r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?\b"
    r"|\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"
    r"|\b\d{1,2}[:h]\d{2}\b"
)
_ANSWER_NUMBER = re.compile(r"(?<![\w.,])(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)(?![\w])")
_SOURCE_NUMBER = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class ToolCall:
    name: str
    args: dict
    result: object = None

    @property
    def failed(self) -> bool:
        return isinstance(self.result, dict) and "error" in self.result


@dataclass
class Transcript:
    question: str
    answer: str = ""
    calls: list[ToolCall] = field(default_factory=list)
    specialist: str | None = None  # assistente-geral: quem respondeu (None = ele mesmo)
    error: str | None = None


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


# --- Números ------------------------------------------------------------------------


def answer_numbers(text: str) -> list[tuple[str, list[tuple[float, int]]]]:
    """Números da resposta: (texto, [(valor, casas decimais) possíveis])."""
    text = _DATES.sub(" ", text)
    return [(token, _readings(token)) for token in _ANSWER_NUMBER.findall(text)]


def _readings(token: str) -> list[tuple[float, int]]:
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", token):
        whole, _, decimals = token.partition(",")
        readings = [(float(whole.replace(".", "") + "." + (decimals or "0")), len(decimals))]
        if not decimals and token.count(".") == 1:
            readings.append((float(token), 3))  # 7.045 em inglês
        return readings
    if "," in token:
        return [(float(token.replace(",", ".")), len(token.split(",")[1]))]
    if "." in token:
        return [(float(token), len(token.split(".")[1]))]
    return [(float(token), 0)]


def _collect(value, out: list[float]) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, int | float):
        out.append(abs(float(value)))
    elif isinstance(value, str):
        out.extend(float(n) for n in _SOURCE_NUMBER.findall(value))
    elif isinstance(value, dict):
        for item in value.values():
            _collect(item, out)
    elif isinstance(value, list | tuple):
        for item in value:
            _collect(item, out)


def source_numbers(transcript: Transcript, extra: tuple[str, ...] = ()) -> list[float]:
    values: list[float] = []
    _collect([transcript.question, *extra], values)
    for call in transcript.calls:
        _collect(call.args, values)
        _collect(call.result, values)
    values += [v * 100 for v in values]
    return sorted(set(values))


def _grounded(readings: list[tuple[float, int]], sources: list[float]) -> bool:
    for value, decimals in readings:
        tolerance = 0.5 * 10**-decimals + 1e-9
        i = bisect.bisect_left(sources, value - tolerance)
        if i < len(sources) and sources[i] <= value + tolerance:
            return True
    return False


def ungrounded_numbers(transcript: Transcript, extra: tuple[str, ...] = ()) -> list[str]:
    sources = source_numbers(transcript, extra)
    missing = []
    for token, readings in answer_numbers(transcript.answer):
        if all(d == 0 and v <= SMALL_INTEGER for v, d in readings):
            continue
        if not _grounded(readings, sources):
            missing.append(token)
    return missing


# --- Ferramentas --------------------------------------------------------------------


def _norm(value) -> frozenset[str] | str:
    text = str(value).strip().upper()
    if "," in text:
        return frozenset(p.strip() for p in text.split(",") if p.strip())
    return text


def _arg_matches(call: ToolCall, name: str, expected: str) -> bool:
    if call.args.get(name) is not None:
        actual = call.args[name]
    else:
        actual = tool_schema(call.name).get(name, {}).get("default")
        if actual is None:
            return False
    if expected == "*":
        return True
    return _norm(actual) == _norm(expected)


def call_matches(call: ToolCall, expected: ExpectedCall) -> bool:
    return call.name in expected.tools and all(
        _arg_matches(call, k, v) for k, v in expected.args.items()
    )


def _describe(expected: ExpectedCall) -> str:
    tools = "|".join(expected.tools)
    args = ", ".join(f"{k}={v}" for k, v in expected.args.items())
    return f"{tools}({args})"


def _called(transcript: Transcript) -> str:
    return "; ".join(
        f"{c.name}({json.dumps(c.args, ensure_ascii=False)})" for c in transcript.calls
    )


# --- Caso ---------------------------------------------------------------------------


def check_case(
    case: EvalCase, transcript: Transcript, extra_sources: tuple[str, ...] = ()
) -> list[CheckResult]:
    """Todas as conferências do caso. ``extra_sources``: textos que também valem como
    fonte de número (ex.: a data de hoje dada ao agente)."""
    expect = case.expect
    answer = transcript.answer
    results = [
        CheckResult(
            "completed",
            transcript.error is None and bool(answer.strip()),
            transcript.error or ("" if answer.strip() else "empty answer"),
        )
    ]
    if expect.specialist is not None:
        actual = transcript.specialist or NO_SPECIALIST
        results.append(CheckResult("specialist", actual == expect.specialist, f"got {actual}"))
    if expect.no_tools:
        results.append(CheckResult("no_tools", not transcript.calls, _called(transcript)))
    for expected in expect.calls:
        ok = any(call_matches(c, expected) for c in transcript.calls)
        detail = "" if ok else f"called: {_called(transcript) or 'nothing'}"
        results.append(CheckResult(f"call {_describe(expected)}", ok, detail))
    for expected in expect.forbidden_args:
        bad = [c for c in transcript.calls if call_matches(c, expected)]
        detail = f"{len(bad)} call(s)" if bad else ""
        results.append(CheckResult(f"not {_describe(expected)}", not bad, detail))
    if expect.forbidden_tools:
        bad = sorted({c.name for c in transcript.calls if c.name in expect.forbidden_tools})
        results.append(CheckResult("forbidden_tools", not bad, ", ".join(bad)))

    for pattern in expect.answer_all:
        results.append(
            CheckResult(f"answer has /{pattern}/", re.search(pattern, answer) is not None)
        )
    if expect.answer_any:
        ok = any(re.search(p, answer) for p in expect.answer_any)
        results.append(CheckResult("answer has one of answer_any", ok))
    for pattern in expect.answer_none:
        match = re.search(pattern, answer)
        detail = match.group(0) if match else ""
        results.append(CheckResult(f"answer lacks /{pattern}/", match is None, detail))
    if expect.grounded_numbers:
        missing = ungrounded_numbers(transcript, extra_sources)
        results.append(CheckResult("grounded_numbers", not missing, ", ".join(missing)))
    return results
