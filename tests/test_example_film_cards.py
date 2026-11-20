"""examples/film_cards/run.py: a card drawn from its file, with a generated logo."""
import subprocess
import sys
from pathlib import Path

from PIL import Image

RUN = Path(__file__).parent.parent / "examples" / "film_cards" / "run.py"


def test_example_draws_the_card(tmp_path):
    out = tmp_path / "ex"
    done = subprocess.run([sys.executable, str(RUN), str(out)], capture_output=True, text=True,
                          timeout=120)
    assert done.returncode == 0, done.stderr[-2000:]
    assert done.stdout.splitlines()[:6] == [
        "image      120 to   280",
        "title      350 to   518",
        "divider    558 to   560",
        "names      606 to   708",
        "names      734 to   894",
        "text       944 to   975"]
    assert Image.open(out / "card.png").size == (1920, 1080)
    assert Image.open(out / "card_480p.png").size == (854, 480)
