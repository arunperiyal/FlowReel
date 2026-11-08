"""Make black-background versions of the IIT Kharagpur logo in assets/.

Usage: python prepare_logo.py
  iitkgp_logo_white.png  all-white version: the navy becomes white
  iitkgp_logo_panel.png  original colours on a rounded white panel
"""
import io
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

SOURCE_ZIP = "IIT-Kharagpur-Logo-Vector.zip"
SOURCE_PNG = "IIT Kharagpur Logo Vector.svg .png"
OUT = Path("assets")
MARGIN = 0.10  # white space around the logo on the panel, as a fraction of its height
CORNER = 0.06  # panel corner radius, as a fraction of its height


def main():
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        logo = Image.open(io.BytesIO(archive.read(SOURCE_PNG))).convert("RGBA")
    OUT.mkdir(exist_ok=True)

    white = Image.new("RGBA", logo.size, (255, 255, 255, 0))
    white.putalpha(logo.getchannel("A"))
    white.save(OUT / "iitkgp_logo_white.png")

    pad = int(MARGIN * logo.height)
    size = (logo.width + 2 * pad, logo.height + 2 * pad)
    panel = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1),
                                            radius=int(CORNER * size[1]), fill="white")
    panel.alpha_composite(logo, (pad, pad))
    panel.save(OUT / "iitkgp_logo_panel.png")


if __name__ == "__main__":
    main()
