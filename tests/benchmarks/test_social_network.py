"""Benchmark for social network schema with async resolvers.

This benchmark simulates a realistic social network API with:
- Nested object types (User -> Posts -> Comments -> Author)
- List fields with multiple items
- All async resolvers to test the async execution path
- Various query depths and breadths

Queries are pre-parsed and pre-validated to measure only execution time.
Uses uvloop for faster async execution.
"""

import asyncio
from typing import Any

import pytest
import uvloop

# Set uvloop as the default event loop policy
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

from graphql import (
    DocumentNode,
    GraphQLArgument,
    GraphQLField,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
    execute,
    parse,
    validate,
)

# Simulated data store
USERS = {
    str(i): {
        "id": str(i),
        "username": f"user_{i}",
        "email": f"user{i}@example.com",
        "displayName": f"User {i}",
        "bio": f"This is the bio for user {i}. They enjoy coding and GraphQL.",
        "followerCount": i * 100,
        "followingCount": i * 50,
        "createdAt": "2024-01-15T10:30:00Z",
    }
    for i in range(1, 101)
}

POSTS = {
    str(i): {
        "id": str(i),
        "authorId": str((i % 10) + 1),
        "title": f"Post {i}: Interesting thoughts about GraphQL",
        "content": f"This is the content of post {i}. " * 5,
        "likeCount": i * 10,
        "commentCount": i % 20,
        "createdAt": "2024-01-20T14:00:00Z",
        "updatedAt": "2024-01-21T09:00:00Z",
    }
    for i in range(1, 201)
}

COMMENTS = {
    str(i): {
        "id": str(i),
        "postId": str((i % 50) + 1),
        "authorId": str((i % 10) + 1),
        "text": f"This is comment {i}. Great post!",
        "likeCount": i % 50,
        "createdAt": "2024-01-22T11:00:00Z",
    }
    for i in range(1, 501)
}


# Async resolvers that simulate minimal async overhead
async def resolve_user(_obj: Any, _info: Any, id: str) -> dict | None:
    return USERS.get(id)


async def resolve_users(_obj: Any, _info: Any, limit: int = 10) -> list[dict]:
    return list(USERS.values())[:limit]


async def resolve_post(_obj: Any, _info: Any, id: str) -> dict | None:
    return POSTS.get(id)


async def resolve_posts(_obj: Any, _info: Any, limit: int = 10) -> list[dict]:
    return list(POSTS.values())[:limit]


async def resolve_user_posts(user: dict, _info: Any, limit: int = 10) -> list[dict]:
    user_id = user["id"]
    return [p for p in POSTS.values() if p["authorId"] == user_id][:limit]


async def resolve_post_author(post: dict, _info: Any) -> dict | None:
    return USERS.get(post["authorId"])


async def resolve_post_comments(post: dict, _info: Any, limit: int = 10) -> list[dict]:
    post_id = post["id"]
    return [c for c in COMMENTS.values() if c["postId"] == post_id][:limit]


async def resolve_comment_author(comment: dict, _info: Any) -> dict | None:
    return USERS.get(comment["authorId"])


async def resolve_comment_post(comment: dict, _info: Any) -> dict | None:
    return POSTS.get(comment["postId"])


async def resolve_user_followers(user: dict, _info: Any, limit: int = 10) -> list[dict]:
    # Simulate followers as other users
    user_id = int(user["id"])
    follower_ids = [(user_id + i) % 100 + 1 for i in range(1, limit + 1)]
    return [USERS[str(fid)] for fid in follower_ids if str(fid) in USERS]


async def resolve_user_following(user: dict, _info: Any, limit: int = 10) -> list[dict]:
    user_id = int(user["id"])
    following_ids = [(user_id + i * 2) % 100 + 1 for i in range(1, limit + 1)]
    return [USERS[str(fid)] for fid in following_ids if str(fid) in USERS]


# Note: Scalar fields use the default resolver (dict key access) which is sync.
# Only relationship fields (author, posts, comments, followers, following) have
# explicit async resolvers to simulate real-world data fetching patterns.


# Build schema - scalar fields use default resolver, only relationships are async
CommentType: GraphQLObjectType = GraphQLObjectType(
    name="Comment",
    fields=lambda: {
        "id": GraphQLField(GraphQLNonNull(GraphQLString)),
        "text": GraphQLField(GraphQLNonNull(GraphQLString)),
        "likeCount": GraphQLField(GraphQLNonNull(GraphQLInt)),
        "createdAt": GraphQLField(GraphQLNonNull(GraphQLString)),
        "author": GraphQLField(UserType, resolve=resolve_comment_author),
        "post": GraphQLField(PostType, resolve=resolve_comment_post),
    },
)

