import datetime
import json

import pytest

from maximo_agents.analysis.backlog import (
    age_bucket,
    age_bucket_ranges,
    backlog_report,
    format_backlog_text,
)
from maximo_agents.analysis.config import load_client_config

D = datetime.date
AS_OF = D(2026, 11, 6)
CONFIG = load_client_config("itambe")


def wo(wonum, status, reportdate, statusdate=None, **extra):
    record = {
        "wonum": wonum,
        "siteid": "FABRICA",
        "description": f"OS {wonum}",
        "status": status,
        "reportdate": reportdate,
        "statusdate": statusdate or reportdate,
        "worktype": None,
        "wopriority": None,
        "assetnum": None,
        "location": None,
        "persongroup": None,
    }
    record.update(extra)
    return record


@pytest.mark.parametrize(
    "days, label",
    [
        (0, "0-30"),
        (30, "0-30"),
        (31, "31-90"),
        (90, "31-90"),
        (91, "91-180"),
        (180, "91-180"),
        (181, "181-365"),
        (365, "181-365"),
        (366, ">365"),
        (6000, ">365"),
        (None, "no date"),
    ],
)
def test_age_bucket(days, label):
    assert age_bucket(days) == label


def test_age_bucket_ranges_are_contiguous():
    ranges = age_bucket_ranges(AS_OF, D(2006, 1, 1))
    assert ranges[0] == ("0-30", D(2026, 10, 7), AS_OF)
    assert ranges[1] == ("31-90", D(2026, 8, 8), D(2026, 10, 6))
    assert ranges[-1] == (">365", D(2006, 1, 1), D(2025, 11, 5))  # 366 dias antes
    for (_, start, _), (_, _, end) in zip(ranges, ranges[1:], strict=False):
        assert end == start - datetime.timedelta(days=1)
    # Começo recente: faixas antigas somem; a última vai até o começo.
    assert age_bucket_ranges(AS_OF, D(2026, 9, 1)) == [
        ("0-30", D(2026, 10, 7), AS_OF),
        ("31-90", D(2026, 9, 1), D(2026, 10, 6)),
    ]


def test_backlog_report():
    records = [
        wo("1", "APROG", "2026-11-01T08:00:00", worktype="CO", wopriority=1, location="L1"),
        wo(
            "2",
            "APROG",
            "2026-03-13T13:24:18",
            "2026-10-07T10:00:00",
            worktype="MS",
            wopriority=3,
            location="L1",
        ),
        wo("3", "EMAND", "2009-08-13T00:00:00", worktype=None, location="L2"),
        wo("4", "EMAND", "2026-10-06T23:59:59", worktype="", siteid="MINERACAO"),
        wo("5", "CONCL", "2026-01-01T00:00:00"),  # fechada: não deveria vir
        wo("6", "AAPROV", None),
    ]
    report = backlog_report(records, {"0-30": 1, ">365": 9}, CONFIG, AS_OF)
    opened = report["open"]
    assert opened["total"] == 5
    assert opened["by_age_days"] == {
        "0-30": 1,
        "31-90": 1,  # 2026-10-06 = 31 dias
        "91-180": 0,
        "181-365": 1,  # 2026-03-13 = 238 dias
        ">365": 1,
        "no date": 1,
    }
    assert opened["median_age_days"] == (31 + 238) // 2
    assert opened["by_status"]["APROG"] == {
        "count": 2,
        "median_days_in_status": 17,  # 5 e 30 dias (17,5 truncado)
        "max_days_in_status": 30,
    }
    assert list(opened["by_status"]) == ["APROG", "EMAND", "AAPROV"]
    assert opened["by_worktype"] == {"(empty)": 3, "CO": 1, "MS": 1}
    assert opened["by_priority"] == {"(empty)": 3, "1": 1, "3": 1}
    assert opened["by_site"] == {"FABRICA": 4, "MINERACAO": 1}
    assert opened["top_locations"] == {"(empty)": 2, "L1": 2, "L2": 1}
    assert [row["wonum"] for row in opened["oldest"]] == ["3", "2", "4", "1", "6"]
    assert opened["oldest"][0]["worktype"] is None  # nada de NaN
    assert report["executed"] == {
        "statuses": ["POSEXEC"],
        "total": 10,
        "by_age_days": {"0-30": 1, "31-90": 0, "91-180": 0, "181-365": 0, ">365": 9},
    }
    assert report["ignored"] == {"CONCL": 1}
    json.dumps(report)  # serializável (vai para o agente)


def test_empty_backlog():
    report = backlog_report([], {}, CONFIG, AS_OF)
    assert report["open"]["total"] == 0
    assert report["open"]["median_age_days"] is None
    assert report["executed"]["total"] == 0
    assert "ABERTAS: 0 OS" in format_backlog_text(report)


def test_text_report():
    records = [wo("3", "EMAND", "2009-08-13T00:00:00", description=None)]
    text = format_backlog_text(backlog_report(records, {">365": 5}, CONFIG, AS_OF))
    assert "ABERTAS: 1 OS" in text
    assert "EXECUTADAS, AGUARDANDO FECHAMENTO (POSEXEC): 5 OS" in text
    assert "nan" not in text.lower().replace("manutenção", "")
