"""Rules every automation script in maximo_scripts/ must follow."""

import ast
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parents[2] / "maximo_scripts"
SCRIPTS = sorted(SCRIPTS_DIR.glob("*/*.py"))
BEGIN = "# --- BEGIN COMMON"
END = "# --- END COMMON ---"

# Mbo calls that change Maximo data. JSONArray.add (response building) is allowed.
WRITE_CALLS = {"setValue", "save", "changeStatus", "delete", "deleteAll", "addAtEnd"}


def common_block(path):
    text = path.read_text(encoding="utf-8")
    assert text.count(BEGIN) == 1 and text.count(END) == 1, path.name
    return text[text.index(BEGIN) : text.index(END)]


def test_scripts_found():
    assert {path.name for path in SCRIPTS} >= {"QUERYWORKORDERS.py", "QUERYASSETS.py"}


def test_common_block_identical():
    # Decision 2026-10-29: copy the shared code into each script, no library script.
    blocks = {path.name: common_block(path) for path in SCRIPTS}
    reference = blocks["QUERYASSETS.py"]
    for name, block in blocks.items():
        assert block == reference, f"{name}: common block differs from QUERYASSETS.py"


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda path: path.name)
def test_script_is_ascii(path):
    assert path.read_text(encoding="utf-8").isascii()


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda path: path.name)
def test_script_imports_no_python_stdlib(path):
    # Maximo's Jython has no standard library: only Java/Maximo imports.
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    imports = [line.split()[1] for line in lines if line.startswith(("import ", "from "))]
    assert imports
    assert all(name.split(".")[0] in ("java", "psdi", "com") for name in imports)


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda path: path.name)
def test_script_keeps_globals_out_of_top_level_bindings(path):
    # Maximo calls toString on every top-level binding after the script runs; one
    # holding globals() recurses into itself (StackOverflowError -> BMXAA1649E).
    def module_level(nodes):
        for node in nodes:
            if isinstance(node, ast.FunctionDef | ast.ClassDef):
                continue
            yield node
            for field in ("body", "orelse", "handlers", "finalbody"):
                yield from module_level(getattr(node, field, []))

    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in module_level(tree.body):
        if isinstance(node, ast.Assign | ast.AnnAssign | ast.AugAssign):
            value = node.value
            assert not (
                isinstance(value, ast.Call) and getattr(value.func, "id", None) == "globals"
            ), f"line {node.lineno}: top-level binding holds globals()"


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda path: path.name)
def test_script_never_writes(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert not calls & WRITE_CALLS
