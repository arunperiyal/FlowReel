"""Labels in the frame: Lato through VTK's font file, sized in pixels."""
import numpy as np
import pytest
import pyvista as pv

from flowreel.scene.text import font_file, label_at, lato


def test_lato_sets_the_font_file_and_pixel_size():
    from vtkmodules.vtkCommonCore import VTK_FONT_FILE
    from vtkmodules.vtkRenderingCore import vtkTextProperty
    prop = lato(vtkTextProperty(), 17.6, "#ff0000", 0.5, bold=True)
    assert prop.GetFontFamily() == VTK_FONT_FILE
    assert prop.GetFontFile() == font_file("Bold") and prop.GetFontFile().endswith(".ttf")
    assert prop.GetFontSize() == 18 and prop.GetOpacity() == 0.5
    assert np.allclose(prop.GetColor(), (1, 0, 0))


def ink(size):
    plotter = pv.Plotter(off_screen=True, window_size=[200, 120])
    try:
        plotter.set_background("black")
        plotter.add_mesh(pv.Sphere(radius=0.2, center=(0, -3, 0)), color="#000020")
        plotter.camera.position, plotter.camera.focal_point = (0, 0, 10), (0, 0, 0)
        assert label_at(plotter.renderer, "x 10", (0, 0, 0), size, "#ffffff") is not None
        assert label_at(plotter.renderer, "behind", (0, 0, 20), size, "#ffffff") is None
        img = np.asarray(plotter.screenshot(return_img=True))[:, :, 0]
    except (RuntimeError, OSError) as error:
        pytest.skip(f"off-screen rendering is not available: {error}")
    finally:
        plotter.close()
    rows = np.flatnonzero((img > 100).any(axis=1))
    cols = np.flatnonzero((img > 100).any(axis=0))
    return np.ptp(rows) + 1, ((cols.min() + cols.max()) / 2, (rows.min() + rows.max()) / 2)


def test_a_label_is_centred_and_sized_in_pixels():
    small, centre = ink(12)
    big, _ = ink(36)
    assert abs(centre[0] - 100) < 4 and abs(centre[1] - 60) < 4   # centred on its point
    assert 2.4 < big / small < 3.6                        # three times the pixels
    assert 0.5 * 36 < big <= 36