PostType: GraphQLObjectType = GraphQLObjectType(
    name="Post",
    fields=lambda: {
        "id": GraphQLField(GraphQLNonNull(GraphQLString)),
        "title": GraphQLField(GraphQLNonNull(GraphQLString)),
        "content": GraphQLField(GraphQLNonNull(GraphQLString)),
        "likeCount": GraphQLField(GraphQLNonNull(GraphQLInt)),
        "commentCount": GraphQLField(GraphQLNonNull(GraphQLInt)),
        "createdAt": GraphQLField(GraphQLNonNull(GraphQLString)),
        "updatedAt": GraphQLField(GraphQLNonNull(GraphQLString)),
        "author": GraphQLField(UserType, resolve=resolve_post_author),
        "comments": GraphQLField(
            GraphQLNonNull(GraphQLList(GraphQLNonNull(CommentType))),
            args={"limit": GraphQLArgument(GraphQLInt, default_value=10)},
            resolve=resolve_post_comments,
        ),
    },
)

UserType: GraphQLObjectType = GraphQLObjectType(
    name="User",
    fields=lambda: {
        "id": GraphQLField(GraphQLNonNull(GraphQLString)),
        "username": GraphQLField(GraphQLNonNull(GraphQLString)),
        "email": GraphQLField(GraphQLNonNull(GraphQLString)),
        "displayName": GraphQLField(GraphQLNonNull(GraphQLString)),
        "bio": GraphQLField(GraphQLNonNull(GraphQLString)),
        "followerCount": GraphQLField(GraphQLNonNull(GraphQLInt)),
        "followingCount": GraphQLField(GraphQLNonNull(GraphQLInt)),
        "createdAt": GraphQLField(GraphQLNonNull(GraphQLString)),
        "posts": GraphQLField(
            GraphQLNonNull(GraphQLList(GraphQLNonNull(PostType))),
            args={"limit": GraphQLArgument(GraphQLInt, default_value=10)},
            resolve=resolve_user_posts,
        ),
        "followers": GraphQLField(
            GraphQLNonNull(GraphQLList(GraphQLNonNull(UserType))),
            args={"limit": GraphQLArgument(GraphQLInt, default_value=10)},
            resolve=resolve_user_followers,
        ),
        "following": GraphQLField(
            GraphQLNonNull(GraphQLList(GraphQLNonNull(UserType))),
            args={"limit": GraphQLArgument(GraphQLInt, default_value=10)},
            resolve=resolve_user_following,
        ),
    },
)

QueryType = GraphQLObjectType(
    name="Query",
    fields={
        "user": GraphQLField(
            UserType,
            args={"id": GraphQLArgument(GraphQLNonNull(GraphQLString))},
            resolve=resolve_user,
        ),
        "users": GraphQLField(
            GraphQLNonNull(GraphQLList(GraphQLNonNull(UserType))),
            args={"limit": GraphQLArgument(GraphQLInt, default_value=10)},
            resolve=resolve_users,
        ),
        "post": GraphQLField(
            PostType,
            args={"id": GraphQLArgument(GraphQLNonNull(GraphQLString))},
            resolve=resolve_post,
        ),
        "posts": GraphQLField(
            GraphQLNonNull(GraphQLList(GraphQLNonNull(PostType))),
            args={"limit": GraphQLArgument(GraphQLInt, default_value=10)},
            resolve=resolve_posts,
        ),
    },
)

schema = GraphQLSchema(query=QueryType)


# Test queries of varying complexity

# Simple: Single user with basic fields
QUERY_SIMPLE = """
query {
    user(id: "1") {
        id
        username
        displayName
        bio
    }
}
"""

# Medium: User with posts
QUERY_MEDIUM = """
query {
    user(id: "1") {
        id
        username
        displayName
        followerCount
        followingCount
        posts(limit: 5) {
            id
            title
            content
            likeCount
            commentCount
        }
    }
}
"""

# Complex: User with posts, comments, and nested authors
QUERY_COMPLEX = """
query {
    user(id: "1") {
        id
        username
        displayName
        bio
        followerCount
        followingCount
        createdAt
        posts(limit: 5) {
            id
            title
            content
            likeCount
            commentCount
            createdAt
            author {
                id
                username
            }
            comments(limit: 3) {
                id
                text
                likeCount
                author {
                    id
                    username
                    displayName
                }
            }
        }
    }
}
"""

