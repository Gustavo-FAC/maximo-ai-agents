import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "maximo_scripts" / "querywostatus" / "QUERYWOSTATUS.py"
_spec = importlib.util.spec_from_file_location("querywostatus", SCRIPT)
qws = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qws)

BASE = {"date_from": "2026-01-01", "date_to": "2026-01-31"}
WO_SCOPE = qws.WO_WHERE % ""


def query(**params):
    return qws.build_query({**BASE, **params}, "GERENTE1")


def error_code(**params):
    with pytest.raises(qws.ParamError) as exc:
        qws.build_query(params, "GERENTE1")
    return exc.value.code


# Day, parse_date, parse_list and the rest of the common block: tested through
# test_queryworkorders.py; test_script_common.py checks the block is identical.


def test_defaults():
    q = query()
    assert q["page"] == 1
    assert q["page_size"] == qws.DEFAULT_PAGE_SIZE
    assert q["offset"] == 0
    assert q["fields"] == list(qws.DEFAULT_FIELDS)
    assert q["filters"] == {}
    assert q["order_by"] == "wonum, siteid, changedate, wostatusid"


def test_date_range_on_changedate_inclusive():
    q = query()
    assert [(obj, attr, day.isoformat()) for obj, attr, day in q["binds"][:2]] == [
        ("WOSTATUS", "CHANGEDATE", "2026-01-01"),
        ("WOSTATUS", "CHANGEDATE", "2026-02-01"),
    ]
    assert q["where"].startswith("changedate >= :1 and changedate < :2")


def test_work_order_scope_always_applied():
    # Only work orders and activities, as in QUERYWORKORDERS; never tasks.
    q = query()
    assert WO_SCOPE in q["where"]
    assert "w.istask = 0" in q["where"]
    assert "w.wonum = wostatus.wonum and w.siteid = wostatus.siteid" in q["where"]
    assert len(q["binds"]) == 4  # two dates + two site authorization binds
    assert q["where"].count(":") == len(q["binds"])


def test_dates_required():
    assert error_code(date_to="2026-01-31") == "required"
    assert error_code(date_from="2026-01-01") == "required"
    assert error_code(status="COMP") == "required"
    assert error_code(assetnum="MCA5853") == "required"


def test_wonums_without_dates():
    q = qws.build_query({"wonums": "1564759, 1564757", "date_to": "*"}, "GERENTE1")
    assert q["date_from"] is None and q["date_to"] is None
    assert q["filters"] == {"wonums": ["1564759", "1564757"]}
    assert q["binds"][:2] == [
        ("WOSTATUS", "WONUM", "1564759"),
        ("WOSTATUS", "WONUM", "1564757"),
    ]
    assert q["where"].startswith("wonum in (:1, :2)")
    assert "changedate" not in q["where"]
    assert q["where"].count(":") == len(q["binds"])


def test_wonums_with_dates_still_validate():
    assert query(wonums="1564759")["date_from"] == "2026-01-01"
    assert error_code(wonums="1564759", date_from="2026-01-01") == "required"
    assert error_code(wonums=" , ") == "required"  # empty list must not unbound the query
    assert error_code(wonums="1", date_from="2024-01-01", date_to="2026-01-31") == (
        "range_too_large"
    )


def test_range_order_limit_and_format():
    assert error_code(date_from="2026-02-01", date_to="2026-01-01") == "invalid_range"
    assert error_code(date_from="2025-01-01", date_to="2026-01-02") == "range_too_large"
    assert query(date_from="2025-01-01", date_to="2026-01-01")["date_to"] == "2026-01-01"
    assert error_code(date_from="2026-02-30", date_to="2026-03-01") == "invalid_date"


def test_status_change_filters_bound_not_inlined():
    q = query(siteid="fabrica", status="COMP,INPRG,COMP", changeby="maxadmin")
    assert q["filters"] == {
        "siteid": ["FABRICA"],
        "status": ["COMP", "INPRG"],
        "changeby": ["MAXADMIN"],
    }
    assert "siteid in (:3)" in q["where"]
    assert "status in (:4, :5)" in q["where"]
    assert "changeby in (:6)" in q["where"]
    assert "FABRICA" not in q["where"]
    assert ("WOSTATUS", "CHANGEBY", "MAXADMIN") in q["binds"]


def test_work_order_filters_inside_subquery():
    q = query(assetnum="MCA5853", location="L3T05M1,L3T05M2", worktype="CO", persongroup="mec")
    assert q["filters"] == {
        "assetnum": ["MCA5853"],
        "location": ["L3T05M1", "L3T05M2"],
        "persongroup": ["MEC"],
        "worktype": ["CO"],
    }
    assert (
        "w.istask = 0 and w.assetnum in (:3) and w.location in (:4, :5)"
        " and w.persongroup in (:6) and w.worktype in (:7))"
    ) in q["where"]
    assert q["binds"][2:7] == [
        ("WORKORDER", "ASSETNUM", "MCA5853"),
        ("WORKORDER", "LOCATION", "L3T05M1"),
        ("WORKORDER", "LOCATION", "L3T05M2"),
        ("WORKORDER", "PERSONGROUP", "MEC"),
        ("WORKORDER", "WORKTYPE", "CO"),
    ]
    assert q["where"].count(":") == len(q["binds"])


