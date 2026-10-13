"""URI character rules shared by the parser, the builder and the request helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable

from ._errors import ListUnsubscribeError

# RFC 3986 section 3.1 scheme, then only characters a URI may hold (sections 2.2 and 2.3)
# with every "%" starting a two-digit escape (section 2.1).
_SCHEME = r"[A-Za-z][A-Za-z0-9+.\-]*:"
_URI = re.compile(_SCHEME + r"(?:[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=]|%[0-9A-Fa-f]{2})*")


def uri_problem(uri: str) -> str | None:
    """Explain why ``uri`` is not a URI that may go between angle brackets, or None."""
    if not uri:
        return "empty URI"
    if not re.match(_SCHEME, uri):
        return f"URI has no scheme: {uri!r}"
    if _URI.fullmatch(uri) is None:
        return f"URI holds a character outside RFC 3986 or a bad escape: {uri!r}"
    return None


def check_uri(uri: str) -> str:
    """Return ``uri`` unchanged, or raise ``ListUnsubscribeError`` if it is not valid."""
    problem = uri_problem(uri)
    if problem is not None:
        raise ListUnsubscribeError(problem)
    return uri


def scheme_of(uri: str) -> str:
    """The lower-cased scheme of ``uri``, or an empty string when it has none."""
    match = re.match(r"([A-Za-z][A-Za-z0-9+.\-]*):", uri)
    return match.group(1).lower() if match else ""


def mailto_links(uris: Iterable[str]) -> list[str]:
    """Return only the ``mailto:`` URIs, preserving order."""
    return [uri for uri in uris if scheme_of(uri) == "mailto"]


def http_links(uris: Iterable[str]) -> list[str]:
    """Return only the ``http:`` and ``https:`` URIs, preserving order."""
    return [uri for uri in uris if scheme_of(uri) in ("http", "https")]
