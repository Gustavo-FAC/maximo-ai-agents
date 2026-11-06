"""Tempo em status: para onde vai o tempo das OS concluídas no período.

Funções puras sobre o histórico de status (fetch.fetch_completed_histories). A vida
da OS vai da 1ª mudança registrada até a 1ª mudança para um status da classe
'closed' (conclusão); o que vem depois (ex.: concluída -> fechada) fica de fora.
Entram só as OS cuja conclusão caiu no período. Tempo em um status = intervalo até
a mudança seguinte da mesma OS.
"""

import datetime

import pandas as pd

from maximo_agents.analysis.backlog import counts
from maximo_agents.analysis.config import CLOSED, ClientConfig

DEFAULT_TOP = 20
TOP_CLOSED_BY = 10
UNKNOWN = "unknown"  # status fora da configuração do cliente
SECONDS_PER_DAY = 86400
KEY = ["siteid", "wonum"]


def to_frame(changes: list[dict], config: ClientConfig) -> pd.DataFrame:
    columns = ["wonum", "siteid", "status", "changedate", "changeby", "wostatusid"]
    frame = pd.DataFrame.from_records(changes, columns=columns)
    frame["changed"] = pd.to_datetime(frame["changedate"], errors="coerce")
    frame = frame[frame["changed"].notna()]
    frame = frame.assign(status_class=frame["status"].map(config.class_of).fillna(UNKNOWN))
    order = [*KEY, "changed", "wostatusid"]
    return frame.sort_values(order, kind="stable").reset_index(drop=True)


def life_until_completion(frame: pd.DataFrame) -> pd.DataFrame:
    """Mudanças de cada OS até a 1ª conclusão (inclusive), com o tempo até a seguinte."""
    closes = frame["status_class"] == CLOSED
    closed_before = closes.astype(int).groupby([frame[k] for k in KEY]).cumsum() - closes
    life = frame[closed_before == 0].assign(closes=closes[closed_before == 0])
    grouped = life.groupby(KEY, sort=False)
    next_changed = grouped["changed"].shift(-1)
    return life.assign(
        next_status=grouped["status"].shift(-1),
        days=(next_changed - life["changed"]).dt.total_seconds() / SECONDS_PER_DAY,
    )


def per_work_order(life: pd.DataFrame) -> pd.DataFrame:
    grouped = life.groupby(KEY, sort=False)
    result = grouped.agg(
        started=("changed", "first"), steps=("changed", "size"), completes=("closes", "any")
    )
    last = grouped.tail(1).set_index(KEY)
    return result.assign(
        completed=last["changed"],
        completion_status=last["status"],
        closed_by=last["changeby"],
    )


def stats(series: pd.Series) -> dict:
    values = series.dropna()
    if not len(values):
        return {"median": None, "p90": None, "mean": None}
    return {
        "median": _days(values.median()),
        "p90": _days(values.quantile(0.9)),
        "mean": _days(values.mean()),
    }


def status_stats(intervals: pd.DataFrame, total_days: float) -> list[dict]:
    rows = []
    for status, group in intervals.groupby("status", sort=False):
        days = group["days"]
        rows.append(
            {
                "status": status,
                "class": group["status_class"].iloc[0],
                "work_orders": len(group[KEY].drop_duplicates()),
                "intervals": len(group),
                "total_days": _days(days.sum()),
                "share": _share(days.sum(), total_days),
                "median_days": _days(days.median()),
                "p90_days": _days(days.quantile(0.9)),
                "max_days": _days(days.max()),
            }
        )
    rows.sort(key=lambda r: (-r["total_days"], r["status"]))
    return rows


def transition_stats(intervals: pd.DataFrame, top: int) -> list[dict]:
    rows = []
    for (source, target), group in intervals.groupby(["status", "next_status"], sort=False):
        rows.append(
            {
                "from": source,
                "to": target,
                "count": len(group),
                "median_days": _days(group["days"].median()),
                "total_days": _days(group["days"].sum()),
            }
        )
    rows.sort(key=lambda r: (-r["count"], -r["total_days"], r["from"], r["to"]))
    return rows[:top]


def slowest(cohort: pd.DataFrame, intervals: pd.DataFrame, top: int) -> list[dict]:
    rows = []
    ordered = cohort.sort_values("lead_days", ascending=False, kind="stable").head(top)
    for (siteid, wonum), wo in ordered.iterrows():
        steps = intervals[(intervals["siteid"] == siteid) & (intervals["wonum"] == wonum)]
        path = [f"{s} {d:.1f}" for s, d in zip(steps["status"], steps["days"], strict=True)]
        rows.append(
            {
                "wonum": wonum,
                "siteid": siteid,
                "lead_time_days": _days(wo["lead_days"]),
                "completed": wo["completed"].date().isoformat(),
                "path": " > ".join([*path, str(wo["completion_status"])]),
            }
        )
    return rows


