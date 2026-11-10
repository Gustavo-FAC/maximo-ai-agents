"""MTBF e MTTR por duas bases, sem misturar (decisão do usuário, 2026-11-10).

Base OS corretivas (fetch.fetch_corrective_work_orders): falha = OS dos tipos
corretivos do cliente com reportdate no período, canceladas fora. Tempo de reparo =
actfinish - actstart, só OS com as duas datas e fim depois do início. Por objeto
(ativo ou location): MTTR = média do tempo de reparo; MTBF = dias do período / falhas
(tempo de calendário, sem descontar o reparo nem horário de operação).

Base paradas (fetch.fetch_downtime_histories, ASSETSTATUS): parada = queda
(isrunning falso) até o retorno seguinte do mesmo ativo, pelas datas. O campo
downtime gravado no retorno vai à parte (nem sempre bate com as datas). Por ativo:
paradas = quedas no período; horas paradas = parte de cada parada dentro do período;
MTTR = média da duração das paradas que começaram e terminaram no período;
MTBF = (horas do período - horas paradas) / paradas; disponibilidade = 1 - horas
paradas / horas do período.

Sem a lista de todos os ativos, não há MTBF nem disponibilidade da frota: só por objeto.
"""

import datetime

import pandas as pd

from maximo_agents.analysis.backlog import counts
from maximo_agents.analysis.config import CANCELLED, ClientConfig
from maximo_agents.analysis.recurrence import has_value, month_counts

DEFAULT_TOP = 20
SECONDS_PER_HOUR = 3600
HOURS_PER_DAY = 24
TRUE_FLAGS = {"1", "true", "y", "yes"}
FALSE_FLAGS = {"0", "false", "n", "no"}


# --- Comum ----------------------------------------------------------------------------


def period_bounds(date_from: datetime.date, date_to: datetime.date):
    """Início do 1º dia e início do dia seguinte ao último (fim exclusivo)."""
    return pd.Timestamp(date_from), pd.Timestamp(date_to + datetime.timedelta(days=1))


def hours_stats(series: pd.Series) -> dict:
    values = series.dropna()
    if not len(values):
        return {"mean": None, "median": None, "p90": None}
    return {
        "mean": _hours(values.mean()),
        "median": _hours(values.median()),
        "p90": _hours(values.quantile(0.9)),
    }


def flag(value) -> bool | None:
    """Booleano do Maximo (True/False, 1/0, "Y"/"N"...); None se não der para ler."""
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().lower()
    if text in TRUE_FLAGS:
        return True
    if text in FALSE_FLAGS:
        return False
    return None


# --- Base OS corretivas ---------------------------------------------------------------


def work_order_frame(records: list[dict], config: ClientConfig) -> pd.DataFrame:
    columns = ["wonum", "siteid", "description", "status", "worktype", "assetnum"]
    columns += ["location", "reportdate", "actstart", "actfinish"]
    frame = pd.DataFrame.from_records(records, columns=columns)
    started = pd.to_datetime(frame["actstart"], errors="coerce")
    finished = pd.to_datetime(frame["actfinish"], errors="coerce")
    hours = (finished - started).dt.total_seconds() / SECONDS_PER_HOUR
    return frame.assign(
        reported=pd.to_datetime(frame["reportdate"], errors="coerce"),
        status_class=frame["status"].map(config.class_of),
        repair_hours=hours.where(hours >= 0),
        has_dates=started.notna() & finished.notna(),
    )


def work_order_objects(frame: pd.DataFrame, key: str, period_days: int, top: int) -> dict:
    """Falhas, MTBF e MTTR por objeto (siteid + key), em dois rankings."""
    data = frame[has_value(frame[key])].sort_values(["siteid", key, "reported", "wonum"])
    other = "location" if key == "assetnum" else "assetnum"
    rows = []
    for (siteid, value), group in data.groupby(["siteid", key], sort=False):
        repairs = group["repair_hours"].dropna()
        others = group[other][has_value(group[other])]
        last = group.iloc[-1]
        rows.append(
            {
                key: value,
                "siteid": siteid,
                "failures": len(group),
                "mtbf_days": round(period_days / len(group), 1),
                "mttr_hours": _hours(repairs.mean()) if len(repairs) else None,
                "median_repair_hours": _hours(repairs.median()) if len(repairs) else None,
                "repair_hours": _hours(repairs.sum()),
                "with_repair_time": len(repairs),
                other: others.mode().iloc[0] if len(others) else None,
                "last_wonum": last["wonum"],
                "last": last["reported"].date().isoformat() if pd.notna(last["reported"]) else None,
            }
        )
    by_failures = sorted(rows, key=lambda r: (-r["failures"], -r["repair_hours"], str(r[key])))
    by_repair = sorted(rows, key=lambda r: (-r["repair_hours"], -r["failures"], str(r[key])))
    return {
        "objects": len(rows),
        "top_by_failures": by_failures[:top],
        "top_by_repair_hours": [r for r in by_repair if r["repair_hours"] > 0][:top],
    }


