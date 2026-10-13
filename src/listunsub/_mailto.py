"""Read ``mailto:`` URIs (RFC 6068) and turn one into the unsubscribe message."""

from __future__ import annotations

import re
from dataclasses import dataclass
from email.message import EmailMessage
from urllib.parse import unquote

from ._errors import ListUnsubscribeError
from ._uri import scheme_of

_ESCAPE = r"%[0-9A-Fa-f]{2}"
_PATH = re.compile(rf"(?:[A-Za-z0-9\-._~!$&'()*+,;=:@]|{_ESCAPE})*")
_QCHAR = re.compile(rf"(?:[A-Za-z0-9\-._~!$'()*+,;:@]|{_ESCAPE})*")
# Section 4: only these are safe and useful in general; the rest are left out of a message.
_MESSAGE_FIELDS = ("subject", "keywords")


def _decode(text: str, strict: bool) -> str:
    if not strict:
        return unquote(text, errors="replace")
    try:
        return unquote(text, errors="strict")
    except UnicodeDecodeError:
        raise ListUnsubscribeError(f"escapes are not UTF-8: {text!r}") from None


@dataclass(frozen=True)
class Mailto:
    """A decoded ``mailto:`` URI: the recipients and the other header fields, in order.

    Field names are lower-cased (they are case-insensitive); ``to`` holds the addresses of
    the path followed by those of any ``to`` field, which is merged into it.
    """

    to: tuple[str, ...]
    fields: tuple[tuple[str, str], ...] = ()

    def get(self, name: str) -> str | None:
        """The first value of field ``name`` (case-insensitive), or None."""
        wanted = name.lower()
        return next((value for key, value in self.fields if key == wanted), None)

    @property
    def subject(self) -> str | None:
        """The ``subject`` field, if any."""
        return self.get("subject")

    @property
    def body(self) -> str | None:
        """The ``body`` pseudo field: the text of the message, if any."""
        return self.get("body")

    def to_message(self, sender: str) -> EmailMessage:
        """Compose the message this URI asks for, sent by ``sender``.

        Only To, Subject, Keywords and the body are used (RFC 6068 sections 3 and 4 call
        the others unsafe or say they must be ignored). Raises ``ListUnsubscribeError``
        when there is no recipient or a header value holds a line break.
        """
        if not self.to:
            raise ListUnsubscribeError("the mailto URI names no recipient")
        message = EmailMessage()
        headers = [("From", sender), ("To", ", ".join(self.to))]
        headers += [(name.title(), value) for name in _MESSAGE_FIELDS if (value := self.get(name))]
        for name, value in headers:
            if "\r" in value or "\n" in value:
                raise ListUnsubscribeError(f"line break in the {name} header value")
            message[name] = value
        message.set_content(self.body or "")
        return message


def parse_mailto(uri: str, *, strict: bool = False) -> Mailto:
    """Decode a ``mailto:`` URI as RFC 6068 section 2 describes.

    Percent escapes are decoded as UTF-8 (a ``+`` stays a plus), the fragment is ignored,
    and empty addresses are skipped. ``strict=True`` also enforces the grammar: allowed
    characters, ``name=value`` fields, UTF-8 escapes and ``local@domain`` addresses; a
    violation raises ``ListUnsubscribeError``, as does a URI of another scheme.
    """
    if scheme_of(uri) != "mailto":
        raise ListUnsubscribeError(f"not a mailto URI: {uri!r}")
    rest = uri[len("mailto:") :].split("#", 1)[0]
    path, _, query = rest.partition("?")
    if strict and _PATH.fullmatch(path) is None:
        raise ListUnsubscribeError(f"character not allowed in a mailto URI: {uri!r}")
    to = [_decode(address, strict) for address in path.split(",") if address]
    fields: list[tuple[str, str]] = []
    for item in query.split("&") if query else ():
        name, equals, value = item.partition("=")
        if strict and (not equals or not all(_QCHAR.fullmatch(p) for p in (name, value))):
            raise ListUnsubscribeError(f"malformed field {item!r} in a mailto URI")
        if not equals:
            continue
        name = _decode(name, strict).lower()
        value = _decode(value, strict)
        if name == "to":
            to += [address for address in value.split(",") if address]
        else:
            fields.append((name, value))
    if strict:
        for address in to:
            local, at, domain = address.rpartition("@")
            if not (local and at and domain):
                raise ListUnsubscribeError(f"not an addr-spec: {address!r}")
    return Mailto(tuple(to), tuple(fields))
