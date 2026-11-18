"""OS atrasadas: data de previsão antes de hoje, sem execução, por equipe, ativo...

Funções puras sobre a lista de OS já buscada (fetch.fetch_overdue_candidates). A IA
não faz contas: o relatório sai daqui pronto, serializável em JSON.

Regra (por cliente, config [overdue]): OS num dos status configurados (padrão: todos
os abertos) cuja data de previsão (config.overdue_date_field) é anterior à data da
análise. Dias de atraso = dias desde a data de previsão. OS sem data de previsão não
contam como atrasadas e são contadas à parte. "Além da tolerância" = mais de
tolerance_days dias de atraso; as duas contagens saem juntas porque o cliente pode ler
a regra com ou sem tolerância.
"""

import datetime

import pandas as pd

from maximo_agents.analysis.backlog import EMPTY, _table, _value, counts
from maximo_agents.analysis.config import ClientConfig
from maximo_agents.analysis.fetch import OVERDUE_FIELDS

# (limite inferior, limite superior inclusivo ou None, rótulo), em dias de atraso.
DAYS_LATE_BUCKETS = (
    (1, 7, "1-7"),
    (8, 30, "8-30"),
    (31, 90, "31-90"),
    (91, 365, "91-365"),
    (366, None, ">365"),
)
DEFAULT_TOP = 20
MOST_LATE = 10


def to_frame(records: list[dict], config: ClientConfig, as_of: datetime.date) -> pd.DataFrame:
    columns = [*OVERDUE_FIELDS, config.crew_field, config.overdue_date_field]
    frame = pd.DataFrame.from_records(records, columns=columns)
    frame = frame.rename(columns={config.crew_field: "crew", config.overdue_date_field: "due"})
    due = pd.to_datetime(frame["due"], errors="coerce").dt.normalize()
    frame["days_late"] = (pd.Timestamp(as_of) - due).dt.days.astype("Int64")
    return frame


def days_late_bucket(days: int) -> str:
    for low, high, label in DAYS_LATE_BUCKETS:
        if days >= low and (high is None or days <= high):
            return label
    raise ValueError(f"Not overdue: {days} days.")


def _groups(late: pd.DataFrame, column: str, tolerance: int, limit: int | None = None) -> dict:
    """Por valor da coluna: atrasadas, além da tolerância e maior atraso (dias)."""
    keys = late[column].astype("string").fillna(EMPTY).replace("", EMPTY)
    result = {}
    for key, group in late.groupby(keys, sort=False):
        days = group["days_late"]
        result[str(key)] = {
            "overdue": len(group),
            "beyond_tolerance": int((days > tolerance).sum()),
            "max_days_late": int(days.max()),
        }
    ordered = sorted(result.items(), key=lambda kv: (-kv[1]["overdue"], kv[0]))
    if limit is not None:
        ordered = ordered[:limit]
    return dict(ordered)