def work_order_reliability(
    records: list[dict],
    config: ClientConfig,
    date_from: datetime.date,
    date_to: datetime.date,
    top: int = DEFAULT_TOP,
) -> dict:
    frame = work_order_frame(records, config)
    cancelled = frame["status_class"] == CANCELLED
    valid = frame[~cancelled]
    period_days = (date_to - date_from).days + 1
    finish_before_start = valid["has_dates"] & valid["repair_hours"].isna()
    return {
        "basis": "corrective work orders",
        "worktypes": list(config.corrective_worktypes),
        "failures": len(valid),
        "cancelled_excluded": int(cancelled.sum()),
        "with_repair_time": int(valid["repair_hours"].notna().sum()),
        "without_repair_dates": int((~valid["has_dates"]).sum()),
        "finish_before_start": int(finish_before_start.sum()),
        "without_asset": int((~has_value(valid["assetnum"])).sum()),
        "without_location": int((~has_value(valid["location"])).sum()),
        "mttr_hours": hours_stats(valid["repair_hours"]),
        "repair_hours": _hours(valid["repair_hours"].sum()),
        "by_worktype": counts(valid["worktype"]),
        "by_month": month_counts(valid, date_from, date_to),
        "by_asset": work_order_objects(valid, "assetnum", period_days, top),
        "by_location": work_order_objects(valid, "location", period_days, top),
    }


# --- Base paradas (ASSETSTATUS) -------------------------------------------------------


def downtime_frame(changes: list[dict]) -> tuple[pd.DataFrame, int, int]:
    """Mudanças legíveis em ordem por ativo, sem repetidas; e quantas saíram de cada tipo."""
    columns = ["assetnum", "siteid", "assetstatusid", "changedate", "isrunning", "downtime"]
    columns += ["code", "operational", "wonum", "location"]
    frame = pd.DataFrame.from_records(changes, columns=columns)
    frame = frame.assign(
        changed=pd.to_datetime(frame["changedate"], errors="coerce"),
        running=frame["isrunning"].map(flag),
        recorded=pd.to_numeric(frame["downtime"], errors="coerce"),
    )
    readable = frame["changed"].notna() & frame["running"].notna() & has_value(frame["assetnum"])
    frame = frame[readable].sort_values(
        ["siteid", "assetnum", "changed", "assetstatusid"], kind="stable"
    )
    # Pares repetidos (mesma data e mesmo estado) vistos na homologação: contam uma vez.
    unique = frame.drop_duplicates(["siteid", "assetnum", "changed", "running"])
    return unique.reset_index(drop=True), len(frame) - len(unique), int((~readable).sum())


STOP_COLUMNS = ["siteid", "assetnum", "start", "end", "recorded_hours", "code", "operational"]
STOP_COLUMNS += ["wonum", "location"]


