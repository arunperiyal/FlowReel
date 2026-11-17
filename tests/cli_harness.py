"""Run flowreel commands in-process with output captured (as shellkit's own tests do)."""
import io

from rich.console import Console
from shellkit import Runtime

from flowreel.cli import make_app


class Shell:
    """``run(line)`` returns ``(status, stdout, stderr)`` of that line only."""

    def __init__(self, storage):
        self.out = io.StringIO()
        self.err = io.StringIO()
        self.rt = Runtime(make_app(storage),
                          console=Console(file=self.out, width=200, color_system=None),
                          err_console=Console(file=self.err, width=200, color_system=None))

    def run(self, line):
        for buf in (self.out, self.err):
            buf.seek(0), buf.truncate()
        status = self.rt.execute_line(line)
        return status, self.out.getvalue(), self.err.getvalue()
