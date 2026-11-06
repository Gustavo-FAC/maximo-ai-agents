"""CLI das análises, para conferir números contra o Maximo.

uv run python -m maximo_agents.analysis backlog [--client itambe] [--as-of AAAA-MM-DD]
    [--since AAAA-MM-DD] [--json]
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
)
from maximo_agents.config.settings import get_settings
from maximo_agents.mcp.session import open_maximo_session


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m maximo_agents.analysis")
    sub = parser.add_subparsers(dest="analysis", required=True)
    backlog = sub.add_parser("backlog", help="OS abertas e executadas (idade pelo reportdate)")
    backlog.add_argument("--client", default=None, help="Cliente (padrão: TENANT_ID do .env)")
    backlog.add_argument("--as-of", type=datetime.date.fromisoformat, default=None)
    backlog.add_argument("--since", type=datetime.date.fromisoformat, default=None)
    backlog.add_argument("--max-records", type=int, default=DEFAULT_MAX_RECORDS)
    backlog.add_argument("--json", action="store_true", help="Relatório em JSON")
    return parser.parse_args(argv)


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
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_backlog_text(report))
        print(f"\n({len(records)} OS lidas do Maximo em {elapsed:.0f} s)")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Saída em UTF-8 no console do Windows (acentos das descrições).
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.analysis == "backlog":
        return asyncio.run(run_backlog(args))
    return 2


if __name__ == "__main__":
    sys.exit(main())
