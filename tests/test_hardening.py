"""Hostile input: every failure is a ListUnsubscribeError, never another exception."""

from __future__ import annotations

import pytest

from listunsub import (
    ListUnsubscribeError,
    actions,
    build_mailto,
    choose,
    header_line,
    one_click_request,
    parse_mailto,
)


@pytest.mark.parametrize(
    "uri",
    ["https://[::1/u", "https://a.test:99999/u", "https://a.test:x/u", "https://[v1.x]:-1/"],
)
def test_a_bad_authority_is_a_library_error(uri: str) -> None:
    with pytest.raises(ListUnsubscribeError, match="bad authority"):
        one_click_request(uri)


def test_choose_skips_an_https_uri_with_a_bad_authority() -> None:
    field = "<https://[::1/u>, <https://a.test/ok>"
    post = "List-Unsubscribe=One-Click"
    assert [a.kind for a in actions(field, post, dkim_verified=True)][:1] == ["one-click"]
    assert choose(field, post, dkim_verified=True).uri == "https://a.test/ok"  # type: ignore[union-attr]


def test_a_valid_port_is_kept() -> None:
    assert one_click_request("https://a.test:8443/u").url == "https://a.test:8443/u"


@pytest.mark.parametrize("char", ["\x85", "\x9f", "\u2028", "\u2029"])
def test_header_line_refuses_unicode_line_breaks_and_c1_controls(char: str) -> None:
    with pytest.raises(ListUnsubscribeError, match="control character"):
        header_line("X", f"a{char}b")


def test_header_line_keeps_other_non_ascii_text() -> None:
    assert header_line("X", "café \xa0") == "X: café \xa0"


@pytest.mark.parametrize("char", ["\x0b", "\x0c", "\x1c", "\x85", "\u2028", "\u2029"])
def test_mailto_values_refuse_any_line_break(char: str) -> None:
    with pytest.raises(ListUnsubscribeError, match="line break"):
        build_mailto("a@b.co", subject=f"a{char}b")
    with pytest.raises(ListUnsubscribeError, match="line break"):
        parse_mailto(f"mailto:a@b.co?subject=a{char}b").to_message("me@x.test")


def test_a_trailing_line_break_is_refused_too() -> None:
    with pytest.raises(ListUnsubscribeError, match="line break"):
        build_mailto("a@b.co", subject="a\n")
    with pytest.raises(ListUnsubscribeError, match="line break"):
        parse_mailto("mailto:a@b.co?subject=a%0A").to_message("me@x.test")


def test_an_empty_value_is_allowed_in_build_mailto() -> None:
    assert build_mailto("a@b.co", subject="") == "mailto:a@b.co?subject="
