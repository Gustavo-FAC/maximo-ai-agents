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
        "AAPROV AGENV ACONDF APPR APRV APROG WMATL AMATER AGEXEC AGEXECFIL AGINSP DEVPCM "
        "EMAND INPRG OSFILENC".split()
    )
    assert config.statuses_of(EXECUTED) == ["POSEXEC"]
    assert len(config.status_classes) == 22  # domínio SYNONYM da Itambé + AMATER antigo
    assert config.class_of("AMATER") == "open"
    assert config.corrective_worktypes == ("CO", "EM")
    assert config.currency == "BRL"
    assert config.crew_field == "crewid"  # persongroup vazio na Itambé
    assert config.preventive_worktypes == ("MPV", "MPR", "INSP", "IL", "MS")
    assert config.week_start == "sunday"
    assert config.modality_field == "modalidade"


def test_class_from_internal_value_or_explicit():
    config = parse_client_config("t", VALID)
    assert config.status_classes == {"A": OPEN, "B": EXECUTED}
    assert config.name == "Teste"
    assert config.corrective_worktypes == ()  # opcional
    assert config.currency is None  # opcional
    assert config.crew_field == "persongroup"  # padrão
    assert config.preventive_worktypes == ()  # opcional
    assert config.week_start is None  # opcional
    assert config.modality_field is None  # opcional
    assert config.issued_executed_measure == "pct_executed_now"  # padrão


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
        {"currency": "R$"},
        {"currency": "brl"},
        {"currency": "REAL"},
        {"preventive_worktypes": "MPV"},
        {"week_start": "friday"},
        {"currency": 986},
        {"crew_field": "ownergroup"},
        {"crew_field": "CREWID"},
        {"overdue": "A"},
        {"overdue": {"statuses": ["B"]}},  # executada, não aberta
        {"overdue": {"statuses": ["X"]}},  # status desconhecido
        {"overdue": {"date_field": "reportdate"}},
        {"overdue": {"tolerance_days": -1}},
        {"overdue": {"tolerance_days": 366}},
        {"overdue": {"tolerance_days": "7"}},
        {"overdue": {"tolerance_days": True}},
        {"modality_field": "MODALIDADE"},
        {"modality_field": "modalidade; drop"},
        {"modality_field": 1},
        {"issued_executed": "pct_executed_now"},
        {"issued_executed": {"measure": "executed_now"}},
        {"preventive_compliance": []},
        {"preventive_compliance": {"done_statuses": ["A"]}},  # aberta, não concluída
        {"preventive_compliance": {"pending_statuses": ["B"]}},  # executada
        {"preventive_compliance": {"pending_statuses": ["X"]}},  # desconhecido
    ],
)
def test_invalid_config(change):
    with pytest.raises(ClientConfigError):
        parse_client_config("t", {**VALID, **change})


def test_overdue_defaults_and_values():
    config = parse_client_config("t", VALID)
    assert config.overdue_status_list() == ["A"]  # sem regra: todos os abertos
    assert config.overdue_date_field == "targstartdate"
    assert config.overdue_tolerance_days == 0
    config = parse_client_config(
        "t",
        {**VALID, "overdue": {"statuses": ["A"], "date_field": "schedstart", "tolerance_days": 3}},
    )
    assert config.overdue_statuses == ("A",)
    assert config.overdue_date_field == "schedstart"
    assert config.overdue_tolerance_days == 3


def test_missing_history_start():
    data = dict(VALID)
    del data["history_start"]
    with pytest.raises(ClientConfigError):
        parse_client_config("t", data)


@pytest.mark.parametrize("client_id", ["../itambe", "itambe.toml", "", "nao_existe"])
def test_bad_or_unknown_client(client_id):
    with pytest.raises(ClientConfigError):
        load_client_config(client_id)
