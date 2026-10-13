"""Pick how a mail receiver should unsubscribe, from what the sender offers."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Literal

from ._errors import ListUnsubscribeError
from ._header import ListUnsubscribe, parse_header
from ._mailto import parse_mailto
from ._oneclick import is_one_click, one_click_request
from ._uri import scheme_of, uri_problem

Scheme = Literal["https", "http", "mailto"]


@dataclass(frozen=True)
class Action:
    """One way to unsubscribe: ``one-click`` (POST, RFC 8058), ``web`` (open the page in a
    browser) or ``mailto`` (send the message the URI describes)."""

    kind: Literal["one-click", "web", "mailto"]
    uri: str


def _usable(uri: str, scheme: str) -> bool:
    if uri_problem(uri) is not None:
        return False
    if scheme == "mailto":
        try:
            return bool(parse_mailto(uri, strict=True).to)
        except ListUnsubscribeError:
            return False
    return True


def actions(
    list_unsubscribe: str | ListUnsubscribe,
    post: str | None = None,
    *,
    dkim_verified: bool = False,
    schemes: Collection[Scheme] = ("https", "http", "mailto"),
) -> list[Action]:
    """Every usable way to unsubscribe, best first.

    One-click comes first, but only when ``post`` is the RFC 8058 value, an HTTPS URI that
    can be POSTed to exists, and the caller has verified a DKIM signature covering both
    fields (``dkim_verified``; section 4 says not to offer one-click otherwise). The other
    URIs follow in the sender's order (RFC 2369: left-most supported first), keeping only
    those whose scheme is in ``schemes`` and that are well formed. Try the next one only
    if the previous one failed.
    """
    header = (
        parse_header(list_unsubscribe) if isinstance(list_unsubscribe, str) else list_unsubscribe
    )
    found: list[Action] = []
    if dkim_verified and post is not None and is_one_click(post):
        for uri in header.https:
            try:
                one_click_request(uri)
            except ListUnsubscribeError:
                continue
            found.append(Action("one-click", uri))
            break
    for uri in header.uris:
        scheme = scheme_of(uri)
        if scheme in schemes and _usable(uri, scheme):
            found.append(Action("mailto" if scheme == "mailto" else "web", uri))
    return found


def choose(
    list_unsubscribe: str | ListUnsubscribe,
    post: str | None = None,
    *,
    dkim_verified: bool = False,
    schemes: Collection[Scheme] = ("https", "http", "mailto"),
) -> Action | None:
    """The best way to unsubscribe (the first of ``actions``), or None if there is none."""
    found = actions(list_unsubscribe, post, dkim_verified=dkim_verified, schemes=schemes)
    return found[0] if found else None
