"""Tests for mypyc compilation infrastructure."""

from __future__ import annotations


def describe_mypyc_detection():
    """Tests for mypyc detection utilities."""

    def exports_detection_functions():
        """The graphql module exports mypyc detection functions."""
        import graphql

        assert hasattr(graphql, "is_mypyc_enabled")
        assert hasattr(graphql, "get_mypyc_modules")
        assert callable(graphql.is_mypyc_enabled)
        assert callable(graphql.get_mypyc_modules)

    def is_mypyc_enabled_returns_bool():
        """is_mypyc_enabled returns a boolean."""
        import graphql

        result = graphql.is_mypyc_enabled()
        assert isinstance(result, bool)

    def get_mypyc_modules_returns_frozenset():
        """get_mypyc_modules returns a frozenset of strings."""
        import graphql

        result = graphql.get_mypyc_modules()
        assert isinstance(result, frozenset)


def describe_mypyc_module():
    """Tests for the graphql_mypyc module."""

    def can_import_graphql_mypyc():
        """The graphql_mypyc module can be imported."""
        import graphql_mypyc

        assert graphql_mypyc is not None

    def exports_activate_deactivate():
        """The graphql_mypyc module exports activate/deactivate functions."""
        import graphql_mypyc

        assert hasattr(graphql_mypyc, "activate")
        assert hasattr(graphql_mypyc, "deactivate")
        assert hasattr(graphql_mypyc, "is_active")
        assert callable(graphql_mypyc.activate)
        assert callable(graphql_mypyc.deactivate)
        assert callable(graphql_mypyc.is_active)

    def exports_compiled_modules_set():
        """The graphql_mypyc module exports COMPILED_MODULES."""
        import graphql_mypyc

        assert hasattr(graphql_mypyc, "COMPILED_MODULES")
        assert isinstance(graphql_mypyc.COMPILED_MODULES, frozenset)

    def exports_version():
        """The graphql_mypyc module exports __version__."""
        import graphql_mypyc

        assert hasattr(graphql_mypyc, "__version__")
        assert isinstance(graphql_mypyc.__version__, str)


def describe_mypyc_activation():
    """Tests for mypyc activation/deactivation."""

    def activation_is_idempotent():
        """Calling activate multiple times is safe."""
        import graphql_mypyc

        # Should already be active from auto-activation
        result1 = graphql_mypyc.activate()
        result2 = graphql_mypyc.activate()
        assert result1 is True
        assert result2 is True

    def deactivation_works():
        """Deactivation disables mypyc mode."""
        import graphql
        import graphql_mypyc

        # Deactivate
        graphql_mypyc.deactivate()
        assert graphql_mypyc.is_active() is False
        assert graphql.is_mypyc_enabled() is False

        # Reactivate for other tests
        graphql_mypyc.activate()
        assert graphql_mypyc.is_active() is True
        assert graphql.is_mypyc_enabled() is True

    def deactivation_is_idempotent():
        """Calling deactivate multiple times is safe."""
        import graphql_mypyc

        # Deactivate twice
        graphql_mypyc.deactivate()
        result1 = graphql_mypyc.deactivate()
        result2 = graphql_mypyc.deactivate()
        assert result1 is True
        assert result2 is True

        # Reactivate for other tests
        graphql_mypyc.activate()


def describe_mypyc_auto_activation():
    """Tests for automatic mypyc activation on import."""

    def auto_activates_when_graphql_mypyc_available():
        """Auto-activates mypyc when graphql_mypyc is installed."""
        # Since graphql_mypyc is in our src/, it's always available
        # and should be auto-activated when graphql is imported
        import graphql

        # The module should report as enabled (hook is installed)
        # Note: This tests the hook infrastructure, not actual compilation
        assert graphql.is_mypyc_enabled() is True

    def compiled_modules_reflects_current_state():
        """get_mypyc_modules returns the currently compiled modules."""
        import graphql
        import graphql_mypyc

        # The compiled modules set should match what's registered
        modules = graphql.get_mypyc_modules()
        assert modules == graphql_mypyc.COMPILED_MODULES


