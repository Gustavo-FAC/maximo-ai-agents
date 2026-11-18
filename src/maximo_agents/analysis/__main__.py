"""CLI das análises, para conferir números contra o Maximo.

uv run python -m maximo_agents.analysis backlog [--client itambe] [--as-of AAAA-MM-DD]
    [--since AAAA-MM-DD] [--json]
uv run python -m maximo_agents.analysis overdue [--client itambe] [--as-of AAAA-MM-DD]
    [--tolerance-days 7] [--top 20] [--json]
uv run python -m maximo_agents.analysis issued-executed [--client itambe] [--as-of AAAA-MM-DD]
    [--month AAAA-MM] [--months 1] [--group-by crew|worktype] [--json]
uv run python -m maximo_agents.analysis preventive-compliance [--client itambe]
    [--as-of AAAA-MM-DD] [--month AAAA-MM] [--months 1] [--group-by crew|worktype|modality]
uv run python -m maximo_agents.analysis recurrence [--client itambe] [--as-of AAAA-MM-DD]
    [--days 365] [--repeat-days 30] [--top 20] [--json]
uv run python -m maximo_agents.analysis status-time [--client itambe] [--as-of AAAA-MM-DD]
    [--days 90] [--worktype CO,EM] [--top 20] [--json]
uv run python -m maximo_agents.analysis material [--client itambe] [--as-of AAAA-MM-DD]
    [--days 365] [--top 20] [--json]
uv run python -m maximo_agents.analysis reliability [--client itambe] [--as-of AAAA-MM-DD]
    [--days 365] [--asset MOI0001] [--location L1] [--top 20] [--json]
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
    fetch_downtime_histories,
    fetch_issued_and_finished,
    fetch_material_usage,
    fetch_overdue_candidates,
    fetch_preventive_work_orders,
    fetch_work_orders_by_number,
)
from maximo_agents.analysis.issued_executed import (
    GROUP_BY,
    format_issued_executed_text,
    issued_executed_report,
)
from maximo_agents.analysis.issued_executed import period as issued_period
from maximo_agents.analysis.material import format_material_text, material_report
from maximo_agents.analysis.overdue import format_overdue_text, overdue_report
from maximo_agents.analysis.preventive_compliance import GROUP_BY as COMPLIANCE_GROUP_BY
from maximo_agents.analysis.preventive_compliance import (
    compliance_report,
    format_compliance_text,
)
from maximo_agents.analysis.recurrence import (
    DEFAULT_REPEAT_DAYS,
    DEFAULT_TOP,
    format_recurrence_text,
    recurrence_report,
)
from maximo_agents.analysis.reliability import format_reliability_text, reliability_report
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

    overdue = sub.add_parser("overdue", help="OS atrasadas (regra do cliente)")
    common(overdue)
    overdue.add_argument(
        "--tolerance-days", type=int, default=None, help="Padrão: tolerância do cliente"
    )
    overdue.add_argument("--top", type=int, default=DEFAULT_TOP)

    issued = sub.add_parser("issued-executed", help="OS emitidas x executadas por mês")
    common(issued)
    issued.add_argument("--month", default=None, help="Último mês AAAA-MM (padrão: o anterior)")
    issued.add_argument("--months", type=int, default=1, help="Quantos meses até --month")
    issued.add_argument("--group-by", choices=GROUP_BY, default="crew")

    compliance = sub.add_parser("preventive-compliance", help="Cumprimento de preventivas")
    common(compliance)
    compliance.add_argument("--month", default=None, help="Último mês AAAA-MM")
    compliance.add_argument("--months", type=int, default=1, help="Quantos meses até --month")
    compliance.add_argument("--group-by", choices=COMPLIANCE_GROUP_BY, default="crew")

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

    reliability = sub.add_parser("reliability", help="MTBF e MTTR (OS corretivas e paradas)")
    common(reliability)
    reliability.add_argument("--days", type=int, default=365, help="Período até --as-of")
    reliability.add_argument("--asset", default="", help="Ativos separados por vírgula")
    reliability.add_argument("--location", default="", help="Locations separadas por vírgula")
    reliability.add_argument("--top", type=int, default=DEFAULT_TOP)
    return parser.parse_args(argv)


def split_codes(text: str) -> list[str]:
    return [code.strip() for code in text.split(",") if code.strip()]


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


async def run_overdue(args: argparse.Namespace) -> int:
    settings = get_settings()
    config = load_client_config(args.client or settings.tenant_id)
    as_of = args.as_of or datetime.date.today()
    start = time.perf_counter()
    async with open_maximo_session(settings) as call_tool:
        records = await fetch_overdue_candidates(
            call_tool, config, as_of, max_records=args.max_records
        )
    elapsed = time.perf_counter() - start
    report = overdue_report(records, config, as_of, args.tolerance_days, args.top)
    print_report(args, report, format_overdue_text(report), records, elapsed)
    return 0


async def run_issued_executed(args: argparse.Namespace) -> int:
    settings = get_settings()
    config = load_client_config(args.client or settings.tenant_id)
    as_of = args.as_of or datetime.date.today()
    if args.month:
        last_month = datetime.date.fromisoformat(f"{args.month}-01")
    else:
        last_month = as_of.replace(day=1) - datetime.timedelta(days=1)
    date_from, date_to = issued_period(last_month, args.months, as_of)
    start = time.perf_counter()
    async with open_maximo_session(settings) as call_tool:
        issued, finished = await fetch_issued_and_finished(
            call_tool, config, date_from, date_to, max_records=args.max_records
        )
    elapsed = time.perf_counter() - start
    report = issued_executed_report(
        issued, finished, config, last_month, args.months, as_of, args.group_by
    )
    print_report(args, report, format_issued_executed_text(report), issued, elapsed)
    if not args.json:
        print(f"({len(finished)} OS terminadas no período lidas do Maximo)")
    return 0


def last_month_of(args: argparse.Namespace, as_of: datetime.date) -> datetime.date:
    if args.month:
        return datetime.date.fromisoformat(f"{args.month}-01")
    return as_of.replace(day=1) - datetime.timedelta(days=1)


async def run_preventive_compliance(args: argparse.Namespace) -> int:
    settings = get_settings()
    config = load_client_config(args.client or settings.tenant_id)
    as_of = args.as_of or datetime.date.today()
    last_month = last_month_of(args, as_of)
    date_from, date_to = issued_period(last_month, args.months, as_of)
    start = time.perf_counter()
    async with open_maximo_session(settings) as call_tool:
        records = await fetch_preventive_work_orders(
            call_tool, config, date_from, date_to, max_records=args.max_records
        )
    elapsed = time.perf_counter() - start
    report = compliance_report(records, config, last_month, args.months, as_of, args.group_by)
    print_report(args, report, format_compliance_text(report), records, elapsed)
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
    worktypes = split_codes(args.worktype)
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


async def run_reliability(args: argparse.Namespace) -> int:
    settings = get_settings()
    config = load_client_config(args.client or settings.tenant_id)
    date_to = args.as_of or datetime.date.today()
    date_from = date_to - datetime.timedelta(days=args.days - 1)
    assetnums, locations = split_codes(args.asset), split_codes(args.location)
    start = time.perf_counter()
    async with open_maximo_session(settings) as call_tool:
        work_orders = await fetch_corrective_work_orders(
            call_tool,
            config,
            date_from,
            date_to,
            max_records=args.max_records,
            assetnums=assetnums,
            locations=locations,
        )
        changes = await fetch_downtime_histories(
            call_tool, config, date_from, date_to, assetnums, locations, args.max_records
        )
    elapsed = time.perf_counter() - start
    report = reliability_report(
        work_orders, changes, config, date_from, date_to, assetnums, locations, args.top
    )
    text = format_reliability_text(report)
    print_report(args, report, text, work_orders, elapsed)
    if not args.json:
        print(f"({len(changes)} mudanças de estado de ativo lidas do Maximo)")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Saída em UTF-8 no console do Windows (acentos das descrições).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(sys.argv[1:] if argv is None else argv)
    runners = {
        "backlog": run_backlog,
        "overdue": run_overdue,
        "issued-executed": run_issued_executed,
        "preventive-compliance": run_preventive_compliance,
        "recurrence": run_recurrence,
        "status-time": run_status_time,
        "material": run_material,
        "reliability": run_reliability,
    }
    return asyncio.run(runners[args.analysis](args))


if __name__ == "__main__":
    sys.exit(main())
