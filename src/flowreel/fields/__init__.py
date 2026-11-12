"""Derived fields, computed from velocity and pressure only (docs/PLAN.md, Section 6).

``compute(grid, names, **params)`` is the entry point; see docs/fields.md.
"""
from flowreel.fields import kinematics  # noqa: F401  (registers its fields)
from flowreel.fields.registry import (Field, available, compute, describe, register, resolve,
                                      unregister)

__all__ = ["Field", "available", "compute", "describe", "register", "resolve", "unregister"]
