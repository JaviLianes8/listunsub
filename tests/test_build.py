from __future__ import annotations

import pytest

from listunsub import ListUnsubscribeError, build, header_line, parse, sender_headers


def test_build_brackets_and_joins_in_order() -> None:
    uris = ["mailto:unsub@example.com", "https://example.com/unsub"]
    assert build(uris) == "<mailto:unsub@example.com>, <https://example.com/unsub>"
    assert build(iter(uris[:1])) == "<mailto:unsub@example.com>"


def test_build_round_trips_through_strict_parse() -> None:
    uris = ["mailto:a@b.co?subject=x%20y&body=z", "https://a.test/u?id=1&t=%2F#f"]
    assert parse(build(uris), strict=True) == uris


@pytest.mark.parametrize(
    "uri",
    [
        "",
        " https://a.test/u",
        "https://a.test/u u",
        "https://a.test/<x>",
        "https://a.test/u>, <https://evil.test/",
        "https://a.test/u\r\nBcc: x@evil.test",
        "https://a.test/\x00",
        "https://a.test/café",
        "https://a.test/%2",
        "a.test/u",
        "1http://a.test/",
    ],
)
def test_build_refuses_what_would_break_or_inject(uri: str) -> None:
    with pytest.raises(ListUnsubscribeError):
        build([uri])


def test_build_needs_a_uri() -> None:
    with pytest.raises(ListUnsubscribeError, match="at least one URI"):
        build([])


def test_header_line_keeps_a_short_field_on_one_line() -> None:
    assert header_line("List-Unsubscribe", "<https://a.test/u>") == (
        "List-Unsubscribe: <https://a.test/u>"
    )


def test_header_line_folds_after_commas_within_the_width() -> None:
    value = build(
        ["mailto:listrequest@example.com?subject=unsubscribe", "https://a.test/" + "u" * 50]
    )
    line = header_line("List-Unsubscribe", value)
    first, second = line.split("\r\n")
    assert first == "List-Unsubscribe: <mailto:listrequest@example.com?subject=unsubscribe>,"
    assert second == " <https://a.test/" + "u" * 50 + ">"
    assert parse(line.split(":", 1)[1], strict=True) == parse(value)


def test_header_line_honours_the_width_exactly() -> None:
    assert header_line("X", "aaa bbb", width=7) == "X: aaa\r\n bbb"
    assert header_line("X", "aaa bb", width=9) == "X: aaa bb"
    assert header_line("X", "aaa bbb", width=9) == "X: aaa\r\n bbb"


def test_a_long_word_stays_whole_on_the_first_line() -> None:
    assert header_line("X", "a" * 90) == "X: " + "a" * 90
    assert header_line("X", "  a   b ") == "X: a b"


def test_header_line_refuses_the_hard_limit() -> None:
    assert len(header_line("X", "a" * 995)) == 998
    with pytest.raises(ListUnsubscribeError, match="998"):
        header_line("X", "a" * 996)
    with pytest.raises(ListUnsubscribeError, match="998"):
        header_line("X", "a b" + "c" * 998)


@pytest.mark.parametrize("name", ["", "Bad Name", "Bad:Name", "Café", "A\x7f"])
def test_header_line_refuses_bad_names(name: str) -> None:
    with pytest.raises(ListUnsubscribeError, match="field name"):
        header_line(name, "x")


@pytest.mark.parametrize("value", ["a\r\nBcc: x", "a\nb", "a\rb", "a\x00", "a\x7f"])
def test_header_line_refuses_control_characters(value: str) -> None:
    with pytest.raises(ListUnsubscribeError, match="control character"):
        header_line("X", value)


def test_header_line_keeps_tabs() -> None:
    assert header_line("X", "a\tb") == "X: a\tb"


def test_sender_headers_give_both_one_click_fields() -> None:
    assert sender_headers("https://a.test/u/opaque") == {
        "List-Unsubscribe": "<https://a.test/u/opaque>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }
    both = sender_headers("https://a.test/u", "mailto:u@a.test?subject=unsubscribe")
    assert both["List-Unsubscribe"] == "<https://a.test/u>, <mailto:u@a.test?subject=unsubscribe>"


@pytest.mark.parametrize(
    ("https", "mailto"),
    [
        ("http://a.test/u", None),
        ("https://u@a.test/u", None),
        ("https://a.test/u", "https://a.test/v"),
        ("https://a.test/u", "mailto:?subject=x"),
        ("https://a.test/u", "mailto:nobody"),
        ("https://a.test/u", "mailto:u@a.test?subject=a b"),
    ],
)
def test_sender_headers_refuse_bad_input(https: str, mailto: str | None) -> None:
    with pytest.raises(ListUnsubscribeError):
        sender_headers(https, mailto)
