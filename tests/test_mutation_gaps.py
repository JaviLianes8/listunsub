"""Tests added after the mutation run showed behaviour no other test pinned."""

from __future__ import annotations

import dataclasses
import io
import json
import runpy
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from listunsub import (
    Action,
    ListUnsubscribeError,
    Mailto,
    OneClickRequest,
    Problem,
    actions,
    audit,
    build_mailto,
    header_line,
    http_links,
    mailto_links,
    one_click_request,
    parse,
    parse_header,
    parse_mailto,
    signed_headers,
)
from listunsub._cli import main


def test_the_link_filters() -> None:
    uris = ["MAILTO:a@b.co", "https://a.test/", "HTTP://b.test/", "ftp://c.test/", "httpx:y"]
    assert mailto_links(uris) == ["MAILTO:a@b.co"]
    assert http_links(iter(uris)) == ["https://a.test/", "HTTP://b.test/"]
    assert mailto_links([]) == [] and http_links([]) == []


@pytest.mark.parametrize(
    "value",
    [Action("web", "x:y"), Problem("c", "m"), Mailto(()), OneClickRequest("u", "t", b"")],
)
def test_result_types_are_frozen(value: object) -> None:
    field = dataclasses.fields(value)[0].name  # type: ignore[arg-type]
    with pytest.raises(dataclasses.FrozenInstanceError):
        setattr(value, field, None)


def test_actions_never_offers_one_click_by_default() -> None:
    found = actions("<https://a.test/u>", "List-Unsubscribe=One-Click")
    assert found == [Action("web", "https://a.test/u")]


def test_the_lenient_parser_stops_at_the_first_stray_text() -> None:
    assert parse("junk:x>") == []
    assert parse("<a:b>x<c:d>") == ["a:b"]
    assert parse("<a:b>,<c:d>") == ["a:b", "c:d"]
    assert parse("<<a:b>") == []
    assert parse("<a:b>,,<c:d>") == ["a:b", "c:d"]


def test_invalid_base64_characters_leave_the_word_alone() -> None:
    for word in ("=?UTF-8?B?Y2Fm!w==?=", "=?UTF-8?B?Y2Fm!Zg==?="):
        assert parse_header(f"({word}) <a:b>").comments == (word,)


def test_a_one_character_boundary_is_accepted() -> None:
    assert one_click_request("https://a.test/u", boundary="b").body.startswith(b"--b\r\n")


@pytest.mark.parametrize("uri", ["mailto:a^b@x.test", 'mailto:a"b@x.test'])
def test_strict_mailto_refuses_characters_outside_the_path_rule(uri: str) -> None:
    with pytest.raises(ListUnsubscribeError, match="character not allowed in a mailto URI"):
        parse_mailto(uri, strict=True)


def test_blank_addresses_are_dropped() -> None:
    assert parse_mailto("mailto:%20,a@b.co").to == ("a@b.co",)


@pytest.mark.parametrize(
    ("address", "reason"),
    [
        ("<a@b.co", "control character or angle bracket in address '<a@b.co'"),
        ("a@b.co>", "control character or angle bracket in address 'a@b.co>'"),
        ('"a b@x.test', "white space in address '\"a b@x.test'"),
        ('a b"@x.test', "white space in address 'a b\"@x.test'"),
        ("nobody", "not an addr-spec: 'nobody'"),
    ],
)
def test_unusable_addresses_are_refused_everywhere(address: str, reason: str) -> None:
    for call in (lambda: build_mailto(address), lambda: Mailto((address,)).to_message("m@y.t")):
        with pytest.raises(ListUnsubscribeError) as caught:
            call()
        assert caught.value.reason == reason


@pytest.mark.parametrize(
    ("call", "reason"),
    [
        (lambda: header_line("X", "a\x00"), "control character in a header value"),
        (lambda: parse_mailto("mailto:a@b.co?s=%FF", strict=True), "escapes are not UTF-8: '%FF'"),
        (
            lambda: parse_mailto("mailto:a@b.co?s", strict=True),
            "malformed field 's' in a mailto URI",
        ),
        (
            lambda: build_mailto("a@b.co", fields=[("to", "x")]),
            "field 'to' is invalid, repeated or 'to'",
        ),
        (lambda: build_mailto("a@b.co", subject="a\nb"), "line break in the 'subject' field"),
        (lambda: signed_headers("h=a::b"), "empty or invalid field name in the DKIM h= tag"),
        (
            lambda: parse_mailto("mailto:a@b.co?subject=a%0Ab").to_message("m@y.t"),
            "line break or control character in the Subject value",
        ),
        (
            lambda: one_click_request("https://a.test/u", boundary="a b"),
            "boundary must be 1 to 70 token characters: 'a b'",
        ),
    ],
)
def test_error_reasons_are_exact(call: Callable[[], object], reason: str) -> None:
    with pytest.raises(ListUnsubscribeError) as caught:
        call()
    assert caught.value.reason == reason


def test_audit_messages_are_exact() -> None:
    assert audit("<http://a.test/u>, <mailto:?subject=x>", "List-Unsubscribe=One-Click") == [
        Problem("invalid-mailto", "no recipient in 'mailto:?subject=x'"),
        Problem("no-https", "one-click needs an https URI in List-Unsubscribe"),
    ]


def test_the_command_line_keeps_text_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "m.eml"
    path.write_bytes(b"List-Unsubscribe: (=?utf-8?Q?caf=C3=A9?=) <https://a.test/u>\r\n\r\n")
    out = io.BytesIO()
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(out, encoding="utf-8"))
    main([str(path)])
    assert "café".encode() in out.getvalue()
    assert json.loads(out.getvalue())["comments"] == ["café"]


def test_python_dash_m_runs_the_command_line(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin = io.TextIOWrapper(io.BytesIO(b"List-Unsubscribe: <https://a.test/u>\r\n\r\n"))
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys, "argv", ["listunsub"])
    with pytest.raises(SystemExit) as caught:
        runpy.run_module("listunsub", run_name="__main__")
    assert caught.value.code == 1
