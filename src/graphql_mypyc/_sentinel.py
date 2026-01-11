"""Sentinel module for mypyc compilation testing.

This module is compiled with mypyc to verify the compilation infrastructure
works correctly. It will be removed once real modules are compiled.
"""

from __future__ import annotations

__all__ = ["SENTINEL_VALUE", "add_numbers", "fibonacci", "is_compiled", "sum_squares"]

# A constant value that can be checked
SENTINEL_VALUE: str = "mypyc-compiled"


def is_compiled() -> bool:
    """Return True if this module was compiled with mypyc.

    Checks if the module is loaded from a .so extension file.
    """
    return __file__.endswith(".so")


def add_numbers(a: int, b: int) -> int:
    """Simple function to test mypyc compilation.

    This is a simple pure function that benefits from mypyc compilation.
    """
    return a + b


def fibonacci(n: int) -> int:
    """Compute fibonacci number recursively.

    This is intentionally slow to show mypyc speedup.
    """
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def sum_squares(n: int) -> int:
    """Sum of squares from 1 to n.

    Loop-based computation that benefits from mypyc.
    """
    total = 0
    for i in range(1, n + 1):
        total += i * i
    return total
