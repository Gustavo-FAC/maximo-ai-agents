# QUERYWORKORDERS - read-only work order query, published as an MCP tool.
#
# Maximo Manage automation script without launch point, language Jython 2.7.
# Source of truth: maximo_scripts/queryworkorders/. Never edit directly in Maximo.
#
# Code must run on Jython 2.7 and CPython 3: the pure functions below (parsing,
# validation, where clause) are tested by tests/unit/test_queryworkorders.py.
# Java/Maximo imports live only inside run(). No Python standard library imports:
# Maximo's Jython does not ship it ("No module named datetime").

MAX_DATE_RANGE_DAYS = 366
MAX_WONUMS = 50
MAX_LIST_VALUES = 20
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500

# Values that mean "parameter not informed" (literal variables need a default).
UNSET_VALUES = ("", "*")

DATE_FIELDS = (
    "reportdate",
    "statusdate",
    "targstartdate",
    "targcompdate",
    "schedstart",
    "schedfinish",
    "actstart",
    "actfinish",
)
DEFAULT_DATE_FIELD = "reportdate"

# Attribute -> output type. Only these attributes can be selected.
FIELD_TYPES = {
    "wonum": "str",
    "siteid": "str",
    "description": "str",
    "status": "str",
    "statusdate": "date",
    "worktype": "str",
    "wopriority": "int",
    "assetnum": "str",
    "location": "str",
    "persongroup": "str",
    "lead": "str",
    "owner": "str",
    "reportedby": "str",
    "reportdate": "date",
    "targstartdate": "date",
    "targcompdate": "date",
    "schedstart": "date",
    "schedfinish": "date",
    "actstart": "date",
    "actfinish": "date",
    "changedate": "date",
    "estdur": "float",
    "actlabhrs": "float",
    "actlabcost": "float",
    "actmatcost": "float",
    "acttotalcost": "float",
    "failurecode": "str",
    "problemcode": "str",
    "parent": "str",
}
DEFAULT_FIELDS = (
    "wonum",
    "siteid",
    "description",
    "status",
    "worktype",
    "wopriority",
    "assetnum",
    "location",
    "persongroup",
    "reportdate",
    "actstart",
    "actfinish",
)

# Parameter -> (WORKORDER attribute, value type, max values).
LIST_FILTERS = (
    ("siteid", "siteid", "str", MAX_LIST_VALUES),
    ("wonums", "wonum", "str", MAX_WONUMS),
    ("status", "status", "str", MAX_LIST_VALUES),
    ("priority", "wopriority", "int", MAX_LIST_VALUES),
    ("assetnum", "assetnum", "str", MAX_LIST_VALUES),
    ("location", "location", "str", MAX_LIST_VALUES),
    ("persongroup", "persongroup", "str", MAX_LIST_VALUES),
    ("worktype", "worktype", "str", MAX_LIST_VALUES),
)

PARAM_NAMES = (
    "date_from",
    "date_to",
    "date_field",
    "siteid",
    "wonums",
    "status",
    "priority",
    "assetnum",
    "location",
    "persongroup",
    "worktype",
    "fields",
    "page",
    "page_size",
)

# Work orders and activities only (no tasks, changes or releases).
BASE_WHERE = (
    "woclass in (select value from synonymdomain where domainid = 'WOCLASS'"
    " and maxvalue in ('WORKORDER', 'ACTIVITY')) and istask = 0"
)

# Required permission, checked in code. Not script variables: every variable becomes
# a tool parameter, so the caller could override authapp/authsigoption.
PERMISSION_APP = "WOTRACK"
PERMISSION_OPTION = "READ"
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


def parse_fields(raw):
    if is_unset(raw):
        return list(DEFAULT_FIELDS)
    fields = []
    for item in to_text(raw).split(","):
        item = item.strip().lower()
        if not item:
            continue
        if item not in FIELD_TYPES:
            raise ParamError("unknown_field", "fields", "Unknown field: %s." % item)
        if item not in fields:
            fields.append(item)
    if "wonum" not in fields:
        fields.insert(0, "wonum")
    if "siteid" not in fields:
        fields.insert(1, "siteid")
    return fields


