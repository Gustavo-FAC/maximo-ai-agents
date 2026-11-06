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

    def statuses_of(self, *classes: str) -> list[str]:
        """Status externos das classes pedidas, em ordem alfabética."""
        return sorted(s for s, c in self.status_classes.items() if c in classes)

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

    corrective = data.get("corrective_worktypes", [])
    if not isinstance(corrective, list) or not all(isinstance(w, str) and w for w in corrective):
        raise ClientConfigError(f"{client_id}: 'corrective_worktypes' must be a list of codes.")

    currency = data.get("currency")
    if currency is not None and not (
        isinstance(currency, str)
        and len(currency) == 3
        and currency.isascii()
        and currency.isalpha()
        and currency.isupper()
    ):
        raise ClientConfigError(f"{client_id}: 'currency' must be an ISO 4217 code (e.g. BRL).")

    return ClientConfig(
        client_id=client_id,
        name=str(data.get("name", client_id)),
        sites=tuple(sites),
        history_start=history_start,
        status_classes=status_classes,
        corrective_worktypes=tuple(corrective),
        currency=currency,
    )
