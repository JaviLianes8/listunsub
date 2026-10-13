from __future__ import annotations

import pytest

from listunsub import parse_header


def comment(text: str) -> str:
    (decoded,) = parse_header(f"({text}) <a:b>").comments
    return decoded


@pytest.mark.parametrize(
    ("encoded", "decoded"),
    [
        ("=?UTF-8?B?Y2Fmw6k=?=", "café"),
        ("=?utf-8?q?caf=C3=A9_list?=", "café list"),
        ("=?ISO-8859-1*fr?Q?caf=E9?=", "café"),
        ("see =?UTF-8?Q?caf=C3=A9?= now", "see café now"),
        ("=?UTF-8?Q?a?=\t=?UTF-8?Q?b?=", "ab"),
        ("=?UTF-8?Q?a?= x =?UTF-8?Q?b?=", "a x b"),
    ],
)
def test_encoded_words_in_comments_are_decoded(encoded: str, decoded: str) -> None:
    assert comment(encoded) == decoded


@pytest.mark.parametrize(
    "text",
    [
        "=?nosuchcharset?Q?a?=",
        "=?UTF-8?B?not base64?=",
        "=?UTF-8?B?Y2Fm?w==?=",
        "=?UTF-8?Q?=FF?=",
        "=?UTF-8?X?a?=",
        "x=?UTF-8?Q?a?=",
        "=?UTF-8?Q?a?=x",
        "plain text",
    ],
)
def test_anything_else_is_left_as_written(text: str) -> None:
    assert comment(text) == text


def test_a_bad_word_keeps_the_space_before_the_next_good_one() -> None:
    assert comment("=?x-none?Q?a?= =?UTF-8?Q?b?=") == "=?x-none?Q?a?= b"


def test_a_word_inside_a_nested_comment_is_decoded() -> None:
    assert comment("a (=?UTF-8?Q?b?=) c") == "a (b) c"
