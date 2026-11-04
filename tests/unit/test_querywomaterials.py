import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "maximo_scripts" / "querywomaterials" / "QUERYWOMATERIALS.py"
_spec = importlib.util.spec_from_file_location("querywomaterials", SCRIPT)
qwm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qwm)

BASE = {"date_from": "2026-01-01", "date_to": "2026-01-31"}


def query(**params):
    return qwm.build_query({**BASE, **params}, "GERENTE1")


def error_code(**params):
    with pytest.raises(qwm.ParamError) as exc:
        qwm.build_query(params, "GERENTE1")
    return exc.value.code


def wo_scope(conditions):
    return qwm.WO_WHERE % conditions


# Day, parse_date, parse_list and the rest of the common block: tested through
# test_queryworkorders.py; test_script_common.py checks the block is identical.


def test_defaults():
    q = query()
    assert q["page"] == 1
    assert q["page_size"] == qwm.DEFAULT_PAGE_SIZE
    assert q["offset"] == 0
    assert q["fields"] == list(qwm.DEFAULT_FIELDS)
    assert q["filters"] == {}
    assert q["include_balance"] is False
    assert q["date_field"] == "reportdate"
    assert q["order_by"] == "wonum, siteid, wpitemid"


def test_date_range_applies_to_top_work_order():
    q = query(date_field="SchedStart")
    assert q["date_field"] == "schedstart"
    assert [(obj, attr, day.isoformat()) for obj, attr, day in q["binds"][:2]] == [
        ("WORKORDER", "SCHEDSTART", "2026-01-01"),
        ("WORKORDER", "SCHEDSTART", "2026-02-01"),
    ]
    assert q["where"].startswith(wo_scope(" and w.schedstart >= :1 and w.schedstart < :2"))
    assert q["where"].count(":") == len(q["binds"])


def test_work_order_scope_goes_through_wogroup():
    # Lines planned on a task belong to the top work order of its group.
    scope = wo_scope("")
    assert "t.wonum = wpmaterial.wonum and t.siteid = wpmaterial.siteid" in scope
    assert "w.wonum = t.wogroup and w.siteid = t.siteid" in scope
    assert "w.istask = 0" in scope
    assert "'WORKORDER', 'ACTIVITY'" in scope


def test_invalid_date_field():
    assert error_code(**BASE, date_field="changedate") == "invalid_date_field"
    assert error_code(**BASE, date_field="requiredate") == "invalid_date_field"


def test_dates_required():
    assert error_code(date_to="2026-01-31") == "required"
    assert error_code(date_from="2026-01-01") == "required"
    assert error_code(itemnums="10001") == "required"
    assert error_code(assetnum="MCA5853") == "required"


def test_wonums_without_dates_match_top_work_order():
    q = qwm.build_query({"wonums": "1564759, 1564757", "date_to": "*"}, "GERENTE1")
    assert q["date_from"] is None and q["date_to"] is None
    assert q["filters"] == {"wonums": ["1564759", "1564757"]}
    assert q["binds"][:2] == [
        ("WORKORDER", "WONUM", "1564759"),
        ("WORKORDER", "WONUM", "1564757"),
    ]
    assert q["where"].startswith(wo_scope(" and w.wonum in (:1, :2)"))
    assert q["where"].count(":") == len(q["binds"])


def test_wonums_with_dates_still_validate():
    assert query(wonums="1564759")["date_from"] == "2026-01-01"
    assert error_code(wonums="1564759", date_from="2026-01-01") == "required"
    assert error_code(wonums=" , ") == "required"
    assert error_code(wonums="1", date_from="2024-01-01", date_to="2026-01-31") == (
        "range_too_large"
    )


def test_range_order_limit_and_format():
    assert error_code(date_from="2026-02-01", date_to="2026-01-01") == "invalid_range"
    assert error_code(date_from="2025-01-01", date_to="2026-01-02") == "range_too_large"
    assert query(date_from="2025-01-01", date_to="2026-01-01")["date_to"] == "2026-01-01"
    assert error_code(date_from="2026-02-30", date_to="2026-03-01") == "invalid_date"


def test_material_filters_bound_not_inlined():
    q = query(siteid="fabrica", itemnums="10001,10002,10001", storeloc="alm01")
    assert q["filters"] == {
        "siteid": ["FABRICA"],
        "itemnums": ["10001", "10002"],
        "storeloc": ["ALM01"],
    }
    assert q["where"].startswith("siteid in (:1) and itemnum in (:2, :3) and location in (:4)")
    assert q["binds"][:4] == [
        ("WPMATERIAL", "SITEID", "FABRICA"),
        ("WPMATERIAL", "ITEMNUM", "10001"),
        ("WPMATERIAL", "ITEMNUM", "10002"),
        ("WPMATERIAL", "LOCATION", "ALM01"),
    ]
    assert "FABRICA" not in q["where"]


