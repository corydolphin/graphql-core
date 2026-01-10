# mypyc Integration Plan: graphql-core-turbo

This document outlines the implementation plan for exposing a mypyc-compiled variant of graphql-core as an optional "extras" dependency.

## Overview

**Goal**: Users can `pip install graphql-core[fast]` to automatically get compiled modules for better performance, with zero code changes required.

**Approach**: Automatic activation (Approach A) - when `graphql-core-turbo` is installed alongside `graphql-core`, the compiled modules are automatically used via an import hook.

---

## Phase 0: Type System Enforcement (Precursor)

Before implementing mypyc compilation, we establish type-level markers to enforce which classes are safe to compile. This serves as both documentation and enforcement.

### The `@final` Decorator Strategy

```python
from typing import final
```

| Marker | Meaning | mypyc Safety |
|--------|---------|--------------|
| `@final` class | Cannot be subclassed | ✅ Safe to compile |
| No marker (designed for subclassing) | Users may subclass | ❌ Don't compile the class |
| Internal helper classes | Not part of public API | ✅ Safe to compile |

### Class Classification

Based on analysis of the codebase, here's how each public class should be marked:

#### Language Module

| Class | Current Usage | Recommended Marker | Rationale |
|-------|--------------|-------------------|-----------|
| `Lexer` | Public API, instantiated directly | `@final` | No documented subclassing use case |
| `Parser` | Internal API, explicitly for subclassing | **No marker** | Docstring: "to assist people in implementing their own parsers" |
| `Visitor` | Public API, always subclassed | **No marker** | Core extension point for AST traversal |
| `ParallelVisitor` | Public API, used directly | `@final` | Wrapper, not meant for subclassing |
| `Source` | Public API, instantiated directly | `@final` | Simple data holder |
| `Token` | Public API, instantiated by Lexer | `@final` | Internal structure |
| AST Nodes (`*Node`) | Public API, instantiated directly | `@final` | Data classes, no subclassing pattern |

#### Execution Module

| Class | Current Usage | Recommended Marker | Rationale |
|-------|--------------|-------------------|-----------|
| `ExecutionContext` | Public API via `execution_context_class` param | **No marker** | Explicitly designed for subclassing |
| `ExecutionResult` | Public API, returned from execute | `@final` | Simple result container |
| `MiddlewareManager` | Public API, instantiated directly | `@final` | No subclassing pattern |
| `GraphQLResolveInfo` | Public API, passed to resolvers | `@final` | Read-only info object |

#### Validation Module

| Class | Current Usage | Recommended Marker | Rationale |
|-------|--------------|-------------------|-----------|
| `ValidationContext` | Internal, passed to rules | Review needed | Rules receive it but don't subclass |
| `ASTValidationRule` | Subclassed by all validation rules | **No marker** | Core extension point |
| Built-in rules | Internal implementations | `@final` | Users shouldn't subclass built-in rules |

#### Type Module (Schema Layer)

The type system classes use **composition over inheritance** - customization is done via function parameters (`resolve_type`, `is_type_of`, `serialize`, etc.), not method overrides. Analysis of the entire codebase and tests shows **zero actual subclasses** of any GraphQL type class.

| Class | Subclassing in Practice | Recommended Marker | Rationale |
|-------|------------------------|-------------------|-----------|
| `GraphQLScalarType` | Never | `@final` | Custom scalars use `serialize`/`parse_value` functions |
| `GraphQLObjectType` | Never (docstring example only) | `@final` | Uses `is_type_of` function parameter |
| `GraphQLInterfaceType` | Never | `@final` | Uses `resolve_type` function parameter |
| `GraphQLUnionType` | Never | `@final` | Uses `resolve_type` function parameter |
| `GraphQLEnumType` | Never | `@final` | Instantiated with enum values |
| `GraphQLInputObjectType` | Never (docstring example only) | `@final` | Instantiated with input fields |
| `GraphQLField` | Never | `@final` | Pure data class with `resolve` function |
| `GraphQLArgument` | Never | `@final` | Pure data class |
| `GraphQLInputField` | Never | `@final` | Pure data class |
| `GraphQLList` | Never | `@final` | Simple type wrapper |
| `GraphQLNonNull` | Never | `@final` | Simple type wrapper |
| `GraphQLDirective` | Never | `@final` | Instantiated with locations/args |
| `GraphQLSchema` | Never | `@final` | Schema container |
| `GraphQLResolveInfo` | N/A (NamedTuple) | Already final | Immutable data passed to resolvers |

