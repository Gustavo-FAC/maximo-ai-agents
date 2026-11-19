import importlib.util
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).parents[2] / "maximo_scripts" / "querymeterreadings" / "QUERYMETERREADINGS.py"
)
_spec = importlib.util.spec_from_file_location("querymeterreadings", SCRIPT)
qmr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qmr)

BASE = {"date_from": "2026-01-01", "date_to": "2026-01-31"}


def query(**params):
    return qmr.build_query({**BASE, **params}, "GERENTE1")


def error_code(**params):
    with pytest.raises(qmr.ParamError) as exc:
        qmr.build_query(params, "GERENTE1")
    return exc.value.code


# Day, parse_date, parse_list and the rest of the common block: tested through
# test_queryworkorders.py; test_script_common.py checks the block is identical.


def test_defaults_read_measurements():
    q = query()
    assert (q["reading_type"], q["object"]) == ("MEASUREMENT", "MEASUREMENT")
    assert q["fields"] == list(qmr.DEFAULT_FIELDS)
    assert (q["page"], q["page_size"], q["offset"]) == (1, qmr.DEFAULT_PAGE_SIZE, 0)
    assert q["filters"] == {}
    assert q["order_by"].endswith("measuredate, measurementid")


@pytest.mark.parametrize(
    ("raw", "obj", "date"),
    [
        ("measurement", "MEASUREMENT", "measuredate"),
        (" Continuous ", "METERREADING", "readingdate"),
    ],
)
def test_date_range_on_reading_date_inclusive(raw, obj, date):
    q = query(reading_type=raw)
    assert q["object"] == obj
    assert [(o, a, d.isoformat()) for o, a, d in q["binds"][:2]] == [
        (obj, date.upper(), "2026-01-01"),
        (obj, date.upper(), "2026-02-01"),
    ]
    assert q["where"].startswith(f"{date} >= :1 and {date} < :2")
    assert q["where"].count(":") == len(q["binds"])


def test_reading_type_invalid():
    assert error_code(**BASE, reading_type="gauge") == "invalid_reading_type"
    assert error_code(**BASE, reading_type="METERREADING") == "invalid_reading_type"


def test_dates_always_required():
    assert error_code(date_to="2026-01-31") == "required"
    assert error_code(date_from="2026-01-01") == "required"
    assert error_code(assetnum="ATV001") == "required"
    assert error_code(date_from="2026-02-01", date_to="2026-01-01") == "invalid_range"
    assert error_code(date_from="2025-01-01", date_to="2026-01-02") == "range_too_large"
    assert query(date_from="2025-01-01", date_to="2026-01-01")["date_to"] == "2026-01-01"


def test_list_filters_bound_not_inlined():
    q = query(siteid="fabrica", assetnum="atv1,ATV2", metername="temp", pointnum="p1")
    assert q["filters"] == {
        "siteid": ["FABRICA"],
        "assetnum": ["ATV1", "ATV2"],
        "metername": ["TEMP"],
        "pointnum": ["P1"],
    }
    assert "siteid in (:3)" in q["where"]
    assert "assetnum in (:4, :5)" in q["where"]
    assert "metername in (:6)" in q["where"]
    assert "pointnum in (:7)" in q["where"]
    assert "FABRICA" not in q["where"]
    assert ("MEASUREMENT", "POINTNUM", "P1") in q["binds"]
    assert q["where"].count(":") == len(q["binds"])


@pytest.mark.parametrize("name", ["location", "pointnum"])
def test_measurement_only_filters_refused_for_continuous(name):
    assert error_code(**BASE, reading_type="continuous", **{name: "X"}) == "not_supported"
    assert query(reading_type="continuous", **{name: "*"})["filters"] == {}


def test_continuous_filters_use_meterreading():
    q = query(reading_type="continuous", assetnum="A1", inspector="joao")
    assert ("METERREADING", "ASSETNUM", "A1") in q["binds"]
    assert ("METERREADING", "INSPECTOR", "JOAO") in q["binds"]


