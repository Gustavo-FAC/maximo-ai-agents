import datetime

import pytest

from maximo_agents.analysis.config import (
    CANCELLED,
    CLOSED,
    EXECUTED,
    OPEN,
    ClientConfigError,
    load_client_config,
    parse_client_config,
)

VALID = {
    "name": "Teste",
    "sites": ["S1"],
    "history_start": "2020-01-01",
    "statuses": {"A": {"internal": "WAPPR"}, "B": {"internal": "INPRG", "class": "executed"}},
}


def test_itambe_status_classes():
    config = load_client_config("itambe")
    assert config.sites == ("FABRICA", "MINERACAO")
    assert config.history_start == datetime.date(2006, 1, 1)
    assert config.class_of("POSEXEC") == EXECUTED  # decisão do usuário, 2026-11-06
    assert config.class_of("PREVCAN") == CANCELLED  # interno CLOSE, exceção
    assert config.class_of("APROG") == OPEN
    assert config.class_of("CONCL") == CLOSED
    assert config.class_of("FECHAR") == CLOSED
    assert config.class_of("CANCEL") == CANCELLED
    assert config.class_of("NOVO") is None
    assert config.class_of(None) is None
    assert config.statuses_of(OPEN) == sorted(
        "AAPROV AGENV ACONDF APPR APRV APROG WMATL AGEXEC AGEXECFIL AGINSP DEVPCM EMAND "
        "INPRG OSFILENC".split()
    )
    assert config.statuses_of(EXECUTED) == ["POSEXEC"]
    assert len(config.status_classes) == 22  # domínio SYNONYM da Itambé + AMATER antigo
    assert config.class_of("AMATER") == "open"
    assert config.corrective_worktypes == ("CO", "EM")


def test_class_from_internal_value_or_explicit():
    config = parse_client_config("t", VALID)
    assert config.status_classes == {"A": OPEN, "B": EXECUTED}
    assert config.name == "Teste"
    assert config.corrective_worktypes == ()  # opcional


@pytest.mark.parametrize(
    "change",
    [
        {"statuses": {}},
        {"statuses": {"A": {"internal": "XYZ"}}},  # interno desconhecido sem class
        {"statuses": {"A": {"class": "pending"}}},
        {"statuses": {"A": "WAPPR"}},
        {"history_start": "01/01/2020"},
        {"sites": "S1"},
        {"sites": [""]},
        {"corrective_worktypes": "CO"},
        {"corrective_worktypes": ["CO", ""]},
    ],
)
def test_invalid_config(change):
    with pytest.raises(ClientConfigError):
        parse_client_config("t", {**VALID, **change})


def test_missing_history_start():
    data = dict(VALID)
    del data["history_start"]
    with pytest.raises(ClientConfigError):
        parse_client_config("t", data)


@pytest.mark.parametrize("client_id", ["../itambe", "itambe.toml", "", "nao_existe"])
def test_bad_or_unknown_client(client_id):
    with pytest.raises(ClientConfigError):
        load_client_config(client_id)