**Hot Path Impact**: These classes are accessed constantly during execution:
- `GraphQLObjectType.fields` - every field resolution
- `GraphQLField.type` / `GraphQLField.resolve` - every field
- Type predicates (`is_object_type()`, `is_list_type()`, etc.) - type checking

Compiling the type module would significantly speed up the inner execution loop.

**Note**: The docstrings show a class-based pattern (`class PersonType(GraphQLObjectType)`) but this is:
1. Never used in the graphql-core codebase itself
2. Never used in the test suite
3. A theoretical alternative, not the recommended approach

Before adding `@final`, we should:
1. Search popular downstream projects (Strawberry, Ariadne, Graphene) for any subclassing
2. Add deprecation warnings for one release cycle if any are found
3. Document the function-based customization as the official pattern

### Implementation Steps

#### Step 0.1: Add `@final` to safe-to-compile classes

```python
# src/graphql/language/lexer.py
from typing import final

@final
class Lexer:
    """GraphQL Lexer..."""
```

```python
# src/graphql/language/source.py
from typing import final

@final
class Source:
    """A representation of source input to GraphQL..."""
```

```python
# src/graphql/execution/types.py
from typing import final

@final
class ExecutionResult:
    """The result of GraphQL execution..."""
```

#### Step 0.2: Document non-final classes

Add explicit documentation for classes designed for subclassing:

```python
# src/graphql/execution/execute.py
class ExecutionContext(IncrementalPublisherContext):
    """Data that must be available at all points during query execution.

    This class is designed to be subclassed. Pass your subclass to the
    ``execution_context_class`` parameter of :func:`execute` or :func:`subscribe`.

    Common extension points:
        - Override ``execute_field`` to customize field resolution
        - Override ``build_resolve_info`` to add custom context
    """
```

```python
# src/graphql/language/visitor.py
class Visitor:
    """Visitor that walks through an AST.

    This class is designed to be subclassed. Override ``enter_*`` and ``leave_*``
    methods to handle specific node types during traversal.
    """
```

#### Step 0.3: Add runtime warning for subclassing `@final` classes

For defense in depth, add a runtime check during development:

```python
# src/graphql/_compat.py
import warnings
from typing import final

def warn_on_subclass(cls):
    """Decorator that warns when a @final class is subclassed."""
    original_init_subclass = cls.__init_subclass__

    @classmethod
    def __init_subclass__(subcls, **kwargs):
        warnings.warn(
            f"{cls.__name__} is marked @final and should not be subclassed. "
            f"Subclassing may break with mypyc compilation.",
            DeprecationWarning,
            stacklevel=2,
        )
        original_init_subclass.__func__(subcls, **kwargs)

    cls.__init_subclass__ = __init_subclass__
    return cls
```

Usage:
```python
@final
@warn_on_subclass
class Lexer:
    ...
```

#### Step 0.4: Test that type checkers enforce `@final`

Add tests that verify mypy catches `@final` violations:

```python
# tests/type_checking/test_final_enforcement.py
"""
These tests verify that mypy correctly reports errors for @final violations.
Run with: mypy tests/type_checking/
"""

from graphql.language import Lexer

# mypy should error: Cannot inherit from final class "Lexer"
class CustomLexer(Lexer):  # type: ignore[misc]
    pass
```

### mypyc Compilation Rules

After Phase 0, the compilation rules become simple:

