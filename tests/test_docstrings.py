"""Every public module, class, function and method of the package has a docstring
(.claude/rules/documentation.md).

A method that overrides a documented one (a layer's ``draw``, a panel's ``build``) has
its base's docstring, as ``inspect.getdoc`` reads it. The ``do_*`` handlers of a command
are the exception: each is documented by its action's ``--help``, which the command
reference (docs/reference/commands.md) prints.
"""
import importlib
import inspect
import pkgutil

import flowreel


def public_names():
    """``(dotted name, object)`` of every public module, class, function and method."""
    for info in pkgutil.walk_packages(flowreel.__path__, "flowreel."):
        if any(part.startswith("_") for part in info.name.split(".")[1:]):
            continue
        module = importlib.import_module(info.name)
        yield info.name, module
        for name, obj in vars(module).items():
            if name.startswith("_") or getattr(obj, "__module__", None) != module.__name__:
                continue
            if not (inspect.isclass(obj) or inspect.isfunction(obj)):
                continue
            yield f"{info.name}.{name}", obj
            if not inspect.isclass(obj):
                continue
            command = any(base.__name__ == "BaseCommand" for base in obj.__mro__)
            for member, value in vars(obj).items():
                if member.startswith("_") or (command and member.startswith("do_")):
                    continue
                if inspect.isfunction(value) or isinstance(value, property):
                    yield f"{info.name}.{name}.{member}", getattr(obj, member)


def test_every_public_name_has_a_docstring():
    missing = [name for name, obj in public_names() if not inspect.getdoc(obj)]
    assert missing == [], "no docstring:\n" + "\n".join(missing)