def build_query(raw, userid):
    """Validate raw parameters and build the where clause with bind values.

    Returns a dict. "binds" is a list of (object, attribute, value) in placeholder
    order; values never go into the where text.

    The date range is required, except when wonums is given and both dates are
    omitted: wonums is capped at MAX_WONUMS, so the query stays bounded.
    """
    wonums = parse_list("wonums", raw.get("wonums"), "str", MAX_WONUMS)
    if wonums and is_unset(raw.get("date_from")) and is_unset(raw.get("date_to")):
        date_from = date_to = None
    else:
        date_from = parse_date("date_from", raw.get("date_from"))
        date_to = parse_date("date_to", raw.get("date_to"))
        if date_to.ordinal < date_from.ordinal:
            raise ParamError("invalid_range", "date_to", "date_to must be on or after date_from.")
        if date_to.ordinal - date_from.ordinal + 1 > MAX_DATE_RANGE_DAYS:
            raise ParamError(
                "range_too_large",
                "date_to",
                "Date range is limited to %d days." % MAX_DATE_RANGE_DAYS,
            )

    date_field = raw.get("date_field")
    date_field = DEFAULT_DATE_FIELD if is_unset(date_field) else to_text(date_field).strip().lower()
    if date_field not in DATE_FIELDS:
        raise ParamError(
            "invalid_date_field",
            "date_field",
            "date_field must be one of: %s." % ", ".join(DATE_FIELDS),
        )

    page = parse_int("page", raw.get("page"), 1, 1, 100000)
    page_size = parse_int("page_size", raw.get("page_size"), DEFAULT_PAGE_SIZE, 1, MAX_PAGE_SIZE)
    fields = parse_fields(raw.get("fields"))

    binds = []
    clauses = [BASE_WHERE]
    if date_from is not None:
        # date_to is inclusive: compare with the start of the next day.
        binds.append(("WORKORDER", date_field.upper(), date_from))
        binds.append(("WORKORDER", date_field.upper(), Day(date_to.ordinal + 1)))
        clauses.append("%s >= :1 and %s < :2" % (date_field, date_field))

    filters = {}
    for name, attribute, kind, max_items in LIST_FILTERS:
        values = parse_list(name, raw.get(name), kind, max_items)
        if not values:
            continue
        filters[name] = values
        placeholders = []
        for value in values:
            binds.append(("WORKORDER", attribute.upper(), value))
            placeholders.append(":%d" % len(binds))
        clauses.append("%s in (%s)" % (attribute, ", ".join(placeholders)))

    binds.append(("GROUPUSER", "USERID", userid))
    binds.append(("GROUPUSER", "USERID", userid))
    clauses.append(SITE_AUTH_WHERE % (len(binds) - 1, len(binds)))

    return {
        "where": " and ".join(clauses),
        "binds": binds,
        "order_by": "%s desc, wonum" % date_field,
        "date_field": date_field,
        "date_from": date_from.isoformat() if date_from is not None else None,
        "date_to": date_to.isoformat() if date_to is not None else None,
        "filters": filters,
        "fields": fields,
        "page": page,
        "page_size": page_size,
        "offset": (page - 1) * page_size,
    }


def permission_binds(userid):
    return [
        ("APPLICATIONAUTH", "APP", PERMISSION_APP),
        ("APPLICATIONAUTH", "OPTIONNAME", PERMISSION_OPTION),
        ("GROUPUSER", "USERID", userid),
    ]


def build_response(query, total, items):
    page_size = query["page_size"]
    total_pages = (total + page_size - 1) // page_size
    return {
        "total": total,
        "page": query["page"],
        "page_size": page_size,
        "total_pages": total_pages,
        "returned": len(items),
        "has_more": query["page"] < total_pages,
        "date_field": query["date_field"],
        "date_from": query["date_from"],
        "date_to": query["date_to"],
        "filters": query["filters"],
        "items": items,
    }


def error_response(code, parameter, message):
    return {"error": {"code": code, "parameter": parameter, "message": message}}


def collect_params(variables, body, query_param):
    """Read each parameter from literal variable, JSON body or query string.

    How the MCP Server delivers arguments is not confirmed yet, so the first source
    with a value wins. Returns (raw, sources); sources holds names, never values.
    """
    raw = {}
    sources = {}
    for name in PARAM_NAMES:
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


