"""rate: output panels (plan Section 9.3): drawn at the film's output frames."""
import numpy as np
import pytest
from PIL import Image

from flowreel import compose
from flowreel.compose.rate import output_positions, times_at
from tests.test_layout_panels import setup


def test_output_positions_between_frames_and_through_holds():
    assert output_positions(3) == [0, 1, 2]
    assert output_positions(3, 2) == [0, 0.5, 1, 1.5, 2]
    assert output_positions(3, 2, holds=[(1, 3)]) == [0, 0.5, 1, 1, 1, 1, 1.5, 2]
    assert output_positions(2, 4, holds=[(0.6, 2)]) == [0, 0.25, 0.5, 0.6, 0.6, 0.75, 1]
    assert output_positions(2, 1, holds=[(5, 2)]) == [0, 1, 1, 1]          # past the end
    with pytest.raises(ValueError):
        output_positions(0)
    with pytest.raises(ValueError):
        output_positions(2, 0)


def test_times_at_interpolates_and_holds_at_the_ends():
    assert times_at([0, 1, 3], [0, 0.5, 1, 1.5, 2, 2.5, -1]) == [0, 0.5, 1, 2, 3, 3, 0]


def test_without_output_the_tile_is_composed_like_any_panel(tmp_path):
    folder, lay = setup(tmp_path, rate="output")
    rep = compose.layout(lay, folder / "out", panels={"processes": False})
    assert rep.count("composed") == 3 and rep.overlays == []


def test_with_output_the_panel_is_drawn_per_output_frame(tmp_path):
    folder, lay = setup(tmp_path, rate="output")
    output = output_positions(3, 3, holds=[(1, 2)])               # 7 + 2 output frames
    rep = compose.layout(lay, folder / "out", output=output, panels={"processes": False})
    assert rep.count("composed") == 3                              # the flow, at its rate
    composed = np.asarray(Image.open(rep.folder / "frame_00000.png"))
    assert (composed[:, 40:] == 0).all()                           # the panel left out
    (tile, panel), = rep.overlays
    assert tile.at == (40, 0) and tile.size == (80, 60)
    assert panel.folder == folder / "out" / "lift_output" and panel.count("drawn") == 9
    held = [np.asarray(Image.open(panel.folder / f"frame_{j:05d}.png")) for j in (3, 4, 5)]
    assert (held[0] == held[1]).all() and (held[1] == held[2]).all()
    assert not (held[0] == np.asarray(Image.open(panel.folder / "frame_00002.png"))).all()
    again = compose.layout(lay, folder / "out", output=output, panels={"processes": False})
    assert again.overlays[0][1].count("skipped") == 9


def test_a_layout_of_output_panels_only_composes_nothing(tmp_path):
    folder, lay = setup(tmp_path, rate="output")
    from dataclasses import replace
    lay = replace(lay, tiles=lay.tiles[1:])
    rep = compose.layout(lay, folder / "out", output=[0, 0.5, 1], panels={"processes": False})
    assert rep.frames == [] and rep.overlays[0][1].count("drawn") == 3


def dot_row(path, colour=(255, 0, 0)):
    """Row of the series' dot: the mean row of the line's colour at its right end."""
    p = np.asarray(Image.open(path).convert("RGB")).astype(int)
    mask = (np.abs(p - colour).sum(axis=2) < 60)
    rows, cols = np.nonzero(mask)
    end = cols >= cols.max() - 3
    return rows[end].mean(), cols.max()


def test_a_dot_drawn_between_two_flow_frames_lies_between_their_values(tmp_path):
    import yaml
    folder, _ = setup(tmp_path)
    (folder / "motion.yml").write_text(yaml.safe_dump(
        {"type": "series", "size": [200, 150], "times": [0.0, 1.0, 2.0],
         "x": {"range": [0, 2]}, "y": {"range": [0, 4]}, "legend": False,
         "lines": [{"body": "bare", "series": "motion", "column": "y", "colour": "#ff0000"}]}))
    lay = compose.from_dict({"size": [240, 150], "tiles": [
        {"frames": "flow", "at": [0, 0], "size": [40, 30]},
        {"panel": "motion.yml", "rate": "output", "at": [40, 0], "size": [200, 150]}]},
        file=str(folder / "board.yml"))
    rep = compose.layout(lay, folder / "out", output=output_positions(3, 2),
                         panels={"processes": False})
    folder_out = rep.overlays[0][1].folder
    (r0, c0), (r_half, c_half), (r1, c1) = (dot_row(folder_out / f"frame_{j:05d}.png")
                                            for j in (0, 1, 2))
    # y = t^2: 0 at the first flow frame, 1 at the second, 0.25 between them (t = 0.5)
    assert r1 < r_half < r0                                       # higher value, higher up
    assert c0 < c_half < c1                                       # and between in time
    expected = r0 + (r1 - r0) * 0.25                              # the value, not the mean
    assert abs(r_half - expected) < 2
