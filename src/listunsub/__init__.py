"""Typed, zero-dependency codec for the email List-Unsubscribe headers."""

from __future__ import annotations

from ._links import build, http_links, mailto_links, parse
from ._oneclick import ONE_CLICK_POST, is_one_click, one_click_post

__version__ = "0.1.0"

__all__ = [
    "ONE_CLICK_POST",
    "build",
    "http_links",
    "is_one_click",
    "mailto_links",
    "one_click_post",
    "parse",
]