def stops_of(frame: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por parada: queda até o retorno seguinte (end vazio = ainda parado).

    Queda repetida antes do retorno vale a 1ª; retorno sem queda (cadastro) é ignorado.
    """
    stops = []
    for (siteid, assetnum), group in frame.groupby(["siteid", "assetnum"], sort=False):
        down = None
        for row in group.itertuples(index=False):
            if not row.running:
                down = down if down is not None else row
            elif down is not None:
                stops.append(_stop(siteid, assetnum, down, row))
                down = None
        if down is not None:
            stops.append(_stop(siteid, assetnum, down, None))
    stops_frame = pd.DataFrame.from_records(stops, columns=STOP_COLUMNS)
    for column in ("start", "end"):
        stops_frame[column] = pd.to_datetime(stops_frame[column])
    return stops_frame


def _stop(siteid, assetnum, down, up) -> dict:
    def first(name):
        values = (getattr(r, name) for r in (down, up) if r is not None)
        return next((v for v in values if _present(v)), None)

    return {
        "siteid": siteid,
        "assetnum": assetnum,
        "start": down.changed,
        "end": up.changed if up is not None else pd.NaT,
        "recorded_hours": up.recorded if up is not None else None,
        "code": first("code"),
        "operational": flag(down.operational),
        "wonum": first("wonum"),
        "location": first("location"),
    }


def with_period(stops: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Horas de cada parada dentro do período e marcas de início e fim no período."""
    stop_end = stops["end"].fillna(end).clip(upper=end)
    overlap = (stop_end - stops["start"].clip(lower=start)).dt.total_seconds() / SECONDS_PER_HOUR
    started_in = (stops["start"] >= start) & (stops["start"] < end)
    ended_in = stops["end"].notna() & (stops["end"] <= end)
    duration = (stops["end"] - stops["start"]).dt.total_seconds() / SECONDS_PER_HOUR
    return stops.assign(
        hours_in_period=overlap.clip(lower=0),
        started_in=started_in,
        completed_in=started_in & ended_in,
        down_at_end=stops["start"].lt(end) & ~ended_in,
        duration_hours=duration,
    )


def downtime_assets(stops: pd.DataFrame, period_hours: float, top: int) -> dict:
    rows = []
    for (siteid, assetnum), group in stops.groupby(["siteid", "assetnum"], sort=False):
        started = group[group["started_in"]]
        completed = group[group["completed_in"]]
        down_hours = float(group["hours_in_period"].sum())
        locations = group["location"].dropna()
        mtbf = mttr = None
        if len(completed):
            mttr = _hours(completed["duration_hours"].mean())
        if len(started):
            mtbf = round((period_hours - down_hours) / len(started) / HOURS_PER_DAY, 1)
        rows.append(
            {
                "assetnum": assetnum,
                "siteid": siteid,
                "stops": len(started),
                "downtime_hours": _hours(down_hours),
                "mttr_hours": mttr,
                "mtbf_days": mtbf,
                "availability_pct": round(100 * (1 - down_hours / period_hours), 2),
                "recorded_downtime_hours": _hours(completed["recorded_hours"].sum()),
                "down_at_end": bool(group["down_at_end"].any()),
                "location": locations.mode().iloc[0] if len(locations) else None,
                "last_code": _last(group["code"]),
                "last_wonum": _last(group["wonum"]),
            }
        )
    rows.sort(key=lambda r: (-r["downtime_hours"], -r["stops"], str(r["assetnum"])))
    return {"assets": len(rows), "top": rows[:top]}


def downtime_reliability(
    changes: list[dict],
    date_from: datetime.date,
    date_to: datetime.date,
    top: int = DEFAULT_TOP,
) -> dict:
    start, end = period_bounds(date_from, date_to)
    period_hours = (end - start).total_seconds() / SECONDS_PER_HOUR
    frame, duplicates, unreadable = downtime_frame(changes)
    stops = with_period(stops_of(frame), start, end)
    # Só paradas com alguma hora no período (ou começadas nele, mesmo com 0 h).
    stops = stops[(stops["hours_in_period"] > 0) | stops["started_in"]]
    started = stops[stops["started_in"]]
    completed = stops[stops["completed_in"]]
    return {
        "basis": "asset downtime records",
        "stops": len(started),
        "completed_stops": len(completed),
        "down_at_end_of_period": int(stops["down_at_end"].sum()),
        "assets_with_downtime": len(stops[["siteid", "assetnum"]].drop_duplicates()),
        "downtime_hours": _hours(stops["hours_in_period"].sum()),
        "recorded_downtime_hours": _hours(completed["recorded_hours"].sum()),
        "mttr_hours": hours_stats(completed["duration_hours"]),
        "by_code": counts(started["code"]),
        "by_operational": counts(started["operational"].map({True: "yes", False: "no"})),
        "by_month": month_counts(started.rename(columns={"start": "reported"}), date_from, date_to),
        "duplicates_removed": duplicates,
        "unreadable_changes": unreadable,
        "by_asset": downtime_assets(stops, period_hours, top),
    }


# --- Relatório ------------------------------------------------------------------------


def reliability_report(
    work_orders: list[dict],
    downtime_changes: list[dict],
    config: ClientConfig,
    date_from: datetime.date,
    date_to: datetime.date,
    assetnums: list[str] | None = None,
    locations: list[str] | None = None,
    top: int = DEFAULT_TOP,
) -> dict:
    return {
        "client": config.client_id,
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "period_days": (date_to - date_from).days + 1,
        "assetnums": list(assetnums or []),
        "locations": list(locations or []),
        "work_orders": work_order_reliability(work_orders, config, date_from, date_to, top),
        "downtime": downtime_reliability(downtime_changes, date_from, date_to, top),
    }


def format_reliability_text(report: dict) -> str:
    wo = report["work_orders"]
    dt = report["downtime"]
    scope = ""
    if report["assetnums"]:
        scope += f" - ativos {', '.join(report['assetnums'])}"
    if report["locations"]:
        scope += f" - locations {', '.join(report['locations'])}"
    lines = [
        f"MTBF e MTTR - {report['client']} - {report['date_from']} a {report['date_to']} "
        f"({report['period_days']} dias){scope}",
        "",
        f"== BASE OS CORRETIVAS ({', '.join(wo['worktypes'])}, reportdate)",
        f"Falhas: {wo['failures']} (canceladas fora: {wo['cancelled_excluded']}; "
        f"sem ativo: {wo['without_asset']}; sem location: {wo['without_location']})",
        f"Com tempo de reparo (actstart -> actfinish): {wo['with_repair_time']}; "
        f"sem as datas: {wo['without_repair_dates']}; fim antes do início: "
        f"{wo['finish_before_start']}",
        f"MTTR (h): média {wo['mttr_hours']['mean']}, mediana {wo['mttr_hours']['median']}, "
        f"p90 {wo['mttr_hours']['p90']}; horas de reparo: {wo['repair_hours']}",
    ]
    for key, title in (("assetnum", "ATIVOS"), ("location", "LOCATIONS")):
        part = wo["by_asset" if key == "assetnum" else "by_location"]
        lines += ["", f"-- {title}: {part['objects']} com falha (por falhas)"]
        lines += _wo_rows(part["top_by_failures"], key)
        lines += ["", f"-- {title} por horas de reparo"]
        lines += _wo_rows(part["top_by_repair_hours"], key)

    lines += [
        "",
        "== BASE PARADAS (ASSETSTATUS)",
        f"Paradas no período: {dt['stops']} (concluídas no período: {dt['completed_stops']}; "
        f"parados no fim: {dt['down_at_end_of_period']}); ativos: {dt['assets_with_downtime']}",
        f"Horas paradas no período: {dt['downtime_hours']} (gravado no Maximo nas concluídas: "
        f"{dt['recorded_downtime_hours']})",
        f"MTTR (h): média {dt['mttr_hours']['mean']}, mediana {dt['mttr_hours']['median']}, "
        f"p90 {dt['mttr_hours']['p90']}",
        f"Repetidas removidas: {dt['duplicates_removed']}; ilegíveis: {dt['unreadable_changes']}",
        "",
        f"  {'assetnum':<14}{'site':<11}{'paradas':>8}{'h paradas':>11}{'MTTR h':>9}"
        f"{'MTBF d':>9}{'disp. %':>9}  código",
    ]
    for row in dt["by_asset"]["top"]:
        lines.append(
            f"  {row['assetnum']!s:<14}{row['siteid']!s:<11}{row['stops']:>8}"
            f"{row['downtime_hours']:>11}{_dash(row['mttr_hours']):>9}"
            f"{_dash(row['mtbf_days']):>9}{row['availability_pct']:>9}  {row['last_code'] or '-'}"
        )
    return "\n".join(lines)


def _wo_rows(rows: list[dict], key: str) -> list[str]:
    lines = [
        f"  {key:<14}{'site':<11}{'falhas':>7}{'MTBF d':>9}{'MTTR h':>9}{'med. h':>9}"
        f"{'h reparo':>10}{'c/ tempo':>9}  última OS"
    ]
    for row in rows:
        lines.append(
            f"  {row[key]!s:<14}{row['siteid']!s:<11}{row['failures']:>7}{row['mtbf_days']:>9}"
            f"{_dash(row['mttr_hours']):>9}{_dash(row['median_repair_hours']):>9}"
            f"{row['repair_hours']:>10}{row['with_repair_time']:>9}  {row['last_wonum']}"
        )
    return lines


def _present(value) -> bool:
    return value is not None and not (isinstance(value, float) and pd.isna(value)) and value != ""


def _dash(value) -> str:
    return "-" if value is None else str(value)


def _last(series: pd.Series):
    values = [v for v in series if _present(v)]
    return values[-1] if values else None


def _hours(value) -> float:
    return round(float(value), 2) if pd.notna(value) else 0.0
