"""Sync execution helpers optimized for mypyc compilation.

This module contains the hot paths of GraphQL execution extracted
for mypyc compilation. These functions avoid async/await which
mypyc doesn't handle well.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..pyutils import Undefined

if TYPE_CHECKING:
    from ..type import GraphQLLeafType, GraphQLOutputType

__all__ = [
    "complete_leaf_value",
    "resolve_field_value_sync",
    "unwrap_type",
]


def complete_leaf_value(return_type: GraphQLLeafType, result: Any) -> Any:
    """Complete a leaf value.

    Complete a Scalar or Enum by serializing to a valid value, returning null if
    serialization is not possible.
    """
    serialized_result = return_type.serialize(result)
    if serialized_result is Undefined or serialized_result is None:
        msg = (
            f"Expected `{return_type}.serialize({result!r})`"
            " to return non-nullable value, returned:"
            f" {serialized_result!r}"
        )
        raise TypeError(msg)
    return serialized_result


def resolve_field_value_sync(
    source: Any,
    field_name: str,
) -> Any:
    """Resolve a field value synchronously using default resolution.

    This is the inlined default resolver logic optimized for the common case
    of dict sources.
    """
    # Check dict first (most common) to avoid expensive Mapping isinstance
    source_type = type(source)
    if source_type is dict:
        return source.get(field_name)
    # For other mapping types, use get
    if hasattr(source, "get") and callable(source.get):
        return source.get(field_name)
    # For objects, use getattr
    return getattr(source, field_name, None)


def unwrap_type(
    return_type: GraphQLOutputType,
) -> tuple[GraphQLOutputType, bool, bool]:
    """Unwrap a type and return (inner_type, is_non_null, is_list).

    This extracts the inner type from NonNull and List wrappers.
    """
    is_non_null = return_type._is_non_null_type
    if is_non_null:
        inner = return_type.of_type  # type: ignore[union-attr]
        is_list = inner._is_list_type
        if is_list:
            return inner.of_type, True, True  # type: ignore[union-attr]
        return inner, True, False

    is_list = return_type._is_list_type
    if is_list:
        return return_type.of_type, False, True  # type: ignore[union-attr]

    return return_type, False, False


def complete_sync_leaf_field(
    return_type: GraphQLOutputType,
    source: Any,
    field_name: str,
    parent_type_name: str,
) -> tuple[Any, bool]:
    """Complete a leaf field synchronously.

    Returns (result, success). If success is False, caller should use standard path.

    This is the fast path for:
    - Default resolver (no custom resolver)
    - Leaf type return (scalar/enum)
    - Sync execution (no awaitables)
    """
    # Resolve the value
    result = resolve_field_value_sync(source, field_name)

    # If callable, need to use standard path (may need ResolveInfo)
    if callable(result):
        return None, False

    # Unwrap NonNull if present
    inner_type = return_type
    is_non_null = return_type._is_non_null_type
    if is_non_null:
        inner_type = return_type.of_type  # type: ignore[union-attr]

    # Only handle leaf types in fast path
    if not inner_type._is_leaf_type:
        return None, False

    # Handle null
    if result is None or result is Undefined:
        if is_non_null:
            msg = (
                f"Cannot return null for non-nullable field"
                f" {parent_type_name}.{field_name}."
            )
            raise TypeError(msg)
        return None, True

    # Handle exceptions
    if isinstance(result, Exception):
        raise result

    # Serialize the leaf value
    serialized = complete_leaf_value(inner_type, result)  # type: ignore[arg-type]
    return serialized, True
