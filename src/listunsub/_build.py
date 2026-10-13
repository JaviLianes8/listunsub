"""Write List-Unsubscribe field bodies and fold header lines safely."""

from __future__ import annotations

import re
from collections.abc import Iterable

from ._errors import ListUnsubscribeError
from ._mailto import parse_mailto
from ._oneclick import ONE_CLICK_POST, one_click_request
from ._uri import check_uri

_FIELD_NAME = re.compile(r"[\x21-\x39\x3b-\x7e]+")
# Unicode line and paragraph separators: str.splitlines and some mail code break on them.
_BREAKS = "\u2028\u2029"


def build(uris: Iterable[str]) -> str:
    """Render URIs as a List-Unsubscribe field body: each bracketed, comma-separated.

    Every URI must have a scheme and hold only RFC 3986 characters (so no white space,
    angle brackets, line breaks or raw non-ASCII text); otherwise, or when no URI is
    given, ``ListUnsubscribeError`` is raised. Order is preference, left first.
    """
    parts = [f"<{check_uri(uri)}>" for uri in uris]
    if not parts:
        raise ListUnsubscribeError("at least one URI is needed")
    return ", ".join(parts)


def header_line(name: str, value: str, *, width: int = 78) -> str:
    """Return ``name: value`` folded at spaces so lines stay within ``width`` characters.

    Lines are joined by CRLF followed by a space (RFC 5322 section 2.2.3); no CRLF ends
    the result. A word too long to fold stays on its own line, but a line over the hard
    998-octet limit (section 2.1.1, counted in UTF-8) raises ``ListUnsubscribeError``,
    as do a bad field name and a value holding a line break or another control character.
    """
    if _FIELD_NAME.fullmatch(name) is None:
        raise ListUnsubscribeError(f"invalid header field name: {name!r}")
    for index, char in enumerate(value):
        if (ord(char) < 0x20 and char != "\t") or 0x7F <= ord(char) <= 0x9F or char in _BREAKS:
            raise ListUnsubscribeError("control character in a header value", index)
    lines = [f"{name}:"]
    for word in value.split(" "):
        if not word:
            continue
        if len(lines[-1]) + 1 + len(word) <= width or lines[-1] == f"{name}:":
            lines[-1] += f" {word}"
        else:
            lines.append(f" {word}")
    for line in lines:
        # The limit counts octets; non-ASCII text (RFC 6532) is sent as UTF-8.
        if len(line.encode()) > 998:
            raise ListUnsubscribeError("a header line would exceed 998 octets")
    return "\r\n".join(lines)


def sender_headers(https: str, mailto: str | None = None) -> dict[str, str]:
    """Return the List-Unsubscribe and List-Unsubscribe-Post fields for one-click.

    ``https`` is the URI that unsubscribes the recipient when POSTed to; RFC 8058 wants it
    to identify list and recipient with a hard-to-forge token. ``mailto`` is an optional
    fallback for clients without web access. Remember the DKIM signature must cover both
    fields (RFC 8058 section 4).
    """
    one_click_request(https)
    uris = [https]
    if mailto is not None:
        if not parse_mailto(check_uri(mailto), strict=True).to:
            raise ListUnsubscribeError(f"the mailto URI names no recipient: {mailto!r}")
        uris.append(mailto)
    return {"List-Unsubscribe": build(uris), "List-Unsubscribe-Post": ONE_CLICK_POST}
