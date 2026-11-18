"""CLI dos evals: lista os casos ou roda no LLM do gateway e no Maximo do .env.

    uv run python -m maximo_agents.evals --list
    uv run python -m maximo_agents.evals [--only ID,...] [--agent NOME] [--today AAAA-MM-DD]

Precisa de LLM_PROVIDER/LLM_MODEL (e a chave do provedor) e MAXIMO_MCP_URL/
MAXIMO_API_KEY. Relatório JSON em ``tests/evals/reports/`` (fora do git).
Saída 0 = todos passaram; 1 = algum falhou; 2 = configuração.
"""

import argparse
import asyncio
import datetime
import sys
from pathlib import Path

from maximo_agents.analysis.config import load_client_config
from maximo_agents.config.settings import get_settings
from maximo_agents.evals.cases import AGENTS, DEFAULT_CASES, CaseError, EvalCase, load_cases
from maximo_agents.evals.runner import report, run_case, write_report
from maximo_agents.llm.gateway import LLMConfigError, create_chat_model
from maximo_agents.mcp.session import MaximoSessionError, open_maximo_session

DEFAULT_REPORTS = Path("tests/evals/reports")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m maximo_agents.evals")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--only", default="", help="Case ids, comma-separated.")
    parser.add_argument("--agent", choices=AGENTS, help="Only cases of this agent.")
    parser.add_argument(
        "--today",
        type=datetime.date.fromisoformat,
        default=None,
        help="Date the agent sees as today (YYYY-MM-DD). Default: today.",
    )
    parser.add_argument("--list", action="store_true", help="List the cases and exit.")
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORTS)
    return parser.parse_args(argv)


def select(cases: list[EvalCase], only: str, agent: str | None) -> list[EvalCase]:
    wanted = {i.strip() for i in only.split(",") if i.strip()}
    unknown = wanted - {c.id for c in cases}
    if unknown:
        raise CaseError(f"Unknown case ids: {sorted(unknown)}.")
    return [
        c for c in cases if (not wanted or c.id in wanted) and (agent is None or c.agent == agent)
    ]


def print_list(cases: list[EvalCase]) -> None:
    for case in cases:
        gap = f"  [falta: {case.gap}]" if case.gap else ""
        print(f"{case.id:28} {case.agent:17} {case.question}{gap}")
    print(f"\n{len(cases)} casos.")


async def run_all(cases, settings, config, today, out: Path) -> int:
    model = create_chat_model(settings)
    runs = []
    async with open_maximo_session(settings) as call_tool:
        for case in cases:
            run = await run_case(case, model, call_tool, config, today)
            runs.append(run)
            status = "PASS" if run.passed else "FAIL"
            print(f"{status} {case.id} ({run.seconds:.0f} s)", flush=True)
            for check in run.failures:
                detail = f": {check.detail}" if check.detail else ""
                print(f"     - {check.name}{detail}", flush=True)
    model_name = f"{settings.llm_provider}/{settings.llm_model}"
    path = write_report(report(runs, today, model_name), out)
    passed = sum(r.passed for r in runs)
    print(f"\n{passed}/{len(runs)} casos passaram. Relatório: {path}")
    return 0 if passed == len(runs) else 1


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parse_args(sys.argv[1:] if argv is None else argv)
    settings = get_settings()
    config = load_client_config(settings.tenant_id)
    today = args.today or datetime.date.today()
    try:
        cases = select(
            load_cases(args.cases, today, config.week_start or "monday"), args.only, args.agent
        )
    except (CaseError, OSError) as e:
        print(f"Casos inválidos: {e}", file=sys.stderr)
        return 2
    if args.list:
        print_list(cases)
        return 0
    try:
        return asyncio.run(run_all(cases, settings, config, today, args.out))
    except (LLMConfigError, MaximoSessionError) as e:
        print(f"Configuração: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
