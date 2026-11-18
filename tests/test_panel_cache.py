"""Panel frames are skipped unless their key (settings, time, style, files) changed."""
import os

from flowreel.compose import panels
from flowreel.compose.panel_file import from_dict

from test_panel_loop import Bar, bar  # noqa: F401  (registers test_bar)


class Reading(Bar):
    """The test bar, reading a file."""

    name = "test_reading"
    path = None

    def files(self):
        return [self.path]


panels.register(Reading)


def statuses(rep):
    return [f[2] for f in rep.frames]


def test_fresh_frames_are_skipped(tmp_path):
    panels.panel(bar(), tmp_path, processes=False)
    assert statuses(panels.panel(bar(), tmp_path, processes=False)) == ["skipped"] * 3
    assert statuses(panels.panel(bar(), tmp_path, force=True, processes=False)) == ["drawn"] * 3


def test_a_changed_time_settings_or_style(tmp_path):
    panels.panel(bar(), tmp_path, processes=False)
    rep = panels.panel(bar(times=(0.25, 0.6, 1.0)), tmp_path, processes=False)
    assert statuses(rep) == ["skipped", "drawn", "skipped"]
    assert statuses(panels.panel(bar(colour="red"), tmp_path, processes=False)) == ["drawn"] * 3
    rep = panels.panel(bar(colour="red", style={"background": "#202020"}), tmp_path, processes=False)
    assert statuses(rep) == ["drawn"] * 3


def test_a_rewritten_file(tmp_path):
    data = tmp_path / "data.csv"
    data.write_text("1\n")
    Reading.path = data
    pf = from_dict({"type": "test_reading", "size": [40, 10], "times": [0.5]}, file="r.yml")
    panels.panel(pf, tmp_path, processes=False)
    assert statuses(panels.panel(pf, tmp_path, processes=False)) == ["skipped"]
    st = data.stat()
    os.utime(data, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
    assert statuses(panels.panel(pf, tmp_path, processes=False)) == ["drawn"]
