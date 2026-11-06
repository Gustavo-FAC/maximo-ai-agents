"""Backlog de OS: abertas (e executadas à parte) por idade, status, tipo, equipe...

Funções puras sobre a lista de OS já buscada (fetch.py). A IA não faz contas: o
relatório sai daqui pronto, serializável em JSON.

Idade = dias desde o reportdate (decisão do usuário, 2026-11-06). Dias no status =
dias desde o statusdate.
"""

import datetime

import pandas as pd

from maximo_agents.analysis.config import EXECUTED, OPEN, ClientConfig

# (limite inferior, limite superior inclusivo ou None, rótulo)
AGE_BUCKETS = (
    (0, 30, "0-30"),
    (31, 90, "31-90"),
    (91, 180, "91-180"),
    (181, 365, "181-365"),
    (366, None, ">365"),
)
NO_DATE = "no date"
EMPTY = "(empty)"
TOP_LOCATIONS = 10
OLDEST = 10


def to_frame(records: list[dict], config: ClientConfig, as_of: datetime.date) -> pd.DataFrame:
    columns = ["wonum", "siteid", "description", "status", "statusdate", "worktype"]
    columns += ["wopriority", "assetnum", "location", "persongroup", "reportdate"]
    frame = pd.DataFrame.from_records(records, columns=columns)
    frame["status_class"] = frame["status"].map(config.class_of)
    as_of_ts = pd.Timestamp(as_of)
    for column, target in (("reportdate", "age_days"), ("statusdate", "days_in_status")):
        dates = pd.to_datetime(frame[column], errors="coerce").dt.normalize()
        days = (as_of_ts - dates).dt.days
        frame[target] = days.clip(lower=0).astype("Int64")
    frame["age_bucket"] = frame["age_days"].map(age_bucket)
    return frame


def age_bucket_ranges(
    as_of: datetime.date, history_start: datetime.date
) -> list[tuple[str, datetime.date, datetime.date]]:
    """(rótulo, reportdate inicial, reportdate final) de cada faixa de idade, inclusivo.

    Faixas inteiras antes de history_start ficam de fora; a última vai até
    history_start.
    """
    ranges = []
    for low, high, label in AGE_BUCKETS:
        date_to = as_of - datetime.timedelta(days=low)
        date_from = history_start if high is None else as_of - datetime.timedelta(days=high)
        date_from = max(date_from, history_start)
        if date_from <= date_to:
            ranges.append((label, date_from, date_to))
    return ranges


def age_bucket(days) -> str:
    if days is None or pd.isna(days):
        return NO_DATE
    for low, high, label in AGE_BUCKETS:
        if days >= low and (high is None or days <= high):
            return label
    return NO_DATE


def counts(series: pd.Series, limit: int | None = None) -> dict[str, int]:
    """Contagem por valor, maior primeiro (empate: valor); vazio vira EMPTY."""
    values = series.astype("string").fillna(EMPTY).replace("", EMPTY)
    table = values.value_counts()
    ordered = sorted(table.items(), key=lambda kv: (-kv[1], kv[0]))
    if limit is not None:
        ordered = ordered[:limit]
    return {str(k): int(v) for k, v in ordered}


def bucket_counts(buckets: pd.Series) -> dict[str, int]:
    """OS por faixa de idade, todas as faixas na ordem; "no date" só se houver."""
    by_age = {label: 0 for _, _, label in AGE_BUCKETS}
    by_age.update(counts(buckets))
    if not by_age.get(NO_DATE):
        by_age.pop(NO_DATE, None)
    return by_age


def summarize(frame: pd.DataFrame) -> dict:
    by_status = {}
    for status, group in frame.groupby("status", sort=False, dropna=False):
        days = group["days_in_status"].dropna()
        by_status[str(status)] = {
            "count": len(group),
            "median_days_in_status": int(days.median()) if len(days) else None,
            "max_days_in_status": int(days.max()) if len(days) else None,
            "by_age_days": bucket_counts(group["age_bucket"]),
        }
    by_status = dict(sorted(by_status.items(), key=lambda kv: (-kv[1]["count"], kv[0])))

    oldest = frame.sort_values(["age_days", "wonum"], ascending=[False, True], na_position="last")
    oldest_rows = [
        {
            "wonum": _value(row.wonum),
            "siteid": _value(row.siteid),
            "status": _value(row.status),
            "worktype": _value(row.worktype),
            "reportdate": _value(row.reportdate),
            "age_days": None if pd.isna(row.age_days) else int(row.age_days),
            "description": _value(row.description),
        }
        for row in oldest.head(OLDEST).itertuples()
    ]

    ages = frame["age_days"].dropna()
    return {
        "total": len(frame),
        "median_age_days": int(ages.median()) if len(ages) else None,
        "by_age_days": bucket_counts(frame["age_bucket"]),
        "by_status": by_status,
        "by_worktype": counts(frame["worktype"]),
        "by_priority": counts(frame["wopriority"].astype("Int64")),
        "by_persongroup": counts(frame["persongroup"]),
        "by_site": counts(frame["siteid"]),
        "top_locations": counts(frame["location"], TOP_LOCATIONS),
        "oldest": oldest_rows,
    }


