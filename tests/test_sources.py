import pytest

from flowreel import sources
from flowreel.box import Box
from flowreel.sources import Source


def test_toy_source_satisfies_protocol(toy_source):
    assert isinstance(toy_source, Source)


def test_flow_returns_requested_fields_only(toy_source):
    g = toy_source.flow(0, ["U", "p"], None)
    assert set(g.point_data.keys()) == {"U", "p"}


def test_flow_crop_reduces_cells(toy_source):
    full = toy_source.flow(0, ["U"], None)
    part = toy_source.flow(0, ["U"], Box((-1, -1, 0), (0, 0, 1)))
    assert 0 < part.n_cells < full.n_cells


def test_series_has_time_column(toy_source):
    assert list(toy_source.series("x").columns)[0] == "time"


def test_register_and_create(toy_source):
    sources.register("toy-test", lambda **kw: toy_source)
    assert "toy-test" in sources.available()
    assert sources.create("toy-test") is toy_source
    with pytest.raises(ValueError):
        sources.register("toy-test", lambda **kw: toy_source)


def test_unknown_adapter_lists_available():
    with pytest.raises(KeyError, match="available"):
        sources.create("nope")
