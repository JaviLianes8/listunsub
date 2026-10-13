from __future__ import annotations

from listunsub import Problem, audit

GOOD = "<https://a.test/u/opaque>, <mailto:u@a.test?subject=unsubscribe>"
POST = "List-Unsubscribe=One-Click"
DKIM = "v=1; d=a.test; h=from:list-unsubscribe:list-unsubscribe-post; b=x"


def codes(problems: list[Problem]) -> list[str]:
    return [problem.code for problem in problems]


def test_a_complete_one_click_message_is_clean() -> None:
    assert audit(GOOD, POST, dkim_signatures=[DKIM]) == []
    assert audit([GOOD], [POST], dkim_signatures=DKIM) == []
    assert audit(GOOD, POST) == []


def test_missing_fields() -> None:
    assert codes(audit(None)) == ["missing-list-unsubscribe", "missing-post"]
    assert codes(audit([], [])) == ["missing-list-unsubscribe", "missing-post"]


def test_duplicate_fields() -> None:
    assert codes(audit([GOOD, GOOD], [POST, POST])) == [
        "duplicate-list-unsubscribe",
        "duplicate-post",
    ]


def test_an_invalid_field_is_reported_and_still_read_leniently() -> None:
    problems = audit("<https://a.test/u> junk", POST)
    assert problems == [Problem("invalid-list-unsubscribe", "expected ',' after '>' at offset 19")]


def test_no_https_uri() -> None:
    assert codes(audit("<mailto:u@a.test>, <http://a.test/u>", POST)) == ["no-https"]
    assert codes(audit("junk", POST)) == ["invalid-list-unsubscribe", "no-https"]


def test_an_https_uri_that_cannot_be_posted_to() -> None:
    problems = audit("<https://user@a.test/u>", POST)
    assert codes(problems) == ["unusable-https"]
    assert "user information" in problems[0].message


def test_broken_mailto_uris() -> None:
    assert codes(audit("<https://a.test/u>, <mailto:?subject=x>", POST)) == ["invalid-mailto"]
    problems = audit("<https://a.test/u>, <mailto:nobody>", POST)
    assert problems == [Problem("invalid-mailto", "not an addr-spec: 'nobody'")]


def test_post_value_problems() -> None:
    assert codes(audit(GOOD)) == ["missing-post"]
    problems = audit(GOOD, "List-Unsubscribe=Yes")
    assert problems == [
        Problem("invalid-post", "List-Unsubscribe-Post is not 'List-Unsubscribe=One-Click'")
    ]
    assert codes(audit(GOOD, [POST, "x"])) == ["duplicate-post"]
    assert codes(audit(GOOD, ["x", POST])) == ["duplicate-post", "invalid-post"]


def test_dkim_problems() -> None:
    assert codes(audit(GOOD, POST, dkim_signatures=[])) == ["missing-dkim"]
    assert codes(audit(GOOD, POST, dkim_signatures=["h=from:list-unsubscribe"])) == [
        "dkim-not-covering"
    ]
    assert audit(GOOD, POST, dkim_signatures=["h=from", DKIM]) == []


def test_only_the_first_field_is_checked_when_duplicated() -> None:
    assert codes(audit([GOOD, "junk"], POST)) == ["duplicate-list-unsubscribe"]
