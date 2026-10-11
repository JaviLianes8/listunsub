"""The RFC 8058 one-click List-Unsubscribe-Post value."""

from __future__ import annotations

ONE_CLICK_POST = "List-Unsubscribe=One-Click"
"""The sole List-Unsubscribe-Post value defined by RFC 8058."""


def one_click_post() -> str:
    """Return the List-Unsubscribe-Post value that enables one-click unsubscribe."""
    return ONE_CLICK_POST


def is_one_click(value: str) -> bool:
    """Report whether a List-Unsubscribe-Post value requests one-click unsubscribe.

    The match ignores case and any surrounding or internal whitespace.
    """
    return "".join(value.split()).lower() == ONE_CLICK_POST.replace(" ", "").lower()
