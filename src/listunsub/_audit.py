"""Check a message's unsubscribe fields against RFC 2369, RFC 8058 and the mailbox rules."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ._dkim import dkim_covers
from ._errors import ListUnsubscribeError
from ._header import parse_header
from ._mailto import parse_mailto
from ._oneclick import ONE_CLICK_POST, is_one_click, one_click_request


@dataclass(frozen=True)
class Problem:
    """A finding of ``audit``: a stable ``code`` and an explanation."""

    code: str
    message: str


def _values(field: str | Sequence[str] | None) -> list[str]:
    if field is None:
        return []
    return [field] if isinstance(field, str) else list(field)


def audit(
    list_unsubscribe: str | Sequence[str] | None,
    post: str | Sequence[str] | None = None,
    *,
    dkim_signatures: str | Sequence[str] | None = None,
) -> list[Problem]:
    """List what keeps a message's unsubscribe fields from being valid one-click.

    Pass each field body, or a sequence holding every occurrence of the field. Gmail and
    Yahoo require RFC 8058 one-click on bulk marketing and subscribed mail, so a missing
    HTTPS URI or post value is reported. ``dkim_signatures`` are the DKIM-Signature field
    bodies; None skips the DKIM check, an empty sequence means the message has none. An
    empty result means nothing was found.
    """
    found: list[Problem] = []

    def report(code: str, message: str) -> None:
        found.append(Problem(code, message))

    fields, posts = _values(list_unsubscribe), _values(post)
    if not fields:
        report("missing-list-unsubscribe", "there is no List-Unsubscribe field")
    if len(fields) > 1:
        report("duplicate-list-unsubscribe", "RFC 2369 allows one List-Unsubscribe field")
    if len(posts) > 1:
        report("duplicate-post", "RFC 8058 asks for one List-Unsubscribe-Post field")
    https: tuple[str, ...] = ()
    if fields:
        try:
            header = parse_header(fields[0], strict=True)
        except ListUnsubscribeError as error:
            report("invalid-list-unsubscribe", str(error))
            header = parse_header(fields[0])
        https = header.https
        for uri in header.mailto:
            try:
                if not parse_mailto(uri, strict=True).to:
                    report("invalid-mailto", f"no recipient in {uri!r}")
            except ListUnsubscribeError as error:
                report("invalid-mailto", str(error))
        for uri in https:
            try:
                one_click_request(uri)
            except ListUnsubscribeError as error:
                report("unusable-https", str(error))
        if not https:
            report("no-https", "one-click needs an https URI in List-Unsubscribe")
    if not posts:
        report("missing-post", "there is no List-Unsubscribe-Post field, so no one-click")
    elif not is_one_click(posts[0]):
        report("invalid-post", f"List-Unsubscribe-Post is not {ONE_CLICK_POST!r}")
    if dkim_signatures is not None:
        signatures = _values(dkim_signatures)
        if not signatures:
            report("missing-dkim", "one-click needs a DKIM signature (RFC 8058 section 4)")
        elif not any(dkim_covers(signature) for signature in signatures):
            report("dkim-not-covering", "no DKIM signature covers both unsubscribe fields")
    return found