```python
# graphql-core-turbo compilation targets

# ✅ SAFE: Classes marked @final
COMPILE_CLASSES = [
    "graphql.language.lexer.Lexer",
    "graphql.language.source.Source",
    "graphql.execution.types.ExecutionResult",
    # ... all @final classes
]

# ✅ SAFE: All standalone functions
COMPILE_FUNCTIONS = [
    "graphql.language.parser.parse",  # Function, not class
    "graphql.execution.execute.execute",
    "graphql.execution.execute.execute_sync",
    # ... all public functions
]

# ❌ NEVER COMPILE: Classes without @final (designed for subclassing)
DO_NOT_COMPILE = [
    "graphql.execution.execute.ExecutionContext",
    "graphql.language.parser.Parser",
    "graphql.language.visitor.Visitor",
    "graphql.validation.ASTValidationRule",
]
```

### Type Checking CI Integration

Add to CI pipeline:

```yaml
# .github/workflows/lint.yml
- name: Verify @final annotations
  run: |
    # Ensure all classes in COMPILE_CLASSES are marked @final
    python scripts/verify_final_markers.py
```

```python
# scripts/verify_final_markers.py
"""Verify that classes intended for mypyc compilation are marked @final."""

import ast
import sys
from pathlib import Path

MUST_BE_FINAL = {
    "src/graphql/language/lexer.py": ["Lexer"],
    "src/graphql/language/source.py": ["Source"],
    "src/graphql/execution/types.py": ["ExecutionResult"],
}

def check_final_markers():
    errors = []
    for filepath, classes in MUST_BE_FINAL.items():
        tree = ast.parse(Path(filepath).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name in classes:
                decorators = [d.id for d in node.decorator_list
                             if isinstance(d, ast.Name)]
                if "final" not in decorators:
                    errors.append(f"{filepath}: {node.name} missing @final")
    return errors

if __name__ == "__main__":
    errors = check_final_markers()
    if errors:
        print("Missing @final markers:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    print("All @final markers present ✓")
```

---

## Package Structure

```
graphql-core/                    # Existing repo (modified)
├── src/graphql/
│   ├── __init__.py              # Modified: adds turbo activation
│   ├── _turbo.py                # NEW: turbo detection & status
│   └── ...
└── pyproject.toml               # Modified: adds [fast] extras

graphql-core-turbo/              # NEW separate repo/package
├── src/graphql_turbo/
│   ├── __init__.py              # Package init + activate()
│   ├── _hook.py                 # Import hook implementation
│   ├── language/
│   │   ├── __init__.py
│   │   ├── parser.py            # Compiled with mypyc
│   │   └── lexer.py             # Compiled with mypyc
│   └── execution/
│       ├── __init__.py
│       └── execute.py           # Compiled with mypyc
├── pyproject.toml               # mypyc build configuration
└── setup.py                     # Required for mypyc builds
```

---

## Phase 1: Changes to graphql-core

### 1.1 Add turbo detection module

**New file**: `src/graphql/_turbo.py`

```python
"""Turbo mode detection and status reporting."""

from __future__ import annotations

# Track whether turbo mode is active
_turbo_active: bool = False
_turbo_modules: set[str] = set()


def is_turbo_active() -> bool:
    """Return True if turbo (mypyc-compiled) modules are in use."""
    return _turbo_active


def get_turbo_modules() -> frozenset[str]:
    """Return the set of modules currently using turbo compilation."""
    return frozenset(_turbo_modules)


def _set_turbo_active(active: bool, modules: set[str]) -> None:
    """Internal: called by graphql_turbo to register activation."""
    global _turbo_active, _turbo_modules
    _turbo_active = active
    _turbo_modules = modules
```

### 1.2 Modify `src/graphql/__init__.py`

Add at the **top** of the file (after docstring, before other imports):

```python
# Attempt to activate turbo mode if graphql-core-turbo is installed
def _try_activate_turbo() -> None:
    try:
        import graphql_turbo
        graphql_turbo.activate()
    except ImportError:
        pass

_try_activate_turbo()
del _try_activate_turbo  # Clean up namespace
```

Add to exports:

```python
from ._turbo import is_turbo_active, get_turbo_modules

__all__ = [
    # ... existing exports ...
    "is_turbo_active",
    "get_turbo_modules",
]
```

