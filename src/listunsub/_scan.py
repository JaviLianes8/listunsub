"""Walk a header field body: folding white space and comments (RFC 5322 section 3.2.2)."""

from __future__ import annotations

import re

from ._errors import ListUnsubscribeError
from ._rfc2047 import decode_words

# Controls (tab aside), line separators and bidi overrides, unsafe to show from a comment.
_UNSAFE = re.compile(r"[\x00-\x08\x0a-\x1f\x7f-\x9f\u2028\u2029\u202a-\u202e\u2066-\u2069]")
_WSP = " \t"


class Scanner:
    """A cursor over a field body that knows folding and nested comments.

    In strict mode a line break (CRLF, or LF as Python text usually carries it) must be
    followed by white space (a fold), a bare CR is refused, and a comment must be closed
    and hold no control character, even quoted; otherwise those slips are tolerated.
    Comment text is untrusted: controls, line separators and bidi overrides in it are
    replaced by U+FFFD.
    """

    def __init__(self, text: str, *, strict: bool) -> None:
        self.text = text
        self.pos = 0
        self.strict = strict

    def at_end(self) -> bool:
        return self.pos >= len(self.text)

    def peek(self) -> str:
        return self.text[self.pos] if self.pos < len(self.text) else ""

    def fail(self, reason: str, offset: int | None = None) -> ListUnsubscribeError:
        return ListUnsubscribeError(reason, self.pos if offset is None else offset)

    def _skip_break(self) -> bool:
        """Step over CRLF, CR or LF; report whether one was there."""
        text, start = self.text, self.pos
        if text.startswith("\r\n", start):
            self.pos += 2
        elif text[start : start + 1] == "\n" or (
            text[start : start + 1] == "\r" and not self.strict
        ):
            self.pos += 1
        else:
            return False
        if self.strict and self.peek() not in (" ", "\t"):
            raise self.fail("line break not followed by white space", start)
        return True

    def skip_cfws(self) -> list[str]:
        """Skip white space, folds and comments; return the comments' decoded text."""
        comments: list[str] = []
        while not self.at_end():
            char = self.peek()
            if char in _WSP:
                self.pos += 1
            elif self._skip_break():
                continue
            elif char == "(":
                comments.append(_UNSAFE.sub("\ufffd", decode_words(self._comment())))
            else:
                break
        return comments

    def _comment(self) -> str:
        """Read a comment starting at "(": its unfolded text, nested parentheses kept."""
        start = self.pos
        self.pos += 1
        depth = 1
        out: list[str] = []
        while not self.at_end():
            char = self.peek()
            if self._skip_break():
                continue
            self.pos += 1
            if char == "\\" and not self.at_end():
                if self.strict and _UNSAFE.match(self.peek()):
                    raise self.fail("quoted pair of a control character", self.pos)
                out.append(self.peek())
                self.pos += 1
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return "".join(out)
            elif self.strict and ((ord(char) < 0x20 and char != "\t") or ord(char) == 0x7F):
                raise self.fail("control character in a comment", self.pos - 1)
            out.append(char)
        if self.strict:
            raise self.fail("comment is not closed", start)
        return "".join(out)

    def bracketed(self) -> str | None:
        """Read ``<...>`` at the cursor and return what is inside, white space removed.

        Returns None, leaving the cursor where it was, when no closing bracket follows or
        another "<" comes first: the item is then not a bracketed URI.
        """
        start = self.pos
        end = self.text.find(">", start + 1)
        if end < 0 or "<" in self.text[start + 1 : end]:
            if self.strict:
                raise self.fail("'<' is not closed by '>'", start)
            return None
        inside = self.text[start + 1 : end]
        if self.strict:
            for index, char in enumerate(inside, start + 1):
                if char in " \t\r\n":
                    raise self.fail("white space inside angle brackets", index)
        self.pos = end + 1
        return re.sub(r"[ \t\r\n]+", "", inside)
