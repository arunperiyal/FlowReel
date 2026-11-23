"""Backend choice: OSMesa when installed, else EGL; a forced one is kept."""
import pytest

from flowreel.scene import backend as B


def test_auto_prefers_osmesa_then_egl(monkeypatch):
    have = {"osmesa": True, "egl": True}
    monkeypatch.setattr(B, "installed", lambda name: have[name])
    assert B.choose("auto") == "osmesa"
    have["osmesa"] = False
    assert B.choose() == "egl"
    have["egl"] = False
    assert B.choose() is None


def test_forced_backend_is_kept_even_if_missing(monkeypatch):
    monkeypatch.setattr(B, "installed", lambda name: False)
    assert B.choose("egl") == "egl"


def test_unknown_backend_is_an_error():
    with pytest.raises(ValueError, match="osmesa"):
        B.choose("vulkan")


def test_environment_sets_window_and_threads():
    env = B.environment("osmesa", 3)
    assert env["VTK_DEFAULT_OPENGL_WINDOW"] == "vtkOSOpenGLRenderWindow"
    assert env["LP_NUM_THREADS"] == env["OMP_NUM_THREADS"] == "3"
    assert B.environment(None) == {}


@pytest.mark.parametrize("name", ["osmesa", "egl"])
def test_installed_backend_makes_its_window(name):
    """Drawn in a fresh process, as jobs check draws: one process cannot load two
    OpenGL libraries, and the tests' own windows are of one kind (conftest.py)."""
    if not B.installed(name):
        pytest.skip(f"{name} is not installed")
    from flowreel.jobs.check import try_backend
    result = try_backend(name)
    if result.status != "works":
        pytest.skip(f"{name} cannot open a window here: {result.error}")
    assert result.status == "works"


def test_vtks_own_filters_are_used(monkeypatch):
    """Where this VTK has VTK-m's stand-ins (conda-forge's VTK 9.7), they are turned
    off; where it has none, nothing happens."""
    import sys
    import types
    calls = []
    fake = types.ModuleType("vtkmodules.vtkAcceleratorsVTKmFilters")
    fake.vtkmFilterOverrides = types.SimpleNamespace(SetEnabled=calls.append)
    monkeypatch.setitem(sys.modules, "vtkmodules.vtkAcceleratorsVTKmFilters", fake)
    from flowreel.scene.backend import plain_vtk_filters
    plain_vtk_filters()
    assert calls == [False]
    monkeypatch.setitem(sys.modules, "vtkmodules.vtkAcceleratorsVTKmFilters", None)
    plain_vtk_filters()                               # ImportError: nothing to turn off
    assert calls == [False]
