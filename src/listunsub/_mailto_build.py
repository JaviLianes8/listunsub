"""Write ``mailto:`` URIs with the escaping RFC 6068 asks of URI producers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import quote

from ._errors import ListUnsubscribeError

# Escaping a delimiter is always legal, so "&", ";", "=" and "," stay escaped in addresses,
# and "&", "=" and "+" in values (section 5: a "+" may be read as a space).
_ADDRESS_SAFE = "!$'()*+:"
_VALUE_SAFE = "!$'()*,;:@"
_FIELD_NAME = re.compile(r"[\x21-\x39\x3b-\x7e]+")


def _address(address: str) -> str:
    local, at, domain = address.rpartition("@")
    if not (local and at and domain):
        raise ListUnsubscribeError(f"not an addr-spec: {address!r}")
    return f"{quote(local, safe=_ADDRESS_SAFE)}@{quote(domain, safe=_ADDRESS_SAFE)}"


def build_mailto(
    to: str | Iterable[str],
    *,
    subject: str | None = None,
    body: str | None = None,
    fields: Iterable[tuple[str, str]] = (),
) -> str:
    """Build a ``mailto:`` URI for one or more addresses and optional header fields.

    Non-ASCII text is written as UTF-8 escapes, spaces as ``%20``. Line breaks in
    ``body`` become ``%0D%0A`` (bare LF or CR are made CRLF first); a line break in any
    other value, a repeated field, a ``to`` field (use ``to``), an invalid field name or
    an address without ``@`` raises ``ListUnsubscribeError``.
    """
    addresses = [to] if isinstance(to, str) else list(to)
    if not addresses:
        raise ListUnsubscribeError("at least one address is needed")
    items = list(fields)
    if subject is not None:
        items.append(("subject", subject))
    if body is not None:
        items.append(("body", re.sub(r"\r\n|\r|\n", "\r\n", body)))
    seen: set[str] = set()
    query: list[str] = []
    for name, value in items:
        key = name.lower()
        if _FIELD_NAME.fullmatch(name) is None or key == "to" or key in seen:
            raise ListUnsubscribeError(f"field {name!r} is invalid, repeated or 'to'")
        if key != "body" and value.splitlines() not in ([], [value]):
            raise ListUnsubscribeError(f"line break in the {name!r} field")
        seen.add(key)
        query.append(f"{quote(name, safe='')}={quote(value, safe=_VALUE_SAFE)}")
    uri = "mailto:" + ",".join(_address(address) for address in addresses)
    return uri + ("?" + "&".join(query) if query else "")
