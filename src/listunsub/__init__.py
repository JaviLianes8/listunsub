"""Typed, zero-dependency codec for the email List-Unsubscribe headers."""

from __future__ import annotations

from collections.abc import Iterable

from ._audit import Problem, audit
from ._build import build, header_line, sender_headers
from ._choose import Action, actions, choose
from ._dkim import dkim_covers, signed_headers
from ._errors import ListUnsubscribeError
from ._header import ListUnsubscribe, parse, parse_header
from ._mailto import Mailto, parse_mailto
from ._mailto_build import build_mailto
from ._oneclick import (
    ONE_CLICK_POST,
    OneClickRequest,
    is_one_click,
    one_click_post,
    one_click_request,
)
from ._uri import scheme_of

__version__ = "0.2.0"

__all__ = [
    "ONE_CLICK_POST",
    "Action",
    "ListUnsubscribe",
    "ListUnsubscribeError",
    "Mailto",
    "OneClickRequest",
    "Problem",
    "actions",
    "audit",
    "build",
    "build_mailto",
    "choose",
    "dkim_covers",
    "header_line",
    "http_links",
    "is_one_click",
    "mailto_links",
    "one_click_post",
    "one_click_request",
    "parse",
    "parse_header",
    "parse_mailto",
    "sender_headers",
    "signed_headers",
]


def mailto_links(uris: Iterable[str]) -> list[str]:
    """Return only the ``mailto:`` URIs, preserving order."""
    return [uri for uri in uris if scheme_of(uri) == "mailto"]


def http_links(uris: Iterable[str]) -> list[str]:
    """Return only the ``http:`` and ``https:`` URIs, preserving order."""
    return [uri for uri in uris if scheme_of(uri) in ("http", "https")]
