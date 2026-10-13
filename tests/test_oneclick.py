from __future__ import annotations

import re

import pytest

from listunsub import (
    ONE_CLICK_POST,
    ListUnsubscribeError,
    OneClickRequest,
    is_one_click,
    one_click_post,
    one_click_request,
)


def test_the_value_is_the_rfc_8058_pair() -> None:
    assert ONE_CLICK_POST == "List-Unsubscribe=One-Click"
    assert one_click_post() == ONE_CLICK_POST


@pytest.mark.parametrize(
    "value",
    [
        "List-Unsubscribe=One-Click",
        "list-unsubscribe=one-click",
        "LIST-UNSUBSCRIBE=ONE-CLICK",
        "  List-Unsubscribe=One-Click\r\n",
        "\tList-Unsubscribe=One-Click ",
    ],
)
def test_the_pair_matches_in_any_case_with_surrounding_space(value: str) -> None:
    assert is_one_click(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "List-Unsubscribe = One-Click",
        "List-Unsubscribe=One-Click; x=y",
        "List-Unsubscribe=One-Click&x=y",
        "List-Unsubscribe=Yes",
        "One-Click",
        "List-Unsubscribe=One-\r\n Click",
    ],
)
def test_anything_else_is_not_one_click(value: str) -> None:
    assert not is_one_click(value)


def test_the_urlencoded_request_matches_the_rfc_example() -> None:
    request = one_click_request("https://example.com/unsubscribe/opaquepart", form="urlencoded")
    assert request == OneClickRequest(
        "https://example.com/unsubscribe/opaquepart",
        "application/x-www-form-urlencoded",
        b"List-Unsubscribe=One-Click",
    )
    assert request.method == "POST"
    assert request.headers == {
        "Content-Type": "application/x-www-form-urlencoded",
        "Content-Length": "26",
    }


def test_the_multipart_request_has_the_exact_body() -> None:
    request = one_click_request("https://a.test/u?t=1", boundary="b0")
    assert request.content_type == "multipart/form-data; boundary=b0"
    assert request.body == (
        b'--b0\r\nContent-Disposition: form-data; name="List-Unsubscribe"\r\n\r\n'
        b"One-Click\r\n--b0--"
    )
    assert request.headers["Content-Length"] == str(len(request.body))


def test_multipart_is_the_default_with_a_fresh_random_boundary() -> None:
    first, second = (one_click_request("https://a.test/u") for _ in range(2))
    pattern = r"multipart/form-data; boundary=(listunsub-[0-9a-f]{32})"
    match = re.fullmatch(pattern, first.content_type)
    assert match is not None
    assert first.body.startswith(f"--{match.group(1)}\r\n".encode())
    assert first.content_type != second.content_type


def test_the_fragment_is_dropped_and_an_empty_path_becomes_slash() -> None:
    assert one_click_request("https://a.test/u?x=1#frag").url == "https://a.test/u?x=1"
    assert one_click_request("HTTPS://a.test").url == "https://a.test/"
    assert one_click_request("https://a.test:8443?q").url == "https://a.test:8443/?q"


@pytest.mark.parametrize(
    ("uri", "reason"),
    [
        ("http://a.test/u", "one-click needs an https URI: 'http://a.test/u'"),
        ("mailto:a@b.co", "one-click needs an https URI: 'mailto:a@b.co'"),
        ("https://user:pw@a.test/u", "must not carry user information"),
        ("https://user@a.test/u", "must not carry user information"),
        ("https:///u", "one-click URI has no host: 'https:///u'"),
        ("https:u", "one-click URI has no host: 'https:u'"),
        ("https://a.test/u u", "URI holds a character outside RFC 3986"),
    ],
)
def test_unsafe_uris_are_refused(uri: str, reason: str) -> None:
    with pytest.raises(ListUnsubscribeError, match=re.escape(reason)):
        one_click_request(uri)


@pytest.mark.parametrize("boundary", ["", "a b", "a;b", 'a"b', "x" * 71, "café"])
def test_a_boundary_outside_the_safe_set_is_refused(boundary: str) -> None:
    with pytest.raises(ListUnsubscribeError, match="boundary"):
        one_click_request("https://a.test/u", boundary=boundary)


def test_a_seventy_character_boundary_is_accepted() -> None:
    boundary = "'+_.-" + "x" * 65
    assert one_click_request("https://a.test/u", boundary=boundary).content_type.endswith(boundary)


def test_an_unknown_form_is_refused() -> None:
    with pytest.raises(ListUnsubscribeError, match="unknown form encoding"):
        one_click_request("https://a.test/u", form="json")  # type: ignore[arg-type]
