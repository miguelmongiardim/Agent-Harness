from __future__ import annotations


def add_numbers(a, b):
    """Add two numbers."""
    return a + b


def total(values):
    result = 0
    for value in values:
        result = add_numbers(result, value)
    return result
