"""The generated reference pages (tools/reference.py) match the code: run
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


@pytest.mark.parametrize("name", ["commands.md", "yaml.md"])
def test_the_page_is_up_to_date(generated, name):
    pages, _ = generated
    path = ROOT / "docs" / "reference" / name
    assert path.read_text() == pages[path], \
        f"docs/reference/{name} is out of date: run python tools/reference.py"


def test_every_key_the_code_accepts_is_documented(generated):
    _, missing = generated
    assert missing == [], "keys without a row in their guide page:\n" + "\n".join(missing)


def test_every_command_is_on_the_page(reference):
    text = (ROOT / "docs" / "reference" / "commands.md").read_text()
    for name, _, helps in reference.command_groups():
        for action, _ in helps:
            assert f"### `{f'flowreel {name} {action}'.rstrip()}`" in text


def test_a_key_is_found_by_its_row(reference):
    rows = [reference.Row(["view"], {"type": "a view name"}, "cameras.md", "a-shots-camera"),
            reference.Row(["keys.view"], {"type": "a view"}, "cameras.md", "camera-tracks"),
            reference.Row(["arrow"], {"keys": "`from`, `to`; `width`"}, "captions.md", "shapes")]
    assert reference.find_row(rows, "camera.view").names == ["view"]
    assert reference.find_row(rows, "tracks.keys.view").names == ["keys.view"]
    assert reference.find_row(rows, "shapes.arrow.width").names == ["arrow"]
    assert reference.find_row(rows, "shapes.arrow.colour") is None
    assert reference._match_path("tiles[].stations", "shot") == "tiles.stations.shot"
    assert reference._match_path("blocks[] (title)", "size") == "blocks.title.size"
    assert reference._match_path("bodies.NAME (virtual)", "shape") == "bodies.shape"
