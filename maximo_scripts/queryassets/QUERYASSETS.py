# QUERYASSETS - read-only asset query, published as an MCP tool.
#
# Maximo Manage automation script without launch point, language Jython 2.7.
# Source of truth: maximo_scripts/queryassets/. Never edit directly in Maximo.
#
# Code must run on Jython 2.7 and CPython 3: the pure functions below (parsing,
# validation, where clause) are tested by tests/unit/test_queryassets.py.
# Java/Maximo imports live only inside runtime functions. No Python standard library
# imports: Maximo's Jython does not ship it ("No module named datetime").

# --- BEGIN COMMON (identical in every script; see tests/unit/test_script_common.py) ---

# Values that mean "parameter not informed" (literal variables need a default).
UNSET_VALUES = ("", "*")

# Required permission, checked in code. Not script variables: every variable becomes
# a tool parameter, so the caller could override authapp/authsigoption.
PERMISSION_WHERE = (
    "app = :1 and optionname = :2"
    " and groupname in (select groupname from groupuser where userid = :3)"
)

# Only sites the calling user is authorized for (defense in depth).
SITE_AUTH_WHERE = (
    "(exists (select 1 from groupuser gu, maxgroup mg"
    " where gu.groupname = mg.groupname and gu.userid = :%d and mg.authallsites = 1)"
    " or siteid in (select sa.siteid from siteauth sa, groupuser gu"
    " where sa.groupname = gu.groupname and gu.userid = :%d))"
)

# Implicit variables Maximo may inject; logged by name to learn which exist on the
# MCP path.
IMPLICIT_NAMES = ("request", "requestBody", "userInfo", "service", "httpMethod")

# Parameter "text": words that must all appear in the description.
MAX_TEXT_WORDS = 5
MIN_WORD_LENGTH = 2
MAX_TEXT_LENGTH = 100
TEXT_WHERE = "upper(description) like :%d"


class ParamError(Exception):
    def __init__(self, code, parameter, message):
        Exception.__init__(self, message)
        self.code = code
        self.parameter = parameter
        self.message = message


def to_text(value):
    # "%s" keeps unicode on Jython 2.7; str() fails on non-ASCII (accented values).
    return "%s" % (value,)


def is_unset(value):
    return value is None or to_text(value).strip() in UNSET_VALUES


class Day(object):
    """Calendar date as days since 1970-01-01 (Hinnant's civil calendar algorithms)."""

    def __init__(self, ordinal):
        self.ordinal = ordinal

    @classmethod
    def from_ymd(cls, year, month, day):
        y = year - 1 if month <= 2 else year
        era = y // 400
        yoe = y - era * 400
        doy = (153 * (month - 3 if month > 2 else month + 9) + 2) // 5 + day - 1
        doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
        return cls(era * 146097 + doe - 719468)

    def ymd(self):
        z = self.ordinal + 719468
        era = z // 146097
        doe = z - era * 146097
        yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
        doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
        mp = (5 * doy + 2) // 153
        day = doy - (153 * mp + 2) // 5 + 1
        month = mp + 3 if mp < 10 else mp - 9
        year = yoe + era * 400 + (1 if month <= 2 else 0)
        return (year, month, day)

    def isoformat(self):
        return "%04d-%02d-%02d" % self.ymd()


def parse_iso_day(text):
    """Day from YYYY-MM-DD, or None if text is not a valid calendar date."""
    parts = text.split("-")
    if [len(part) for part in parts] != [4, 2, 2]:
        return None
    if not all(char in "0123456789" for char in "".join(parts)):
        return None
    year, month, day = [int(part) for part in parts]
    if not 1 <= month <= 12:
        return None
    value = Day.from_ymd(year, month, day)
    # Round trip rejects days that do not exist, e.g. 2026-02-30.
    return value if value.ymd() == (year, month, day) else None


def parse_date(name, raw):
    if is_unset(raw):
        raise ParamError("required", name, "%s is required (YYYY-MM-DD)." % name)
    value = parse_iso_day(to_text(raw).strip())
    if value is None:
        raise ParamError("invalid_date", name, "%s must be YYYY-MM-DD." % name)
    return value


