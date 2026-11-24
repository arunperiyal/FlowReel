"""Make a project from a generated case, as a person would: ``project init``, ``data import``,
then the tag's ``domain.yml`` written by hand.

Shared by the examples whose data is made by a script (``long_span``, ``riser500``,
``bodies``, ``compose_layout``). ``make_project`` links the case folder as the tag, and
keeps what the import measured (the ``measured:`` block) under the example's own
``domain.yml``, which gives the units, the bodies and the reader's options.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def flowreel(folder: Path, *args: str) -> str:
    """Run ``flowreel ARGS`` in ``folder``; stop with its message if it fails. Returns its
    output."""
    done = subprocess.run([sys.executable, "-m", "flowreel", *args], cwd=folder,
                          capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(done.stderr or done.stdout)
    return done.stdout


def make_project(folder: Path, tag: str, domain: Path, kind: str = "plt",
                 path: str = "case", flags: tuple[str, ...] = (), echo: bool = False) -> Path:
    """A project in ``folder`` with the case ``folder/path`` as the tag ``tag``.

    ``domain`` is the example's ``domain.yml``: it replaces what the import wrote before
    ``measured:``. ``flags`` are more arguments of ``data import``; with ``echo`` the
    ``domain.yml`` the import wrote is printed first. Returns the tag's ``domain.yml``. A
    second call finds the project made and changes nothing."""
    target = folder / "data" / tag / "domain.yml"
    if target.is_file():
        return target
    if not (folder / "flowreel.yml").is_file():
        flowreel(folder, "project", "init", "--force")
    flowreel(folder, "data", "import", kind, "--path", path, "--tag", tag, *flags)
    written = target.read_text()
    if echo:
        print(written)
    target.write_text(domain.read_text().rstrip("\n") + "\n" + written[written.index("\nmeasured:") + 1:])
    return target
