"""Refusing a render that cannot fit, and a windowed source's own estimate."""
import pytest

from flowreel.scene import memory
from flowreel.scene.memory import BASE_BYTES, GB, NotEnoughMemory, check_fits, estimate_job
from flowreel.scene.rendering import Scene, render
from flowreel.sources.flexflow import FlexflowSource

from conftest import ToySource
from test_plt_window import BOX, NX, NY, NZ, case  # noqa: F401
from test_render import VIEWS, toy_shot


class Heavy(ToySource):
    """A source that says each step needs 1 GB."""

    def memory_per_step(self, crop):
        return 1.0


def test_jobs_that_fit_and_jobs_that_do_not():
    scene = Scene.make(toy_shot(), Heavy(), VIEWS)
    per_job = BASE_BYTES + GB
    assert estimate_job(scene) == per_job
    room = 10 * GB                                   # 8 GB usable: four jobs of 1.7 GB
    assert check_fits(scene, [0, 1], 4, available=room) == per_job
    with pytest.raises(NotEnoughMemory, match=r"-j 5 needs about 8\.5 GB .* use -j 4 or fewer"):
        check_fits(scene, [0, 1], 5, available=room)
    with pytest.raises(NotEnoughMemory, match=r"one frame needs about 1\.7 GB .* crop"):
        check_fits(scene, [0], 1, available=GB)


def test_render_refuses_before_drawing(tmp_path, monkeypatch):
    monkeypatch.setattr(memory, "available_memory", lambda: GB)
    with pytest.raises(NotEnoughMemory):
        render(toy_shot(), source=Heavy(), views=VIEWS, out=tmp_path, processes=False)
    assert not (tmp_path / "toy").exists()
    report = render(toy_shot(), [0], source=Heavy(), views=VIEWS, out=tmp_path,
                    processes=False, check_memory=False)
    assert report.count("rendered") == 1


def test_no_estimate_no_check():
    class Silent(ToySource):
        memory_per_step = None
    assert estimate_job(Scene.make(toy_shot(), Silent(), VIEWS)) is None


def test_a_windowed_estimate_follows_the_window(case):  # noqa: F811
    src = FlexflowSource(case, cache=None)
    whole, window = src.memory_per_step(None), src.memory_per_step(BOX)
    nodes, cells = 41 * (NY + 1) * (NZ + 1), 40 * NY * NZ
    assert window == pytest.approx(2 * (nodes * 7 * 4 + cells * 9 * 8) / 1e9)
    assert whole > 9 * window                        # 400 cells along against 40