def parse_int(name, raw, default, minimum, maximum):
    if is_unset(raw):
        return default
    text = to_text(raw).strip()
    if not text.isdigit():
        raise ParamError("invalid_integer", name, "%s must be an integer." % name)
    value = int(text)
    if value < minimum or value > maximum:
        raise ParamError(
            "out_of_range", name, "%s must be between %d and %d." % (name, minimum, maximum)
        )
    return value


def parse_list(name, raw, kind, max_items):
    if is_unset(raw):
        return []
    values = []
    for item in to_text(raw).split(","):
        item = item.strip()
        if not item:
            continue
        if kind == "int":
            if not item.isdigit():
                raise ParamError("invalid_integer", name, "%s accepts integers only." % name)
            item = int(item)
        else:
            item = item.upper()
        if item not in values:
            values.append(item)
    if len(values) > max_items:
        raise ParamError(
            "too_many_values", name, "%s accepts at most %d values." % (name, max_items)
        )
    return values


def parse_fields(raw, field_types, default_fields, key_fields):
    """Requested fields, validated against field_types; key fields always first."""
    if is_unset(raw):
        return list(default_fields)
    fields = []
    for item in to_text(raw).split(","):
        item = item.strip().lower()
        if not item:
            continue
        if item not in field_types:
            raise ParamError("unknown_field", "fields", "Unknown field: %s." % item)
        if item not in fields:
            fields.append(item)
    for index, key in enumerate(key_fields):
        if key not in fields:
            fields.insert(index, key)
    return fields


def add_in_filter(clauses, binds, obj, attribute, values):
    """Append "attribute in (:n, ...)" with one bind per value."""
    placeholders = []
    for value in values:
        binds.append((obj, attribute.upper(), value))
        placeholders.append(":%d" % len(binds))
    clauses.append("%s in (%s)" % (attribute, ", ".join(placeholders)))


def parse_text(raw):
    """Search words (upper case), each must appear in the description; [] if unset."""
    if is_unset(raw):
        return []
    text = to_text(raw).strip()
    if len(text) > MAX_TEXT_LENGTH:
        raise ParamError(
            "out_of_range", "text", "text accepts at most %d characters." % MAX_TEXT_LENGTH
        )
    if "%" in text or "_" in text:
        # Would act as LIKE wildcards; escape syntax differs between databases.
        raise ParamError("invalid_text", "text", "text must not contain % or _.")
    words = []
    for word in text.upper().split():
        if len(word) < MIN_WORD_LENGTH:
            raise ParamError(
                "invalid_text",
                "text",
                "Each word in text needs at least %d characters." % MIN_WORD_LENGTH,
            )
        if word not in words:
            words.append(word)
    if len(words) > MAX_TEXT_WORDS:
        raise ParamError(
            "too_many_values", "text", "text accepts at most %d words." % MAX_TEXT_WORDS
        )
    return words


def add_text_filter(clauses, binds, obj, words):
    """Append one "upper(description) like :n" per word, wildcards in the bind."""
    for word in words:
        binds.append((obj, "DESCRIPTION", "%" + word + "%"))
        clauses.append(TEXT_WHERE % len(binds))


def add_site_auth(clauses, binds, userid):
    binds.append(("GROUPUSER", "USERID", userid))
    binds.append(("GROUPUSER", "USERID", userid))
    clauses.append(SITE_AUTH_WHERE % (len(binds) - 1, len(binds)))


def permission_binds(app, option, userid):
    return [
        ("APPLICATIONAUTH", "APP", app),
        ("APPLICATIONAUTH", "OPTIONNAME", option),
        ("GROUPUSER", "USERID", userid),
    ]


def paging(page, page_size, total, returned):
    total_pages = (total + page_size - 1) // page_size
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "returned": returned,
        "has_more": page < total_pages,
    }


def error_response(code, parameter, message):
    return {"error": {"code": code, "parameter": parameter, "message": message}}


def collect_params(param_names, variables, body, query_param):
    """Read each parameter from literal variable, JSON body or query string.

    How the MCP Server delivers arguments is not confirmed yet, so the first source
    with a value wins. Returns (raw, sources); sources holds names, never values.
    """
    raw = {}
    sources = {}
    for name in param_names:
        value = variables.get(name)
        source = "variable"
        if is_unset(value) and body:
            value = body.get(name)
            source = "body"
        if is_unset(value) and query_param is not None:
            value = query_param(name)
            source = "query"
        raw[name] = value
        if not is_unset(value):
            sources[name] = source
    return raw, sources


