"""Regression tests for the findings of the independent review."""

from __future__ import annotations

import inspect
import io
import json
import sys
from pathlib import Path

import pytest

import listunsub
from listunsub import (
    ListUnsubscribeError,
    actions,
    build_mailto,
    header_line,
    parse_header,
    parse_mailto,
    signed_headers,
)
from listunsub._cli import main

POST = "List-Unsubscribe=One-Click"
REPLACED = chr(0xFFFD)


def test_the_command_line_writes_utf8_whatever_the_console_encoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "m.eml"
    path.write_bytes(b"List-Unsubscribe: (=?utf-8?B?5pel5pys?=) <https://a.test/u>\r\n\r\n")
    out = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(out, encoding="cp1252"))
    assert main([str(path)]) == 1
    assert json.loads(out.getvalue().decode("utf-8"))["comments"] == [chr(0x65E5) + chr(0x672C)]


@pytest.mark.parametrize(
    "uri", ["mailto:a%00b@x.test", "mailto:a@x.test?subject=a%1Bb", "mailto:a@x.test?keywords=%7F"]
)
def test_to_message_refuses_control_characters(uri: str) -> None:
    with pytest.raises(ListUnsubscribeError):
        parse_mailto(uri).to_message("me@y.test")


def test_to_message_checks_the_sender() -> None:
    mailto = parse_mailto("mailto:a@x.test")
    with pytest.raises(ListUnsubscribeError, match="control character in the From"):
        mailto.to_message("me" + chr(0) + "@y.test")
    with pytest.raises(ListUnsubscribeError, match="the sender is empty"):
        mailto.to_message(" ")


@pytest.mark.parametrize(
    "uri",
    [
        "mailto:a%0D%0Ab@x.test",
        "mailto:a%00b@x.test",
        "mailto:a@x.test?to=%3Cev@z.test%3E",
        "mailto:a@b.co,%20c@d.co",
        "mailto:a%20b@x.test",
        "mailto:a@x%20y.test",
    ],
)
def test_strict_mailto_refuses_unusable_addresses(uri: str) -> None:
    with pytest.raises(ListUnsubscribeError):
        parse_mailto(uri, strict=True)


def test_lenient_mailto_trims_addresses_and_strict_keeps_quoted_spaces() -> None:
    assert parse_mailto("mailto:a@b.co,%20c@d.co").to == ("a@b.co", "c@d.co")
    assert parse_mailto("mailto:%22a%20b%22@x.test", strict=True).to == ('"a b"@x.test',)


def test_an_internationalized_domain_is_sent_in_idna_form() -> None:
    message = parse_mailto("mailto:a@b%C3%BCcher.de?subject=x").to_message("me@y.test")
    assert message["To"] == "a@xn--bcher-kva.de"
    assert build_mailto("a@b" + chr(0xFC) + "cher.de") == "mailto:a@xn--bcher-kva.de"


def test_a_non_ascii_local_part_cannot_be_sent() -> None:
    with pytest.raises(ListUnsubscribeError, match="local part is not ASCII"):
        parse_mailto("mailto:caf%C3%A9@x.test").to_message("me@y.test")


def test_a_domain_without_idna_form_is_refused_or_escaped() -> None:
    bad = "a@" + "x" * 64 + chr(0xE9) + ".test"
    with pytest.raises(ListUnsubscribeError, match="no IDNA form"):
        parse_mailto(build_mailto(bad)).to_message("me@y.test")
    assert build_mailto(bad).endswith("%C3%A9.test")


def test_one_click_needs_https_among_the_schemes() -> None:
    field = "<https://h.test/>, <mailto:a@x.test>"
    found = actions(field, POST, dkim_verified=True, schemes=["mailto"])
    assert [a.kind for a in found] == ["mailto"]
    with pytest.raises(ListUnsubscribeError, match="collection"):
        actions(field, schemes="https")  # type: ignore[arg-type]


def test_web_uris_need_a_host() -> None:
    assert actions("<https:>, <http:foo>, <https://[x/>, <http://h.test/>") == [
        listunsub.Action("web", "http://h.test/")
    ]


@pytest.mark.parametrize(
    "encoded",
    ["=?utf-8?Q?a=0D=0ABcc:_x=00?=", "=?utf-8?Q?=E2=80=AEx?=", "=?utf-8?Q?a=E2=80=A8b?="],
)
def test_unsafe_decoded_comment_text_is_replaced(encoded: str) -> None:
    (comment,) = parse_header(f"({encoded}) <a:b>").comments
    assert REPLACED in comment
    assert all(ch.isprintable() or ch == " " for ch in comment)


@pytest.mark.parametrize("charset", ["unicode_escape", "raw_unicode_escape", "idna", "punycode"])
def test_codecs_that_are_not_charsets_are_not_decoded(charset: str) -> None:
    word = f"=?{charset}?Q?=5Cu202e?="
    assert parse_header(f"({word}) <a:b>").comments == (word,)


def test_a_quoted_control_is_replaced_and_refused_when_strict() -> None:
    value = "(a" + "\\" + chr(13) + chr(10) + " x) <a:b>"
    assert parse_header(value).comments == ("a" + REPLACED + " x",)
    with pytest.raises(ListUnsubscribeError, match="quoted pair of a control character"):
        parse_header("(a" + "\\" + chr(0) + ") <a:b>", strict=True)


def test_strict_refuses_a_bare_carriage_return() -> None:
    with pytest.raises(ListUnsubscribeError):
        parse_header("<a:b>," + chr(13) + " <c:d>", strict=True)
    assert parse_header("<a:b>," + chr(13) + " <c:d>").uris == ("a:b", "c:d")
    assert parse_header("<a:b>,\n <c:d>", strict=True).uris == ("a:b", "c:d")


def test_header_line_counts_the_limit_in_octets() -> None:
    assert header_line("X", chr(0xE9) * 497).endswith(chr(0xE9))
    with pytest.raises(ListUnsubscribeError, match="998 octets"):
        header_line("X", chr(0xE9) * 498)


@pytest.mark.parametrize("signature", ["h=" + chr(0), "h=list unsubscribe", "h=a; b=" + chr(0xE9)])
def test_dkim_values_must_be_valchar(signature: str) -> None:
    with pytest.raises(ListUnsubscribeError):
        signed_headers(signature)


def test_the_package_init_only_re_exports() -> None:
    defined = [
        name
        for name, value in vars(listunsub).items()
        if inspect.isfunction(value) and value.__module__ == "listunsub"
    ]
    assert defined == []


def test_escaped_commas_never_split_addresses() -> None:
    assert parse_mailto("mailto:a%2Cb@x.test").to == ("a,b@x.test",)
    assert parse_mailto("mailto:?to=a%2Cb@x.test").to == ("a,b@x.test",)
