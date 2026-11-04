import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).parents[2] / "maximo_scripts" / "queryassetdowntime" / "QUERYASSETDOWNTIME.py"
)
_spec = importlib.util.spec_from_file_location("queryassetdowntime", SCRIPT)
qad = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qad)

BASE = {"date_from": "2026-01-01", "date_to": "2026-01-31"}


def query(**params):
    return qad.build_query({**BASE, **params}, "GERENTE1")


def error_code(**params):
    with pytest.raises(qad.ParamError) as exc:
        qad.build_query(params, "GERENTE1")
    return exc.value.code


# Day, parse_date, parse_list and the rest of the common block: tested through
# test_queryworkorders.py; test_script_common.py checks the block is identical.


def test_defaults():
    q = query()
    assert q["page"] == 1
    assert q["page_size"] == qad.DEFAULT_PAGE_SIZE
    assert q["offset"] == 0
    assert q["fields"] == list(qad.DEFAULT_FIELDS)
    assert q["filters"] == {}
    assert q["order_by"] == "assetnum, siteid, changedate, assetstatusid"


def test_date_range_on_changedate_inclusive():
    q = query()
    assert [(obj, attr, day.isoformat()) for obj, attr, day in q["binds"][:2]] == [
        ("ASSETSTATUS", "CHANGEDATE", "2026-01-01"),
        ("ASSETSTATUS", "CHANGEDATE", "2026-02-01"),
    ]
    assert q["where"].startswith("changedate >= :1 and changedate < :2")
    assert len(q["binds"]) == 4  # two dates + two site authorization binds
    assert q["where"].count(":") == len(q["binds"])


def test_dates_required():
    assert error_code(date_to="2026-01-31") == "required"
    assert error_code(date_from="2026-01-01") == "required"
    assert error_code(code="MANUT") == "required"
    assert error_code(location="L3T05M1") == "required"
    assert error_code(event="down") == "required"


@pytest.mark.parametrize(("name", "attribute"), [("assetnums", "ASSETNUM"), ("wonums", "WONUM")])
def test_lookup_without_dates(name, attribute):
    q = qad.build_query({name: "atv001, ATV002", "date_to": "*"}, "GERENTE1")
    assert q["date_from"] is None and q["date_to"] is None
    assert q["filters"] == {name: ["ATV001", "ATV002"]}
    assert q["binds"][:2] == [
        ("ASSETSTATUS", attribute, "ATV001"),
        ("ASSETSTATUS", attribute, "ATV002"),
    ]
    assert q["where"].startswith(f"{attribute.lower()} in (:1, :2)")
    assert "changedate" not in q["where"]
    assert q["where"].count(":") == len(q["binds"])


def test_lookup_with_dates_still_validates():
    assert query(assetnums="ATV001")["date_from"] == "2026-01-01"
    assert error_code(assetnums="ATV001", date_from="2026-01-01") == "required"
    assert error_code(assetnums=" , ") == "required"  # empty list must not unbound the query
    assert error_code(wonums="1", date_from="2024-01-01", date_to="2026-01-31") == (
        "range_too_large"
    )


def test_range_order_limit_and_format():
    assert error_code(date_from="2026-02-01", date_to="2026-01-01") == "invalid_range"
    assert error_code(date_from="2025-01-01", date_to="2026-01-02") == "range_too_large"
    assert query(date_from="2025-01-01", date_to="2026-01-01")["date_to"] == "2026-01-01"
    assert error_code(date_from="2026-02-30", date_to="2026-03-01") == "invalid_date"


def test_list_filters_bound_not_inlined():
    q = query(siteid="fabrica", location="L3T05M1,L3T05M2", code="manut", changeby="maxadmin")
    assert q["filters"] == {
        "siteid": ["FABRICA"],
        "location": ["L3T05M1", "L3T05M2"],
        "code": ["MANUT"],
        "changeby": ["MAXADMIN"],
    }
    assert "siteid in (:3)" in q["where"]
    assert "location in (:4, :5)" in q["where"]
    assert "code in (:6)" in q["where"]
    assert "changeby in (:7)" in q["where"]
    assert "FABRICA" not in q["where"]
    assert ("ASSETSTATUS", "CODE", "MANUT") in q["binds"]
    assert q["where"].count(":") == len(q["binds"])


@pytest.mark.parametrize(("raw", "sql"), [("down", "isrunning = 0"), (" UP ", "isrunning = 1")])
def test_event_is_fixed_sql(raw, sql):
    q = query(event=raw)
    assert sql in q["where"]
    assert q["filters"] == {"event": raw.strip().upper()}
    assert len(q["binds"]) == 4  # no bind for the event


def test_event_invalid_and_unset():
    assert error_code(**BASE, event="0 or 1=1") == "invalid_event"
    assert error_code(**BASE, event="running") == "invalid_event"
    assert "isrunning" not in query(event="*")["where"]


def test_bind_numbers_follow_clause_order():
    q = query(assetnums="A1", wonums="1", code="X", event="down")
    where = q["where"]
    numbers = [int(part.split()[0].strip("(),")) for part in where.split(":")[1:]]
    assert numbers == list(range(1, len(q["binds"]) + 1))