# Maximo runtime (Jython only) ------------------------------------------------


def to_json(value):
    from com.ibm.json.java import JSONArray, JSONObject

    if isinstance(value, dict):
        obj = JSONObject()
        for key in value:
            obj.put(key, to_json(value[key]))
        return obj
    if isinstance(value, list):
        arr = JSONArray()
        for item in value:
            arr.add(to_json(item))
        return arr
    return value


def read_body(body):
    """Parse requestBody (String or byte[]) into a dict; None if absent or not JSON."""
    if body is None:
        return None
    try:
        from com.ibm.json.java import JSONObject

        if not hasattr(body, "strip"):
            from java.lang import String

            body = String(body, "UTF-8")
        if not body.strip().startswith("{"):
            return None
        obj = JSONObject.parse(body)
        return dict((key, obj.get(key)) for key in obj.keySet())
    except Exception:
        return None


def read_item(mbo, fields, field_types, date_format):
    item = {}
    for field in fields:
        kind = field_types[field]
        if mbo.isNull(field):
            item[field] = None
        elif kind == "date":
            item[field] = date_format.format(mbo.getDate(field))
        elif kind == "int":
            item[field] = mbo.getInt(field)
        elif kind == "float":
            item[field] = mbo.getDouble(field)
        elif kind == "bool":
            item[field] = mbo.getBoolean(field)
        else:
            item[field] = mbo.getString(field)
    return item


def format_where(user_info, where, binds):
    """Where clause with bind values set by SqlFormat (never concatenated)."""
    from java.text import SimpleDateFormat
    from psdi.mbo import SqlFormat

    # UserInfo gives SqlFormat the locale/timezone setObject needs.
    sqf = SqlFormat(user_info, where)
    day_format = SimpleDateFormat("yyyy-MM-dd")
    for index, (obj, attribute, value) in enumerate(binds):
        if isinstance(value, Day):
            sqf.setTimestamp(index + 1, day_format.parse(value.isoformat()))
        else:
            sqf.setObject(index + 1, obj, attribute, to_text(value))
    return sqf.format()


def has_permission(user_info, app, option):
    from psdi.server import MXServer

    binds = permission_binds(app, option, user_info.getUserName())
    auth_set = MXServer.getMXServer().getMboSet("APPLICATIONAUTH", user_info)
    try:
        auth_set.setWhere(format_where(user_info, PERMISSION_WHERE, binds))
        return not auth_set.isEmpty()
    finally:
        auth_set.cleanup()


def query_page(user_info, object_name, query, field_types):
    """Run query (where, binds, order_by, fields, offset, page_size): (total, items)."""
    from java.text import SimpleDateFormat
    from psdi.mbo import MboConstants
    from psdi.server import MXServer

    mboset = MXServer.getMXServer().getMboSet(object_name, user_info)
    try:
        mboset.setFlag(MboConstants.DISCARDABLE, True)
        mboset.setWhere(format_where(user_info, query["where"], query["binds"]))
        mboset.setOrderBy(query["order_by"])
        total = mboset.count()  # one SQL count; never call count() again
        items = []
        output_format = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss")
        index = query["offset"]
        end = min(total, index + query["page_size"])
        while index < end:
            mbo = mboset.getMbo(index)
            if mbo is None:
                break
            items.append(read_item(mbo, query["fields"], field_types, output_format))
            index += 1
        return total, items
    finally:
        mboset.cleanup()