def test_work_order_filters_inside_subquery():
    q = query(status="APPR,WMATL", assetnum="MCA5853", location="L3T05M1", worktype="CO")
    assert q["filters"] == {
        "status": ["APPR", "WMATL"],
        "assetnum": ["MCA5853"],
        "location": ["L3T05M1"],
        "worktype": ["CO"],
    }
    assert (
        " and w.status in (:3, :4) and w.assetnum in (:5) and w.location in (:6)"
        " and w.worktype in (:7))"
    ) in q["where"]
    assert q["binds"][2:7] == [
        ("WORKORDER", "STATUS", "APPR"),
        ("WORKORDER", "STATUS", "WMATL"),
        ("WORKORDER", "ASSETNUM", "MCA5853"),
        ("WORKORDER", "LOCATION", "L3T05M1"),
        ("WORKORDER", "WORKTYPE", "CO"),
    ]
    assert q["where"].count(":") == len(q["binds"])


def test_location_is_work_order_storeloc_is_storeroom():
    q = query(location="L3T05M1", storeloc="ALM01")
    assert ("WORKORDER", "LOCATION", "L3T05M1") in q["binds"]
    assert ("WPMATERIAL", "LOCATION", "ALM01") in q["binds"]


def test_bind_numbers_follow_clause_order():
    q = query(siteid="S1", itemnums="I1", wonums="1", status="APPR", persongroup="MEC")
    numbers = [int(part.split()[0].strip("(),")) for part in q["where"].split(":")[1:]]
    assert numbers == list(range(1, len(q["binds"]) + 1))


def test_injection_stays_in_binds():
    payload = "X' OR '1'='1"
    q = query(assetnum=payload, itemnums=payload)
    assert payload.upper() not in q["where"]
    assert ("WORKORDER", "ASSETNUM", payload.upper()) in q["binds"]
    assert ("WPMATERIAL", "ITEMNUM", payload.upper()) in q["binds"]


def test_list_limits():
    wonums = ",".join(str(n) for n in range(qwm.MAX_WONUMS))
    assert len(query(wonums=wonums)["filters"]["wonums"]) == qwm.MAX_WONUMS
    assert error_code(**BASE, wonums=wonums + ",X") == "too_many_values"
    items = ",".join(str(n) for n in range(qwm.MAX_ITEMNUMS + 1))
    assert error_code(**BASE, itemnums=items) == "too_many_values"
    many = ",".join(f"L{n}" for n in range(qwm.MAX_LIST_VALUES + 1))
    assert error_code(**BASE, storeloc=many) == "too_many_values"
    assert error_code(**BASE, status=many) == "too_many_values"


def test_site_authorization_always_applied():
    q = query(siteid="FABRICA", assetnum="A1")
    n = len(q["binds"])
    assert q["binds"][-2:] == [("GROUPUSER", "USERID", "GERENTE1")] * 2
    assert q["where"].endswith(qwm.SITE_AUTH_WHERE % (n - 1, n))


def test_authorized_sites_become_explicit_site_filter():
    q = qwm.build_query(BASE, "GERENTE1", ["FABRICA", "MATRIZ"])
    assert q["where"].startswith("siteid in (:1, :2) and exists")
    assert q["binds"][:2] == [
        ("WPMATERIAL", "SITEID", "FABRICA"),
        ("WPMATERIAL", "SITEID", "MATRIZ"),
    ]
    assert q["filters"] == {}
    n = len(q["binds"])
    assert q["where"].endswith(qwm.SITE_AUTH_WHERE % (n - 1, n))
    assert q["where"].count(":") == n


def test_requested_siteid_wins_over_authorized_sites():
    q = qwm.build_query({**BASE, "siteid": "fabrica"}, "GERENTE1", ["FABRICA", "MATRIZ"])
    assert q["where"].startswith("siteid in (:1) and")
    assert ("WPMATERIAL", "SITEID", "MATRIZ") not in q["binds"]


def test_permissions_are_fixed_in_code():
    assert (qwm.PERMISSION_APP, qwm.PERMISSION_OPTION) == ("WOTRACK", "READ")
    assert (qwm.BALANCE_APP, qwm.BALANCE_OPTION) == ("INVENTOR", "READ")
    assert "authapp" not in qwm.PARAM_NAMES


def test_fields():
    q = query(fields="Vendor, wpitemid, vendor")
    assert q["fields"] == ["wonum", "siteid", "vendor", "wpitemid"]
    assert error_code(**BASE, fields="wonum,sanum") == "unknown_field"  # client field


