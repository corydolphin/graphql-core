"""Import hook that redirects graphql.* to compiled graphql_mypyc.* modules."""

from __future__ import annotations

import sys
from contextlib import suppress
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec
from importlib.util import find_spec
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import ModuleType

__all__ = [
    "COMPILED_MODULES",
    "install_hook",
    "is_hook_installed",
    "uninstall_hook",
]

# Modules that have compiled equivalents in graphql_mypyc.
# Start with a minimal set for POC, expand as we compile more.
COMPILED_MODULES: frozenset[str] = frozenset(
    {
        # Sentinel module for testing the import hook infrastructure.
        # Remove this once real modules are compiled.
        "graphql._sentinel",
        # Phase 1: Type system (hot path during execution)
        # "graphql.type.definition",
        # "graphql.type.scalars",
        # Phase 2: Language
        # "graphql.language.lexer",
        # Phase 3: Execution
        # "graphql.execution.execute",
    }
)


class _MypycLoader(Loader):
    """Loader that imports from graphql_mypyc but registers as graphql."""

    def __init__(self, mypyc_name: str) -> None:
        self.mypyc_name = mypyc_name
        self._module: ModuleType | None = None

    def create_module(self, _spec: ModuleSpec) -> ModuleType | None:
        """Import the mypyc-compiled module."""
        import importlib

        self._module = importlib.import_module(self.mypyc_name)
        return self._module

    def exec_module(self, module: ModuleType) -> None:
        """Module already executed in create_module."""


class _MypycFinder(MetaPathFinder):
    """Meta path finder that redirects graphql.* to graphql_mypyc.*."""

    def find_spec(
        self,
        fullname: str,
        _path: Sequence[str] | None,
        _target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        """Find module spec, redirecting compiled modules to mypyc versions."""
        if fullname not in COMPILED_MODULES:
            return None

        # Map graphql.foo.bar -> graphql_mypyc.foo.bar
        mypyc_name = fullname.replace("graphql.", "graphql_mypyc.", 1)

        # Check if the mypyc module actually exists
        # Temporarily remove ourselves to avoid recursion
        try:
            idx = sys.meta_path.index(self)
            sys.meta_path.pop(idx)
            try:
                mypyc_spec = find_spec(mypyc_name)
            finally:
                sys.meta_path.insert(idx, self)
        except ValueError:
            mypyc_spec = find_spec(mypyc_name)

        if mypyc_spec is None:
            return None

        # Return a spec that will load the mypyc module
        return ModuleSpec(
            name=fullname,
            loader=_MypycLoader(mypyc_name),
            origin=mypyc_spec.origin,
        )


_finder: _MypycFinder | None = None


def install_hook() -> bool:
    """Install the import hook. Returns True if newly installed."""
    global _finder  # noqa: PLW0603
    if _finder is not None:
        return False  # Already installed

    _finder = _MypycFinder()
    # Insert at beginning to intercept before normal finders
    sys.meta_path.insert(0, _finder)
    return True


def uninstall_hook() -> bool:
    """Remove the import hook. Returns True if it was installed."""
    global _finder  # noqa: PLW0603
    if _finder is None:
        return False

    with suppress(ValueError):
        sys.meta_path.remove(_finder)
    _finder = None
    return True


def is_hook_installed() -> bool:
    """Check if the import hook is currently installed."""
    return _finder is not None
