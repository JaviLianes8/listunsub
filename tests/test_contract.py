from __future__ import annotations

import importlib.resources

import listunsub

PUBLIC_API: list[str] = [
    "ONE_CLICK_POST",
    "Action",
    "ListUnsubscribe",
    "ListUnsubscribeError",
    "Mailto",
    "OneClickRequest",
    "Problem",
    "actions",
    "audit",
    "build",
    "build_mailto",
    "choose",
    "dkim_covers",
    "header_line",
    "http_links",
    "is_one_click",
    "mailto_links",
    "one_click_post",
    "one_click_request",
    "parse",
    "parse_header",
    "parse_mailto",
    "sender_headers",
    "signed_headers",
]


def test_all_lists_exactly_the_public_api() -> None:
    assert sorted(listunsub.__all__) == sorted(PUBLIC_API)


def test_every_exported_name_resolves() -> None:
    for name in listunsub.__all__:
        assert hasattr(listunsub, name)


def test_version_is_a_three_part_string() -> None:
    parts = listunsub.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_the_package_ships_type_information() -> None:
    assert importlib.resources.files("listunsub").joinpath("py.typed").is_file()


def test_the_error_is_a_value_error_with_reason_and_offset() -> None:
    error = listunsub.ListUnsubscribeError("bad", 3)
    assert isinstance(error, ValueError)
    assert (error.reason, error.offset, str(error)) == ("bad", 3, "bad at offset 3")
    assert str(listunsub.ListUnsubscribeError("bad")) == "bad"


def test_the_results_are_frozen() -> None:
    header = listunsub.parse_header("<https://a.test/u>")
    try:
        header.uris = ()  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("ListUnsubscribe is mutable")