def main(scope, throwable, script_name, param_names, run):
    """Run the tool against the script scope and return the response dict.

    Everything lives in locals: after the script ends, Maximo calls toString on
    every top-level binding, and a binding holding globals() recurses into
    itself (StackOverflowError -> BMXAA1649E).
    """
    service = scope.get("service")
    req = scope.get("request")
    try:
        raw, sources = collect_params(
            param_names,
            scope,
            read_body(scope.get("requestBody")),
            req.getQueryParam if req is not None else None,
        )
        # No isLoggingEnabled() on ScriptService in MAS 9.2; log_debug filters by level.
        if service is not None:
            service.log_debug(
                "%s implicit vars: %s; param sources: %s"
                % (script_name, [n for n in IMPLICIT_NAMES if scope.get(n) is not None], sources)
            )
        user_info = req.getUserInfo() if req is not None else scope.get("userInfo")
        if user_info is None:
            # Fail closed: never query without the caller's identity.
            return error_response("no_user", None, "Caller identity not available.")
        return run(user_info, raw)
    except ParamError as e:
        return error_response(e.code, e.parameter, e.message)
    except (Exception, throwable) as e:
        # Throwable: Java exceptions (e.g. NullPointerException) may bypass Exception.
        if service is not None:
            service.log_error("%s failed: %s" % (script_name, e))
        return error_response("internal_error", None, "Query failed. See Maximo log.")


# --- END COMMON ---

SCRIPT_NAME = "QUERYASSETS"
OBJECT_NAME = "ASSET"
PERMISSION_APP = "ASSET"
PERMISSION_OPTION = "READ"

MAX_ASSETNUMS = 50
MAX_LIST_VALUES = 20
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500
# Specifications make each item large: smaller pages.
MAX_SPECS_PAGE_SIZE = 50
# Specifications read for one page of assets; above it, "specs_truncated" is true.
MAX_SPECS = 3000

# Attribute -> output type. Only these attributes can be selected. Standard ASSET
# attributes only: client-specific ones (e.g. Itambe's cci_*) break other clients.
FIELD_TYPES = {
    "assetnum": "str",
    "siteid": "str",
    "description": "str",
    "status": "str",
    "statusdate": "date",
    "location": "str",
    "parent": "str",
    "children": "bool",
    "assettype": "str",
    "priority": "int",
    "isrunning": "bool",
    "failurecode": "str",
    "classstructureid": "str",
    "itemnum": "str",
    "manufacturer": "str",
    "vendor": "str",
    "serialnum": "str",
    "assettag": "str",
    "installdate": "date",
    "purchaseprice": "float",
    "replacecost": "float",
    "totalcost": "float",
    "ytdcost": "float",
    "totdowntime": "float",
    "changedate": "date",
    "assetuid": "int",
}
DEFAULT_FIELDS = (
    "assetnum",
    "siteid",
    "description",
    "status",
    "location",
    "parent",
    "assettype",
    "priority",
    "isrunning",
)
KEY_FIELDS = ("assetnum", "siteid")

# Parameter -> (ASSET attribute, value type, max values).
LIST_FILTERS = (
    ("siteid", "siteid", "str", MAX_LIST_VALUES),
    ("assetnums", "assetnum", "str", MAX_ASSETNUMS),
    ("status", "status", "str", MAX_LIST_VALUES),
    ("location", "location", "str", MAX_LIST_VALUES),
    ("parent", "parent", "str", MAX_LIST_VALUES),
    ("assettype", "assettype", "str", MAX_LIST_VALUES),
    ("priority", "priority", "int", MAX_LIST_VALUES),
    ("failurecode", "failurecode", "str", MAX_LIST_VALUES),
)

PARAM_NAMES = (
    "siteid",
    "assetnums",
    "ancestor",
    "status",
    "location",
    "parent",
    "assettype",
    "priority",
    "failurecode",
    "text",
    "spec_attribute",
    "spec_min",
    "spec_max",
    "spec_unit",
    "include_specs",
    "fields",
    "page",
    "page_size",
)

FLAG_TRUE = ("Y", "YES", "TRUE", "1")
FLAG_FALSE = ("N", "NO", "FALSE", "0")

# Specifications (technical data sheet, ASSETSPEC) returned with include_specs.
SPEC_FIELD_TYPES = {
    "assetattrid": "str",
    "section": "str",
    "alnvalue": "str",
    "numvalue": "float",
    "tablevalue": "str",
    "datevalue": "date",
    "measureunitid": "str",
    "orgid": "str",
}
SPEC_FIELDS = tuple(SPEC_FIELD_TYPES)
# Value columns by preference; an attribute fills only the one of its data type.
SPEC_VALUE_FIELDS = ("numvalue", "alnvalue", "tablevalue", "datevalue")

