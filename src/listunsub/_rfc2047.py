"""Decode RFC 2047 encoded words, as they may appear inside a comment."""

from __future__ import annotations

import base64
import binascii
import codecs
import re

_WORD = re.compile(r"=\?([^?\s()]+)\?([BbQq])\?([^?\s]*)\?=")
_HEX = re.compile(rb"=([0-9A-Fa-f]{2})")


def _decode(charset: str, encoding: str, text: str) -> str | None:
    # RFC 2231 lets a language follow the charset after "*".
    name = charset.split("*", 1)[0]
    try:
        codecs.lookup(name)
        raw = text.encode("ascii")
        if encoding in "Bb":
            data = base64.b64decode(raw, validate=True)
        else:
            data = _HEX.sub(lambda m: bytes([int(m.group(1), 16)]), raw.replace(b"_", b" "))
        return data.decode(name)
    except (LookupError, UnicodeError, binascii.Error, ValueError):
        return None


def decode_words(text: str) -> str:
    """Replace each well-formed encoded word in ``text`` by the text it encodes.

    A word only counts when white space or a parenthesis surrounds it (section 5), white
    space between two adjacent encoded words is dropped (section 6.2), and a word with an
    unknown charset or broken encoding is left as it is.
    """
    out: list[str] = []
    last = 0
    word_end = -1
    for match in _WORD.finditer(text):
        start, end = match.span()
        if start > 0 and text[start - 1] not in " \t(":
            continue
        if end < len(text) and text[end] not in " \t)":
            continue
        decoded = _decode(*match.groups())
        if decoded is None:
            continue
        gap = text[last:start]
        if word_end == last and not gap.strip(" \t"):
            gap = ""
        out.extend((gap, decoded))
        last = word_end = end
    out.append(text[last:])
    return "".join(out)
