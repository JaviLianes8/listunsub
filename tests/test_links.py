import pytest

from listunsub import build, http_links, mailto_links, parse


def test_parse_single_https() -> None:
    assert parse("<https://example.com/unsub?id=1>") == ["https://example.com/unsub?id=1"]


def test_parse_single_mailto() -> None:
    assert parse("<mailto:unsub@example.com>") == ["mailto:unsub@example.com"]


def test_parse_multiple_in_order() -> None:
    header = "<mailto:unsub@example.com>, <https://example.com/unsub>"
    assert parse(header) == ["mailto:unsub@example.com", "https://example.com/unsub"]


def test_parse_tolerates_surrounding_whitespace() -> None:
    assert parse("  <https://example.com/u>  ,  <mailto:a@b.co> ") == [
        "https://example.com/u",
        "mailto:a@b.co",
    ]


def test_parse_removes_folding_whitespace_inside_a_uri() -> None:
    assert parse("<https://example.com/\r\n unsub>") == ["https://example.com/unsub"]


def test_parse_ignores_unbracketed_and_empty_entries() -> None:
    assert parse("garbage, <>, <mailto:a@b.co>, more") == ["mailto:a@b.co"]


def test_parse_of_empty_header_is_empty() -> None:
    assert parse("") == []


def test_build_single() -> None:
    assert build(["https://example.com/unsub"]) == "<https://example.com/unsub>"


def test_build_multiple() -> None:
    uris = ["mailto:unsub@example.com", "https://example.com/unsub"]
    assert build(uris) == "<mailto:unsub@example.com>, <https://example.com/unsub>"


def test_build_strips_and_drops_empty() -> None:
    assert build([" https://example.com/u ", "", "  "]) == "<https://example.com/u>"


def test_build_rejects_uri_with_angle_bracket() -> None:
    with pytest.raises(ValueError):
        build(["https://example.com/<x>"])


def test_build_rejects_uri_with_newline() -> None:
    with pytest.raises(ValueError):
        build(["https://example.com/\nunsub"])


def test_parse_build_round_trip() -> None:
    header = "<mailto:unsub@example.com>, <https://example.com/unsub?id=1>"
    assert build(parse(header)) == header


def test_mailto_links_filters() -> None:
    uris = ["mailto:a@b.co", "https://example.com/u", "MAILTO:c@d.co"]
    assert mailto_links(uris) == ["mailto:a@b.co", "MAILTO:c@d.co"]


def test_http_links_filters_both_schemes() -> None:
    uris = ["mailto:a@b.co", "http://x.co/u", "HTTPS://y.co/u"]
    assert http_links(uris) == ["http://x.co/u", "HTTPS://y.co/u"]
