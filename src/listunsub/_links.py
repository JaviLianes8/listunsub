"""Parse and build RFC 2369 List-Unsubscribe header values."""

from __future__ import annotations

import re
from collections.abc import Iterable

_BRACKETED = re.compile(r"<([^<>]*)>")
_FORBIDDEN = ("<", ">", "\r", "\n")


def parse(header: str) -> list[str]:
    """Return the URIs from a List-Unsubscribe value, in order.

    URIs live between angle brackets and are separated by commas. Surrounding
    and folding whitespace is removed, and empty or unbracketed text is ignored.
    """
    uris: list[str] = []
    for match in _BRACKETED.findall(header):
        uri = "".join(match.split())
        if uri:
            uris.append(uri)
    return uris


def build(uris: Iterable[str]) -> str:
    """Render URIs as a List-Unsubscribe value: comma-separated, each bracketed.

    Each URI is stripped of surrounding whitespace, and empty ones are dropped.
    A URI containing an angle bracket or a line break is rejected, since it would
    break the header syntax.
    """
    parts: list[str] = []
    for uri in uris:
        clean = uri.strip()
        if not clean:
            continue
        if any(bad in clean for bad in _FORBIDDEN):
            raise ValueError(f"URI is not valid inside a List-Unsubscribe value: {uri!r}")
        parts.append(f"<{clean}>")
    return ", ".join(parts)


def mailto_links(uris: Iterable[str]) -> list[str]:
    """Return only the ``mailto:`` URIs, preserving order."""
    return [uri for uri in uris if uri.lower().startswith("mailto:")]


def http_links(uris: Iterable[str]) -> list[str]:
    """Return only the ``http:`` and ``https:`` URIs, preserving order."""
    return [uri for uri in uris if uri.lower().startswith(("http://", "https://"))]
