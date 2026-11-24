"""The panel file: type, size, times (a list or a shot's frame times) and style."""
import pytest
import yaml

from flowreel.compose.panel_file import from_dict, frame_times, load
from flowreel.compose.style import Style
from flowreel.scene.errors import ConfigError

from tag_fixture import tag_project
from test_plt_window import case  # noqa: F401  (two PLT steps at times 1 and 2)


def test_a_panel_with_a_list_of_times():
    p = from_dict({"type": "series", "size": [320, 200], "times": [0, 0.5, 1],
                   "rows": []}, file="panels/lift.yml")
    assert p.type == "series" and p.name == "lift" and p.size == (320, 200)
    assert frame_times(p) == [0.0, 0.5, 1.0]
    assert p.style == Style() and p.options == {"rows": []}


def test_times_of_a_shot(case):  # noqa: F811
    tag_project(case, "t", kind="plt", source={"path": "../..", "cache": None})
    shot = {"name": "w", "source": "t",
            "time": {"steps": [1, 2]}, "camera": {"view": "v"},
            "layers": [{"type": "outline", "bounds": "domain"}]}
    (case / "w.yml").write_text(yaml.safe_dump(shot))
    p = from_dict({"type": "series", "times": {"shot": "w.yml"}}, file=str(case / "p.yml"))
    assert p.times == (case / "w.yml").resolve()
    assert frame_times(p) == [1.0, 2.0]


def test_style_inline_from_a_file_and_overridden(tmp_path):
    (tmp_path / "film.yml").write_text("font_size: 20\ncolours: ['#ff0000', red]\ntext: white\n")
    (tmp_path / "p.yml").write_text("type: series\ntimes: [0]\n"
                                    "style: {from: film.yml, font_size: 12, maths: cm}\n")
    s = load(tmp_path / "p.yml").style
    assert (s.font_size, s.maths, s.text, s.colours) == (12, "cm", "white", ("#ff0000", "red"))
    (tmp_path / "q.yml").write_text("type: series\ntimes: [0]\nstyle: film.yml\n")
    assert load(tmp_path / "q.yml").style.font_size == 20


@pytest.mark.parametrize("data, msg", [
    ({"times": [0]}, r"p\.yml: missing key 'type'"),
    ({"type": "series"}, r"missing key 'times'"),
    ({"type": "series", "times": []}, r"times: expected at least 1 entries"),
    ({"type": "series", "times": [1, 0.5]}, r"times\[1\]: times must not decrease"),
    ({"type": "series", "times": {"shot": "nope.yml"}}, r"times\.shot: no shot file"),
    ({"type": "series", "times": [0], "size": [10]}, r"size: expected \[width, height\]"),
    ({"type": "series", "times": [0], "style": {"maths": "lato"}}, r"style\.maths: 'lato' is not allowed"),
    ({"type": "series", "times": [0], "style": {"text": "#12"}}, r"style\.text: expected a colour"),
    ({"type": "series", "times": [0], "style": {"line_width": 0}}, r"style\.line_width: must be positive"),
    ({"type": "series", "times": [0], "style": {"fontsize": 3}}, r"style\.fontsize: unknown key .*'font_size'"),
    ({"type": "series", "times": [0], "style": "none.yml"}, r"style\.from: no style file"),
])
def test_errors(data, msg):
    with pytest.raises(ConfigError, match=msg):
        from_dict(data, file="p.yml")
