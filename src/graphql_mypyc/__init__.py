"""graphql-mypyc: mypyc-compiled modules for graphql-core.

This package provides mypyc-compiled versions of performance-critical
graphql-core modules. When installed alongside graphql-core, compiled
modules are automatically used via an import hook.

Usage:
    # Automatic (recommended) - just install the package:
    pip install graphql-core[mypyc]

    # Manual activation (if needed):
    import graphql_mypyc
    graphql_mypyc.activate()

    # Then use graphql normally:
    from graphql import parse, execute
"""

from __future__ import annotations

from ._hook import COMPILED_MODULES, install_hook, uninstall_hook

__version__ = "3.3.0a11"
__all__ = ["COMPILED_MODULES", "activate", "deactivate", "is_active"]

_activated: bool = False


def activate() -> bool:
    """Activate mypyc mode by installing the import hook.

    Returns True if activation was successful (or already active).
    Call this before importing any graphql modules for best results.
    """
    global _activated  # noqa: PLW0603

    if _activated:
        return True

    # Install the import hook
    install_hook()

    # Register with graphql-core's mypyc detection
    try:
        from graphql import _mypyc

        _mypyc._activate(COMPILED_MODULES)  # noqa: SLF001
    except ImportError:
        pass  # graphql-core not installed or old version

    _activated = True
    return True


def deactivate() -> bool:
    """Deactivate mypyc mode.

    Note: Already-imported modules will remain compiled versions.
    Returns True if deactivation was successful.
    """
    global _activated  # noqa: PLW0603

    if not _activated:
        return True

    uninstall_hook()

    try:
        from graphql import _mypyc

        _mypyc._deactivate()  # noqa: SLF001
    except ImportError:
        pass

    _activated = False
    return True


def is_active() -> bool:
    """Return True if mypyc mode is currently active."""
    return _activated
