"""Parsing utilities – course code extraction, HTML stripping."""

from __future__ import annotations

import re
from html.parser import HTMLParser


# Matches patterns like [CMPSC 291A S26] or [CS 8 W25]
_COURSE_RE = re.compile(r"\[([A-Z]{1,6}\s+\d+[A-Z]*)\s+([A-Z]\d{2})\]")


def extract_course_code(title: str) -> tuple[str, str] | None:
    """Extract (course_code, quarter_code) from a Canvas event title.

    Returns None if the pattern is not found.

    Example:
        "Homework 3 [CMPSC 291A S26]" -> ("CMPSC 291A", "S26")
    """
    match = _COURSE_RE.search(title)
    if match:
        return match.group(1), match.group(2)
    return None


class _HTMLStripper(HTMLParser):
    """Minimal HTML stripper using stdlib HTMLParser."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts).strip()


def strip_html(text: str) -> str:
    """Remove HTML tags from *text* and return plain text."""
    if not text or "<" not in text:
        return text
    stripper = _HTMLStripper()
    stripper.feed(text)
    return stripper.get_text()
