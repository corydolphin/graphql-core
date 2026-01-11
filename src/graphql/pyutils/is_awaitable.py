"""Check whether objects are awaitable"""

from __future__ import annotations

import inspect
from types import CoroutineType, GeneratorType
from typing import TYPE_CHECKING, Any, TypeGuard

if TYPE_CHECKING:
    from collections.abc import Awaitable

__all__ = ["is_awaitable"]

CO_ITERABLE_COROUTINE = inspect.CO_ITERABLE_COROUTINE

# Fast-path set of types that are never awaitable
# Using type() check is faster than isinstance() for common cases
_NON_AWAITABLE_TYPES: frozenset[type] = frozenset(
    {
        str,
        int,
        float,
        bool,
        dict,
        list,
        tuple,
        type(None),
        bytes,
        set,
        frozenset,
    }
)


def is_awaitable(value: Any) -> TypeGuard[Awaitable]:
    """Return True if object can be passed to an ``await`` expression.

    Instead of testing whether the object is an instance of abc.Awaitable, we
    check the existence of an `__await__` attribute. This is much faster.
    """
    # Fast path: common types that are never awaitable
    # type() is faster than isinstance() and these exact types cannot be awaitable
    if type(value) in _NON_AWAITABLE_TYPES:
        return False

    return (
        # check for coroutine objects
        isinstance(value, CoroutineType)
        # check for old-style generator based coroutine objects
        or (
            isinstance(value, GeneratorType)  # for Python < 3.11
            and bool(value.gi_code.co_flags & CO_ITERABLE_COROUTINE)
        )
        # check for other awaitables (e.g. futures)
        or hasattr(value, "__await__")
    )
