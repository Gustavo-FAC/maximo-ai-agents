"""Configuração das análises por cliente (arquivos TOML em analysis/clients/).

Cada cliente tem status próprios (valor externo). A classe do status (aberta,
executada, fechada, cancelada) vem do valor interno do Maximo, que é padrão, salvo
exceção explícita do cliente.
"""

import datetime
import tomllib
from dataclasses import dataclass
from pathlib import Path

CLIENTS_DIR = Path(__file__).parent / "clients"

OPEN = "open"
EXECUTED = "executed"
CLOSED = "closed"
CANCELLED = "cancelled"
STATUS_CLASSES = (OPEN, EXECUTED, CLOSED, CANCELLED)

# Atributo da OS que guarda a equipe: persongroup (padrão) ou crewid (ex.: Itambé).
CREW_FIELDS = ("persongroup", "crewid")

# Dia em que a semana do cliente começa ("MPs desta semana").
WEEK_STARTS = ("sunday", "monday")

# Data de previsão da OS que define o atraso ("início previsto" ou fim previsto).
OVERDUE_DATE_FIELDS = ("targstartdate", "schedstart", "targcompdate", "schedfinish")
DEFAULT_OVERDUE_DATE_FIELD = "targstartdate"
MAX_TOLERANCE_DAYS = 365

# Medida de emitidas × executadas que é o indicador do cliente (as outras vão de apoio).
ISSUED_EXECUTED_MEASURES = (
    "pct_executed_now",
    "pct_executed_same_month",
    "pct_executed_in_month_vs_issued",
)

# Valor interno do domínio WOSTATUS (padrão do Maximo) -> classe.
INTERNAL_STATUS_CLASS = {
    "WAPPR": OPEN,
    "APPR": OPEN,
    "WSCH": OPEN,
    "WMATL": OPEN,
    "WPCOND": OPEN,
    "INPRG": OPEN,
    "COMP": CLOSED,
    "CLOSE": CLOSED,
    "HISTEDIT": CLOSED,
    "CAN": CANCELLED,
}


class ClientConfigError(ValueError):
    """Arquivo de configuração do cliente ausente ou inválido."""


@dataclass(frozen=True)
class ClientConfig:
    client_id: str
    name: str
    sites: tuple[str, ...]
    history_start: datetime.date
    status_classes: dict[str, str]  # status externo -> classe
    corrective_worktypes: tuple[str, ...] = ()
    currency: str | None = None  # ISO 4217 dos custos (ex.: BRL)
    crew_field: str = "persongroup"  # um de CREW_FIELDS
    preventive_worktypes: tuple[str, ...] = ()
    week_start: str | None = None  # um de WEEK_STARTS
    # Atraso: OS nesses status (vazio = todos os abertos) com a data de previsão antes
    # de hoje; além da tolerância conta à parte.
    overdue_statuses: tuple[str, ...] = ()
    overdue_date_field: str = DEFAULT_OVERDUE_DATE_FIELD  # um de OVERDUE_DATE_FIELDS
    overdue_tolerance_days: int = 0
    # Atributo da OS com a modalidade de manutenção (campo do cliente; None = não tem).
    modality_field: str | None = None
    issued_executed_measure: str = "pct_executed_now"  # um de ISSUED_EXECUTED_MEASURES

    def statuses_of(self, *classes: str) -> list[str]:
        """Status externos das classes pedidas, em ordem alfabética."""
        return sorted(s for s, c in self.status_classes.items() if c in classes)

    def overdue_status_list(self) -> list[str]:
        """Status que podem estar atrasados: os configurados ou todos os abertos."""
        return sorted(self.overdue_statuses) or self.statuses_of(OPEN)

    def class_of(self, status: str | None) -> str | None:
        return self.status_classes.get(status) if status else None


def load_client_config(client_id: str, clients_dir: Path = CLIENTS_DIR) -> ClientConfig:
    if not client_id.isascii() or not client_id.isidentifier():
        raise ClientConfigError(f"Invalid client id: {client_id!r}.")
    path = clients_dir / f"{client_id}.toml"
    if not path.is_file():
        raise ClientConfigError(f"No configuration for client '{client_id}'.")
    with path.open("rb") as file:
        data = tomllib.load(file)
    return parse_client_config(client_id, data)


