"""A small project of one geometry tag, for tests that need a shot's ``source`` to be a tag."""
from pathlib import Path

import yaml


def tag_project(folder, tag: str = "g", *, body: str = "grooved_cylinder", bodies: dict | None = None,
                units: dict | None = None, source: dict | None = None, kind: str = "geometry") -> Path:
    """Write ``folder/flowreel.yml`` and ``folder/data/<tag>/domain.yml`` (a tag of ``kind``,
    by default a body made in code, with ``bodies`` and ``units`` as given); returns
    ``folder``. A shot file in it says ``source: <tag>``."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "flowreel.yml").write_text(f"tags: [{tag}]\n")
    where = folder / "data" / tag
    where.mkdir(parents=True, exist_ok=True)
    spec = {"kind": kind, "source": source if source is not None else {"body": body}}
    if units:
        spec["units"] = units
    if bodies:
        spec["bodies"] = bodies
    (where / "domain.yml").write_text(yaml.safe_dump(spec))
    return folder


def declare_bodies(source, text: str, folder):
    """``source`` seen through the ``bodies:`` of ``text`` (YAML), as a tag's ``domain.yml``
    declares them: what a shot of the tag reads. ``folder`` is where their paths start."""
    from flowreel.project.bodies import parse_bodies
    from flowreel.project.names import DeclaredSource
    from flowreel.scene.errors import Checker
    folder = Path(folder)
    data = yaml.safe_load(text) or {}
    bodies = parse_bodies(data.get("bodies"), Checker(folder / "domain.yml").at("bodies"), folder)
    return DeclaredSource(source, bodies)
