from listunsub import ONE_CLICK_POST, is_one_click, one_click_post


def test_one_click_post_value() -> None:
    assert one_click_post() == "List-Unsubscribe=One-Click"


def test_constant_matches_the_helper() -> None:
    assert one_click_post() == ONE_CLICK_POST


def test_is_one_click_accepts_the_canonical_value() -> None:
    assert is_one_click("List-Unsubscribe=One-Click")


def test_is_one_click_ignores_case() -> None:
    assert is_one_click("list-unsubscribe=one-click")


def test_is_one_click_tolerates_whitespace() -> None:
    assert is_one_click("  List-Unsubscribe = One-Click  ")


def test_is_one_click_rejects_other_values() -> None:
    assert not is_one_click("List-Unsubscribe=Something-Else")


def test_is_one_click_rejects_empty() -> None:
    assert not is_one_click("")
