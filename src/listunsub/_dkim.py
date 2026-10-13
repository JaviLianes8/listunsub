"""Read the signed header list of a DKIM-Signature field (RFC 6376 sections 3.2 and 3.5)."""

from __future__ import annotations

import re

from ._errors import ListUnsubscribeError

_TAG_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
# tag-value: VALCHAR runs (%x21-3A / %x3C-7E) separated by white space, already unfolded.
_VALUE = re.compile(r"(?:[!-:<-~]+(?: +[!-:<-~]+)*)?")
_FIELD = re.compile(r"[!-9;-~]+")
ONE_CLICK_FIELDS = ("List-Unsubscribe", "List-Unsubscribe-Post")


def signed_headers(signature: str) -> tuple[str, ...]:
    """The lower-cased field names in the ``h=`` tag of a DKIM-Signature field body.

    Raises ``ListUnsubscribeError`` when the tag list is malformed, repeats a tag (which
    makes the whole list invalid), or has no ``h=`` tag.
    """
    tags: dict[str, str] = {}
    # Unfold, then treat tabs as spaces: FWS may surround tags, names and colons.
    unfolded = re.sub(r"[\r\n]", "", signature).replace("\t", " ")
    for spec in unfolded.split(";"):
        if not spec.strip(" "):
            continue
        name, equals, value = spec.partition("=")
        name = name.strip(" ")
        if not equals or _TAG_NAME.fullmatch(name) is None:
            raise ListUnsubscribeError(f"malformed DKIM tag {spec.strip(' ')!r}")
        if name in tags:
            raise ListUnsubscribeError(f"DKIM tag {name!r} appears twice")
        value = value.strip(" ")
        if _VALUE.fullmatch(value) is None:
            raise ListUnsubscribeError(f"DKIM tag {name!r} has a character outside VALCHAR")
        tags[name] = value
    if "h" not in tags:
        raise ListUnsubscribeError("the DKIM signature has no h= tag")
    names = tuple(part.strip(" ").lower() for part in tags["h"].split(":"))
    if not all(_FIELD.fullmatch(name) for name in names):
        raise ListUnsubscribeError("empty or invalid field name in the DKIM h= tag")
    return names


def dkim_covers(signature: str, fields: tuple[str, ...] = ONE_CLICK_FIELDS) -> bool:
    """Report whether a DKIM-Signature field body signs every one of ``fields``.

    RFC 8058 section 4 requires List-Unsubscribe and List-Unsubscribe-Post (the default)
    in ``h=``. Names compare case-insensitively; a malformed signature covers nothing.
    This reads the tag only, it does not verify the signature.
    """
    try:
        signed = set(signed_headers(signature))
    except ListUnsubscribeError:
        return False
    return all(field.lower() in signed for field in fields)
