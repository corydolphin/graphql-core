"""Character classes

Performance-optimized using frozenset lookups (faster than str methods).
"""

__all__ = [
    "is_digit",
    "is_letter",
    "is_name_continue",
    "is_name_start",
    "DIGITS",
    "NAME_CONTINUE",
    "NAME_START",
    "WHITESPACE",
]

# Pre-computed character sets for O(1) lookup
# Exported for direct inlining in hot paths (lexer)
DIGITS = frozenset("0123456789")
WHITESPACE = frozenset(" \t,\ufeff")  # Space, tab, comma, BOM (ignored tokens)
_DIGITS = DIGITS  # Alias for internal use
_LETTERS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")

# Exported for direct inlining in hot paths (lexer)
NAME_START = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_")
NAME_CONTINUE = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_")


def is_digit(char: str) -> bool:
    """Check whether char is a digit

    For internal use by the lexer only.
    """
    return char in _DIGITS


def is_letter(char: str) -> bool:
    """Check whether char is a plain ASCII letter

    For internal use by the lexer only.
    """
    return char in _LETTERS


def is_name_start(char: str) -> bool:
    """Check whether char is allowed at the beginning of a GraphQL name

    For internal use by the lexer only.
    """
    return char in NAME_START


def is_name_continue(char: str) -> bool:
    """Check whether char is allowed in the continuation of a GraphQL name

    For internal use by the lexer only.
    """
    return char in NAME_CONTINUE
