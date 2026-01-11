"""Sentinel module for mypyc compilation testing (interpreted version).

This is the interpreted fallback version. When graphql_mypyc is installed
and the import hook is active, this module is replaced with the compiled version.
"""

from __future__ import annotations

__all__ = ["SENTINEL_VALUE", "add_numbers", "fibonacci", "is_compiled", "sum_squares"]

SENTINEL_VALUE: str = "interpreted"


def is_compiled() -> bool:
    """Return True if this module was compiled with mypyc."""
    return False


def add_numbers(a: int, b: int) -> int:
    """Simple function to test mypyc compilation."""
    return a + b


def fibonacci(n: int) -> int:
    """Compute fibonacci number recursively."""
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def sum_squares(n: int) -> int:
    """Sum of squares from 1 to n."""
    total = 0
    for i in range(1, n + 1):
        total += i * i
    return total
