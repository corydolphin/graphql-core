"""mypyc compilation status detection and reporting.

This module provides utilities to check whether mypyc-compiled modules
are being used for improved performance.
"""

from __future__ import annotations

__all__ = ["get_mypyc_modules", "is_mypyc_enabled"]

# Track whether mypyc-compiled modules are active
_mypyc_enabled: bool = False
_mypyc_modules: frozenset[str] = frozenset()


def is_mypyc_enabled() -> bool:
    """Return True if mypyc-compiled modules are in use."""
    return _mypyc_enabled


def get_mypyc_modules() -> frozenset[str]:
    """Return the set of module names currently using mypyc compilation."""
    return _mypyc_modules


def _activate(modules: frozenset[str]) -> None:
    """Internal: called by graphql_mypyc to register activation."""
    global _mypyc_enabled, _mypyc_modules  # noqa: PLW0603
    _mypyc_enabled = True
    _mypyc_modules = modules


def _deactivate() -> None:
    """Internal: called by graphql_mypyc to deregister."""
    global _mypyc_enabled, _mypyc_modules  # noqa: PLW0603
    _mypyc_enabled = False
    _mypyc_modules = frozenset()
