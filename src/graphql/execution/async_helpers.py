"""Async execution helpers optimized for mypyc compilation.

This module extracts inline async closures from execute.py into top-level
async functions. This allows mypyc to compile them effectively since
inline closures in async contexts cause code generation issues.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Awaitable, Sequence

from ..pyutils import gather_with_cancel

if TYPE_CHECKING:
    from .types import ExecutionResult, ExperimentalIncrementalExecutionResults

__all__ = [
    "await_field_result",
    "await_fields_results",
    "await_fields_and_wrap",
    "await_field_completion",
    "await_list_results",
    "await_list_item_completion",
    "await_list_and_wrap",
]


async def await_field_result(
    awaitable_result: Awaitable[Any],
    add_increments_func: Any,
) -> Any:
    """Await a single field result and handle increments.

    Replaces the inline `resolve` closure in execute_fields.
    """
    resolved = await awaitable_result
    add_increments_func(resolved.increments)
    return resolved.result


async def await_fields_results(
    results: dict[str, Any],
    awaitable_fields: list[str],
    increments: list[Any] | None,
) -> tuple[dict[str, Any], list[Any] | None]:
    """Await all field results in parallel.

    Replaces the inline `get_results` closure in execute_fields.
    Returns (results_dict, increments).
    """
    if len(awaitable_fields) == 1:
        # If there is only one field, avoid the overhead of parallelization.
        field = awaitable_fields[0]
        results[field] = await results[field]
    else:
        awaited_results = await gather_with_cancel(
            *(results[field] for field in awaitable_fields)
        )
        for field, sub_result in zip(awaitable_fields, awaited_results, strict=True):
            results[field] = sub_result

    return results, increments


async def await_fields_and_wrap(
    results: dict[str, Any],
    awaitable_fields: list[str],
    get_increments_func: Any,
    wrapped_result_class: type,
) -> Any:
    """Await all field results and return wrapped result.

    Replaces the inline `get_results` closure in execute_fields.
    Note: get_increments_func is used instead of passing increments directly because
    increments might be added during field resolution.
    """
    if len(awaitable_fields) == 1:
        # If there is only one field, avoid the overhead of parallelization.
        field = awaitable_fields[0]
        results[field] = await results[field]
    else:
        awaited_results = await gather_with_cancel(
            *(results[field] for field in awaitable_fields)
        )
        results.update(zip(awaitable_fields, awaited_results, strict=True))

    return wrapped_result_class(results, get_increments_func())


async def await_field_completion(
    completed: Awaitable[Any],
    handle_error_func: Any,
    return_type: Any,
    field_group: Any,
    path: Any,
    incremental_context: Any,
    wrapped_result_class: type,
) -> Any:
    """Await field completion and handle errors.

    Replaces the inline `await_completed` closure in execute_field.
    """
    try:
        return await completed
    except Exception as raw_error:
        handle_error_func(
            raw_error,
            return_type,
            field_group,
            path,
            incremental_context,
        )
        return wrapped_result_class(None)


async def await_list_results(
    completed_results: list[Any],
    awaitable_indices: list[int],
    increments: list[Any] | None,
) -> tuple[list[Any], list[Any] | None]:
    """Await all list item results in parallel.

    Replaces the inline `get_completed_results` closure in complete_iterable_value.
    Returns (results_list, increments).
    """
    if len(awaitable_indices) == 1:
        # If there is only one index, avoid the overhead of parallelization.
        index = awaitable_indices[0]
        completed_results[index] = await completed_results[index]
    else:
        awaited_results = await gather_with_cancel(
            *(completed_results[index] for index in awaitable_indices)
        )
        for index, sub_result in zip(awaitable_indices, awaited_results, strict=True):
            completed_results[index] = sub_result

    return completed_results, increments


async def await_list_and_wrap(
    completed_results: list[Any],
    awaitable_indices: list[int],
    get_increments_func: Any,
    wrapped_result_class: type,
) -> Any:
    """Await all list item results and return wrapped result.

    Replaces the inline `get_completed_results` closure in complete_iterable_value.
    Note: get_increments_func is used instead of passing increments directly because
    increments might be added during list item resolution.
    """
    if len(awaitable_indices) == 1:
        # If there is only one index, avoid the overhead of parallelization.
        index = awaitable_indices[0]
        completed_results[index] = await completed_results[index]
    else:
        awaited_results = await gather_with_cancel(
            *(completed_results[index] for index in awaitable_indices)
        )
        for index, sub_result in zip(awaitable_indices, awaited_results, strict=True):
            completed_results[index] = sub_result

    return wrapped_result_class(completed_results, get_increments_func())


async def await_list_item_completion(
    completed_item: Awaitable[Any],
    handle_error_func: Any,
    item_type: Any,
    field_group: Any,
    item_path: Any,
    incremental_context: Any,
    parent_add_increments: Any,
) -> Any:
    """Await list item completion and handle errors.

    Replaces the inline `await_completed` closure in complete_list_item_value.
    """
    try:
        resolved = await completed_item
    except Exception as raw_error:
        handle_error_func(
            raw_error,
            item_type,
            field_group,
            item_path,
            incremental_context,
        )
        return None
    parent_add_increments(resolved.increments)
    return resolved.result


async def await_serial_field_result(
    awaitable_result: Awaitable[Any],
    graphql_wrapped_result: Any,
    response_name: str,
) -> Any:
    """Await a serial field result and update the wrapped result.

    Replaces the inline `set_result` closure in execute_fields_serially.
    """
    resolved = await awaitable_result
    graphql_wrapped_result.result[response_name] = resolved.result
    graphql_wrapped_result.add_increments(resolved.increments)
    return graphql_wrapped_result


async def await_operation_result(
    awaitable_result: Awaitable[Any],
    build_response_func: Any,
    get_errors_func: Any,
    error_class: type,
    result_class: type,
    with_error_func: Any,
) -> Any:
    """Await operation result and build response.

    Replaces the inline `await_result` closure in execute_operation.
    Note: get_errors_func is used instead of passing errors directly because
    the errors list might be None initially and get assigned later.
    """
    try:
        resolved = await awaitable_result
    except Exception as error:
        if isinstance(error, error_class):
            return result_class(None, with_error_func(get_errors_func(), error))
        raise
    return build_response_func(resolved.result, resolved.increments)
