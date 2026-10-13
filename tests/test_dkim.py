from __future__ import annotations

import pytest

from listunsub import ListUnsubscribeError, dkim_covers, signed_headers

SIGNATURE = (
    "v=1; a=rsa-sha256; d=example.com; s=s1;\r\n"
    "\th=From : To:Subject\r\n  :list-unsubscribe: List-Unsubscribe-Post ;\r\n"
    " bh=abc=; b=def"
)


def test_signed_headers_are_lower_cased_and_unfolded() -> None:
    assert signed_headers(SIGNATURE) == (
        "from",
        "to",
        "subject",
        "list-unsubscribe",
        "list-unsubscribe-post",
    )


def test_a_trailing_semicolon_and_empty_tags_are_fine() -> None:
    assert signed_headers("h=a;") == ("a",)
    assert signed_headers(" ; h = a : b ;; ") == ("a", "b")


@pytest.mark.parametrize(
    ("signature", "reason"),
    [
        ("v=1; a=rsa-sha256", "no h= tag"),
        ("v=1; H=from", "no h= tag"),
        ("h=a; h=b", "appears twice"),
        ("h=a; junk", "malformed DKIM tag 'junk'"),
        ("h=a; =x", "malformed"),
        ("h=a; 1x=y", "malformed"),
        ("h=a::b", "empty or invalid field name"),
        ("h=", "empty or invalid field name"),
        ("h=a:", "empty or invalid field name"),
    ],
)
def test_malformed_tag_lists_are_refused(signature: str, reason: str) -> None:
    with pytest.raises(ListUnsubscribeError, match=reason):
        signed_headers(signature)


def test_dkim_covers_needs_both_one_click_fields() -> None:
    assert dkim_covers(SIGNATURE)
    assert not dkim_covers("h=from:list-unsubscribe")
    assert not dkim_covers("h=from:list-unsubscribe-post")
    assert not dkim_covers("h=from:list-unsubscribe-postx:list-unsubscribex")


def test_dkim_covers_any_field_list() -> None:
    assert dkim_covers("h=From:To", ("from",))
    assert not dkim_covers("h=From:To", ("from", "subject"))


def test_a_malformed_signature_covers_nothing() -> None:
    assert not dkim_covers("h=list-unsubscribe:list-unsubscribe-post; h=x")
