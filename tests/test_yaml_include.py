"""include: in any YAML file (yamlfile.py)."""
import pytest

from flowreel.scene.errors import ConfigError
from flowreel.yamlfile import merged, read_yaml


def test_a_mapping_includes_mappings_beneath_its_own_keys(tmp_path):
    (tmp_path / "styles").mkdir()
    (tmp_path / "styles" / "film.yml").write_text(
        "fps: 24\nstyle: {font: Lato, caption: {size: 50, box: false}}\n")
    (tmp_path / "styles" / "more.yml").write_text("style: {caption: {box: true}}\nsize: [8, 8]\n")
    (tmp_path / "film.yml").write_text(
        "include: [styles/film.yml, styles/more.yml]\nsize: [1280, 720]\n"
        "style: {caption: {size: 40}}\n")
    assert read_yaml(tmp_path / "film.yml") == {
        "fps": 24, "size": [1280, 720],
        "style": {"font": "Lato", "caption": {"size": 40, "box": True}}}


def test_a_list_entry_includes_a_list(tmp_path):
    (tmp_path / "common.yml").write_text("- {lines: [one]}\n- {lines: [two]}\n")
    (tmp_path / "text.yml").write_text("- include: common.yml\n- {lines: [three], at: 2}\n")
    assert [d["lines"][0] for d in read_yaml(tmp_path / "text.yml")] == ["one", "two", "three"]


def test_includes_nest_and_resolve_from_their_own_folder(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "inner.yml").write_text("x: 1\n")
    (tmp_path / "a" / "outer.yml").write_text("include: inner.yml\ny: 2\n")
    (tmp_path / "top.yml").write_text("include: a/outer.yml\nz: {include: a/inner.yml}\n")
    assert read_yaml(tmp_path / "top.yml") == {"x": 1, "y": 2, "z": {"x": 1}}


def test_errors(tmp_path):
    (tmp_path / "self.yml").write_text("include: self.yml\n")
    with pytest.raises(ConfigError, match="includes itself"):
        read_yaml(tmp_path / "self.yml")
    (tmp_path / "gone.yml").write_text("include: missing.yml\n")
    with pytest.raises(ConfigError, match=r"gone.yml: include: no file"):
        read_yaml(tmp_path / "gone.yml")
    (tmp_path / "list.yml").write_text("- 1\n")
    (tmp_path / "wrong.yml").write_text("include: list.yml\n")
    with pytest.raises(ConfigError, match="only a mapping"):
        read_yaml(tmp_path / "wrong.yml")
    (tmp_path / "map.yml").write_text("a: 1\n")
    (tmp_path / "wrong2.yml").write_text("- include: map.yml\n")
    with pytest.raises(ConfigError, match="only a list"):
        read_yaml(tmp_path / "wrong2.yml")


def test_shots_and_layouts_include_too(tmp_path):
    from flowreel.film.model import load_layout
    (tmp_path / "base.yml").write_text("background: '#101010'\n")
    (tmp_path / "lay.yml").write_text(
        "include: base.yml\nboxes: [{shape: rectangle, pos: [0, 0], size: [10, 10]}]\n")
    lay = load_layout(tmp_path / "lay.yml")
    assert lay.background == "#101010" and len(lay.boxes) == 1
