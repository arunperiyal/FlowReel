"""The off-screen check: each backend draws in its own process; failures are reported."""
import pytest

from flowreel.jobs import check as C
from flowreel.scene import backend as B


@pytest.mark.parametrize("name", ["osmesa", "egl"])
def test_an_installed_backend_works(name):
    if not B.installed(name):
        pytest.skip(f"{name} is not installed")
    result = C.try_backend(name)
    assert result.status == "works", result.error
    assert 0 < result.seconds < C.TIMEOUT and result.text().startswith(f"{name:<8} works in ")


def test_a_missing_backend_is_not_tried(monkeypatch):
    monkeypatch.setattr(B, "installed", lambda name: False)
    result = C.try_backend("osmesa")
    assert result == C.BackendResult("osmesa", "not installed")
    assert result.text() == "osmesa   not installed"


def test_a_failing_backend_is_reported_not_raised():
    name = "egl" if B.installed("egl") else "osmesa"
    if not B.installed(name):
        pytest.skip("no off-screen backend is installed")
    result = C.try_backend(name, extra_env={B.ENV: "vtkNoSuchWindow"})
    assert result.status == "fails"
    # VTK up to 9.6 falls back to another window, which the check refuses; 9.7 crashes
    assert (result.error.endswith(f"not a {B.WINDOW_CLASS[name]}")
            or result.error.startswith("killed by SIG")), result.error


def test_a_crash_says_what_was_printed_last(monkeypatch):
    monkeypatch.setattr(B, "installed", lambda name: True)
    monkeypatch.setattr(C, "SCRIPT", "import os, signal, sys; print('VTK: no window', "
                                     "file=sys.stderr, flush=True); os.kill(os.getpid(), signal.SIGSEGV)")
    assert C.try_backend("egl").error == "killed by SIGSEGV; last said: VTK: no window"


def test_a_crash_and_a_hang_are_reported(monkeypatch):
    monkeypatch.setattr(B, "installed", lambda name: True)
    monkeypatch.setattr(C, "SCRIPT", "import os, signal; os.kill(os.getpid(), signal.SIGSEGV)")
    assert C.try_backend("egl").error == "killed by SIGSEGV"
    monkeypatch.setattr(C, "SCRIPT", "import time; time.sleep(30)")
    result = C.try_backend("egl", timeout=0.5)
    assert (result.status, result.error) == ("fails", "no picture after 0.5 s")


def test_x_is_tried_only_with_a_display():
    assert C.candidates({}) == ["osmesa", "egl"]
    assert C.candidates({"DISPLAY": ":0"}) == ["osmesa", "egl", "x"]


def test_report_and_exit_code(monkeypatch):
    results = {"osmesa": C.BackendResult("osmesa", "not installed"),
               "egl": C.BackendResult("egl", "works", 1.94)}
    monkeypatch.setattr(C, "try_backend", lambda name, timeout: results[name])
    monkeypatch.setattr(B, "choose", lambda backend: "egl")
    report = C.check(backends=["osmesa", "egl"])
    assert report.text() == ("osmesa   not installed\n"
                             "egl      works in 1.9 s\n"
                             "auto -> egl: works")
    assert report.ok and report.exit_code == 0
    results["egl"] = C.BackendResult("egl", "fails", 0.3, "eglInitialize failed")
    report = C.check(backends=["osmesa", "egl"])
    assert report.exit_code == 1
    assert report.text().splitlines()[1:] == ["egl      fails in 0.3 s: eglInitialize failed",
                                              "auto -> egl: does NOT work"]


def test_nothing_installed_fails(monkeypatch):
    monkeypatch.setattr(B, "installed", lambda name: False)
    report = C.check(backends=["osmesa", "egl"])
    assert report.chosen is None and report.exit_code == 1
    assert report.text().endswith("auto -> none (no off-screen backend installed): does NOT work")


def test_main_runs_on_this_machine(capsys):
    if B.choose("auto") is None:
        pytest.skip("no off-screen backend is installed")
    code = C.main(["--timeout", "60"])
    out = capsys.readouterr().out
    assert code == 0 and f"auto -> {B.choose('auto')}: works" in out