# Ad hoc relationships (no dependency on the client's relationship names), bound by
# Maximo from the owner, no caller value. Children are read through their owner: a
# child set without owner fails (JOBTASK, homologation 2026-11-03).
SPEC_RELATION = "$QASSETSPECS"
SPEC_RELATION_WHERE = "assetnum = :assetnum and siteid = :siteid"
SPEC_ORDER_BY = "displaysequence, assetattrid"
ATTR_RELATION = "$QASSETATTR"
ATTR_RELATION_WHERE = "assetattrid = :assetattrid and (orgid = :orgid or orgid is null)"

# Assets anywhere below the given assets in the hierarchy (ASSETANCESTOR).
# ASSETANCESTOR also holds a row of each asset with itself; excluded so that
# 'total' counts descendants only (seen in homologation, 2026-10-29).
ANCESTOR_WHERE = (
    "assetnum in (select aa.assetnum from assetancestor aa"
    " where aa.siteid = asset.siteid and aa.assetnum <> aa.ancestor"
    " and aa.ancestor in (%s))"
)

# Specification filter (ASSETSPEC numeric value). Units of one quantity are compared
# after conversion to its base unit (power: kW; voltage: V): Itambe registers motor
# power in CV or kW depending on the class (consultant, 2026-11-18). Factor = base
# units per unit. A unit outside this table is compared only with itself.
UNIT_FACTORS = {
    "power": (
        ("KW", "1"),
        ("W", "0.001"),
        ("MW", "1000"),
        ("CV", "0.73549875"),
        ("HP", "0.745699872"),
    ),
    "voltage": (("V", "1"), ("KV", "1000")),
}
MAX_SPEC_ATTRIBUTES = 5
MAX_SPEC_NUMBER = 1000000000.0
# Bounds are bound as integers in thousandths (spec value * factor * 1000): no decimal
# separator reaches SqlFormat, whose number parsing follows the user's locale.
SPEC_SCALE = 1000
SPEC_WHERE = (
    "exists (select 1 from assetspec s where s.assetnum = asset.assetnum"
    " and s.siteid = asset.siteid and s.assetattrid in (%s)%s)"
)


def unit_factors(unit):
    """((unit, factor), ...) of the unit's quantity, or None outside UNIT_FACTORS."""
    for units in UNIT_FACTORS.values():
        if unit in dict(units):
            return units
    return None


def parse_number(name, raw):
    """Decimal number ("50", "36.8" or "36,8"), or None when unset."""
    if is_unset(raw):
        return None
    text = to_text(raw).strip()
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        value = float(text)
    except ValueError:
        raise ParamError("invalid_number", name, "%s must be a number." % name)
    if value != value or abs(value) > MAX_SPEC_NUMBER:
        raise ParamError("invalid_number", name, "%s must be a number." % name)
    return value


