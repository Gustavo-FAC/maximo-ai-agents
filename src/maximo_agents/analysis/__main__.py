"""CLI das análises, para conferir números contra o Maximo.

uv run python -m maximo_agents.analysis backlog [--client itambe] [--as-of AAAA-MM-DD]
    [--since AAAA-MM-DD] [--json]
uv run python -m maximo_agents.analysis recurrence [--client itambe] [--as-of AAAA-MM-DD]
    [--days 365] [--repeat-days 30] [--top 20] [--json]
uv run python -m maximo_agents.analysis status-time [--client itambe] [--as-of AAAA-MM-DD]
    [--days 90] [--worktype CO,EM] [--top 20] [--json]
uv run python -m maximo_agents.analysis material [--client itambe] [--as-of AAAA-MM-DD]
    [--days 365] [--top 20] [--json]
"""

import argparse
import asyncio
import datetime
import json
import sys
import time

from maximo_agents.analysis.backlog import backlog_report, format_backlog_text
from maximo_agents.analysis.config import load_client_config
from maximo_agents.analysis.fetch import (
    DEFAULT_MAX_RECORDS,
    count_executed_by_age,
    fetch_backlog_work_orders,
    fetch_completed_histories,
    fetch_corrective_work_orders,
    fetch_material_usage,
    fetch_work_orders_by_number,
)
from maximo_agents.analysis.material import format_material_text, material_report
from maximo_agents.analysis.recurrence import (
    DEFAULT_REPEAT_DAYS,
    DEFAULT_TOP,
    format_recurrence_text,
    recurrence_report,
)
from maximo_agents.analysis.status_time import format_status_time_text, status_time_report
from maximo_agents.config.settings import get_settings
from maximo_agents.mcp.session import open_maximo_session


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m maximo_agents.analysis")
    sub = parser.add_subparsers(dest="analysis", required=True)

    def common(command):
        command.add_argument("--client", default=None, help="Cliente (padrão: TENANT_ID do .env)")
        command.add_argument("--as-of", type=datetime.date.fromisoformat, default=None)
        command.add_argument("--max-records", type=int, default=DEFAULT_MAX_RECORDS)
        command.add_argument("--json", action="store_true", help="Relatório em JSON")

    backlog = sub.add_parser("backlog", help="OS abertas e executadas (idade pelo reportdate)")
    common(backlog)
    backlog.add_argument("--since", type=datetime.date.fromisoformat, default=None)

    recurrence = sub.add_parser("recurrence", help="Reincidência de corretivas")
    common(recurrence)
    recurrence.add_argument("--days", type=int, default=365, help="Período até --as-of")
    recurrence.add_argument("--repeat-days", type=int, default=DEFAULT_REPEAT_DAYS)
    recurrence.add_argument("--top", type=int, default=DEFAULT_TOP)

    status_time = sub.add_parser("status-time", help="Tempo em status das OS concluídas")
    common(status_time)
    status_time.add_argument("--days", type=int, default=90, help="Período até --as-of")
    status_time.add_argument(
        "--worktype", default="", help="Tipos de trabalho separados por vírgula (padrão: todos)"
    )
    status_time.add_argument("--top", type=int, default=DEFAULT_TOP)

    material = sub.add_parser("material", help="Consumo e custo de material")
    common(material)
    material.add_argument("--days", type=int, default=365, help="Período até --as-of")
    material.add_argument("--top", type=int, default=DEFAULT_TOP)
    return parser.parse_args(argv)


def print_report(args, report, text, records, elapsed, unit="OS") -> None:
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(text)
        print(f"\n({len(records)} {unit} lidas do Maximo em {elapsed:.0f} s)")


async def run_backlog(args: argparse.Namespace) -> int:
    settings = get_settings()
    config = load_client_config(args.client or settings.tenant_id)
    as_of = args.as_of or datetime.date.today()
    start = time.perf_counter()
    async with open_maximo_session(settings) as call_tool:
        records = await fetch_backlog_work_orders(
            call_tool, config, as_of, since=args.since, max_records=args.max_records
        )
        executed_by_age = await count_executed_by_age(call_tool, config, as_of, since=args.since)
    elapsed = time.perf_counter() - start
    report = backlog_report(records, executed_by_age, config, as_of)
    print_report(args, report, format_backlog_text(report), records, elapsed)
    return 0


async def run_recurrence(args: argparse.Namespace) -> int:
    settings = get_settings()
    config = load_client_config(args.client or settings.tenant_id)
    date_to = args.as_of or datetime.date.today()
    date_from = date_to - datetime.timedelta(days=args.days - 1)
    start = time.perf_counter()
    async with open_maximo_session(settings) as call_tool:
        records = await fetch_corrective_work_orders(
            call_tool, config, date_from, date_to, max_records=args.max_records
        )
    elapsed = time.perf_counter() - start
    report = recurrence_report(records, config, date_from, date_to, args.repeat_days, args.top)
    print_report(args, report, format_recurrence_text(report), records, elapsed)
    return 0


async def run_status_time(args: argparse.Namespace) -> int:
    settings = get_settings()
    config = load_client_config(args.client or settings.tenant_id)
    date_to = args.as_of or datetime.date.today()
    date_from = date_to - datetime.timedelta(days=args.days - 1)
    worktypes = [w.strip() for w in args.worktype.split(",") if w.strip()]
    start = time.perf_counter()
    async with open_maximo_session(settings) as call_tool:
        changes = await fetch_completed_histories(
            call_tool, config, date_from, date_to, worktypes, max_records=args.max_records
        )
    elapsed = time.perf_counter() - start
    report = status_time_report(changes, config, date_from, date_to, worktypes, args.top)
    text = format_status_time_text(report)
    print_report(args, report, text, changes, elapsed, unit="mudanças de status")
    return 0


async def run_material(args: argparse.Namespace) -> int:
    settings = get_settings()
    config = load_client_config(args.client or settings.tenant_id)
    date_to = args.as_of or datetime.date.today()
    date_from = date_to - datetime.timedelta(days=args.days - 1)
    start = time.perf_counter()
    async with open_maximo_session(settings) as call_tool:
        transactions = await fetch_material_usage(
            call_tool, config, date_from, date_to, max_records=args.max_records
        )
        pairs = [(t.get("siteid"), t.get("refwo")) for t in transactions]
        work_orders = await fetch_work_orders_by_number(
            call_tool, pairs, max_records=args.max_records
        )
    elapsed = time.perf_counter() - start
    report = material_report(transactions, work_orders, config, date_from, date_to, args.top)
    text = format_material_text(report)
    print_report(args, report, text, transactions, elapsed, unit="transações de material")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Saída em UTF-8 no console do Windows (acentos das descrições).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(sys.argv[1:] if argv is None else argv)
    runners = {
        "backlog": run_backlog,
        "recurrence": run_recurrence,
        "status-time": run_status_time,
        "material": run_material,
    }
    return asyncio.run(runners[args.analysis](args))


if __name__ == "__main__":
    sys.exit(main())
