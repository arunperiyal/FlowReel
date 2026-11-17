import pytest

from flowreel.scene import layers as L
from flowreel.scene.errors import Checker, ConfigError


@L.register
class Probe(L.Layer):
    name = "probe"
    options = (
        L.Option("field", track=False, required=True),
        L.Option("opacity", "number", default=1.0),
        L.Option("colour", "colour", default="#ff0000"),
        L.Option("style", "choice", default="solid", choices=("solid", "ghost")),
    )


def build(**spec):
    return L.build({"type": "probe", "field": "Q", **spec}, Checker("s.yml", ("layers", 0)))


def test_defaults_and_raw_options():
    v = build().values(0)
    assert v["field"] == "Q" and v["opacity"] == 1.0 and v["style"] == "solid"


def test_options_are_tracks():
    layer = build(opacity={"from": 0, "to": 1, "frames": [0, 10]})
    assert layer.values(0)["opacity"] == 0 and layer.values(10)["opacity"] == 1
    assert 0 < layer.values(5)["opacity"] < 1


def test_registry_lists_and_rejects_duplicates():
    assert "probe" in L.available() and L.layer_type("probe") is Probe
    with pytest.raises(ValueError, match="already registered"):
        L.register(Probe)


@pytest.mark.parametrize("spec, msg", [
    ({"type": "prob", "field": "Q"}, r"layers\[0\].type: .*did you mean 'probe'"),
    ({"type": "probe"}, r"missing key 'field'"),
    ({"type": "probe", "field": "Q", "style": "ghots"}, r"layers\[0\].style: .*did you mean 'ghost'"),
    ({"type": "probe", "field": "Q", "opacity": {"from": 0}}, r"layers\[0\].opacity: opacity: missing key"),
    ({"type": "probe", "field": "Q", "colour": "nope"}, r"layers\[0\].colour"),
])
def test_errors_name_the_place(spec, msg):
    with pytest.raises(ConfigError, match=msg):
        L.build(spec, Checker("s.yml", ("layers", 0)))


def test_base_draw_is_not_implemented():
    with pytest.raises(NotImplementedError):
        build().draw(None, L.Frame(0, 0, 0.0))