def status_time_report(
    changes: list[dict],
    config: ClientConfig,
    date_from: datetime.date,
    date_to: datetime.date,
    worktypes: list[str] | tuple[str, ...] = (),
    top: int = DEFAULT_TOP,
) -> dict:
    frame = to_frame(changes, config)
    life = life_until_completion(frame)
    wos = per_work_order(life)

    start = pd.Timestamp(date_from)
    end = pd.Timestamp(date_to + datetime.timedelta(days=1))
    in_period = wos["completes"] & (wos["completed"] >= start) & (wos["completed"] < end)
    with_history = wos["steps"] > 1
    cohort = wos[in_period & with_history]
    cohort = cohort.assign(
        lead_days=(cohort["completed"] - cohort["started"]).dt.total_seconds() / SECONDS_PER_DAY
    )
    in_cohort = pd.MultiIndex.from_frame(life[KEY]).isin(cohort.index)
    intervals = life[in_cohort & ~life["closes"]]
    total_days = float(intervals["days"].sum())

    by_class = intervals.groupby("status_class")["days"].sum().sort_values(ascending=False)
    months = {str(m): 0 for m in pd.period_range(date_from, date_to, freq="M")}
    for month, count in cohort["completed"].dt.to_period("M").astype(str).value_counts().items():
        months[month] = int(count)

    return {
        "client": config.client_id,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "worktypes": list(worktypes),
        "work_orders": len(cohort),
        "without_history": int((in_period & ~with_history).sum()),
        "completed_outside_period": int((wos["completes"] & ~in_period).sum()),
        "not_completed": int((~wos["completes"]).sum()),
        "lead_time_days": stats(cohort["lead_days"]),
        "total_days": _days(total_days),
        "by_month": months,
        "completion_status": counts(cohort["completion_status"]),
        "closed_by": counts(cohort["closed_by"], TOP_CLOSED_BY),
        "by_class": {
            str(cls): {"days": _days(days), "share": _share(days, total_days)}
            for cls, days in by_class.items()
        },
        "by_status": status_stats(intervals, total_days),
        "transitions": transition_stats(intervals, top),
        "slowest": slowest(cohort, intervals, top),
        "unknown_statuses": sorted(
            str(s) for s in frame.loc[frame["status_class"] == UNKNOWN, "status"].dropna().unique()
        ),
    }


def format_status_time_text(report: dict) -> str:
    worktypes = ", ".join(report["worktypes"]) or "todos"
    lead = report["lead_time_days"]
    lines = [
        f"Tempo em status - {report['client']} - OS concluídas de {report['date_from']} "
        f"a {report['date_to']} (tipos: {worktypes})",
        "Vida da OS: da 1ª mudança de status registrada até a 1ª conclusão (status fechado).",
        "",
        f"OS concluídas: {report['work_orders']} (só com a conclusão no histórico: "
        f"{report['without_history']}; concluídas fora do período: "
        f"{report['completed_outside_period']})",
        f"Lead time (dias): mediana {lead['median']}, p90 {lead['p90']}, média {lead['mean']}",
    ]
    if report["unknown_statuses"]:
        lines.append(f"Status fora da configuração: {', '.join(report['unknown_statuses'])}")
    lines += ["", "Tempo por classe:"]
    lines += [
        f"  {cls:<12}{v['days']:>10} d {v['share']:>6}%" for cls, v in report["by_class"].items()
    ]
    lines += [
        "",
        "== STATUS (onde o tempo fica)",
        f"  {'status':<11}{'classe':<10}{'OS':>6}{'passagens':>10}{'dias':>10}{'%':>7}"
        f"{'mediana':>9}{'p90':>8}{'máx':>8}",
    ]
    for row in report["by_status"]:
        lines.append(
            f"  {row['status']!s:<11}{row['class']:<10}{row['work_orders']:>6}"
            f"{row['intervals']:>10}{row['total_days']:>10}{row['share']:>7}"
            f"{row['median_days']:>9}{row['p90_days']:>8}{row['max_days']:>8}"
        )
    lines += ["", "== TRANSIÇÕES MAIS COMUNS", f"  {'de > para':<24}{'vezes':>7}{'mediana d':>11}"]
    for row in report["transitions"]:
        step = f"{row['from']} > {row['to']}"
        lines.append(f"  {step:<24}{row['count']:>7}{row['median_days']!s:>11}")
    lines += ["", "== OS MAIS DEMORADAS (status e dias em cada um)"]
    for row in report["slowest"]:
        lines.append(
            f"  {row['wonum']!s:<10}{row['siteid']!s:<11}{row['lead_time_days']:>8} d  "
            f"{row['completed']}  {row['path'][:90]}"
        )
    lines += _table("Status da conclusão", report["completion_status"])
    lines += _table("Quem concluiu", report["closed_by"])
    lines += _table("Conclusões por mês", report["by_month"])
    return "\n".join(lines)


def _days(value) -> float:
    return round(float(value), 1)


def _share(part: float, whole: float) -> float:
    return round(100 * float(part) / whole, 1) if whole else 0.0


def _table(title: str, values: dict[str, int]) -> list[str]:
    return ["", f"{title}:"] + [f"  {key:<20}{count:>7}" for key, count in values.items()]