def backlog_report(
    open_records: list[dict],
    executed_by_age: dict[str, int],
    config: ClientConfig,
    as_of: datetime.date,
) -> dict:
    """Abertas com detalhe; executadas só contadas por faixa de idade.

    Executadas (POSEXEC na Itambé) são ~109 mil desde 2007: contadas pelo total do
    script por faixa de reportdate, sem baixar as OS.
    """
    frame = to_frame(open_records, config, as_of)
    other = frame[frame["status_class"] != OPEN]
    by_age = {label: 0 for _, _, label in AGE_BUCKETS}
    by_age.update(executed_by_age)
    return {
        "client": config.client_id,
        "as_of": as_of.isoformat(),
        "age_basis": "reportdate",
        "open": summarize(frame[frame["status_class"] == OPEN]),
        "executed": {
            "statuses": config.statuses_of(EXECUTED),
            "total": sum(by_age.values()),
            "by_age_days": by_age,
        },
        # Não deveria haver: a busca filtra pelos status abertos.
        "ignored": counts(other["status"]),
    }


def format_backlog_text(report: dict) -> str:
    lines = [f"Backlog de OS - {report['client']} - em {report['as_of']} (idade pelo reportdate)"]
    part = report[OPEN]
    lines += ["", f"== ABERTAS: {part['total']} OS (idade mediana: {part['median_age_days']} dias)"]
    if part["total"]:
        lines += _table("Idade (dias)", part["by_age_days"])
        lines += ["", "Status: OS (dias no status: mediana / máximo)"]
        for status, info in part["by_status"].items():
            lines.append(
                f"  {status:<12}{info['count']:>7}   "
                f"({info['median_days_in_status']} / {info['max_days_in_status']})"
            )
        labels = [label for _, _, label in AGE_BUCKETS]
        lines += ["", "Status x idade (dias desde o reportdate):"]
        lines.append(f"  {'':<12}" + "".join(f"{label:>9}" for label in labels))
        for status, info in part["by_status"].items():
            ages = info["by_age_days"]
            lines.append(f"  {status:<12}" + "".join(f"{ages[label]:>9}" for label in labels))
        lines += _table("Tipo de trabalho", part["by_worktype"])
        lines += _table("Prioridade", part["by_priority"])
        lines += _table("Equipe", part["by_persongroup"])
        lines += _table("Site", part["by_site"])
        lines += _table(f"Locations (top {TOP_LOCATIONS})", part["top_locations"])
        lines += ["", f"Mais antigas (top {OLDEST}):"]
        for row in part["oldest"]:
            lines.append(
                f"  {row['wonum']:<10}{row['siteid']:<11}{row['status']:<10}"
                f"{str(row['worktype'] or EMPTY):<9}{row['age_days']!s:>6} d  "
                f"{(row['description'] or '')[:60]}"
            )
    executed = report[EXECUTED]
    statuses = ", ".join(executed["statuses"])
    lines += ["", f"== EXECUTADAS, AGUARDANDO FECHAMENTO ({statuses}): {executed['total']} OS"]
    lines += _table("Idade (dias)", executed["by_age_days"])
    if report["ignored"]:
        lines += _table("Ignoradas (status fora da classe)", report["ignored"])
    return "\n".join(lines)


def _value(value):
    """Valor ausente do pandas (NaN/NA) vira None no relatório."""
    return None if value is None or pd.isna(value) else value


def _table(title: str, values: dict[str, int]) -> list[str]:
    return ["", f"{title}:"] + [f"  {key:<20}{count:>7}" for key, count in values.items()]