### 1.3 Modify `pyproject.toml`

Add the `fast` extras:

```toml
[project.optional-dependencies]
fast = ["graphql-core-turbo>=3.3.0a11"]
```

---

## Phase 2: Create graphql-core-turbo Package

### 2.1 Import Hook Implementation

**File**: `src/graphql_turbo/_hook.py`

```python
"""Import hook that redirects graphql.* to compiled graphql_turbo.* modules."""

from __future__ import annotations

import sys
from importlib.abc import MetaPathFinder, Loader
from importlib.machinery import ModuleSpec
from importlib.util import find_spec
from types import ModuleType
from typing import Sequence

# Modules that have compiled equivalents in graphql_turbo
COMPILED_MODULES: frozenset[str] = frozenset({
    "graphql.language.parser",
    "graphql.language.lexer",
    "graphql.execution.execute",
    # Add more as compilation coverage expands
})


class TurboLoader(Loader):
    """Loader that imports from graphql_turbo but registers as graphql."""

    def __init__(self, turbo_name: str) -> None:
        self.turbo_name = turbo_name
        self._module: ModuleType | None = None

    def create_module(self, spec: ModuleSpec) -> ModuleType | None:
        """Import the turbo module."""
        # Import the compiled module
        import importlib
        self._module = importlib.import_module(self.turbo_name)
        return self._module

    def exec_module(self, module: ModuleType) -> None:
        """Module already executed in create_module."""
        pass


class TurboFinder(MetaPathFinder):
    """Meta path finder that redirects graphql.* to graphql_turbo.*."""

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        """Find module spec, redirecting compiled modules to turbo versions."""
        if fullname not in COMPILED_MODULES:
            return None

        # Map graphql.foo.bar -> graphql_turbo.foo.bar
        turbo_name = fullname.replace("graphql.", "graphql_turbo.", 1)

        # Check if the turbo module actually exists
        turbo_spec = find_spec(turbo_name)
        if turbo_spec is None:
            return None

        # Return a spec that will load the turbo module
        return ModuleSpec(
            name=fullname,
            loader=TurboLoader(turbo_name),
            origin=turbo_spec.origin,
        )


_finder: TurboFinder | None = None


def install_hook() -> bool:
    """Install the import hook. Returns True if newly installed."""
    global _finder
    if _finder is not None:
        return False  # Already installed

    _finder = TurboFinder()
    # Insert at beginning to intercept before normal finders
    sys.meta_path.insert(0, _finder)
    return True


def uninstall_hook() -> bool:
    """Remove the import hook. Returns True if it was installed."""
    global _finder
    if _finder is None:
        return False

    try:
        sys.meta_path.remove(_finder)
    except ValueError:
        pass
    _finder = None
    return True


def is_hook_installed() -> bool:
    """Check if the import hook is currently installed."""
    return _finder is not None
```

### 2.2 Package Init

**File**: `src/graphql_turbo/__init__.py`

```python
"""graphql-core-turbo: mypyc-compiled modules for graphql-core."""

from __future__ import annotations

from ._hook import (
    install_hook,
    uninstall_hook,
    is_hook_installed,
    COMPILED_MODULES,
)

__version__ = "3.3.0a11"

_activated: bool = False


def activate() -> bool:
    """
    Activate turbo mode by installing the import hook.

    Returns True if activation was successful (or already active).
    Call this before importing any graphql modules for best results.
    """
    global _activated

    if _activated:
        return True

    # Install the import hook
    install_hook()

    # Register with graphql-core's turbo detection
    try:
        from graphql import _turbo
        _turbo._set_turbo_active(True, set(COMPILED_MODULES))
    except ImportError:
        pass  # graphql-core not installed or old version

    _activated = True
    return True


def deactivate() -> bool:
    """
    Deactivate turbo mode.

    Note: Already-imported modules will remain compiled versions.
    Returns True if deactivation was successful.
    """
    global _activated

    if not _activated:
        return True

    uninstall_hook()

    try:
        from graphql import _turbo
        _turbo._set_turbo_active(False, set())
    except ImportError:
        pass

    _activated = False
    return True


def is_active() -> bool:
    """Return True if turbo mode is currently active."""
    return _activated


__all__ = [
    "__version__",
    "activate",
    "deactivate",
    "is_active",
    "COMPILED_MODULES",
]
```