def describe_import_hook():
    """Tests for the import hook mechanism."""

    def hook_module_exports():
        """The _hook module exports expected functions."""
        from graphql_mypyc._hook import (
            COMPILED_MODULES,
            install_hook,
            is_hook_installed,
            uninstall_hook,
        )

        assert isinstance(COMPILED_MODULES, frozenset)
        assert callable(install_hook)
        assert callable(uninstall_hook)
        assert callable(is_hook_installed)

    def hook_is_installed_after_activation():
        """The import hook is installed after activation."""
        import graphql_mypyc
        from graphql_mypyc._hook import is_hook_installed

        graphql_mypyc.activate()
        assert is_hook_installed() is True

    def hook_is_removed_after_deactivation():
        """The import hook is removed after deactivation."""
        import graphql_mypyc
        from graphql_mypyc._hook import is_hook_installed

        graphql_mypyc.deactivate()
        assert is_hook_installed() is False

        # Reactivate for other tests
        graphql_mypyc.activate()

    def compiled_modules_contains_sentinel():
        """COMPILED_MODULES includes the sentinel module."""
        from graphql_mypyc._hook import COMPILED_MODULES

        assert "graphql._sentinel" in COMPILED_MODULES


def describe_sentinel_module():
    """Tests for the sentinel module that validates the import hook."""

    def graphql_sentinel_exists():
        """The graphql._sentinel module can be imported."""
        from graphql import _sentinel

        assert _sentinel is not None

    def graphql_mypyc_sentinel_exists():
        """The graphql_mypyc._sentinel module can be imported."""
        from graphql_mypyc import _sentinel

        assert _sentinel is not None

    def sentinel_has_expected_exports():
        """The sentinel module exports expected functions."""
        from graphql import _sentinel

        assert hasattr(_sentinel, "is_compiled")
        assert hasattr(_sentinel, "add_numbers")
        assert hasattr(_sentinel, "SENTINEL_VALUE")
        assert callable(_sentinel.is_compiled)
        assert callable(_sentinel.add_numbers)

    def sentinel_add_numbers_works():
        """The sentinel add_numbers function works correctly."""
        from graphql import _sentinel

        assert _sentinel.add_numbers(2, 3) == 5
        assert _sentinel.add_numbers(-1, 1) == 0

    def hook_redirects_to_mypyc_version():
        """With hook active, graphql._sentinel gets graphql_mypyc._sentinel."""
        import sys

        import graphql_mypyc

        # Ensure hook is active
        graphql_mypyc.activate()

        # Remove any cached import of graphql._sentinel
        if "graphql._sentinel" in sys.modules:
            del sys.modules["graphql._sentinel"]

        # Import with hook active - should get redirected
        from graphql import _sentinel

        # The SENTINEL_VALUE tells us which version we got
        # graphql_mypyc._sentinel has "mypyc-compiled"
        # graphql._sentinel (fallback) has "interpreted"
        assert _sentinel.SENTINEL_VALUE == "mypyc-compiled"

    def without_hook_gets_interpreted_version():
        """With hook inactive, graphql._sentinel is the interpreted version."""
        import sys

        import graphql
        import graphql_mypyc

        # Deactivate hook
        graphql_mypyc.deactivate()

        # Remove any cached import from sys.modules
        if "graphql._sentinel" in sys.modules:
            del sys.modules["graphql._sentinel"]

        # Also remove the cached attribute from the graphql module
        # (Python caches submodule imports as attributes on the parent)
        if hasattr(graphql, "_sentinel"):
            delattr(graphql, "_sentinel")

        # Import without hook - should get original
        from graphql import _sentinel

        assert _sentinel.SENTINEL_VALUE == "interpreted"

        # Reactivate for other tests and clear cache
        graphql_mypyc.activate()
        if "graphql._sentinel" in sys.modules:
            del sys.modules["graphql._sentinel"]
        if hasattr(graphql, "_sentinel"):
            delattr(graphql, "_sentinel")