def test_bind_numbers_follow_clause_order():
    q = query(wonums="1", status="COMP", assetnum="A1")
    where = q["where"]
    numbers = [int(part.split()[0].strip("(),")) for part in where.split(":")[1:]]
    assert numbers == list(range(1, len(q["binds"]) + 1))


def test_injection_stays_in_binds():
    payload = "X' OR '1'='1"
    q = query(assetnum=payload, changeby=payload)
    assert payload.upper() not in q["where"]
    assert ("WORKORDER", "ASSETNUM", payload.upper()) in q["binds"]
    assert ("WOSTATUS", "CHANGEBY", payload.upper()) in q["binds"]


def test_accented_values():
    q = query(status="AGUARD. MATERIAL,CONCLUÍDA")
    assert q["filters"]["status"] == ["AGUARD. MATERIAL", "CONCLUÍDA"]


def test_list_limits():
    wonums = ",".join(str(n) for n in range(qws.MAX_WONUMS))
    assert len(query(wonums=wonums)["filters"]["wonums"]) == qws.MAX_WONUMS
    assert error_code(**BASE, wonums=wonums + ",X") == "too_many_values"
    many = ",".join(f"L{n}" for n in range(qws.MAX_LIST_VALUES + 1))
    assert error_code(**BASE, location=many) == "too_many_values"
    assert error_code(**BASE, status=many) == "too_many_values"


def test_site_authorization_always_applied():
    q = query(siteid="FABRICA", assetnum="A1")
    n = len(q["binds"])
    assert q["binds"][-2:] == [("GROUPUSER", "USERID", "GERENTE1")] * 2
    assert q["where"].endswith(qws.SITE_AUTH_WHERE % (n - 1, n))


def test_authorized_sites_become_explicit_site_filter():
    # WOSTATUS_NDX1 (siteid, changedate, wonum) is used only with the site in the where.
    q = qws.build_query(BASE, "GERENTE1", ["FABRICA", "MATRIZ"])
    assert q["where"].startswith("changedate >= :1 and changedate < :2 and siteid in (:3, :4)")
    assert q["binds"][2:4] == [("WOSTATUS", "SITEID", "FABRICA"), ("WOSTATUS", "SITEID", "MATRIZ")]
    assert q["filters"] == {}  # not asked by the caller
    n = len(q["binds"])
    assert q["where"].endswith(qws.SITE_AUTH_WHERE % (n - 1, n))  # still applied
    assert q["where"].count(":") == n


def test_requested_siteid_wins_over_authorized_sites():
    q = qws.build_query({**BASE, "siteid": "fabrica"}, "GERENTE1", ["FABRICA", "MATRIZ"])
    assert "siteid in (:3)" in q["where"]
    assert ("WOSTATUS", "SITEID", "MATRIZ") not in q["binds"]
    assert q["filters"] == {"siteid": ["FABRICA"]}
    # An empty siteid list falls back to the authorized sites.
    q = qws.build_query({**BASE, "siteid": " , "}, "GERENTE1", ["FABRICA"])
    assert "siteid in (:3)" in q["where"]


def test_authorized_sites_query():
    where, binds = qws.authorized_sites_query("GERENTE1")
    assert where == qws.SITE_AUTH_WHERE % (1, 2)
    assert binds == [("GROUPUSER", "USERID", "GERENTE1")] * 2


def test_permission_is_fixed_in_code():
    assert (qws.PERMISSION_APP, qws.PERMISSION_OPTION) == ("WOTRACK", "READ")
    assert "authapp" not in qws.PARAM_NAMES
    assert "authsigoption" not in qws.PARAM_NAMES


def test_fields():
    q = query(fields="Memo, wostatusid, memo")
    assert q["fields"] == ["wonum", "siteid", "memo", "wostatusid"]
    assert error_code(**BASE, fields="wonum,description") == "unknown_field"


def test_pagination():
    q = query(page="2", page_size="500")
    assert (q["page"], q["page_size"], q["offset"]) == (2, 500, 500)
    assert error_code(**BASE, page_size=str(qws.MAX_PAGE_SIZE + 1)) == "out_of_range"
    assert error_code(**BASE, page="0") == "out_of_range"


def test_every_parameter_is_read():
    raw, _ = qws.collect_params(qws.PARAM_NAMES, {}, None, None)
    assert set(raw) == set(qws.PARAM_NAMES)
    used = {"date_from", "date_to", "fields", "page", "page_size"}
    used |= {name for name, _, _, _ in qws.LIST_FILTERS} | set(qws.WO_FILTERS)
    assert used == set(qws.PARAM_NAMES)


def test_response_metadata():
    q = query(page_size="50")
    resp = qws.build_response(q, 120, [{"wonum": "1"}])
    assert (resp["total_pages"], resp["has_more"], resp["returned"]) == (3, True, 1)
    assert (resp["date_field"], resp["date_from"], resp["date_to"]) == (
        "changedate",
        "2026-01-01",
        "2026-01-31",
    )
    assert resp["items"] == [{"wonum": "1"}]
    no_dates = qws.build_query({"wonums": "1"}, "GERENTE1")
    assert qws.build_response(no_dates, 0, [])["date_from"] is None