def overdue_report(
    records: list[dict],
    config: ClientConfig,
    as_of: datetime.date,
    tolerance_days: int | None = None,
    top: int = DEFAULT_TOP,
) -> dict:
    tolerance = config.overdue_tolerance_days if tolerance_days is None else tolerance_days
    statuses = config.overdue_status_list()
    frame = to_frame(records, config, as_of)
    in_scope = frame[frame["status"].isin(statuses)]
    ignored = frame[~frame["status"].isin(statuses)]

    without_date = in_scope[in_scope["days_late"].isna()]
    dated = in_scope.dropna(subset=["days_late"])
    late = dated[dated["days_late"] >= 1]
    not_yet_due = len(dated) - len(late)

    days = late["days_late"]
    by_days_late = {label: 0 for _, _, label in DAYS_LATE_BUCKETS}
    if len(late):
        by_days_late.update(counts(days.map(days_late_bucket)))
    by_days_late = {label: by_days_late[label] for _, _, label in DAYS_LATE_BUCKETS}

    most_late = late.sort_values(["days_late", "wonum"], ascending=[False, True])
    most_late_rows = [
        {
            "wonum": _value(row.wonum),
            "siteid": _value(row.siteid),
            "status": _value(row.status),
            "worktype": _value(row.worktype),
            "crew": _value(row.crew),
            "assetnum": _value(row.assetnum),
            "location": _value(row.location),
            "due_date": _value(row.due),
            "days_late": int(row.days_late),
            "description": _value(row.description),
        }
        for row in most_late.head(MOST_LATE).itertuples()
    ]

    beyond = int((days > tolerance).sum())
    priority = late.assign(wopriority=late["wopriority"].astype("Int64"))
    return {
        "client": config.client_id,
        "as_of": as_of.isoformat(),
        "rule": {
            "statuses": statuses,
            "due_date_field": config.overdue_date_field,
            "tolerance_days": tolerance,
        },
        "crew_field": config.crew_field,
        "in_scope": len(in_scope),
        "without_due_date": len(without_date),
        "not_yet_due": not_yet_due,
        "overdue": {
            "total": len(late),
            "pct_of_in_scope": round(100 * len(late) / len(in_scope), 1) if len(in_scope) else None,
            "beyond_tolerance": beyond,
            "within_tolerance": len(late) - beyond,
            "median_days_late": int(days.median()) if len(late) else None,
            "max_days_late": int(days.max()) if len(late) else None,
            "by_days_late": by_days_late,
            "by_crew": _groups(late, "crew", tolerance),
            "by_status": _groups(late, "status", tolerance),
            "by_worktype": _groups(late, "worktype", tolerance),
            "by_priority": _groups(priority, "wopriority", tolerance),
            "by_site": _groups(late, "siteid", tolerance),
            "top_assets": _groups(late, "assetnum", tolerance, top),
            "top_locations": _groups(late, "location", tolerance, top),
            "most_late": most_late_rows,
        },
        "without_due_date_by_status": counts(without_date["status"]),
        # Não deveria haver: a busca filtra pelos status da regra.
        "ignored": counts(ignored["status"]),
    }


def format_overdue_text(report: dict) -> str:
    rule = report["rule"]
    part = report["overdue"]
    lines = [
        f"OS atrasadas - {report['client']} - em {report['as_of']}",
        f"Regra: status {', '.join(rule['statuses'])} e {rule['due_date_field']} antes de "
        f"hoje; tolerância {rule['tolerance_days']} dias",
        "",
        f"OS nos status da regra: {report['in_scope']}",
        f"  sem data de previsão (não contam): {report['without_due_date']}",
        f"  no prazo: {report['not_yet_due']}",
        f"  ATRASADAS: {part['total']} ({part['pct_of_in_scope']}%)",
        f"    além da tolerância: {part['beyond_tolerance']}",
        f"    dentro da tolerância: {part['within_tolerance']}",
        f"  atraso mediano / máximo (dias): {part['median_days_late']} / {part['max_days_late']}",
    ]
    if part["total"]:
        lines += _table("Dias de atraso", part["by_days_late"])
        for title, key in (
            (f"Equipe ({report['crew_field']})", "by_crew"),
            ("Status", "by_status"),
            ("Tipo de trabalho", "by_worktype"),
            ("Prioridade", "by_priority"),
            ("Site", "by_site"),
            ("Ativos (top)", "top_assets"),
            ("Locations (top)", "top_locations"),
        ):
            lines += ["", f"{title}: atrasadas / além da tolerância / maior atraso (dias)"]
            for value, info in part[key].items():
                lines.append(
                    f"  {value:<20}{info['overdue']:>7}{info['beyond_tolerance']:>7}"
                    f"{info['max_days_late']:>8}"
                )
        lines += ["", f"Mais atrasadas (top {MOST_LATE}):"]
        for row in part["most_late"]:
            lines.append(
                f"  {row['wonum']:<10}{row['siteid']:<11}{row['status']:<8}"
                f"{str(row['crew'] or EMPTY):<12}{row['days_late']:>6} d  "
                f"{(row['description'] or '')[:50]}"
            )
    if report["without_due_date_by_status"]:
        lines += _table("Sem data de previsão, por status", report["without_due_date_by_status"])
    if report["ignored"]:
        lines += _table("Ignoradas (status fora da regra)", report["ignored"])
    return "\n".join(lines)
