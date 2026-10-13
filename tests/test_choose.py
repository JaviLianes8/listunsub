from __future__ import annotations

from listunsub import Action, actions, choose, parse_header

FIELD = "<mailto:u@a.test?subject=unsubscribe>, <http://a.test/web>, <https://a.test/one>"
POST = "List-Unsubscribe=One-Click"


def test_one_click_comes_first_when_everything_allows_it() -> None:
    assert actions(FIELD, POST, dkim_verified=True) == [
        Action("one-click", "https://a.test/one"),
        Action("mailto", "mailto:u@a.test?subject=unsubscribe"),
        Action("web", "http://a.test/web"),
        Action("web", "https://a.test/one"),
    ]
    assert choose(FIELD, POST, dkim_verified=True) == Action("one-click", "https://a.test/one")


def test_one_click_needs_a_verified_dkim_signature() -> None:
    assert choose(FIELD, POST) == Action("mailto", "mailto:u@a.test?subject=unsubscribe")


def test_one_click_needs_the_post_value() -> None:
    assert choose(FIELD, None, dkim_verified=True) == Action(
        "mailto", "mailto:u@a.test?subject=unsubscribe"
    )
    assert choose(FIELD, "List-Unsubscribe=Yes", dkim_verified=True).kind == "mailto"  # type: ignore[union-attr]


def test_one_click_needs_an_https_uri() -> None:
    assert choose("<http://a.test/u>", POST, dkim_verified=True) == Action("web", "http://a.test/u")


def test_one_click_skips_an_https_uri_it_cannot_post_to() -> None:
    field = "<https://user@a.test/u>, <https://a.test/ok>"
    assert actions(field, POST, dkim_verified=True)[0] == Action("one-click", "https://a.test/ok")
    assert [a.kind for a in actions("<https://user@a.test/u>", POST, dkim_verified=True)] == ["web"]


def test_only_the_first_good_https_uri_is_offered_for_one_click() -> None:
    found = actions("<https://a.test/1>, <https://a.test/2>", POST, dkim_verified=True)
    assert [a.kind for a in found] == ["one-click", "web", "web"]


def test_schemes_limit_the_choice_in_the_senders_order() -> None:
    assert choose(FIELD, schemes=("https", "http")) == Action("web", "http://a.test/web")
    assert choose(FIELD, schemes=["https"]) == Action("web", "https://a.test/one")
    assert choose(FIELD, POST, dkim_verified=True, schemes=()) is None
    assert choose(FIELD, POST, dkim_verified=True, schemes=["mailto"]) == Action(
        "mailto", "mailto:u@a.test?subject=unsubscribe"
    )
    assert choose(FIELD, schemes=()) is None


def test_unknown_and_broken_uris_are_skipped() -> None:
    field = "<ftp://a.test/u>, <mailto:nobody>, <mailto:a@x.test?s=x?y>, <MAILTO:ok@x.test>"
    assert actions(field) == [Action("mailto", "MAILTO:ok@x.test")]
    assert actions("<https://a.test/\x00>, <http://a.test/u>") == [Action("web", "http://a.test/u")]


def test_a_parsed_header_is_accepted() -> None:
    header = parse_header(FIELD)
    assert actions(header) == actions(FIELD)


def test_nothing_usable_gives_none() -> None:
    assert choose("") is None
    assert choose("junk <https://a.test/u>") is None