def test_injection_stays_in_binds():
    payload = "X' OR '1'='1"
    q = query(assetnum=payload, metername=payload)
    assert payload.upper() not in q["where"]
    assert ("MEASUREMENT", "ASSETNUM", payload.upper()) in q["binds"]


def test_list_limits():
    assetnums = ",".join(str(n) for n in range(qmr.MAX_ASSETNUMS))
    assert len(query(assetnum=assetnums)["filters"]["assetnum"]) == qmr.MAX_ASSETNUMS
    assert error_code(**BASE, assetnum=assetnums + ",X") == "too_many_values"
    many = ",".join(f"M{n}" for n in range(qmr.MAX_LIST_VALUES + 1))
    assert error_code(**BASE, metername=many) == "too_many_values"


def test_site_authorization_always_applied():
    q = query(siteid="FABRICA")
    n = len(q["binds"])
    assert q["binds"][-2:] == [("GROUPUSER", "USERID", "GERENTE1")] * 2
    assert q["where"].endswith(qmr.SITE_AUTH_WHERE % (n - 1, n))


def test_authorized_sites_become_explicit_site_filter():
    q = qmr.build_query(BASE, "GERENTE1", ["FABRICA", "MATRIZ"])
    assert q["where"].startswith("measuredate >= :1 and measuredate < :2 and siteid in (:3, :4)")
    assert q["filters"] == {}  # not asked by the caller
    q = qmr.build_query({**BASE, "siteid": "fabrica"}, "GERENTE1", ["FABRICA", "MATRIZ"])
    assert ("MEASUREMENT", "SITEID", "MATRIZ") not in q["binds"]


def test_permission_is_fixed_in_code():
    assert (qmr.PERMISSION_APP, qmr.PERMISSION_OPTION) == ("ASSET", "READ")
    assert "authapp" not in qmr.PARAM_NAMES
    assert "authsigoption" not in qmr.PARAM_NAMES


def test_fields_and_pagination():
    q = query(fields="Reading, delta, reading")
    assert q["fields"] == [
        "assetnum",
        "siteid",
        "metername",
        "readingdate",
        "pointnum",
        "reading",
        "delta",
    ]
    assert error_code(**BASE, fields="measurementvalue") == "unknown_field"
    q = query(page="2", page_size="500")
    assert (q["page"], q["page_size"], q["offset"]) == (2, 500, 500)
    assert error_code(**BASE, page_size=str(qmr.MAX_PAGE_SIZE + 1)) == "out_of_range"


def test_every_reading_type_maps_every_field():
    for source in qmr.READING_TYPES.values():
        assert set(source["attributes"]) == set(qmr.FIELD_TYPES)
        assert set(qmr.KEY_FIELDS) <= set(source["key_fields"])
        for field in source["key_fields"]:
            assert source["attributes"][field] is not None


def test_key_fields_feed_meters_and_points():
    # Found in homologation: fields without pointnum left "points" empty.
    measurement = query(fields="reading")
    assert measurement["fields"] == [
        "assetnum",
        "siteid",
        "metername",
        "readingdate",
        "pointnum",
        "reading",
    ]
    continuous = query(fields="reading", reading_type="continuous")
    assert continuous["fields"] == ["assetnum", "siteid", "metername", "readingdate", "reading"]


def test_plan_read_maps_aliases_and_unavailable():
    attributes = qmr.READING_TYPES["MEASUREMENT"]["attributes"]
    fields = ["assetnum", "readingdate", "reading", "delta", "observation"]
    read, aliases, types, unavailable = qmr.plan_read(
        fields, attributes, lambda name: name != "observation"
    )
    assert read == ["assetnum", "measuredate", "measurementvalue"]
    assert aliases == {"measuredate": "readingdate", "measurementvalue": "reading"}
    assert types == {"assetnum": "str", "measuredate": "date", "measurementvalue": "float"}
    assert unavailable == ["delta", "observation"]  # no attribute / not in this Maximo


