import asyncio
import datetime

import pytest

from maximo_agents.analysis.config import parse_client_config
from maximo_agents.analysis.fetch import (
    PAGE_SIZE,
    WORK_ORDER_TOOL,
    MaximoToolError,
    TooManyRecordsError,
    count_executed_by_age,
    count_work_orders,
    date_windows,
    fetch_backlog_work_orders,
    fetch_corrective_work_orders,
    fetch_work_orders,
)

D = datetime.date
CONFIG = parse_client_config(
    "t",
    {
        "sites": ["FABRICA", "MINERACAO"],
        "history_start": "2024-01-01",
        "statuses": {
            "APROG": {"class": "open"},
            "EMAND": {"internal": "INPRG"},
            "POSEXEC": {"internal": "INPRG", "class": "executed"},
            "CONCL": {"internal": "COMP"},
        },
        "corrective_worktypes": ["CO", "EM"],
    },
)


class FakeTool:
    """Responde por (date_from, page) a partir de um dicionário; grava as chamadas."""

    def __init__(self, pages=None, total=0, error=None):
        self.pages = pages or {}
        self.total = total
        self.error = error
        self.calls = []

    async def __call__(self, name, arguments):
        self.calls.append((name, arguments))
        if self.error:
            return {"error": self.error}
        key = (arguments["date_from"], int(arguments.get("page", "1")))
        items, has_more = self.pages.get(key, ([], False))
        return {"total": self.total, "items": items, "has_more": has_more}


def run(coro):
    return asyncio.run(coro)


def test_date_windows():
    assert date_windows(D(2026, 1, 1), D(2026, 1, 1)) == [(D(2026, 1, 1), D(2026, 1, 1))]
    windows = date_windows(D(2024, 1, 1), D(2026, 11, 6))
    assert windows[0] == (D(2024, 1, 1), D(2024, 12, 31))  # 366 dias (2024 bissexto)
    assert windows[-1][1] == D(2026, 11, 6)
    for (_, end), (start, _) in zip(windows, windows[1:], strict=False):
        assert start == end + datetime.timedelta(days=1)  # sem buraco nem sobreposição
    assert all((b - a).days + 1 <= 366 for a, b in windows)
    with pytest.raises(ValueError):
        date_windows(D(2026, 1, 2), D(2026, 1, 1))


def test_fetch_all_pages_and_windows():
    wo = lambda n: {"wonum": str(n), "siteid": "FABRICA"}  # noqa: E731
    tool = FakeTool(
        pages={
            ("2024-01-01", 1): ([wo(1), wo(2)], True),
            ("2024-01-01", 2): ([wo(2), wo(3)], False),  # wo 2 repetida: some
            ("2025-01-01", 1): ([wo(4)], False),
        }
    )
    records = run(
        fetch_work_orders(
            tool,
            date_from=D(2024, 1, 1),
            date_to=D(2025, 6, 30),
            filters={"status": ["APROG", "EMAND"], "siteid": []},
            fields=("wonum", "siteid"),
        )
    )
    assert [r["wonum"] for r in records] == ["1", "2", "3", "4"]
    assert len(tool.calls) == 3
    name, args = tool.calls[0]
    assert name == WORK_ORDER_TOOL
    assert args == {
        "date_from": "2024-01-01",
        "date_to": "2024-12-31",
        "date_field": "reportdate",
        "fields": "wonum,siteid",
        "page": "1",
        "page_size": str(PAGE_SIZE),
        "status": "APROG,EMAND",  # lista vazia (siteid) não vai
    }
    assert tool.calls[1][1]["page"] == "2"
    assert tool.calls[2][1]["date_to"] == "2025-06-30"


def test_fetch_error_and_limits():
    tool = FakeTool(error={"code": "range_too_large", "parameter": "date_to", "message": "x"})
    with pytest.raises(MaximoToolError) as exc:
        run(
            fetch_work_orders(
                tool, date_from=D(2026, 1, 1), date_to=D(2026, 1, 2), filters={}, fields=("wonum",)
            )
        )
    assert exc.value.code == "range_too_large"
    assert exc.value.parameter == "date_to"

    items = [{"wonum": str(n), "siteid": "S"} for n in range(5)]
    tool = FakeTool(pages={("2026-01-01", 1): (items, False)})
    with pytest.raises(TooManyRecordsError):
        run(
            fetch_work_orders(
                tool,
                date_from=D(2026, 1, 1),
                date_to=D(2026, 1, 2),
                filters={},
                fields=("wonum",),
                max_records=4,
            )
        )

    with pytest.raises(ValueError):
        run(
            fetch_work_orders(
                tool,
                date_from=D(2026, 1, 1),
                date_to=D(2026, 1, 2),
                filters={"status": [str(n) for n in range(21)]},
                fields=("wonum",),
            )
        )


def test_count_sums_totals_of_each_window():
    tool = FakeTool(total=7)
    total = run(
        count_work_orders(
            tool, date_from=D(2024, 1, 1), date_to=D(2026, 1, 1), filters={"status": ["POSEXEC"]}
        )
    )
    assert total == 7 * 2  # 2 janelas de 366 dias
    assert all(args["page_size"] == "1" for _, args in tool.calls)


def test_backlog_fetches_only_open_statuses_with_sites():
    tool = FakeTool(pages={("2026-01-01", 1): ([{"wonum": "1", "siteid": "FABRICA"}], False)})
    records = run(fetch_backlog_work_orders(tool, CONFIG, D(2026, 11, 6), since=D(2026, 1, 1)))
    assert records == [{"wonum": "1", "siteid": "FABRICA"}]
    args = tool.calls[0][1]
    assert args["status"] == "APROG,EMAND"  # sem POSEXEC nem CONCL
    assert args["siteid"] == "FABRICA,MINERACAO"
    assert args["date_from"] == "2026-01-01"
    # Sem since: começa no history_start.
    tool = FakeTool()
    run(fetch_backlog_work_orders(tool, CONFIG, D(2024, 2, 1)))
    assert tool.calls[0][1]["date_from"] == "2024-01-01"


def test_executed_counted_by_age_bucket():
    tool = FakeTool(total=2)
    by_age = run(count_executed_by_age(tool, CONFIG, D(2026, 11, 6)))
    assert list(by_age) == ["0-30", "31-90", "91-180", "181-365", ">365"]
    assert by_age["0-30"] == 2
    assert by_age[">365"] == 2 * 2  # 2024-01-01 a 2025-11-05: 2 janelas
    assert {args["status"] for _, args in tool.calls} == {"POSEXEC"}
    assert all(args["siteid"] == "FABRICA,MINERACAO" for _, args in tool.calls)


def test_corrective_fetch_filters_worktypes_and_sites():
    tool = FakeTool()
    run(fetch_corrective_work_orders(tool, CONFIG, D(2025, 11, 7), D(2026, 11, 6)))
    args = tool.calls[0][1]
    assert args["worktype"] == "CO,EM"
    assert args["siteid"] == "FABRICA,MINERACAO"
    assert "status" not in args  # canceladas saem na análise, pela classe
    assert (args["date_from"], args["date_to"]) == ("2025-11-07", "2026-11-06")
    assert "assetnum" in args["fields"] and "location" in args["fields"]
    without = parse_client_config(
        "t", {"history_start": "2024-01-01", "statuses": {"A": {"class": "open"}}}
    )
    with pytest.raises(ValueError):
        run(fetch_corrective_work_orders(tool, without, D(2026, 1, 1), D(2026, 1, 2)))
