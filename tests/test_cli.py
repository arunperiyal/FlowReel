"""The flowreel entry point: one-shot and the shell's shot context."""
import subprocess
import sys

import pytest

import flowreel
from flowreel.cli import main

from cli_harness import Shell


@pytest.fixture
def sh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return Shell(tmp_path / "store")


def test_version_one_shot(capsys):
    assert main(["--version"]) == 0
    assert capsys.readouterr().out.strip() == f"flowreel {flowreel.__version__}"


def test_the_script_runs():
    done = subprocess.run([sys.executable, "-m", "flowreel", "--version"],
                          capture_output=True, text=True)
    assert done.returncode == 0 and "flowreel" in done.stdout


def test_shot_without_an_action_is_an_error(sh):
    status, _, err = sh.run("shot")
    assert status == 2 and "give an action" in err


def test_shot_context_takes_an_existing_file(sh, tmp_path):
    (tmp_path / "a.yml").write_text("name: a\n")
    assert sh.run("use shot:a.yml")[0] == 0
    assert sh.rt.context.get("shot") == str(tmp_path / "a.yml")
    status, _, err = sh.run("use shot:missing.yml")
    assert status != 0 and "no such file" in err