def test_rename_fields():
    items = [{"measuredate": "2026-01-02T10:00:00", "measurementvalue": 7.5, "assetnum": "A"}]
    qmr.rename_fields(items, {"measuredate": "readingdate", "measurementvalue": "reading"})
    assert items == [{"readingdate": "2026-01-02T10:00:00", "reading": 7.5, "assetnum": "A"}]


def test_meter_and_point_lookups():
    items = [
        {"metername": "TEMP", "pointnum": "P1", "siteid": "FAB"},
        {"metername": "TEMP", "pointnum": "P2", "siteid": "MAT"},
        {"metername": "VIB", "pointnum": None, "siteid": "FAB"},
    ]
    assert qmr.distinct_values(items, "metername") == ["TEMP", "VIB"]
    meters = qmr.build_meter_query(["TEMP", "VIB"], ["metername", "measureunitid"])
    assert meters["where"] == "metername in (:1, :2)"
    assert meters["binds"] == [("METER", "METERNAME", "TEMP"), ("METER", "METERNAME", "VIB")]
    assert meters["page_size"] == 2

    pairs = qmr.point_pairs(items)
    assert pairs == [("P1", "FAB"), ("P2", "MAT")]
    points = qmr.build_point_query(["P1", "P2"], ["FAB", "MAT"], "GERENTE1", ["pointnum"])
    assert points["where"].startswith("pointnum in (:1, :2) and siteid in (:3, :4)")
    assert points["where"].endswith(qmr.SITE_AUTH_WHERE % (5, 6))
    found = [
        {"pointnum": "P1", "siteid": "FAB"},
        {"pointnum": "P1", "siteid": "MAT"},  # same number, other site: not in the page
        {"pointnum": "P2", "siteid": "MAT"},
    ]
    assert qmr.keep_pairs(found, pairs) == [found[0], found[2]]


def test_zero_limits_mean_no_limit():
    # Found in homologation: lowerwarning 30, loweraction 24, upper limits stored as 0.
    points = [
        {
            "pointnum": "2987",
            "upperwarning": 0,
            "lowerwarning": 30,
            "upperaction": 0.0,
            "loweraction": 24,
        },
        {"pointnum": "P2", "upperwarning": None, "lowerwarning": -5.5},
    ]
    assert qmr.clear_zero_limits(points) == [
        {
            "pointnum": "2987",
            "upperwarning": None,
            "lowerwarning": 30,
            "upperaction": None,
            "loweraction": 24,
        },
        {"pointnum": "P2", "upperwarning": None, "lowerwarning": -5.5},
    ]
    assert set(qmr.POINT_LIMITS) <= set(qmr.POINT_FIELD_TYPES)


def test_every_parameter_is_read():
    raw, _ = qmr.collect_params(qmr.PARAM_NAMES, {}, None, None)
    assert set(raw) == set(qmr.PARAM_NAMES)
    used = {"date_from", "date_to", "reading_type", "fields", "page", "page_size"}
    used |= {name for name, _, _, _ in qmr.LIST_FILTERS}
    assert used == set(qmr.PARAM_NAMES)


def test_response_metadata():
    q = query(page_size="50")
    resp = qmr.build_response(q, 120, [{"assetnum": "A1"}], ["delta"], [{"metername": "T"}], [])
    assert (resp["total_pages"], resp["has_more"], resp["returned"]) == (3, True, 1)
    assert (resp["reading_type"], resp["date_field"]) == ("measurement", "readingdate")
    assert resp["fields_unavailable"] == ["delta"]
    assert resp["meters"] == [{"metername": "T"}]
    assert resp["points"] == []
    continuous = query(reading_type="continuous")
    assert "points" not in qmr.build_response(continuous, 0, [], [], [], [])
