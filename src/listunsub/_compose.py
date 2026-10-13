"""Check mail addresses and compose the message a ``mailto:`` URI asks for."""

from __future__ import annotations

import re
from collections.abc import Iterable
from email.message import EmailMessage

from ._errors import ListUnsubscribeError

# C0 and C1 controls (tab aside), DEL, and the Unicode line and paragraph separators.
_CONTROL = re.compile("[\x00-\x08\x0a-\x1f\x7f-\x9f\u2028\u2029]")


def address_problem(address: str) -> str | None:
    """Explain why ``address`` is not a usable ``local@domain`` address, or None.

    Controls and angle brackets are never allowed; white space only inside a quoted
    local part (RFC 6068 section 2, rule 3, and the quoted example of section 6.2).
    """
    local, at, domain = address.rpartition("@")
    if not (local and at and domain):
        return f"not an addr-spec: {address!r}"
    if _CONTROL.search(address) or "<" in address or ">" in address:
        return f"control character or angle bracket in address {address!r}"
    quoted = len(local) > 1 and local.startswith('"') and local.endswith('"')
    if re.search(r"\s", domain) or (re.search(r"\s", local) and not quoted):
        return f"white space in address {address!r}"
    return None


def ascii_domain(domain: str) -> str:
    """The IDNA form of a domain (RFC 6068 section 2, rule 4); ASCII ones are kept."""
    if domain.isascii():
        return domain
    try:
        return domain.encode("idna").decode("ascii")
    except UnicodeError:
        raise ListUnsubscribeError(f"domain has no IDNA form: {domain!r}") from None


def _sendable(address: str) -> str:
    problem = address_problem(address)
    if problem is not None:
        raise ListUnsubscribeError(problem)
    local, _, domain = address.rpartition("@")
    if not local.isascii():
        # Section 2, rule 5: a non-ASCII local part needs an encoding mail does not have.
        raise ListUnsubscribeError(f"local part is not ASCII: {address!r}")
    return f"{local}@{ascii_domain(domain)}"


def compose(
    to: Iterable[str], sender: str, fields: Iterable[tuple[str, str | None]], body: str | None
) -> EmailMessage:
    """Build the message: From ``sender``, To ``to``, the given fields, then ``body``."""
    recipients = [_sendable(address) for address in to]
    if not recipients:
        raise ListUnsubscribeError("the mailto URI names no recipient")
    if not sender.strip():
        raise ListUnsubscribeError("the sender is empty")
    headers = [("From", sender), ("To", ", ".join(recipients))]
    headers += [(name.title(), value) for name, value in fields if value]
    message = EmailMessage()
    for name, value in headers:
        if _CONTROL.search(value):
            raise ListUnsubscribeError(f"line break or control character in the {name} value")
        message[name] = value
    message.set_content(body or "")
    return message
