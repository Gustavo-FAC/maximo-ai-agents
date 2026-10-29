import datetime
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "maximo_scripts" / "queryworkorders" / "QUERYWORKORDERS.py"
_spec = importlib.util.spec_from_file_location("queryworkorders", SCRIPT)
qwo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qwo)

BASE = {"date_from": "2026-01-01", "date_to": "2026-01-31"}


def query(**params):
    return qwo.build_query({**BASE, **params}, "GERENTE1")


def error_code(**params):
    with pytest.raises(qwo.ParamError) as exc:
        qwo.build_query(params, "GERENTE1")
    return exc.value.code


def test_defaults():
    q = query()
    assert q["date_field"] == "reportdate"
    assert q["page"] == 1
    assert q["page_size"] == qwo.DEFAULT_PAGE_SIZE
    assert q["offset"] == 0
    assert q["fields"] == list(qwo.DEFAULT_FIELDS)
    assert q["filters"] == {}
    assert q["order_by"] == "reportdate desc, wonum"


def test_date_to_inclusive():
    q = query()
    assert [(obj, attr, day.isoformat()) for obj, attr, day in q["binds"][:2]] == [
        ("WORKORDER", "REPORTDATE", "2026-01-01"),
        ("WORKORDER", "REPORTDATE", "2026-02-01"),
    ]
    assert "reportdate >= :1 and reportdate < :2" in q["where"]


def test_day_matches_calendar():
    epoch = datetime.date(1970, 1, 1)
    day = datetime.date(1900, 1, 1)
    while day.year <= 2100:
        ours = qwo.Day.from_ymd(day.year, day.month, day.day)
        assert ours.ordinal == (day - epoch).days
        assert ours.isoformat() == day.isoformat()
        day += datetime.timedelta(days=1)


def test_leap_day_and_year_end():
    q = query(date_from="2024-02-29", date_to="2024-12-31")
    assert q["date_from"] == "2024-02-29"
    assert q["binds"][1][2].isoformat() == "2025-01-01"


# Imports, globals() and write calls: tests/unit/test_script_common.py (all scripts).


def test_dates_required():
    assert error_code(date_to="2026-01-31") == "required"
    assert error_code(date_from="2026-01-01") == "required"
    assert error_code(date_from="*", date_to="2026-01-31") == "required"
    assert error_code(status="CONCL") == "required"


def test_wonums_without_dates():
    # wonums is already capped at MAX_WONUMS, so the date range becomes optional.
    q = qwo.build_query({"wonums": "1564759, 1564757", "date_from": "*"}, "GERENTE1")
    assert q["date_from"] is None
    assert q["date_to"] is None
    assert q["filters"] == {"wonums": ["1564759", "1564757"]}
    assert q["binds"][:2] == [
        ("WORKORDER", "WONUM", "1564759"),
        ("WORKORDER", "WONUM", "1564757"),
    ]
    assert "wonum in (:1, :2)" in q["where"]
    assert "reportdate >=" not in q["where"]
    assert q["where"].count(":") == len(q["binds"])


def test_wonums_with_dates_still_filter_and_validate():
    q = query(wonums="1564759")
    assert q["date_from"] == "2026-01-01"
    assert "reportdate >= :1 and reportdate < :2" in q["where"]
    assert error_code(wonums="1564759", date_from="2026-01-01") == "required"
    assert error_code(wonums=" , ") == "required"  # empty list must not unbound the query
    assert error_code(wonums="1564759", date_from="2024-01-01", date_to="2026-01-31") == (
        "range_too_large"
    )


@pytest.mark.parametrize(
    "value",
    [
        "2026-1-1",
        "01/01/2026",
        "2026-02-30",
        "2025-02-29",
        "2026-13-01",
        "2026-00-10",
        "2026-01-00",
        "20260-1-01",
        "2026+01-01",
        "hoje",
    ],
)
def test_invalid_date(value):
    assert error_code(date_from=value, date_to="2026-03-01") == "invalid_date"


def test_range_order_and_limit():
    assert error_code(date_from="2026-02-01", date_to="2026-01-01") == "invalid_range"
    assert error_code(date_from="2025-01-01", date_to="2026-01-02") == "range_too_large"
    assert query(date_from="2025-01-01", date_to="2026-01-01")["date_to"] == "2026-01-01"


def test_date_field_whitelist():
    assert query(date_field="ACTFINISH")["date_field"] == "actfinish"
    assert error_code(**BASE, date_field="description") == "invalid_date_field"
    assert error_code(**BASE, date_field="reportdate; drop table workorder") == (
        "invalid_date_field"
    )


