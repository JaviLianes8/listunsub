"""RFC 8058 one-click: the List-Unsubscribe-Post value and the POST a receiver sends."""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from ._errors import ListUnsubscribeError
from ._uri import check_uri, scheme_of

ONE_CLICK_POST = "List-Unsubscribe=One-Click"
"""The sole List-Unsubscribe-Post value defined by RFC 8058."""

# Boundary characters from RFC 2046 section 5.1.1 that also form an RFC 9110 token, so the
# Content-Type parameter never needs quoting.
_BOUNDARY = re.compile(r"[0-9A-Za-z'+_.\-]{1,70}")


def one_click_post() -> str:
    """Return the List-Unsubscribe-Post value that enables one-click unsubscribe."""
    return ONE_CLICK_POST


def is_one_click(value: str) -> bool:
    """Report whether a List-Unsubscribe-Post field body requests one-click unsubscribe.

    RFC 8058 section 5 allows only the exact key and value; as ABNF strings they match
    without regard to case. White space and folding around the value are ignored, white
    space inside it is not.
    """
    return value.strip(" \t\r\n").lower() == ONE_CLICK_POST.lower()


@dataclass(frozen=True)
class OneClickRequest:
    """The HTTPS POST a mail receiver sends to unsubscribe (RFC 8058 section 3.2).

    Send it as is: no cookies, no authorization, no other context (section 3.1), and do
    not follow a redirect.
    """

    url: str
    content_type: str
    body: bytes
    method: str = "POST"

    @property
    def headers(self) -> dict[str, str]:
        """The Content-Type and Content-Length request headers."""
        return {"Content-Type": self.content_type, "Content-Length": str(len(self.body))}


def one_click_request(
    uri: str,
    *,
    form: Literal["multipart", "urlencoded"] = "multipart",
    boundary: str | None = None,
) -> OneClickRequest:
    """Build the one-click POST for an HTTPS URI taken from List-Unsubscribe.

    RFC 8058 says the body SHOULD be ``multipart/form-data`` and MAY be
    ``application/x-www-form-urlencoded``; ``form`` picks one. ``boundary`` fixes the
    multipart boundary (a random one is drawn otherwise). The fragment is dropped, since
    it is never sent. Raises ``ListUnsubscribeError`` for a URI that is not HTTPS, has no
    host, or carries user information (that would be authorization context).
    """
    if scheme_of(check_uri(uri)) != "https":
        raise ListUnsubscribeError(f"one-click needs an https URI: {uri!r}")
    try:
        parts = urlsplit(uri)
        parts.port  # noqa: B018  (reading it validates the port)
    except ValueError as error:
        raise ListUnsubscribeError(f"one-click URI has a bad authority: {error}") from None
    if "@" in parts.netloc:
        raise ListUnsubscribeError(f"one-click URI must not carry user information: {uri!r}")
    if not parts.hostname:
        raise ListUnsubscribeError(f"one-click URI has no host: {uri!r}")
    url = urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))
    if form == "urlencoded":
        return OneClickRequest(url, "application/x-www-form-urlencoded", ONE_CLICK_POST.encode())
    if form != "multipart":
        raise ListUnsubscribeError(f"unknown form encoding: {form!r}")
    if boundary is None:
        boundary = "listunsub-" + secrets.token_hex(16)
    elif _BOUNDARY.fullmatch(boundary) is None:
        raise ListUnsubscribeError(f"boundary must be 1 to 70 token characters: {boundary!r}")
    name, value = ONE_CLICK_POST.split("=")
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"\r\n'
        "\r\n"
        f"{value}\r\n"
        f"--{boundary}--"
    )
    return OneClickRequest(url, f"multipart/form-data; boundary={boundary}", body.encode())