def test_pagination():
    q = query(page="2", page_size="500")
    assert (q["page"], q["page_size"], q["offset"]) == (2, 500, 500)
    assert error_code(**BASE, page_size=str(qwm.MAX_PAGE_SIZE + 1)) == "out_of_range"
    assert error_code(**BASE, page="0") == "out_of_range"


def test_include_balance_limits_page_and_adds_key_fields():
    q = query(include_balance="y", fields="itemqty")
    assert q["include_balance"] is True
    assert q["page_size"] == qwm.MAX_BALANCE_PAGE_SIZE
    assert q["fields"] == ["wonum", "siteid", "itemqty", "itemnum", "location", "storelocsite"]
    assert error_code(**BASE, include_balance="Y", page_size="51") == "out_of_range"
    assert error_code(**BASE, include_balance="maybe") == "invalid_flag"
    assert query(include_balance="N")["include_balance"] is False


def line(itemnum, storeroom, site="S1", storesite=None):
    return {
        "wonum": "1",
        "siteid": site,
        "itemnum": itemnum,
        "location": storeroom,
        "storelocsite": storesite,
    }


def bin_row(itemnum, storeroom, site, binnum, curbal):
    return {
        "itemnum": itemnum,
        "location": storeroom,
        "siteid": site,
        "binnum": binnum,
        "lotnum": None,
        "conditioncode": None,
        "curbal": curbal,
    }


def test_balance_keys_skip_lines_without_storeroom_and_repeat():
    items = [
        line("I1", "ALM01"),
        line("I1", "ALM01"),
        line("I2", None),
        line("I3", "ALM02", "S1", "S2"),
    ]
    assert qwm.balance_keys(items) == [("I1", "ALM01", "S1"), ("I3", "ALM02", "S2")]


def test_balance_query_binds_each_key_and_authorizes_sites():
    q = qwm.build_balance_query([("I1", "ALM01", "S1"), ("I2", "ALM01", "S1")], "GERENTE1")
    assert q["where"].startswith(
        "((itemnum = :1 and location = :2 and siteid = :3)"
        " or (itemnum = :4 and location = :5 and siteid = :6)) and "
    )
    assert q["binds"][:3] == [
        ("INVBALANCES", "ITEMNUM", "I1"),
        ("INVBALANCES", "LOCATION", "ALM01"),
        ("INVBALANCES", "SITEID", "S1"),
    ]
    assert q["where"].endswith(qwm.SITE_AUTH_WHERE % (7, 8))
    assert q["where"].count(":") == len(q["binds"])
    assert (q["offset"], q["page_size"]) == (0, qwm.MAX_BALANCES)


def test_group_and_attach_balances():
    rows = [
        bin_row("I1", "ALM01", "S1", "A1", 2.0),
        bin_row("I1", "ALM01", "S1", "A2", 3.5),
        bin_row("I3", "ALM02", "S2", None, None),
    ]
    by_key = qwm.group_balances(rows)
    assert by_key[("I1", "ALM01", "S1")]["total"] == 5.5
    assert [b["binnum"] for b in by_key[("I1", "ALM01", "S1")]["bins"]] == ["A1", "A2"]
    assert set(by_key[("I1", "ALM01", "S1")]["bins"][0]) == set(qwm.BIN_FIELDS)
    assert by_key[("I3", "ALM02", "S2")]["total"] == 0.0

    items = [line("I1", "ALM01"), line("I2", None), line("I9", "ALM01")]
    qwm.attach_balances(items, by_key)
    assert items[0]["balance"]["total"] == 5.5
    assert items[1]["balance"] is None  # no storeroom: direct issue or non-stock
    assert items[2]["balance"] == {"total": 0.0, "bins": []}  # not stocked there


def test_every_parameter_is_read():
    raw, _ = qwm.collect_params(qwm.PARAM_NAMES, {}, None, None)
    assert set(raw) == set(qwm.PARAM_NAMES)
    used = {"date_from", "date_to", "date_field", "wonums", "include_balance", "fields"}
    used |= {"page", "page_size"}
    used |= {name for name, _, _, _ in qwm.LIST_FILTERS} | set(qwm.WO_FILTERS)
    assert used == set(qwm.PARAM_NAMES)


def test_response_metadata():
    q = query(page_size="50")
    resp = qwm.build_response(q, 120, [{"wonum": "1"}])
    assert (resp["total_pages"], resp["has_more"], resp["returned"]) == (3, True, 1)
    assert (resp["date_field"], resp["date_from"], resp["date_to"]) == (
        "reportdate",
        "2026-01-01",
        "2026-01-31",
    )
    assert "balances_truncated" not in resp
    with_balance = query(include_balance="Y")
    assert qwm.build_response(with_balance, 0, [], True)["balances_truncated"] is True
