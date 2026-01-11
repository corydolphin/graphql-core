"""Benchmark for social network schema with async resolvers.

This benchmark simulates a realistic social network API with:
- Nested object types (User -> Posts -> Comments -> Author)
- List fields with multiple items
- All async resolvers to test the async execution path
- Various query depths and breadths
"""

import asyncio
from typing import Any

import pytest

from graphql import (
    GraphQLArgument,
    GraphQLField,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
    graphql,
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


# Field resolvers for scalar fields (still async to test async path)
async def resolve_id(obj: dict, _info: Any) -> str:
    return obj["id"]


async def resolve_username(obj: dict, _info: Any) -> str:
    return obj["username"]


async def resolve_email(obj: dict, _info: Any) -> str:
    return obj["email"]


async def resolve_display_name(obj: dict, _info: Any) -> str:
    return obj["displayName"]


async def resolve_bio(obj: dict, _info: Any) -> str:
    return obj["bio"]


async def resolve_follower_count(obj: dict, _info: Any) -> int:
    return obj["followerCount"]


async def resolve_following_count(obj: dict, _info: Any) -> int:
    return obj["followingCount"]


async def resolve_title(obj: dict, _info: Any) -> str:
    return obj["title"]


async def resolve_content(obj: dict, _info: Any) -> str:
    return obj["content"]


async def resolve_text(obj: dict, _info: Any) -> str:
    return obj["text"]


async def resolve_like_count(obj: dict, _info: Any) -> int:
    return obj["likeCount"]


async def resolve_comment_count(obj: dict, _info: Any) -> int:
    return obj["commentCount"]


async def resolve_created_at(obj: dict, _info: Any) -> str:
    return obj["createdAt"]


async def resolve_updated_at(obj: dict, _info: Any) -> str:
    return obj.get("updatedAt", obj["createdAt"])


# Build schema with explicit async resolvers
CommentType: GraphQLObjectType = GraphQLObjectType(
    name="Comment",
    fields=lambda: {
        "id": GraphQLField(GraphQLNonNull(GraphQLString), resolve=resolve_id),
        "text": GraphQLField(GraphQLNonNull(GraphQLString), resolve=resolve_text),
        "likeCount": GraphQLField(GraphQLNonNull(GraphQLInt), resolve=resolve_like_count),
        "createdAt": GraphQLField(GraphQLNonNull(GraphQLString), resolve=resolve_created_at),
        "author": GraphQLField(UserType, resolve=resolve_comment_author),
        "post": GraphQLField(PostType, resolve=resolve_comment_post),
    },
)

PostType: GraphQLObjectType = GraphQLObjectType(
    name="Post",
    fields=lambda: {
        "id": GraphQLField(GraphQLNonNull(GraphQLString), resolve=resolve_id),
        "title": GraphQLField(GraphQLNonNull(GraphQLString), resolve=resolve_title),
        "content": GraphQLField(GraphQLNonNull(GraphQLString), resolve=resolve_content),
        "likeCount": GraphQLField(GraphQLNonNull(GraphQLInt), resolve=resolve_like_count),
        "commentCount": GraphQLField(GraphQLNonNull(GraphQLInt), resolve=resolve_comment_count),
        "createdAt": GraphQLField(GraphQLNonNull(GraphQLString), resolve=resolve_created_at),
        "updatedAt": GraphQLField(GraphQLNonNull(GraphQLString), resolve=resolve_updated_at),
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
        "id": GraphQLField(GraphQLNonNull(GraphQLString), resolve=resolve_id),
        "username": GraphQLField(GraphQLNonNull(GraphQLString), resolve=resolve_username),
        "email": GraphQLField(GraphQLNonNull(GraphQLString), resolve=resolve_email),
        "displayName": GraphQLField(GraphQLNonNull(GraphQLString), resolve=resolve_display_name),
        "bio": GraphQLField(GraphQLNonNull(GraphQLString), resolve=resolve_bio),
        "followerCount": GraphQLField(GraphQLNonNull(GraphQLInt), resolve=resolve_follower_count),
        "followingCount": GraphQLField(GraphQLNonNull(GraphQLInt), resolve=resolve_following_count),
        "createdAt": GraphQLField(GraphQLNonNull(GraphQLString), resolve=resolve_created_at),
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


@pytest.fixture
def event_loop():
    """Create event loop for async benchmarks."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def test_social_simple(benchmark, event_loop):
    """Benchmark simple user query with 4 scalar fields."""
    asyncio.set_event_loop(event_loop)
    result = benchmark(lambda: event_loop.run_until_complete(graphql(schema, QUERY_SIMPLE)))
    assert not result.errors
    assert result.data["user"]["username"] == "user_1"


def test_social_medium(benchmark, event_loop):
    """Benchmark user with posts (5 posts, 5 fields each)."""
    asyncio.set_event_loop(event_loop)
    result = benchmark(lambda: event_loop.run_until_complete(graphql(schema, QUERY_MEDIUM)))
    assert not result.errors
    assert len(result.data["user"]["posts"]) == 5


def test_social_complex(benchmark, event_loop):
    """Benchmark complex nested query (user -> posts -> comments -> authors)."""
    asyncio.set_event_loop(event_loop)
    result = benchmark(lambda: event_loop.run_until_complete(graphql(schema, QUERY_COMPLEX)))
    assert not result.errors
    assert len(result.data["user"]["posts"]) == 5


def test_social_feed(benchmark, event_loop):
    """Benchmark feed query (10 posts with authors and comments)."""
    asyncio.set_event_loop(event_loop)
    result = benchmark(lambda: event_loop.run_until_complete(graphql(schema, QUERY_FEED)))
    assert not result.errors
    assert len(result.data["posts"]) == 10


def test_social_network(benchmark, event_loop):
    """Benchmark social graph query (user with followers and following)."""
    asyncio.set_event_loop(event_loop)
    result = benchmark(lambda: event_loop.run_until_complete(graphql(schema, QUERY_SOCIAL)))
    assert not result.errors
    assert len(result.data["user"]["followers"]) == 5
    assert len(result.data["user"]["following"]) == 5


def test_social_deep(benchmark, event_loop):
    """Benchmark deeply nested query (4 levels deep)."""
    asyncio.set_event_loop(event_loop)
    result = benchmark(lambda: event_loop.run_until_complete(graphql(schema, QUERY_DEEP)))
    assert not result.errors
    assert len(result.data["user"]["posts"]) == 3