def test_injection_stays_in_binds():
    payload = "X' OR '1'='1"
    q = query(assetnums=payload, location=payload)
    assert payload.upper() not in q["where"]
    assert ("ASSETSTATUS", "ASSETNUM", payload.upper()) in q["binds"]
    assert ("ASSETSTATUS", "LOCATION", payload.upper()) in q["binds"]


def test_accented_values():
    q = query(code="ELÉTRICA,MECÂNICA")
    assert q["filters"]["code"] == ["ELÉTRICA", "MECÂNICA"]


def test_list_limits():
    assetnums = ",".join(str(n) for n in range(qad.MAX_ASSETNUMS))
    assert len(query(assetnums=assetnums)["filters"]["assetnums"]) == qad.MAX_ASSETNUMS
    assert error_code(**BASE, assetnums=assetnums + ",X") == "too_many_values"
    wonums = ",".join(str(n) for n in range(qad.MAX_WONUMS + 1))
    assert error_code(**BASE, wonums=wonums) == "too_many_values"
    many = ",".join(f"L{n}" for n in range(qad.MAX_LIST_VALUES + 1))
    assert error_code(**BASE, location=many) == "too_many_values"
    assert error_code(**BASE, code=many) == "too_many_values"


def test_site_authorization_always_applied():
    q = query(siteid="FABRICA", assetnums="A1")
    n = len(q["binds"])
    assert q["binds"][-2:] == [("GROUPUSER", "USERID", "GERENTE1")] * 2
    assert q["where"].endswith(qad.SITE_AUTH_WHERE % (n - 1, n))


def test_authorized_sites_become_explicit_site_filter():
    q = qad.build_query(BASE, "GERENTE1", ["FABRICA", "MATRIZ"])
    assert q["where"].startswith("changedate >= :1 and changedate < :2 and siteid in (:3, :4)")
    assert q["binds"][2:4] == [
        ("ASSETSTATUS", "SITEID", "FABRICA"),
        ("ASSETSTATUS", "SITEID", "MATRIZ"),
    ]
    assert q["filters"] == {}  # not asked by the caller
    n = len(q["binds"])
    assert q["where"].endswith(qad.SITE_AUTH_WHERE % (n - 1, n))  # still applied
    assert q["where"].count(":") == n


def test_requested_siteid_wins_over_authorized_sites():
    q = qad.build_query({**BASE, "siteid": "fabrica"}, "GERENTE1", ["FABRICA", "MATRIZ"])
    assert "siteid in (:3)" in q["where"]
    assert ("ASSETSTATUS", "SITEID", "MATRIZ") not in q["binds"]
    assert q["filters"] == {"siteid": ["FABRICA"]}


def test_authorized_sites_query():
    where, binds = qad.authorized_sites_query("GERENTE1")
    assert where == qad.SITE_AUTH_WHERE % (1, 2)
    assert binds == [("GROUPUSER", "USERID", "GERENTE1")] * 2


def test_permission_is_fixed_in_code():
    assert (qad.PERMISSION_APP, qad.PERMISSION_OPTION) == ("ASSET", "READ")
    assert "authapp" not in qad.PARAM_NAMES
    assert "authsigoption" not in qad.PARAM_NAMES


def test_fields():
    q = query(fields="Downtime, calnum, downtime")
    assert q["fields"] == ["assetnum", "siteid", "downtime", "calnum"]
    assert error_code(**BASE, fields="assetnum,description") == "unknown_field"
    assert (qad.FIELD_TYPES["isrunning"], qad.FIELD_TYPES["downtime"]) == ("bool", "float")


def test_pagination():
    q = query(page="2", page_size="500")
    assert (q["page"], q["page_size"], q["offset"]) == (2, 500, 500)
    assert error_code(**BASE, page_size=str(qad.MAX_PAGE_SIZE + 1)) == "out_of_range"
    assert error_code(**BASE, page="0") == "out_of_range"


def test_every_parameter_is_read():
    raw, _ = qad.collect_params(qad.PARAM_NAMES, {}, None, None)
    assert set(raw) == set(qad.PARAM_NAMES)
    used = {"date_from", "date_to", "event", "fields", "page", "page_size"}
    used |= {name for name, _, _, _ in qad.LIST_FILTERS}
    assert used == set(qad.PARAM_NAMES)


def test_response_metadata():
    q = query(page_size="50")
    resp = qad.build_response(q, 120, [{"assetnum": "A1"}])
    assert (resp["total_pages"], resp["has_more"], resp["returned"]) == (3, True, 1)
    assert (resp["date_field"], resp["date_from"], resp["date_to"]) == (
        "changedate",
        "2026-01-01",
        "2026-01-31",
    )
    assert resp["items"] == [{"assetnum": "A1"}]
    no_dates = qad.build_query({"assetnums": "A1"}, "GERENTE1")
    assert qad.build_response(no_dates, 0, [])["date_from"] is None
