import pytest

from flowreel.scene import layers as L
from flowreel.scene.errors import ConfigError
from flowreel.scene.plan import plan
from flowreel.scene.shot import from_dict


class Clock:
    """A source with steps 0, 10, ..., 90 at time 0.5 per saved step."""
    def steps(self):
        return list(range(0, 100, 10))

    def time(self, step):
        return step / 20


@pytest.fixture(autouse=True)
def _layer():
    if "plan_dummy" not in L.available():
        @L.register
        class D(L.Layer):
            name = "plan_dummy"
            options = (L.Option("opacity", "number", default=1.0),
                       L.Option("level", "number", default=-0.1))


def make(time, layers=None):
    layers = layers or [{"type": "plan_dummy"}]
    return from_dict({"name": "s", "source": "toy:x", "time": time, "layers": layers})


def test_plan_gives_step_time_and_values_per_frame():
    shot = make({"steps": [20, 60], "every": 2},
                [{"type": "plan_dummy", "opacity": {"from": 0, "to": 1, "frames": [0, 2], "ease": "linear"}},
                 {"type": "plan_dummy", "level": -0.5}])
    p = plan(shot, Clock())
    assert p.n_frames == 3 and not p.frozen
    f = p.frame(1)
    assert (f.index, f.step, f.time) == (1, 40, 2.0)
    assert f.values[0]["opacity"] == 0.5 and f.values[0]["level"] == -0.1
    assert f.values[1]["level"] == -0.5
    assert [x.step for x in p] == [20, 40, 60]


def test_frozen_plan_still_varies_values():
    p = plan(make({"frozen": 30, "frames": 3},
                  [{"type": "plan_dummy", "level": {"keys": [[0, 0], [2, 1]], "ease": "linear"}}]),
             Clock())
    assert p.frozen and {p.frame(i).step for i in range(3)} == {30}
    assert [p.frame(i).values[0]["level"] for i in range(3)] == [0, 0.5, 1]


def test_time_errors_name_the_shot_file():
    shot = make({"steps": [500, 600]})
    shot.file = "reveal.yml"
    with pytest.raises(ConfigError, match=r"reveal.yml: time.steps: no saved step"):
        plan(shot, Clock())