def build_spec_filter(raw, clauses, binds, filters):
    """Assets with a specification of these attributes, optionally within bounds.

    Without bounds: assets that have the attribute. With spec_min/spec_max: numeric
    value within them (inclusive). With spec_unit, bounds are in that unit and every
    unit of the same quantity is converted (50 CV = 36.77 kW); specs in other units or
    without unit are left out. Without spec_unit, values are compared as registered.
    """
    attributes = parse_list("spec_attribute", raw.get("spec_attribute"), "str", MAX_SPEC_ATTRIBUTES)
    low = parse_number("spec_min", raw.get("spec_min"))
    high = parse_number("spec_max", raw.get("spec_max"))
    unit_raw = raw.get("spec_unit")
    unit = None if is_unset(unit_raw) else to_text(unit_raw).strip().upper()
    if not attributes:
        for name, value in (("spec_min", low), ("spec_max", high), ("spec_unit", unit)):
            if value is not None:
                raise ParamError(
                    "requires_spec_attribute", name, "%s requires spec_attribute." % name
                )
        return
    if low is not None and high is not None and high < low:
        raise ParamError("invalid_range", "spec_max", "spec_max must be >= spec_min.")
    if unit is not None and low is None and high is None:
        raise ParamError("required", "spec_min", "spec_unit requires spec_min or spec_max.")
    if unit is not None and not 0 < len(unit) <= 20:
        raise ParamError("invalid_unit", "spec_unit", "spec_unit must be a unit code.")

    placeholders = []
    for value in attributes:
        binds.append(("ASSETSPEC", "ASSETATTRID", value))
        placeholders.append(":%d" % len(binds))
    filters["spec_attribute"] = attributes

    extra = ""
    if low is not None or high is not None:
        factor = 1.0
        measure = "s.numvalue * %d" % SPEC_SCALE
        units = unit_factors(unit) if unit is not None else None
        if units is not None:
            # Unit codes and factors in the SQL text come only from UNIT_FACTORS.
            factor = float(dict(units)[unit])
            cases = " ".join("when '%s' then %s" % (code, f) for code, f in units)
            measure = "s.numvalue * (case upper(s.measureunitid) %s end) * %d" % (
                cases,
                SPEC_SCALE,
            )
            codes = [code for code, _ in units]
            extra += " and upper(s.measureunitid) in (%s)" % ", ".join(
                "'%s'" % code for code in codes
            )
            filters["spec_units_compared"] = codes
        elif unit is not None:
            binds.append(("ASSETSPEC", "MEASUREUNITID", unit))
            extra += " and upper(s.measureunitid) = :%d" % len(binds)
            filters["spec_units_compared"] = [unit]
        if unit is not None:
            filters["spec_unit"] = unit
        extra += " and s.numvalue is not null"
        for name, value, operator in (("spec_min", low, ">="), ("spec_max", high, "<=")):
            if value is None:
                continue
            filters[name] = value
            # Integer thousandths of the base unit: no decimal separator to parse.
            binds.append(("ASSETSPEC", "NUMVALUE", "%d" % int(round(value * factor * SPEC_SCALE))))
            extra += " and %s %s :%d" % (measure, operator, len(binds))
    clauses.append(SPEC_WHERE % (", ".join(placeholders), extra))


def parse_flag(name, raw):
    if is_unset(raw):
        return False
    text = to_text(raw).strip().upper()
    if text in FLAG_TRUE:
        return True
    if text in FLAG_FALSE:
        return False
    raise ParamError("invalid_flag", name, "%s must be Y or N." % name)


def build_query(raw, userid):
    """Validate raw parameters and build the where clause with bind values.

    Returns a dict. "binds" is a list of (object, attribute, value) in placeholder
    order; values never go into the where text. No filter is required: assets are
    master data and every response is capped by page_size, with "total" exact.
    """
    include_specs = parse_flag("include_specs", raw.get("include_specs"))
    max_page_size = MAX_SPECS_PAGE_SIZE if include_specs else MAX_PAGE_SIZE
    page = parse_int("page", raw.get("page"), 1, 1, 100000)
    page_size = parse_int(
        "page_size", raw.get("page_size"), min(DEFAULT_PAGE_SIZE, max_page_size), 1, max_page_size
    )
    fields = parse_fields(raw.get("fields"), FIELD_TYPES, DEFAULT_FIELDS, KEY_FIELDS)
    if include_specs and "assetuid" not in fields:
        fields.append("assetuid")  # reopens each asset to read its specifications

    binds = []
    clauses = []
    filters = {}
    for name, attribute, kind, max_items in LIST_FILTERS:
        values = parse_list(name, raw.get(name), kind, max_items)
        if values:
            filters[name] = values
            add_in_filter(clauses, binds, OBJECT_NAME, attribute, values)

    ancestors = parse_list("ancestor", raw.get("ancestor"), "str", MAX_LIST_VALUES)
    if ancestors:
        filters["ancestor"] = ancestors
        placeholders = []
        for value in ancestors:
            binds.append(("ASSETANCESTOR", "ANCESTOR", value))
            placeholders.append(":%d" % len(binds))
        clauses.append(ANCESTOR_WHERE % ", ".join(placeholders))

    words = parse_text(raw.get("text"))
    if words:
        filters["text"] = words
        add_text_filter(clauses, binds, OBJECT_NAME, words)

    build_spec_filter(raw, clauses, binds, filters)

    add_site_auth(clauses, binds, userid)

    return {
        "where": " and ".join(clauses),
        "binds": binds,
        "order_by": "siteid, assetnum",
        "filters": filters,
        "fields": fields,
        "include_specs": include_specs,
        "page": page,
        "page_size": page_size,
        "offset": (page - 1) * page_size,
    }


