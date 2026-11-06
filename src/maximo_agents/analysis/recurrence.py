"""Reincidência de corretivas: o que mais quebra, por ativo e por location.

Funções puras sobre as OS corretivas já buscadas (fetch.py). Canceladas ficam de
fora. Reincidência = corretiva no mesmo ativo (ou location) em até repeat_days dias
depois da anterior, pelo reportdate.
"""

import datetime

import pandas as pd

from maximo_agents.analysis.backlog import counts
from maximo_agents.analysis.config import CANCELLED, ClientConfig

DEFAULT_REPEAT_DAYS = 30
DEFAULT_TOP = 20
SECONDS_PER_DAY = 86400


def to_frame(records: list[dict], config: ClientConfig) -> pd.DataFrame:
    columns = ["wonum", "siteid", "description", "status", "worktype", "assetnum"]
    columns += ["location", "reportdate", "actfinish"]
    frame = pd.DataFrame.from_records(records, columns=columns)
    frame["reported"] = pd.to_datetime(frame["reportdate"], errors="coerce")
    frame["status_class"] = frame["status"].map(config.class_of)
    return frame


def has_value(series: pd.Series) -> pd.Series:
    return series.notna() & (series.astype("string").str.strip() != "")


def object_stats(frame: pd.DataFrame, key: str, repeat_days: int, top: int) -> dict:
    """Falhas por objeto (siteid + key): quantidade, reincidências, intervalo mediano."""
    data = frame[has_value(frame[key]) & frame["reported"].notna()]
    data = data.sort_values(["siteid", key, "reported", "wonum"])
    gaps = data.groupby(["siteid", key])["reported"].diff().dt.total_seconds() / SECONDS_PER_DAY
    data = data.assign(gap_days=gaps, repeat=gaps <= repeat_days)

    other = "location" if key == "assetnum" else "assetnum"
    rows = []
    for (siteid, value), group in data.groupby(["siteid", key], sort=False):
        group_gaps = group["gap_days"].dropna()
        others = group[other][has_value(group[other])]
        last = group.iloc[-1]
        rows.append(
            {
                key: value,
                "siteid": siteid,
                "failures": len(group),
                "repeats": int(group["repeat"].sum()),
                "median_days_between": (
                    round(float(group_gaps.median()), 1) if len(group_gaps) else None
                ),
                "first": group["reported"].iloc[0].date().isoformat(),
                "last": last["reported"].date().isoformat(),
                # Location mais frequente do ativo (ou ativo mais frequente da location).
                other: others.mode().iloc[0] if len(others) else None,
                "last_wonum": last["wonum"],
                "last_description": last["description"] if pd.notna(last["description"]) else None,
            }
        )
    rows.sort(key=lambda r: (-r["failures"], -r["repeats"], str(r[key])))
    return {
        "objects": len(rows),
        "objects_with_repeat_failures": sum(1 for r in rows if r["failures"] >= 2),
        "repeats": int(data["repeat"].sum()),
        "top": rows[:top],
    }


def month_counts(frame: pd.DataFrame, date_from: datetime.date, date_to: datetime.date):
    months = pd.period_range(date_from, date_to, freq="M")
    by_month = {str(m): 0 for m in months}
    found = frame["reported"].dropna().dt.to_period("M").astype(str).value_counts()
    for month, count in found.items():
        if month in by_month:
            by_month[month] = int(count)
    return by_month


def recurrence_report(
    records: list[dict],
    config: ClientConfig,
    date_from: datetime.date,
    date_to: datetime.date,
    repeat_days: int = DEFAULT_REPEAT_DAYS,
    top: int = DEFAULT_TOP,
) -> dict:
    frame = to_frame(records, config)
    cancelled = frame["status_class"] == CANCELLED
    valid = frame[~cancelled]
    return {
        "client": config.client_id,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "date_field": "reportdate",
        "worktypes": list(config.corrective_worktypes),
        "repeat_days": repeat_days,
        "total": len(valid),
        "cancelled_excluded": int(cancelled.sum()),
        "without_asset": int((~has_value(valid["assetnum"])).sum()),
        "without_location": int((~has_value(valid["location"])).sum()),
        "by_worktype": counts(valid["worktype"]),
        "by_status": counts(valid["status"]),
        "by_month": month_counts(valid, date_from, date_to),
        "by_asset": object_stats(valid, "assetnum", repeat_days, top),
        "by_location": object_stats(valid, "location", repeat_days, top),
    }


def format_recurrence_text(report: dict) -> str:
    worktypes = ", ".join(report["worktypes"])
    lines = [
        f"Reincidência de corretivas ({worktypes}) - {report['client']} - "
        f"{report['date_from']} a {report['date_to']} (reportdate)",
        "",
        f"Corretivas: {report['total']} (canceladas fora: {report['cancelled_excluded']}; "
        f"sem ativo: {report['without_asset']}; sem location: {report['without_location']})",
        f"Reincidência = nova corretiva no mesmo objeto em até {report['repeat_days']} dias.",
    ]
    lines += _table("Tipo", report["by_worktype"])
    lines += _table("Mês", report["by_month"])
    for key, title in (("assetnum", "ATIVOS"), ("location", "LOCATIONS")):
        part = report[f"by_{'asset' if key == 'assetnum' else 'location'}"]
        other = "location" if key == "assetnum" else "assetnum"
        lines += [
            "",
            f"== {title}: {part['objects']} com corretiva, "
            f"{part['objects_with_repeat_failures']} com 2 ou mais, "
            f"{part['repeats']} reincidências",
            f"  {key:<14}{'site':<11}{'falhas':>7}{'reinc.':>8}{'mediana d':>11}  "
            f"{'última':<11}{other:<14}última OS",
        ]
        for row in part["top"]:
            median = "-" if row["median_days_between"] is None else row["median_days_between"]
            lines.append(
                f"  {row[key]!s:<14}{row['siteid']!s:<11}{row['failures']:>7}"
                f"{row['repeats']:>8}{median!s:>11}  {row['last']:<11}"
                f"{row[other] or '-'!s:<14}{(row['last_description'] or '')[:45]}"
            )
    return "\n".join(lines)


def _table(title: str, values: dict[str, int]) -> list[str]:
    return ["", f"{title}:"] + [f"  {key:<20}{count:>7}" for key, count in values.items()]
