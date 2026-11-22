"""The generated reference page (tools/reference.py) matches the code: run
``python tools/reference.py`` to bring them up to date."""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def reference():
    spec = importlib.util.spec_from_file_location("reference", ROOT / "tools" / "reference.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["reference"] = module          # its dataclass looks itself up there
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generated(reference):
    return reference.pages()


@pytest.mark.parametrize("name", ["commands.md"])
def test_the_page_is_up_to_date(generated, name):
    pages, _ = generated
    path = ROOT / "docs" / "reference" / name
    assert path.read_text() == pages[path], \
        f"docs/reference/{name} is out of date: run python tools/reference.py"


def test_every_command_is_on_the_page(reference):
    text = (ROOT / "docs" / "reference" / "commands.md").read_text()
    for name, _, helps in reference.command_groups():
        for action, _ in helps:
            assert f"### `flowreel {name} {action}`" in text
