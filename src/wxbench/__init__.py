"""wx-bench core package.

This package is organized around a strict seam between pure domain logic and
boundary adapters. Modules under :mod:`wxbench.domain` should stay free of
side effects, while :mod:`wxbench.providers` and :mod:`wxbench.storage`
implement the thin interfaces that talk to the outside world.
"""

__all__ = ["config"]
