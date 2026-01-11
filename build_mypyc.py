#!/usr/bin/env python
"""Build script for mypyc compilation of graphql modules.

Usage:
    python build_mypyc.py          # Build all configured modules
    python build_mypyc.py --clean  # Remove compiled extensions
    python build_mypyc.py --bench  # Run benchmark comparison

Benchmarks show ~18x speedup for recursive functions and ~16x for loops.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

# Modules to compile with mypyc.
# Excluded due to mypyc limitations:
#   definition.py - conditional class definitions
#   execute.py - complex async triggers code-gen bugs
#   visitor.py - designed for subclassing
#   block_string.py - duck typing with lazy strings
#   type_comparators.py - type issues (list vs tuple)
MYPYC_MODULES = [
    "graphql_mypyc/_sentinel.py",
    "graphql/type/scalars.py",
    "graphql/language/lexer.py",
    "graphql/language/parser.py",
    "graphql/language/predicates.py",
    "graphql/language/character_classes.py",
    "graphql/utilities/coerce_input_value.py",
    "graphql/utilities/value_from_ast.py",
    "graphql/utilities/ast_from_value.py",
    "graphql/utilities/type_from_ast.py",
    "graphql/execution/collect_fields.py",
    "graphql/execution/values.py",
    "graphql/execution/execute_sync.py",
    "graphql/execution/async_helpers.py",
]


def clean() -> None:
    """Remove all compiled .so files from the source tree."""
    src = Path("src")
    if not src.exists():
        src = Path(".")

    count = 0
    for so_file in src.rglob("*.so"):
        print(f"Removing {so_file}")
        so_file.unlink()
        count += 1

    # Also clean build artifacts
    for dirname in ["build", ".mypy_cache"]:
        dirpath = Path(dirname)
        if dirpath.exists():
            print(f"Removing {dirpath}/")
            shutil.rmtree(dirpath)

    print(f"Cleaned {count} .so files")


def build() -> int:
    """Compile modules with mypyc."""
    if not MYPYC_MODULES:
        print("No modules configured for compilation")
        return 0

    # Change to src directory for proper module resolution
    original_dir = os.getcwd()
    src_dir = Path("src")
    if src_dir.exists():
        os.chdir(src_dir)

    try:
        # Verify all modules exist
        for module in MYPYC_MODULES:
            if not Path(module).exists():
                print(f"Error: {module} not found")
                return 1

        print(f"Compiling {len(MYPYC_MODULES)} modules with mypyc...")
        print("Modules:", MYPYC_MODULES)

        try:
            from mypyc.build import mypycify
        except ImportError:
            print("Error: mypyc not installed. Install with: pip install mypy")
            return 1

        # Use mypycify to get extension modules
        try:
            ext_modules = mypycify(
                MYPYC_MODULES,
                opt_level="3",
                debug_level="0",
            )
        except Exception as e:
            print(f"mypycify failed: {e}")
            return 1

        if not ext_modules:
            print("No extension modules generated")
            return 1

        # Build the extensions in-place
        from setuptools import Distribution
        from setuptools.command.build_ext import build_ext

        dist = Distribution({"ext_modules": ext_modules})
        cmd = build_ext(dist)
        cmd.inplace = True
        cmd.ensure_finalized()

        try:
            cmd.run()
        except Exception as e:
            print(f"Build failed: {e}")
            return 1

        print("\nBuild successful!")
        # Show what was built
        for module in MYPYC_MODULES:
            path = Path(module)
            for so_file in path.parent.glob(f"{path.stem}*.so"):
                print(f"  Built: {so_file}")

        return 0

    finally:
        os.chdir(original_dir)


def benchmark() -> int:
    """Run benchmark comparing interpreted vs compiled."""
    import time
    import importlib.util

    print("=== Compiled (graphql_mypyc._sentinel) ===")

    from graphql_mypyc import _sentinel as compiled

    print(f"Module: {compiled.__file__}")
    print(f"is_compiled: {compiled.is_compiled()}")

    # Test fibonacci
    n = 30
    start = time.perf_counter()
    result = compiled.fibonacci(n)
    elapsed_compiled_fib = time.perf_counter() - start
    print(f"fibonacci({n}) = {result} in {elapsed_compiled_fib:.4f}s")

    # Test sum_squares
    n = 1_000_000
    start = time.perf_counter()
    result = compiled.sum_squares(n)
    elapsed_compiled_sq = time.perf_counter() - start
    print(f"sum_squares({n}) = {result} in {elapsed_compiled_sq:.6f}s")

    print()
    print("=== Interpreted (graphql._sentinel) ===")

    # Import the interpreted version directly by path
    spec = importlib.util.spec_from_file_location(
        "_sentinel_interp", "src/graphql/_sentinel.py"
    )
    interp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(interp)  # type: ignore[union-attr]
    print(f"Module: {interp.__file__}")
    print(f"is_compiled: {interp.is_compiled()}")

    # Test fibonacci
    n = 30
    start = time.perf_counter()
    result = interp.fibonacci(n)
    elapsed_interp_fib = time.perf_counter() - start
    print(f"fibonacci({n}) = {result} in {elapsed_interp_fib:.4f}s")

    # Test sum_squares
    n = 1_000_000
    start = time.perf_counter()
    result = interp.sum_squares(n)
    elapsed_interp_sq = time.perf_counter() - start
    print(f"sum_squares({n}) = {result} in {elapsed_interp_sq:.6f}s")

    print()
    print("=== Speedup ===")
    print(f"fibonacci: {elapsed_interp_fib/elapsed_compiled_fib:.1f}x faster")
    print(f"sum_squares: {elapsed_interp_sq/elapsed_compiled_sq:.1f}x faster")

    return 0


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Build graphql modules with mypyc")
    parser.add_argument(
        "--clean", action="store_true", help="Remove compiled extensions"
    )
    parser.add_argument(
        "--bench", action="store_true", help="Run benchmark comparison"
    )
    args = parser.parse_args()

    if args.clean:
        clean()
        return 0

    if args.bench:
        return benchmark()

    return build()


if __name__ == "__main__":
    sys.exit(main())