# Feed: Multiple posts with authors and comments (typical feed query)
QUERY_FEED = """
query {
    posts(limit: 10) {
        id
        title
        content
        likeCount
        commentCount
        createdAt
        author {
            id
            username
            displayName
        }
        comments(limit: 3) {
            id
            text
            author {
                id
                username
            }
        }
    }
}
"""

# Social: User with followers and following (tests recursive types)
QUERY_SOCIAL = """
query {
    user(id: "1") {
        id
        username
        displayName
        followerCount
        followingCount
        followers(limit: 5) {
            id
            username
            displayName
            followerCount
        }
        following(limit: 5) {
            id
            username
            displayName
            followerCount
        }
    }
}
"""

# Deep: Deeply nested query
QUERY_DEEP = """
query {
    user(id: "1") {
        id
        username
        posts(limit: 3) {
            id
            title
            author {
                id
                username
                posts(limit: 2) {
                    id
                    title
                    comments(limit: 2) {
                        id
                        text
                        author {
                            id
                            username
                        }
                    }
                }
            }
        }
    }
}
"""


def _prepare_query(query_str: str) -> DocumentNode:
    """Parse and validate a query, returning the document for execution."""
    document = parse(query_str)
    errors = validate(schema, document)
    if errors:
        raise ValueError(f"Query validation failed: {errors}")
    return document


# Pre-parse and pre-validate all queries at module load time
# This ensures benchmarks measure only execution time
DOC_SIMPLE = _prepare_query(QUERY_SIMPLE)
DOC_MEDIUM = _prepare_query(QUERY_MEDIUM)
DOC_COMPLEX = _prepare_query(QUERY_COMPLEX)
DOC_FEED = _prepare_query(QUERY_FEED)
DOC_SOCIAL = _prepare_query(QUERY_SOCIAL)
DOC_DEEP = _prepare_query(QUERY_DEEP)


@pytest.fixture
def event_loop():
    """Create uvloop event loop for async benchmarks."""
    loop = uvloop.new_event_loop()
    yield loop
    loop.close()


def test_social_simple(benchmark, event_loop):
    """Benchmark simple user query with 4 scalar fields (execution only)."""
    asyncio.set_event_loop(event_loop)
    result = benchmark(lambda: event_loop.run_until_complete(execute(schema, DOC_SIMPLE)))
    assert not result.errors
    assert result.data["user"]["username"] == "user_1"


def test_social_medium(benchmark, event_loop):
    """Benchmark user with posts - 5 posts, 5 fields each (execution only)."""
    asyncio.set_event_loop(event_loop)
    result = benchmark(lambda: event_loop.run_until_complete(execute(schema, DOC_MEDIUM)))
    assert not result.errors
    assert len(result.data["user"]["posts"]) == 5


def test_social_complex(benchmark, event_loop):
    """Benchmark complex nested query - user -> posts -> comments -> authors (execution only)."""
    asyncio.set_event_loop(event_loop)
    result = benchmark(lambda: event_loop.run_until_complete(execute(schema, DOC_COMPLEX)))
    assert not result.errors
    assert len(result.data["user"]["posts"]) == 5


def test_social_feed(benchmark, event_loop):
    """Benchmark feed query - 10 posts with authors and comments (execution only)."""
    asyncio.set_event_loop(event_loop)
    result = benchmark(lambda: event_loop.run_until_complete(execute(schema, DOC_FEED)))
    assert not result.errors
    assert len(result.data["posts"]) == 10


def test_social_network(benchmark, event_loop):
    """Benchmark social graph query - user with followers and following (execution only)."""
    asyncio.set_event_loop(event_loop)
    result = benchmark(lambda: event_loop.run_until_complete(execute(schema, DOC_SOCIAL)))
    assert not result.errors
    assert len(result.data["user"]["followers"]) == 5
    assert len(result.data["user"]["following"]) == 5


def test_social_deep(benchmark, event_loop):
    """Benchmark deeply nested query - 4 levels deep (execution only)."""
    asyncio.set_event_loop(event_loop)
    result = benchmark(lambda: event_loop.run_until_complete(execute(schema, DOC_DEEP)))
    assert not result.errors
    assert len(result.data["user"]["posts"]) == 3
