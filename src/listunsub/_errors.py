"""The single error type the library raises."""

from __future__ import annotations


class ListUnsubscribeError(ValueError):
    """A header, URI or request that does not follow the rules it is checked against.

    ``reason`` is the bare explanation and ``offset`` the index in the checked text where
    the problem was found, when there is one.
    """

    def __init__(self, reason: str, offset: int | None = None) -> None:
        where = "" if offset is None else f" at offset {offset}"
        super().__init__(f"{reason}{where}")
        self.reason = reason
        self.offset = offset