### 2.3 pyproject.toml for graphql-core-turbo

```toml
[project]
name = "graphql-core-turbo"
version = "3.3.0a11"
description = "mypyc-compiled modules for graphql-core (performance boost)"
readme = "README.md"
requires-python = ">=3.10"
license = "MIT"
authors = [{ name = "Christoph Zwerschke", email = "cito@online.de" }]
keywords = ["graphql", "mypyc", "performance"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
]
# No runtime dependency on graphql-core (optional integration)
dependencies = []

[project.urls]
Homepage = "https://github.com/graphql-python/graphql-core-turbo"
Repository = "https://github.com/graphql-python/graphql-core-turbo"

[build-system]
requires = ["setuptools>=61", "mypy>=1.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

### 2.4 setup.py for mypyc

```python
"""Setup script with mypyc compilation."""

from setuptools import setup

# Only compile with mypyc if available and not building sdist
def get_ext_modules():
    try:
        from mypyc.build import mypycify
    except ImportError:
        # mypyc not available, return empty (pure Python fallback)
        return []

    return mypycify(
        [
            "src/graphql_turbo/language/parser.py",
            "src/graphql_turbo/language/lexer.py",
            "src/graphql_turbo/execution/execute.py",
        ],
        opt_level="3",  # Maximum optimization
        debug_level="0",  # No debug overhead
    )


setup(
    ext_modules=get_ext_modules(),
)
```

---

## Phase 3: Testing Strategy

### 3.1 Test Categories

| Test Type | Purpose | Location |
|-----------|---------|----------|
| Unit tests (pure) | Verify graphql-core works alone | `graphql-core/tests/` |
| Unit tests (turbo) | Verify turbo modules work | `graphql-core-turbo/tests/` |
| Integration tests | Verify hook + activation | `graphql-core/tests/turbo/` |
| Behavioral equivalence | Pure vs turbo produce same results | Both repos |
| Performance benchmarks | Measure speedup | `graphql-core/benchmarks/` |

### 3.2 New Tests for graphql-core

**File**: `tests/turbo/test_turbo_detection.py`

```python
"""Tests for turbo mode detection and status."""

from graphql._turbo import (
    is_turbo_active,
    get_turbo_modules,
    _set_turbo_active,
)


def describe_turbo_detection():
    def reports_inactive_by_default():
        # Reset state
        _set_turbo_active(False, set())
        assert is_turbo_active() is False
        assert get_turbo_modules() == frozenset()

    def reports_active_when_set():
        _set_turbo_active(True, {"graphql.language.parser"})
        assert is_turbo_active() is True
        assert "graphql.language.parser" in get_turbo_modules()
        # Reset
        _set_turbo_active(False, set())
```

**File**: `tests/turbo/test_turbo_integration.py`

```python
"""Integration tests for turbo mode activation."""

import sys
import pytest