# ---------------------------------------------------------------------------
# Maximo runtime (Jython only)
# ---------------------------------------------------------------------------


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


def read_item(mbo, fields, date_format):
    item = {}
    for field in fields:
        kind = FIELD_TYPES[field]
        if mbo.isNull(field):
            item[field] = None
        elif kind == "date":
            item[field] = date_format.format(mbo.getDate(field))
        elif kind == "int":
            item[field] = mbo.getInt(field)
        elif kind == "float":
            item[field] = mbo.getDouble(field)
        else:
            item[field] = mbo.getString(field)
    return item


def run(user_info, raw):
    from java.text import SimpleDateFormat
    from psdi.mbo import MboConstants, SqlFormat
    from psdi.server import MXServer

    if user_info is None:
        # Fail closed: never query without the caller's identity.
        return error_response("no_user", None, "Caller identity not available.")

    userid = user_info.getUserName()
    auth_set = MXServer.getMXServer().getMboSet("APPLICATIONAUTH", user_info)
    try:
        # UserInfo gives SqlFormat the locale/timezone setObject needs.
        auth_sqf = SqlFormat(user_info, PERMISSION_WHERE)
        for index, (obj, attribute, value) in enumerate(permission_binds(userid)):
            auth_sqf.setObject(index + 1, obj, attribute, value)
        auth_set.setWhere(auth_sqf.format())
        allowed = not auth_set.isEmpty()
    finally:
        auth_set.cleanup()
    if not allowed:
        return error_response(
            "not_authorized",
            None,
            "User needs %s access to %s." % (PERMISSION_OPTION, PERMISSION_APP),
        )

    query = build_query(raw, userid)

    sqf = SqlFormat(user_info, query["where"])
    day_format = SimpleDateFormat("yyyy-MM-dd")
    for index, (obj, attribute, value) in enumerate(query["binds"]):
        if isinstance(value, Day):
            sqf.setTimestamp(index + 1, day_format.parse(value.isoformat()))
        else:
            sqf.setObject(index + 1, obj, attribute, to_text(value))

    mboset = MXServer.getMXServer().getMboSet("WORKORDER", user_info)
    try:
        mboset.setFlag(MboConstants.DISCARDABLE, True)
        mboset.setWhere(sqf.format())
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
            items.append(read_item(mbo, query["fields"], output_format))
            index += 1
        return build_response(query, total, items)
    finally:
        mboset.cleanup()


# Implicit variables Maximo may inject; logged by name to learn which exist on the
# MCP path.
IMPLICIT_NAMES = ("request", "requestBody", "userInfo", "service", "httpMethod")

try:
    from java.lang import System  # noqa: F401  (resolves only under Jython)

    _IN_MAXIMO = True
except ImportError:  # CPython: module imported by tests
    _IN_MAXIMO = False


def _main(scope, throwable):
    """Run the tool against the script scope and return the response dict.

    Everything lives in locals: after the script ends, Maximo calls toString on
    every top-level binding, and a binding holding globals() recurses into
    itself (StackOverflowError -> BMXAA1649E).
    """
    service = scope.get("service")
    req = scope.get("request")
    try:
        raw, sources = collect_params(
            scope,
            read_body(scope.get("requestBody")),
            req.getQueryParam if req is not None else None,
        )
        # No isLoggingEnabled() on ScriptService in MAS 9.2; log_debug filters by level.
        if service is not None:
            service.log_debug(
                "QUERYWORKORDERS implicit vars: %s; param sources: %s"
                % ([n for n in IMPLICIT_NAMES if scope.get(n) is not None], sources)
            )
        return run(req.getUserInfo() if req is not None else scope.get("userInfo"), raw)
    except ParamError as e:
        return error_response(e.code, e.parameter, e.message)
    except (Exception, throwable) as e:
        # Throwable: Java exceptions (e.g. NullPointerException) may bypass Exception.
        if service is not None:
            service.log_error("QUERYWORKORDERS failed: %s" % e)
        return error_response("internal_error", None, "Query failed. See Maximo log.")


if _IN_MAXIMO:
    from com.ibm.tivoli.maximo.oslc import OslcUtils
    from java.lang import Throwable

    # No top-level variable may reference globals() (see _main).
    responseBody = OslcUtils.jsonToBytes(to_json(_main(globals(), Throwable)))
