"""Shared presentation helpers for human-readable exporters."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


def safe_filename(value: str) -> str:
    """Return a filesystem-safe filename component."""

    if not isinstance(value, str):
        raise TypeError("filename must be a string")

    normalized = re.sub(
        r"[^A-Za-z0-9._-]+",
        "_",
        value.strip(),
    ).strip("._")

    if not normalized:
        raise ValueError(
            "filename does not contain any safe characters"
        )

    return normalized


def format_scalar(value: Any) -> str:
    """Render a scalar value consistently."""

    if value is None:
        return ""

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, (int, float, str)):
        return str(value)

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
    )


def value_type(value: Any) -> str:
    """Return a normalized JSON-style value type."""

    if value is None:
        return "null"

    if isinstance(value, bool):
        return "boolean"

    if isinstance(value, int):
        return "integer"

    if isinstance(value, float):
        return "number"

    if isinstance(value, str):
        return "string"

    if isinstance(value, Mapping):
        return "object"

    if (
        isinstance(value, Sequence)
        and not isinstance(
            value,
            (str, bytes, bytearray),
        )
    ):
        return "array"

    return type(value).__name__


def flatten_values(
    value: Any,
    *,
    path: str = "",
) -> tuple[tuple[str, str, str], ...]:
    """Flatten nested JSON-compatible values."""

    rows: list[tuple[str, str, str]] = []

    if isinstance(value, Mapping):
        if not value:
            return ((path, "{}", "object"),)

        for key, nested_value in value.items():
            nested_path = (
                f"{path}.{key}"
                if path
                else str(key)
            )

            rows.extend(
                flatten_values(
                    nested_value,
                    path=nested_path,
                )
            )

        return tuple(rows)

    if (
        isinstance(value, Sequence)
        and not isinstance(
            value,
            (str, bytes, bytearray),
        )
    ):
        if not value:
            return ((path, "[]", "array"),)

        for index, nested_value in enumerate(value):
            nested_path = f"{path}[{index}]"

            rows.extend(
                flatten_values(
                    nested_value,
                    path=nested_path,
                )
            )

        return tuple(rows)

    return (
        (
            path,
            format_scalar(value),
            value_type(value),
        ),
    )


__all__ = [
    "flatten_values",
    "format_scalar",
    "safe_filename",
    "value_type",
]
