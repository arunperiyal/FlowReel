"""What the camera editor knows, without a window (plan Section 8.3).

:class:`EditorState` collects views into one camera track of a ``cameras.yml``. Each
saved view is a key of the track at the current *frame* (the frame slider), named
``<track>_<frame>``. Every change is written to the file at once (through
:func:`~flowreel.scene.camera_file.save_cameras`), so closing the window, or a crash,
loses nothing; the views and tracks the file held before are kept, and a track of the
same name is taken up where it was left. A view that another track also uses is never
changed: a key on it that is saved again gets a view of its own.

=============  =========================================================================
Action         Does
=============  =========================================================================
``save``       a key at the current frame from the camera's view; replaces a key already
               at that frame
``undo``       goes back one change (save, replace or undo-able step), and rewrites the file
``replace``    the key nearest the current frame takes the camera's view, keeping its frame
``play``       the track's view at every frame, to show it moving
``next_step``  the next time step of the shot (wrapping round), to frame the view
               against the flow at several moments
=============  =========================================================================
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from flowreel.scene.camera_file import save_cameras
from flowreel.scene.camera_path import CameraTrack, build_track, load_tracks
from flowreel.scene.views import View, load_views


@dataclass
class EditorState:
    """The editor's state: the ``path`` of ``cameras.yml``, the ``track`` being made,
    its length in ``frames``, the shot's time ``steps``, and the ``path`` (``linear`` or
    ``spline``) of the track written. Build with :meth:`open`."""

    path: Path
    track: str
    frames: int
    steps: list[int]
    path_kind: str = "linear"
    frame: int = 0
    step_index: int = 0
    keys: dict[int, View] = field(default_factory=dict)       # frame -> view
    names: dict[int, str] = field(default_factory=dict)       # frame -> view name
    others: dict[str, View] = field(default_factory=dict)     # views not of this track
    tracks: dict[str, CameraTrack] = field(default_factory=dict)
    shared: set = field(default_factory=set)                  # views other tracks use
    history: list = field(default_factory=list)

    @classmethod
    def open(cls, path: str | Path, track: str, frames: int, steps, path_kind: str = "linear"):
        """The editor on ``path`` (made when missing) for camera track ``track``.

        An existing track of that name is taken up: its keys (at whole frames) become the
        editor's, with their view names. ``frames`` is the track's length (at least 1).
        ``steps`` are the time steps the editor can show (at least one)."""
        if frames < 1:
            raise ValueError(f"frames must be at least 1, got {frames}")
        steps = list(steps)
        if not steps:
            raise ValueError("the editor needs at least one time step to show")
        path = Path(path)
        views = load_views(path) if path.exists() else {}
        tracks = load_tracks(path, views) if path.exists() else {}
        state = cls(path, track, int(frames), steps, path_kind)
        old = tracks.pop(track, None)
        if old is not None:
            state.path_kind = old.path
            for frame, view in old.keys:
                name = next(n for n, v in views.items() if v == view)
                state.keys[round(frame)] = view
                state.names[round(frame)] = name
        state.shared = {n for t in tracks.values() for n, v in views.items()
                        if any(k[1] == v for k in t.keys)}
        mine = set(state.names.values()) - state.shared
        state.others = {n: v for n, v in views.items() if n not in mine}
        state.tracks = tracks
        return state

    # -- what is shown --------------------------------------------------------------

    @property
    def step(self) -> int:
        """The time step shown."""
        return self.steps[self.step_index]

    def set_frame(self, frame: int) -> None:
        """Move the frame slider (clamped to the track)."""
        self.frame = min(max(int(round(frame)), 0), self.frames - 1)

    def key_frames(self) -> list[int]:
        """The frames that have a saved key, in order."""
        return sorted(self.keys)

    def next_step(self) -> int:
        """Show the next time step (after the last, the first); returns it."""
        self.step_index = (self.step_index + 1) % len(self.steps)
        return self.step

    def set_step(self, index: int) -> int:
        """Show the step at ``index`` of :attr:`steps` (clamped); returns it."""
        self.step_index = min(max(int(round(index)), 0), len(self.steps) - 1)
        return self.step

    def track_now(self) -> CameraTrack | None:
        """The track as it stands (``None`` with no key yet)."""
        if not self.keys:
            return None
        views = {self.names[f]: v for f, v in self.keys.items()}
        return build_track(views, [(f, self.names[f]) for f in sorted(self.keys)],
                           path=self.path_kind, frames=self.frames)

    def play(self) -> list[View]:
        """The track's view at each of its frames (empty with no key)."""
        track = self.track_now()
        return [] if track is None else [track.at(f) for f in range(self.frames)]

    def status(self) -> str:
        """One line for the window: views saved, frame and step."""
        return (f"track {self.track}: {len(self.keys)} view{'s' * (len(self.keys) != 1)} saved"
                f"   frame {self.frame} of {self.frames - 1}   step {self.step}")

    # -- changes ----------------------------------------------------------------------

    def save(self, view: View) -> str:
        """Save ``view`` as the key at the current frame; returns its name."""
        self._remember()
        name = self._own_name(self.frame)
        self.keys[self.frame] = view.with_(name=name)
        self.names[self.frame] = name
        self.write()
        return name

    def replace(self, view: View) -> int | None:
        """Give the key nearest the current frame ``view``, keeping its frame; returns
        that frame (``None`` with no key)."""
        if not self.keys:
            return None
        nearest = min(self.keys, key=lambda f: (abs(f - self.frame), f))
        self._remember()
        name = self._own_name(nearest)
        self.keys[nearest] = view.with_(name=name)
        self.names[nearest] = name
        self.write()
        return nearest

    def undo(self) -> bool:
        """Go back one change; returns ``False`` when there is nothing to undo."""
        if not self.history:
            return False
        self.keys, self.names = self.history.pop()
        self.write()
        return True

    def write(self) -> Path:
        """Write ``cameras.yml``: the other views and tracks as they were, this track's
        views and the track itself (left out while it has no key). A file left with no
        view at all is moved to ``cameras.yml.bak``."""
        views = dict(self.others)
        views.update({self.names[f]: v for f, v in sorted(self.keys.items())})
        tracks = dict(self.tracks)
        track = self.track_now()
        if track is not None:
            tracks[self.track] = track
        if not views:            # every key undone, nothing else in the file
            if self.path.exists():
                self.path.replace(self.path.with_name(self.path.name + ".bak"))
            return self.path
        return save_cameras(self.path, views, tracks)

    def _remember(self) -> None:
        self.history.append((dict(self.keys), dict(self.names)))

    def _own_name(self, frame: int) -> str:
        """The name a new view at ``frame`` is written under: the key's own name, unless
        another track uses that view (it is left as it is, and this key gets a new one)."""
        name = self.names.get(frame)
        if name is None or name in self.shared:
            return self._name(frame)
        return name

    def _name(self, frame: int) -> str:
        name = f"{self.track}_{frame:04d}"
        taken = set(self.others) | set(self.names.values())
        k = 1
        while name in taken:
            name, k = f"{self.track}_{frame:04d}_{k}", k + 1
        return name