def parse_client_config(client_id: str, data: dict) -> ClientConfig:
    statuses = data.get("statuses")
    if not isinstance(statuses, dict) or not statuses:
        raise ClientConfigError(f"{client_id}: [statuses] is missing or empty.")

    status_classes = {}
    for status, entry in statuses.items():
        if not isinstance(entry, dict):
            raise ClientConfigError(f"{client_id}: status {status} must be a table.")
        explicit = entry.get("class")
        internal = entry.get("internal")
        if explicit is not None:
            if explicit not in STATUS_CLASSES:
                raise ClientConfigError(
                    f"{client_id}: status {status} has unknown class {explicit!r}."
                )
            status_classes[status] = explicit
        elif internal in INTERNAL_STATUS_CLASS:
            status_classes[status] = INTERNAL_STATUS_CLASS[internal]
        else:
            raise ClientConfigError(
                f"{client_id}: status {status} needs a known 'internal' value or a 'class'."
            )

    sites = data.get("sites", [])
    if not isinstance(sites, list) or not all(isinstance(s, str) and s for s in sites):
        raise ClientConfigError(f"{client_id}: 'sites' must be a list of site IDs.")

    try:
        history_start = datetime.date.fromisoformat(str(data["history_start"]))
    except (KeyError, ValueError) as e:
        raise ClientConfigError(f"{client_id}: 'history_start' must be YYYY-MM-DD.") from e

    corrective = _worktypes(client_id, data, "corrective_worktypes")
    preventive = _worktypes(client_id, data, "preventive_worktypes")

    week_start = data.get("week_start")
    if week_start is not None and week_start not in WEEK_STARTS:
        raise ClientConfigError(
            f"{client_id}: 'week_start' must be one of: {', '.join(WEEK_STARTS)}."
        )

    currency = data.get("currency")
    if currency is not None and not (
        isinstance(currency, str)
        and len(currency) == 3
        and currency.isascii()
        and currency.isalpha()
        and currency.isupper()
    ):
        raise ClientConfigError(f"{client_id}: 'currency' must be an ISO 4217 code (e.g. BRL).")

    crew_field = data.get("crew_field", "persongroup")
    if crew_field not in CREW_FIELDS:
        raise ClientConfigError(
            f"{client_id}: 'crew_field' must be one of: {', '.join(CREW_FIELDS)}."
        )

    modality_field = data.get("modality_field")
    if modality_field is not None and not (
        isinstance(modality_field, str)
        and modality_field.isascii()
        and modality_field.isidentifier()
        and modality_field.islower()
    ):
        raise ClientConfigError(
            f"{client_id}: 'modality_field' must be a lowercase attribute name."
        )

    issued = data.get("issued_executed", {})
    if not isinstance(issued, dict):
        raise ClientConfigError(f"{client_id}: [issued_executed] must be a table.")
    measure = issued.get("measure", "pct_executed_now")
    if measure not in ISSUED_EXECUTED_MEASURES:
        raise ClientConfigError(
            f"{client_id}: issued_executed 'measure' must be one of: "
            f"{', '.join(ISSUED_EXECUTED_MEASURES)}."
        )

    overdue = _overdue(client_id, data.get("overdue", {}), status_classes)

    return ClientConfig(
        client_id=client_id,
        name=str(data.get("name", client_id)),
        sites=tuple(sites),
        history_start=history_start,
        status_classes=status_classes,
        corrective_worktypes=corrective,
        currency=currency,
        crew_field=crew_field,
        preventive_worktypes=preventive,
        week_start=week_start,
        modality_field=modality_field,
        issued_executed_measure=measure,
        **overdue,
    )


def _overdue(client_id: str, data, status_classes: dict[str, str]) -> dict:
    if not isinstance(data, dict):
        raise ClientConfigError(f"{client_id}: [overdue] must be a table.")
    statuses = _worktypes(client_id, data, "statuses")
    unknown = [s for s in statuses if status_classes.get(s) != OPEN]
    if unknown:
        raise ClientConfigError(
            f"{client_id}: overdue statuses must be open statuses: {', '.join(unknown)}."
        )
    date_field = data.get("date_field", DEFAULT_OVERDUE_DATE_FIELD)
    if date_field not in OVERDUE_DATE_FIELDS:
        raise ClientConfigError(
            f"{client_id}: overdue 'date_field' must be one of: {', '.join(OVERDUE_DATE_FIELDS)}."
        )
    tolerance = data.get("tolerance_days", 0)
    if (
        isinstance(tolerance, bool)
        or not isinstance(tolerance, int)
        or not 0 <= tolerance <= MAX_TOLERANCE_DAYS
    ):
        raise ClientConfigError(
            f"{client_id}: overdue 'tolerance_days' must be an integer from 0 to "
            f"{MAX_TOLERANCE_DAYS}."
        )
    return {
        "overdue_statuses": statuses,
        "overdue_date_field": date_field,
        "overdue_tolerance_days": tolerance,
    }


def _worktypes(client_id: str, data: dict, key: str) -> tuple[str, ...]:
    codes = data.get(key, [])
    if not isinstance(codes, list) or not all(isinstance(w, str) and w for w in codes):
        raise ClientConfigError(f"{client_id}: '{key}' must be a list of codes.")
    return tuple(codes)