def test_unset_filters_ignored():
    q = query(siteid="*", status="", priority=None)
    assert q["filters"] == {}
    assert len(q["binds"]) == 4  # two dates + two site authorization binds


def test_list_filters_bound_not_inlined():
    q = query(siteid="bedford, texas", status="APPR,WAPPR,APPR", priority="1,2")
    assert q["filters"] == {
        "siteid": ["BEDFORD", "TEXAS"],
        "status": ["APPR", "WAPPR"],
        "priority": [1, 2],
    }
    assert "siteid in (:3, :4)" in q["where"]
    assert "status in (:5, :6)" in q["where"]
    assert "wopriority in (:7, :8)" in q["where"]
    assert "BEDFORD" not in q["where"]
    assert ("WORKORDER", "WOPRIORITY", 2) in q["binds"]


def test_injection_stays_in_binds():
    payload = "X' OR '1'='1"
    q = query(assetnum=payload)
    assert payload.upper() not in q["where"]
    assert ("WORKORDER", "ASSETNUM", payload.upper()) in q["binds"]


def test_accented_values():
    q = query(persongroup="mecânica,elétrica")
    assert q["filters"]["persongroup"] == ["MECÂNICA", "ELÉTRICA"]


def test_list_limits():
    wonums = ",".join(str(n) for n in range(qwo.MAX_WONUMS))
    assert len(query(wonums=wonums)["filters"]["wonums"]) == qwo.MAX_WONUMS
    assert error_code(**BASE, wonums=wonums + ",X") == "too_many_values"
    many = ",".join(f"S{n}" for n in range(qwo.MAX_LIST_VALUES + 1))
    assert error_code(**BASE, siteid=many) == "too_many_values"
    assert error_code(**BASE, priority="1,alta") == "invalid_integer"


def test_site_authorization_always_applied():
    q = query(siteid="BEDFORD")
    n = len(q["binds"])
    assert q["binds"][-2:] == [("GROUPUSER", "USERID", "GERENTE1")] * 2
    assert q["where"].endswith(qwo.SITE_AUTH_WHERE % (n - 1, n))


def test_permission_is_fixed_in_code():
    assert qwo.permission_binds("GERENTE1") == [
        ("APPLICATIONAUTH", "APP", "WOTRACK"),
        ("APPLICATIONAUTH", "OPTIONNAME", "READ"),
        ("GROUPUSER", "USERID", "GERENTE1"),
    ]
    assert ":1" in qwo.PERMISSION_WHERE and ":3" in qwo.PERMISSION_WHERE
    # Security values must never be readable from the request.
    assert "authapp" not in qwo.PARAM_NAMES
    assert "authsigoption" not in qwo.PARAM_NAMES


def test_fields():
    q = query(fields="Description, wopriority, description")
    assert q["fields"] == ["wonum", "siteid", "description", "wopriority"]
    assert error_code(**BASE, fields="wonum,password") == "unknown_field"


def test_pagination():
    q = query(page="3", page_size="50")
    assert (q["page"], q["page_size"], q["offset"]) == (3, 50, 100)
    assert error_code(**BASE, page_size=str(qwo.MAX_PAGE_SIZE + 1)) == "out_of_range"
    assert error_code(**BASE, page="0") == "out_of_range"
    assert error_code(**BASE, page="-1") == "invalid_integer"


def test_collect_params_precedence():
    variables = {"date_from": "2026-01-01", "date_to": "*", "siteid": "*"}
    body = {"date_to": "2026-01-31", "siteid": "BEDFORD"}
    query_params = {"siteid": "TEXAS", "page": "2"}
    raw, sources = qwo.collect_params(variables, body, query_params.get)
    assert raw["date_from"] == "2026-01-01"
    assert raw["date_to"] == "2026-01-31"
    assert raw["siteid"] == "BEDFORD"
    assert raw["page"] == "2"
    assert sources == {
        "date_from": "variable",
        "date_to": "body",
        "siteid": "body",
        "page": "query",
    }
    assert set(raw) == set(qwo.PARAM_NAMES)


def test_collect_params_without_body_or_query():
    raw, sources = qwo.collect_params({"date_from": "2026-01-01"}, None, None)
    assert raw["date_from"] == "2026-01-01"
    assert raw["date_to"] is None
    assert sources == {"date_from": "variable"}


def test_response_metadata():
    q = query(page_size="50")
    resp = qwo.build_response(q, 120, [{"wonum": "1"}])
    assert resp["total_pages"] == 3
    assert resp["has_more"] is True
    assert resp["returned"] == 1
    assert qwo.build_response(q, 0, [])["total_pages"] == 0
