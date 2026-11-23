"""film build --watch (Phase 8, branch 7): build, then build again on each change."""
import threading
import time

import pytest

from flowreel.film import watch as W
from flowreel.film.build import build

from film_project import film_file, frames, need_ffmpeg


def test_the_fingerprint_leaves_out_what_the_build_writes(tmp_path):
    (tmp_path / "film.yml").write_text("x")
    (tmp_path / "film.mp4").write_text("x")
    (tmp_path / "film.srt").write_text("x")
    (tmp_path / "clips").mkdir()
    (tmp_path / "clips" / "shot_a.mp4").write_text("x")
    (tmp_path / "text").mkdir()
    (tmp_path / "text" / "a.yml").write_text("x")
    names = [f[0] for f in W.fingerprint(tmp_path)]
    assert names == ["film.yml", "text/a.yml"]
    before = W.fingerprint(tmp_path)
    (tmp_path / "film.mp4").write_text("a new film")
    assert W.fingerprint(tmp_path) == before
    (tmp_path / "text" / "a.yml").write_text("an edit")
    assert W.fingerprint(tmp_path) != before


def test_a_link_to_a_folder_is_not_walked(tmp_path):
    data = tmp_path / "elsewhere"
    data.mkdir()
    (data / "flow.vtu").write_text("x")
    project = tmp_path / "project"
    (project / "data").mkdir(parents=True)
    (project / "data" / "run").symlink_to(data, target_is_directory=True)
    assert W.fingerprint(project) == ()


def watching(film, build_once, edits):
    """Run the watch in a thread; make each edit once the build count reaches its turn."""
    said, calls = [], []

    def once():
        calls.append(time.monotonic())
        build_once()
    done = threading.Event()
    thread = threading.Thread(target=W.watch, args=(film, once), daemon=True, kwargs=dict(
        say=said.append, interval=0.05, settle=0.1, stop=done.is_set))
    thread.start()
    for k, edit in enumerate(edits, start=1):
        deadline = time.monotonic() + 30
        while len(calls) < k and time.monotonic() < deadline:
            time.sleep(0.02)
        time.sleep(0.15)
        edit()
    deadline = time.monotonic() + 30
    while len(calls) < len(edits) + 1 and time.monotonic() < deadline:
        time.sleep(0.02)
    done.set()
    thread.join(timeout=10)
    return calls, said


def test_each_change_builds_again_and_an_error_waits_for_the_next(tmp_path):
    film = tmp_path / "film.yml"
    film.write_text("first")
    outcomes = iter([None, ValueError("a caption is missing its end"), None])

    def once():
        problem = next(outcomes)
        if problem:
            raise problem
    calls, said = watching(film, once, [lambda: film.write_text("second"),
                                        lambda: film.write_text("third")])
    assert len(calls) == 3
    assert "not built: a caption is missing its end" in said
    assert said[-1].startswith("watching ")


def test_a_caption_changed_makes_only_its_shots_clip_again(tmp_path):
    need_ffmpeg()
    frames(tmp_path / "a", 12)
    frames(tmp_path / "b", 6, start=20)
    shots = [{"name": "a", "frames": "a"}, {"name": "b", "frames": "b"}]
    path = film_file(tmp_path, shots)
    results = []

    def once():
        results.append(build(path))

    def caption():
        film_file(tmp_path, [{**shots[0], "text": [{"lines": ["A caption"], "at": [0.1, 0.4]}]},
                             shots[1]])
    calls, _ = watching(path, once, [caption])
    assert len(results) == 2
    assert all(s.built for s in results[0].shots)
    assert {s.name: s.built for s in results[1].shots} == {"a": True, "b": False}


@pytest.mark.parametrize("line, message", [
    ("film build --watch --submit", "--watch builds here"),
    ("film build --watch --force", "every clip on every change"),
])
def test_the_command_refuses_what_watch_cannot_do(tmp_path, monkeypatch, line, message):
    from cli_harness import Shell
    monkeypatch.chdir(tmp_path)
    (tmp_path / "flowreel.yml").write_text("")
    film_file(tmp_path, [{"name": "a", "frames": "a"}])
    status, _, err = Shell(tmp_path).run(line)
    assert status != 0 and message in err


def test_the_command_watches_until_interrupted(tmp_path, monkeypatch):
    from cli_harness import Shell
    from flowreel.film import watch as watch_mod
    seen = {}

    def fake_watch(film, once, **kw):
        seen["film"], seen["skip"] = film, kw["skip"]
        raise KeyboardInterrupt
    monkeypatch.setattr(watch_mod, "watch", fake_watch)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "flowreel.yml").write_text("")
    film_file(tmp_path, [{"name": "a", "frames": "a"}])
    status, out, err = Shell(tmp_path).run("film build --watch")
    assert status == 0, err
    assert "stopped watching" in out and str(seen["film"]).endswith("film.yml")