def describe_turbo_integration():
    @pytest.fixture(autouse=True)
    def clean_imports():
        """Remove graphql imports between tests."""
        # Store original state
        original_modules = set(sys.modules.keys())
        yield
        # Remove any graphql modules added during test
        for mod in list(sys.modules.keys()):
            if mod.startswith(("graphql", "graphql_turbo")):
                if mod not in original_modules:
                    del sys.modules[mod]

    def activates_when_turbo_installed():
        pytest.importorskip("graphql_turbo")

        import graphql
        assert graphql.is_turbo_active() is True

    def works_without_turbo_installed(monkeypatch):
        # Simulate graphql_turbo not being installed
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "graphql_turbo":
                raise ImportError("No module named 'graphql_turbo'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # Fresh import of graphql
        import importlib
        import graphql
        importlib.reload(graphql)

        assert graphql.is_turbo_active() is False
```

### 3.3 Tests for graphql-core-turbo

**File**: `tests/test_hook.py`

```python
"""Tests for the import hook mechanism."""

import sys
import pytest
from graphql_turbo._hook import (
    TurboFinder,
    install_hook,
    uninstall_hook,
    is_hook_installed,
    COMPILED_MODULES,
)


def describe_import_hook():
    @pytest.fixture(autouse=True)
    def clean_hook():
        """Ensure hook is removed after each test."""
        yield
        uninstall_hook()
        # Clean up any imported modules
        for mod in list(sys.modules.keys()):
            if mod.startswith("graphql."):
                del sys.modules[mod]

    def installs_and_uninstalls():
        assert is_hook_installed() is False

        assert install_hook() is True  # Newly installed
        assert is_hook_installed() is True
        assert install_hook() is False  # Already installed

        assert uninstall_hook() is True
        assert is_hook_installed() is False
        assert uninstall_hook() is False  # Already removed

    def hook_is_first_in_meta_path():
        install_hook()
        finder = sys.meta_path[0]
        assert isinstance(finder, TurboFinder)

    def redirects_compiled_modules():
        install_hook()

        # Import a module that should be redirected
        from graphql.language import parser

        # Verify it's actually the turbo version
        assert "graphql_turbo" in parser.__file__

    def does_not_redirect_non_compiled_modules():
        install_hook()

        # Import a module that should NOT be redirected
        from graphql import error

        # Verify it's the original
        assert "graphql_turbo" not in error.__file__
```

**File**: `tests/test_equivalence.py`

```python
"""Tests that compiled modules produce identical results to pure Python."""

import pytest


def describe_behavioral_equivalence():
    """Compiled modules must produce identical results to pure Python."""

    @pytest.fixture
    def pure_parser():
        """Get the pure Python parser."""
        # Direct import bypassing hook
        import importlib.util
        spec = importlib.util.find_spec("graphql.language.parser")
        # ... load without hook

    @pytest.fixture
    def turbo_parser():
        """Get the turbo parser."""
        from graphql_turbo.language import parser
        return parser

    def parse_results_match(pure_parser, turbo_parser):
        query = "{ hello }"
        pure_result = pure_parser.parse(query)
        turbo_result = turbo_parser.parse(query)

        # Compare AST structure
        assert pure_result == turbo_result

    def error_messages_match(pure_parser, turbo_parser):
        bad_query = "{ hello"

        with pytest.raises(Exception) as pure_exc:
            pure_parser.parse(bad_query)

        with pytest.raises(Exception) as turbo_exc:
            turbo_parser.parse(bad_query)

        assert str(pure_exc.value) == str(turbo_exc.value)
```

### 3.4 CI Test Matrix

```yaml
# .github/workflows/test.yml additions

jobs:
  test-pure:
    # Existing tests - graphql-core alone

  test-turbo:
    name: Test with turbo
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12", "3.13"]
        os: [ubuntu-latest, macos-latest, windows-latest]
    steps:
      - uses: actions/checkout@v4
      - name: Install dependencies
        run: |
          pip install -e .
          pip install graphql-core-turbo  # From TestPyPI or local
      - name: Run tests
        run: pytest tests/ -v
      - name: Verify turbo is active
        run: |
          python -c "import graphql; assert graphql.is_turbo_active()"

  test-turbo-equivalence:
    name: Behavioral equivalence
    steps:
      - name: Run equivalence tests
        run: pytest tests/turbo/test_equivalence.py -v
```

---

## Phase 4: CI/CD for graphql-core-turbo

### 4.1 Build Matrix for Platform Wheels

```yaml
# graphql-core-turbo/.github/workflows/build.yml

name: Build wheels

on:
  push:
    tags: ["v*"]
  pull_request:
  workflow_dispatch:

jobs:
  build_wheels:
    name: Build wheel on ${{ matrix.os }}
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]

    steps:
      - uses: actions/checkout@v4

      - name: Build wheels
        uses: pypa/cibuildwheel@v2.16
        env:
          # Build for Python 3.10-3.13
          CIBW_BUILD: "cp310-* cp311-* cp312-* cp313-*"
          # Skip PyPy (mypyc doesn't support it)
          CIBW_SKIP: "pp*"
          # Install mypyc build dependency
          CIBW_BEFORE_BUILD: "pip install mypy"
          # Test the built wheel
          CIBW_TEST_COMMAND: "python -c \"from graphql_turbo.language import parser\""

      - uses: actions/upload-artifact@v4
        with:
          name: wheels-${{ matrix.os }}
          path: ./wheelhouse/*.whl

  build_sdist:
    name: Build source distribution
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install build
      - run: python -m build --sdist
      - uses: actions/upload-artifact@v4
        with:
          name: sdist
          path: dist/*.tar.gz

  publish:
    needs: [build_wheels, build_sdist]
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/v')
    steps:
      - uses: actions/download-artifact@v4
        with:
          path: dist
          merge-multiple: true
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          password: ${{ secrets.PYPI_TOKEN }}
```

---

## Phase 5: Implementation Order

### Step 1: Validate mypyc Compatibility (Week 1)
- [ ] Add mypyc to dev dependencies
- [ ] Attempt to compile `language/parser.py` with mypyc
- [ ] Fix any incompatible patterns (usually dynamic features)
- [ ] Verify tests pass with compiled module

### Step 2: Create graphql-core-turbo Repository (Week 1)
- [ ] Initialize new repository
- [ ] Copy relevant source files
- [ ] Set up mypyc build configuration
- [ ] Create basic CI pipeline

### Step 3: Implement Import Hook (Week 2)
- [ ] Write `_hook.py` with TurboFinder
- [ ] Write `__init__.py` with activate/deactivate
- [ ] Test hook mechanism in isolation

### Step 4: Integrate with graphql-core (Week 2)
- [ ] Add `_turbo.py` detection module
- [ ] Modify `__init__.py` for auto-activation
- [ ] Add `[fast]` extras to pyproject.toml
- [ ] Write integration tests

### Step 5: Equivalence Testing (Week 3)
- [ ] Create comprehensive equivalence test suite
- [ ] Run full graphql-core test suite with turbo active
- [ ] Fix any behavioral differences

### Step 6: Performance Benchmarking (Week 3)
- [ ] Extend existing benchmarks to compare pure vs turbo
- [ ] Document expected speedup percentages
- [ ] Integrate with CodSpeed for tracking

### Step 7: Documentation & Release (Week 4)
- [ ] Write user documentation
- [ ] Update README with installation instructions
- [ ] Release graphql-core-turbo to PyPI
- [ ] Release updated graphql-core with `[fast]` extras

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| mypyc incompatible code patterns | Phase 1 validation; refactor as needed |
| Import order issues | Hook installed before any graphql imports |
| Behavioral differences | Comprehensive equivalence tests |
| Platform-specific bugs | Multi-platform CI matrix |
| PyPy incompatibility | PyPy users get pure Python (no turbo) |
| Version drift between packages | Synchronized version numbers; CI tests both |

---

## User Experience

### Installation
```bash
# Pure Python only (current behavior)
pip install graphql-core

# With compiled modules for better performance
pip install graphql-core[fast]
```

### Usage (no code changes required)
```python
import graphql

# Check if turbo is active (optional, for debugging)
print(f"Turbo active: {graphql.is_turbo_active()}")
# Turbo active: True

# Use graphql normally - compiled modules used automatically
result = graphql.graphql_sync(schema, "{ hello }")
```

### Opting out (if needed)
```python
# Before importing graphql:
import graphql_turbo
graphql_turbo.deactivate()

import graphql  # Now uses pure Python
```

---

## Open Questions

1. **Package naming**: `graphql-core-turbo` vs `graphql-core-fast` vs `graphql-core-compiled`?
2. **Which modules to compile first?** Recommend: parser, lexer, execute (hot paths)
3. **Minimum performance gain threshold?** Should only compile if >10% speedup?
4. **Separate repo or monorepo?** Separate is cleaner for wheel builds
