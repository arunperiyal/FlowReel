"""The documentation website (mkdocs.yml): it builds strictly, holds every page but the
plan, and CI installs the same MkDocs Material as the docs extra."""
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent


def config():
    # mkdocs.yml has a !!python tag (the anchor function); read it without running it
    class Loader(yaml.SafeLoader):
        pass
    Loader.add_multi_constructor("tag:yaml.org,2002:python/", lambda *a: None)
    return yaml.load((ROOT / "mkdocs.yml").read_text(), Loader=Loader)


def nav_pages(items):
    for item in items:
        for value in (item.values() if isinstance(item, dict) else [item]):
            if isinstance(value, list):
                yield from nav_pages(value)
            else:
                yield value


def test_every_page_is_in_the_navigation():
    """Every page in docs/ is on the site; the plan is in plan/, outside it."""
    pages = set(nav_pages(config()["nav"]))
    on_disk = {str(p.relative_to(ROOT / "docs")) for p in (ROOT / "docs").rglob("*.md")}
    assert pages == on_disk
    assert not (ROOT / "docs" / "PLAN.md").exists() and (ROOT / "plan" / "README.md").is_file()


def test_ci_installs_the_pinned_mkdocs_material():
    extra = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"][
        "optional-dependencies"]["docs"]
    workflow = (ROOT / ".github" / "workflows" / "docs.yml").read_text()
    assert re.findall(r"mkdocs-material==[\d.]+", workflow) == extra


def test_the_site_builds_strictly(tmp_path):
    pytest.importorskip("material", reason="needs the docs extra: pip install -e '.[docs]'")
    done = subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--strict", "--site-dir", str(tmp_path / "site")],
        cwd=ROOT, capture_output=True, text=True, timeout=300,
        env={**os.environ, "NO_MKDOCS_2_WARNING": "1"})
    assert done.returncode == 0, done.stderr[-3000:]
    assert (tmp_path / "site" / "rules" / "index.html").is_file()
    assert not (tmp_path / "site" / "PLAN").exists()
