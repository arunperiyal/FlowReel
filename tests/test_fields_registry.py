"""The field registry: declared needs, evaluation order, parameters."""
import numpy as np
import pytest

from flowreel import fields


@pytest.fixture
def scratch():
    """Register throw-away fields and remove them afterwards."""
    names = []

    def add(name, needs=()):
        names.append(name)
        return fields.register(name, needs)

    yield add
    for name in names:
        fields.unregister(name)


def test_raw_inputs_from_components_or_vector(toy_source):
    g = toy_source.flow(0, ["U", "V", "W", "p"], None)
    out = fields.compute(g, ["velocity", "pressure"])
    assert out["velocity"].shape == (g.n_points, 3)
    assert np.array_equal(out["velocity"][:, 1], g["V"])
    assert np.array_equal(out["pressure"], g["p"])
    h = g.copy()
    h.clear_data()
    h["velocity"] = out["velocity"] * 2
    assert np.array_equal(fields.compute(h, "velocity")["velocity"], out["velocity"] * 2)


def test_missing_input_is_reported(toy_source):
    g = toy_source.flow(0, ["U", "V"], None)
    with pytest.raises(KeyError, match="W"):
        fields.compute(g, "velocity")
    with pytest.raises(KeyError, match="'p'"):
        fields.compute(g, "pressure")


def test_shared_need_is_computed_once(toy_source, scratch):
    calls = []

    @scratch("_base", "velocity")
    def base(grid, velocity):
        calls.append("base")
        return velocity[:, 0]

    @scratch("_a", "_base")
    def a(grid, base):
        return base + 1

    @scratch("_b", ("_base", "_a"))
    def b(grid, base, a):
        return base + a

    g = toy_source.flow(0, ["U", "V", "W"], None)
    out = fields.compute(g, ["_b", "_a"])
    assert calls == ["base"]
    assert set(out) == {"_a", "_b"}
    assert np.allclose(out["_b"], 2 * g["U"] + 1)
    assert fields.resolve(["_b"]) == ["velocity", "_base", "_a", "_b"]
    assert set(g.point_data.keys()) == {"U", "V", "W"}  # the grid is left alone


def test_parameters_required_optional_unknown(toy_source, scratch):
    @scratch("_scaled", "velocity")
    def scaled(grid, velocity, *, factor, shift=0.0):
        return factor * velocity + shift

    g = toy_source.flow(0, ["U", "V", "W"], None)
    assert fields.describe("_scaled").required == ("factor",)
    with pytest.raises(TypeError, match="factor"):
        fields.compute(g, "_scaled")
    with pytest.raises(TypeError, match="fcator"):
        fields.compute(g, "_scaled", factor=2, fcator=3)
    out = fields.compute(g, "_scaled", factor=2, shift=1)["_scaled"]
    assert np.allclose(out[:, 0], 2 * g["U"] + 1)


def test_unknown_duplicate_and_circular(scratch):
    with pytest.raises(KeyError, match="available"):
        fields.resolve(["_nope"])
    scratch("_x", "_y")(lambda grid, y: y)
    scratch("_y", "_x")(lambda grid, x: x)
    with pytest.raises(ValueError, match="circular"):
        fields.resolve(["_x"])
    with pytest.raises(ValueError, match="already"):
        fields.register("_x")(lambda grid: 0)
