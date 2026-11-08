"""FlowReel: films of flow simulations from configuration files.

The design is in docs/PLAN.md. Fonts bundled in fonts/ are Lato, under the SIL Open
Font Licence (fonts/OFL.txt).
"""
from pathlib import Path

__version__ = "0.0.1"

FONTS = Path(__file__).resolve().parent / "fonts"
