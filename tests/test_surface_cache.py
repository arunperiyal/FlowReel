"""Frozen shots contour once: later frames read the surface and never load the flow."""
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from flowreel import sources
from flowreel.scene.rendering import Scene
from flowreel.scene.shot import load

from conftest import ToySource
from test_render import VIEWS, toy_shot

REVEAL = Path(__file__).parent / "data" / "reveal"


class Counting(ToySource):
    def __init__(self):
        super().__init__()
        self.reads = 0

    def flow(self, step, fields, crop):
        self.reads += 1
        return super().flow(step, fields, crop)


def iso_shot(time, level=0.5, **iso):
    return toy_shot(time=time, layers=[{"type": "iso", "field": "speed", "level": level, **iso}])


def draw(scene, index):
    try:
        return scene.draw(index)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")


def test_a_frozen_shot_reads_the_flow_once(tmp_path):
    src = Counting()
    scene = Scene.make(iso_shot({"frozen": 10, "frames": 3}), src, VIEWS, cache=tmp_path)
    first = draw(scene, 0)
    assert src.reads == 1 and scene.cache.misses == 1
    again = draw(Scene.make(iso_shot({"frozen": 10, "frames": 3}), src, VIEWS, cache=tmp_path), 2)
    assert src.reads == 1                                   # read from the cache
    assert np.array_equal(first, again)
    plain = draw(Scene.make(iso_shot({"frozen": 10, "frames": 3}), ToySource(), VIEWS), 0)
    assert np.array_equal(first, plain)                     # the cache changes nothing


def test_a_level_track_keeps_one_surface_per_level(tmp_path):
    level = {"keys": [[0, 0.4], [1, 0.4], [2, 0.6]]}
    scene = Scene.make(iso_shot({"frozen": 0, "frames": 3}, level=level), Counting(), VIEWS,
                       cache=tmp_path)
    for i in range(3):
        draw(scene, i)
    assert (scene.cache.misses, scene.cache.hits) == (2, 1)
    assert len(list(tmp_path.glob("*.vtp"))) == 2


def test_a_moving_shot_has_no_cache(tmp_path):
    scene = Scene.make(iso_shot({"steps": [0, 20]}), Counting(), VIEWS, cache=tmp_path)
    assert scene.cache is None


def test_grow_works_on_a_cached_surface(tmp_path):
    shot = iso_shot({"frozen": 0, "frames": 2}, grow_axis="z", grow=0.5)
    src = Counting()
    a = draw(Scene.make(shot, src, VIEWS, cache=tmp_path), 0)
    b = draw(Scene.make(shot, src, VIEWS, cache=tmp_path), 1)
    assert src.reads == 1 and np.array_equal(a, b)


def test_the_reveal_frame_from_a_cached_surface_matches_the_golden_frame(tmp_path):
    from test_reveal_golden import CLEAR_LIMIT, MEAN_LIMIT, difference
    source = sources.create("vtk", path=str(REVEAL / "flow_*.vti"), body=str(REVEAL / "body.vtp"))
    golden = np.asarray(Image.open(REVEAL / "golden.png").convert("RGB"))
    draw(Scene.make(load(REVEAL / "reveal.yml"), source, cache=tmp_path), 0)
    picture = draw(Scene.make(load(REVEAL / "reveal.yml"), source, cache=tmp_path), 16)
    mean, clear = difference(picture, golden)
    assert mean < MEAN_LIMIT and clear < CLEAR_LIMIT, (mean, clear)


def test_a_frozen_render_in_processes_fills_the_cache_once(tmp_path):
    from flowreel.scene import render
    try:
        report = render(iso_shot({"frozen": 0, "frames": 3}), source=ToySource(), views=VIEWS,
                        out=tmp_path, jobs=3)
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    assert report.count("rendered") == 3
    assert len(list((tmp_path / ".cache" / "surfaces").glob("*.vtp"))) == 1


def test_same_relative_source_in_two_folders_is_two_sources(tmp_path):
    """Two shot files that both write path: flow_*.vti mean two data sets: their surfaces
    and frames must not share keys (the domain shot once drew the reveal's wake)."""
    from flowreel.scene.rendering import source_id
    from flowreel.scene.shot import from_dict
    from tag_fixture import tag_project
    spec = {"name": "s", "source": "c", "time": {"frozen": 0}, "camera": {"view": "main"},
            "layers": [{"type": "outline"}]}
    for folder in ("a", "b"):
        tag_project(tmp_path / folder, "c", kind="vtk", source={"path": "flow_*.vti", "body": "b.vtp"})
    a = from_dict(spec, file=str(tmp_path / "a" / "s.yml"))
    b = from_dict(spec, file=str(tmp_path / "b" / "s.yml"))
    assert source_id(a) != source_id(b)
    assert source_id(a)[1]["source"]["path"] == str(tmp_path / "a" / "data" / "c" / "flow_*.vti")
