"""Read a List-Unsubscribe field body by the rules of RFC 2369 section 2."""

from __future__ import annotations

from dataclasses import dataclass

from ._scan import Scanner
from ._uri import scheme_of, uri_problem


@dataclass(frozen=True)
class ListUnsubscribe:
    """The URIs of a List-Unsubscribe field, in the sender's order of preference.

    ``comments`` holds the text of every comment met while reading, with encoded words
    decoded. ``ignored`` is True when text the RFC says to ignore was skipped.
    """

    uris: tuple[str, ...]
    comments: tuple[str, ...] = ()
    ignored: bool = False

    def by_scheme(self, *schemes: str) -> tuple[str, ...]:
        """The URIs whose scheme is one of ``schemes`` (case-insensitive), in order."""
        wanted = {scheme.lower() for scheme in schemes}
        return tuple(uri for uri in self.uris if scheme_of(uri) in wanted)

    @property
    def https(self) -> tuple[str, ...]:
        """The ``https:`` URIs, the only ones RFC 8058 one-click may use."""
        return self.by_scheme("https")

    @property
    def mailto(self) -> tuple[str, ...]:
        """The ``mailto:`` URIs."""
        return self.by_scheme("mailto")


def parse_header(value: str, *, strict: bool = False) -> ListUnsubscribe:
    """Parse a List-Unsubscribe field body (the text after the colon).

    By default the reading follows the client rules of RFC 2369 section 2: a field that
    does not start with "<" is ignored, anything after a bracketed URI is ignored unless a
    comma follows, a sub-item that is not a bracketed URI ends the list, and white space
    inside the brackets is removed. With ``strict=True`` each of those cases, an empty or
    invalid URI and an unclosed comment raise ``ListUnsubscribeError`` instead.
    """
    scan = Scanner(value, strict=strict)
    comments = scan.skip_cfws()
    uris: list[str] = []
    if scan.at_end() and strict:
        raise scan.fail("the field holds no URI")
    while not scan.at_end():
        if scan.peek() != "<":
            if strict:
                raise scan.fail("expected '<'")
            break
        start = scan.pos
        uri = scan.bracketed()
        if uri is None:
            break
        problem = uri_problem(uri)
        if strict and problem is not None:
            raise scan.fail(problem, start)
        if uri:
            uris.append(uri)
        comments += scan.skip_cfws()
        if scan.at_end():
            break
        if scan.peek() != ",":
            if strict:
                raise scan.fail("expected ',' after '>'")
            break
        scan.pos += 1
        comments += scan.skip_cfws()
        while not strict and scan.peek() == ",":
            scan.pos += 1
            comments += scan.skip_cfws()
        if scan.at_end() and strict:
            raise scan.fail("the field ends with a comma")
    return ListUnsubscribe(tuple(uris), tuple(comments), ignored=not scan.at_end())


def parse(value: str, *, strict: bool = False) -> list[str]:
    """Return the URIs of a List-Unsubscribe field body, in order of preference.

    A shortcut for ``list(parse_header(value, strict=strict).uris)``.
    """
    return list(parse_header(value, strict=strict).uris)
