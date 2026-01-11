#!/usr/bin/env python
"""Profile GraphQL execution to find optimization opportunities."""

from __future__ import annotations

import cProfile
import pstats
import time
from io import StringIO

# Ensure we use the local src
import sys
sys.path.insert(0, 'src')

from graphql import (
    GraphQLField,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
    execute_sync,
    parse,
)


def create_test_schema() -> GraphQLSchema:
    """Create a schema with nested objects for testing."""

    # Deeply nested object type
    item_type = GraphQLObjectType(
        "Item",
        {
            "id": GraphQLField(GraphQLNonNull(GraphQLInt)),
            "name": GraphQLField(GraphQLNonNull(GraphQLString)),
            "value": GraphQLField(GraphQLInt),
            "description": GraphQLField(GraphQLString),
        },
    )

    category_type = GraphQLObjectType(
        "Category",
        {
            "id": GraphQLField(GraphQLNonNull(GraphQLInt)),
            "name": GraphQLField(GraphQLNonNull(GraphQLString)),
            "items": GraphQLField(GraphQLList(item_type)),
        },
    )

    user_type = GraphQLObjectType(
        "User",
        {
            "id": GraphQLField(GraphQLNonNull(GraphQLInt)),
            "name": GraphQLField(GraphQLNonNull(GraphQLString)),
            "email": GraphQLField(GraphQLString),
            "categories": GraphQLField(GraphQLList(category_type)),
        },
    )

    query_type = GraphQLObjectType(
        "Query",
        {
            "users": GraphQLField(
                GraphQLList(user_type),
                resolve=lambda obj, info: generate_users(50),
            ),
        },
    )

    return GraphQLSchema(query_type)


def generate_users(count: int) -> list[dict]:
    """Generate test user data."""
    users = []
    for i in range(count):
        users.append({
            "id": i,
            "name": f"User {i}",
            "email": f"user{i}@example.com",
            "categories": [
                {
                    "id": j,
                    "name": f"Category {j}",
                    "items": [
                        {
                            "id": k,
                            "name": f"Item {k}",
                            "value": k * 10,
                            "description": f"Description for item {k}",
                        }
                        for k in range(10)
                    ],
                }
                for j in range(5)
            ],
        })
    return users


QUERY = """
{
    users {
        id
        name
        email
        categories {
            id
            name
            items {
                id
                name
                value
                description
            }
        }
    }
}
"""


def benchmark(schema: GraphQLSchema, document, iterations: int = 100) -> float:
    """Run benchmark and return average time per execution."""
    # Warmup
    for _ in range(5):
        execute_sync(schema, document)

    start = time.perf_counter()
    for _ in range(iterations):
        result = execute_sync(schema, document)
        assert result.errors is None, result.errors
    elapsed = time.perf_counter() - start
    return elapsed / iterations


def profile_execution(schema: GraphQLSchema, document, iterations: int = 20):
    """Profile execution and print stats."""
    profiler = cProfile.Profile()
    profiler.enable()

    for _ in range(iterations):
        execute_sync(schema, document)

    profiler.disable()

    # Print stats
    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats(pstats.SortKey.CUMULATIVE)
    ps.print_stats(40)
    print(s.getvalue())

    # Also print by total time
    print("\n=== By Total Time ===\n")
    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats(pstats.SortKey.TIME)
    ps.print_stats(30)
    print(s.getvalue())


def count_fields():
    """Count how many fields are resolved per execution."""
    # 50 users x (3 scalar fields + 1 list)
    # + 50 users x 5 categories x (2 scalar fields + 1 list)
    # + 50 users x 5 categories x 10 items x 4 scalar fields
    users = 50
    user_scalars = 3  # id, name, email
    categories_per_user = 5
    category_scalars = 2  # id, name
    items_per_category = 10
    item_scalars = 4  # id, name, value, description

    total = (
        users * user_scalars +
        users * categories_per_user * category_scalars +
        users * categories_per_user * items_per_category * item_scalars
    )

    # Plus list handling
    list_fields = (
        1 +  # users
        users * 1 +  # categories per user
        users * categories_per_user * 1  # items per category
    )

    print(f"Scalar fields resolved: {total}")
    print(f"List fields resolved: {list_fields}")
    print(f"Total field resolutions: {total + list_fields}")


def main():
    print("=== GraphQL Execution Profiler ===\n")

    schema = create_test_schema()
    document = parse(QUERY)

    count_fields()
    print()

    # First, run benchmark to get timing
    print("Running benchmark...")
    avg_time = benchmark(schema, document, iterations=100)
    print(f"Average execution time: {avg_time*1000:.2f}ms")
    print(f"Target for 2X: {avg_time*1000/2:.2f}ms")
    print()

    # Then profile to find bottlenecks
    print("=== Profiling (20 iterations) ===\n")
    profile_execution(schema, document, iterations=20)


if __name__ == "__main__":
    main()
