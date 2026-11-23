"""The former name of :mod:`flowreel.sources.plt`, kept so code that imports it, and
shots that say ``flexflow:CASE``, keep working. ``FlexflowSource`` is
:class:`~flowreel.sources.plt.PltSource`."""
from flowreel.sources.plt import *  # noqa: F401,F403
from flowreel.sources.plt import PltSource

FlexflowSource = PltSource