def build_asset_query(assetuids):
    """Assets of one page, reopened to read their specifications (already authorized)."""
    binds = []
    placeholders = []
    for value in assetuids:
        binds.append((OBJECT_NAME, "ASSETUID", value))
        placeholders.append(":%d" % len(binds))
    return {"where": "assetuid in (%s)" % ", ".join(placeholders), "binds": binds}


def spec_item(row, description):
    """One specification: attribute, its description, section, value and unit."""
    value = None
    for field in SPEC_VALUE_FIELDS:
        if row.get(field) is not None:
            value = row[field]
            break
    return {
        "attribute": row.get("assetattrid"),
        "description": description,
        "section": row.get("section"),
        "value": value,
        "unit": row.get("measureunitid"),
    }


def attach_specs(items, by_asset):
    """Put each specification list under its asset ("specs", [] if none)."""
    for item in items:
        item["specs"] = by_asset.get(item["assetuid"], [])


def build_response(query, total, items, specs_truncated=False):
    response = paging(query["page"], query["page_size"], total, len(items))
    response["filters"] = query["filters"]
    if query["include_specs"]:
        response["specs_truncated"] = specs_truncated
    response["items"] = items
    return response


def attribute_description(spec, cache):
    """Description of the spec's attribute (ASSETATTRIBUTE), cached by attribute/org."""
    key = (spec.getString("assetattrid"), spec.getString("orgid"))
    if key not in cache:
        attrs = spec.getMboSet(ATTR_RELATION, "ASSETATTRIBUTE", ATTR_RELATION_WHERE)
        attr = attrs.getMbo(0)
        cache[key] = attr.getString("description") if attr is not None else None
    return cache[key]


def read_specs(user_info, assetuids):
    """Specifications by assetuid, at most MAX_SPECS in all: (by_asset, truncated)."""
    from java.text import SimpleDateFormat
    from psdi.mbo import MboConstants
    from psdi.server import MXServer

    query = build_asset_query(assetuids)
    assets = MXServer.getMXServer().getMboSet(OBJECT_NAME, user_info)
    try:
        assets.setFlag(MboConstants.DISCARDABLE, True)
        assets.setWhere(format_where(user_info, query["where"], query["binds"]))
        output_format = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss")
        by_asset = {}
        descriptions = {}
        read = 0
        index = 0
        asset = assets.getMbo(index)
        while asset is not None:
            specs = asset.getMboSet(SPEC_RELATION, "ASSETSPEC", SPEC_RELATION_WHERE)
            specs.setOrderBy(SPEC_ORDER_BY)
            found = []
            spec_index = 0
            spec = specs.getMbo(spec_index)
            while spec is not None:
                if read >= MAX_SPECS:
                    return by_asset, True
                row = read_item(spec, SPEC_FIELDS, SPEC_FIELD_TYPES, output_format)
                found.append(spec_item(row, attribute_description(spec, descriptions)))
                read += 1
                spec_index += 1
                spec = specs.getMbo(spec_index)
            by_asset[asset.getInt("assetuid")] = found
            index += 1
            asset = assets.getMbo(index)
        return by_asset, False
    finally:
        assets.cleanup()


def run(user_info, raw):
    if not has_permission(user_info, PERMISSION_APP, PERMISSION_OPTION):
        return error_response(
            "not_authorized",
            None,
            "User needs %s access to %s." % (PERMISSION_OPTION, PERMISSION_APP),
        )
    query = build_query(raw, user_info.getUserName())
    total, items = query_page(user_info, OBJECT_NAME, query, FIELD_TYPES)
    truncated = False
    if query["include_specs"] and items:
        by_asset, truncated = read_specs(user_info, [item["assetuid"] for item in items])
        attach_specs(items, by_asset)
    return build_response(query, total, items, truncated)


try:
    from java.lang import System  # noqa: F401  (resolves only under Jython)

    _IN_MAXIMO = True
except ImportError:  # CPython: module imported by tests
    _IN_MAXIMO = False


if _IN_MAXIMO:
    from com.ibm.tivoli.maximo.oslc import OslcUtils
    from java.lang import Throwable

    # No top-level variable may reference globals() (see main).
    responseBody = OslcUtils.jsonToBytes(
        to_json(main(globals(), Throwable, SCRIPT_NAME, PARAM_NAMES, run))
    )
