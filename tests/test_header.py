from __future__ import annotations

import pytest

from listunsub import ListUnsubscribe, ListUnsubscribeError, parse, parse_header


def test_parse_reads_the_uris_in_order() -> None:
    header = "<mailto:unsub@example.com>, <https://example.com/unsub?id=1>"
    assert parse(header) == ["mailto:unsub@example.com", "https://example.com/unsub?id=1"]


def test_surrounding_white_space_and_folds_are_skipped() -> None:
    value = "\r\n  <https://example.com/u>  ,\r\n\t<mailto:a@b.co> "
    assert parse(value) == ["https://example.com/u", "mailto:a@b.co"]
    assert parse("\n <https://a.test/u>,\n <mailto:a@b.co>") == ["https://a.test/u", "mailto:a@b.co"]


def test_white_space_inside_brackets_is_removed() -> None:
    assert parse("<https://example.com/\r\n unsub>") == ["https://example.com/unsub"]
    assert parse("< https://a.test/\tx >") == ["https://a.test/x"]


def test_a_field_not_starting_with_a_bracket_is_ignored() -> None:
    # RFC 2369 section 2, rule 1.
    result = parse_header("garbage, <mailto:a@b.co>")
    assert result == ListUnsubscribe((), (), ignored=True)


def test_text_after_a_uri_ends_the_list_unless_a_comma_follows() -> None:
    # Rule 2.
    assert parse_header("<https://a.test/u> junk, <mailto:a@b.co>") == ListUnsubscribe(
        ("https://a.test/u",), (), ignored=True
    )


def test_a_sub_item_that_is_not_bracketed_ends_the_list() -> None:
    # Rule 3.
    result = parse_header("<https://a.test/u>, junk, <mailto:a@b.co>")
    assert result.uris == ("https://a.test/u",) and result.ignored


def test_comments_are_skipped_and_kept() -> None:
    value = "(first) <https://a.test/u> (second (nested) \\) <x>), <mailto:a@b.co>"
    result = parse_header(value)
    assert result.uris == ("https://a.test/u", "mailto:a@b.co")
    assert result.comments == ("first", "second (nested) ) <x>")
    assert not result.ignored


def test_a_bracket_inside_a_comment_is_not_a_uri() -> None:
    assert parse("(see <https://evil.test/>) <https://a.test/u>") == ["https://a.test/u"]
    assert parse("(see <https://evil.test/>)") == []


def test_a_folded_comment_is_unfolded() -> None:
    assert parse_header("(one\r\n two) <a:b>").comments == ("one two",)


def test_an_unclosed_comment_swallows_the_rest() -> None:
    assert parse_header("(open <a:b>") == ListUnsubscribe((), ("open <a:b>",))


def test_an_unclosed_bracket_ends_the_list() -> None:
    assert parse("<a:b>, <c:d") == ["a:b"]
    assert parse("<a:b>, <c<d:e>") == ["a:b"]


def test_empty_items_are_skipped_when_lenient() -> None:
    assert parse("<a:b>,, <>, <c:d>") == ["a:b", "c:d"]
    assert parse("<a:b>,") == ["a:b"]


def test_empty_values_give_nothing() -> None:
    assert parse("") == [] and parse(" \r\n ") == [] and parse("(only a comment)") == []


def test_the_lenient_parser_returns_uris_as_written() -> None:
    assert parse("<not a uri>") == ["notauri"]


def test_strict_accepts_a_clean_field() -> None:
    value = "(Unsubscribe)\r\n <mailto:a@b.co?subject=x>,\r\n <https://a.test/u> (web)"
    assert parse(value, strict=True) == ["mailto:a@b.co?subject=x", "https://a.test/u"]


@pytest.mark.parametrize(
    ("value", "reason", "offset"),
    [
        ("", "the field holds no URI", 0),
        ("(c) ", "the field holds no URI", 4),
        ("x <a:b>", "expected '<'", 0),
        ("<a:b> x", "expected ',' after '>'", 6),
        ("<a:b>, x", "expected '<'", 7),
        ("<a:b>,", "the field ends with a comma", 6),
        ("<a:b>,,<c:d>", "expected '<'", 6),
        ("<a:b", "'<' is not closed by '>'", 0),
        ("<a:<b>", "'<' is not closed by '>'", 0),
        ("<a: b>", "white space inside angle brackets", 3),
        ("<>", "empty URI", 0),
        ("<nocolon>", "URI has no scheme: 'nocolon'", 0),
        ("<a:b>, <h:\u00e9>", "URI holds a character outside RFC 3986 or a bad escape: 'h:\u00e9'", 7),
        ("<a:%zz>", "URI holds a character outside RFC 3986 or a bad escape: 'a:%zz'", 0),
        ("(open <a:b>", "comment is not closed", 0),
        ("(a\x01) <a:b>", "control character in a comment", 2),
        ("<a:b>\r\n<c:d>", "line break not followed by white space", 5),
        ("(a\nb) <a:b>", "line break not followed by white space", 2),
    ],
)
def test_strict_rejects_what_the_rules_ignore(value: str, reason: str, offset: int) -> None:
    with pytest.raises(ListUnsubscribeError) as caught:
        parse_header(value, strict=True)
    assert (caught.value.reason, caught.value.offset) == (reason, offset)


def test_strict_allows_tabs_and_non_ascii_in_comments() -> None:
    assert parse_header("(caf\u00e9\tlist) <a:b>", strict=True).comments == ("caf\u00e9\tlist",)


def test_lenient_tolerates_bare_line_breaks_and_controls() -> None:
    assert parse_header("<a:b>\r\n<c:d>").uris == ("a:b",)
    assert parse_header("(a\x01) <a:b>").comments == ("a\x01",)


def test_scheme_filters_are_case_insensitive() -> None:
    header = parse_header("<MAILTO:a@b.co>, <HTTPS://a.test/u>, <http://a.test/v>")
    assert header.https == ("HTTPS://a.test/u",)
    assert header.mailto == ("MAILTO:a@b.co",)
    assert header.by_scheme("HTTP", "https") == ("HTTPS://a.test/u", "http://a.test/v")
