from __future__ import annotations

import pytest

from listunsub import ListUnsubscribeError, Mailto, build_mailto, parse_mailto


def test_a_plain_address() -> None:
    assert parse_mailto("mailto:list@example.com") == Mailto(("list@example.com",))


def test_fields_are_decoded_and_names_lower_cased() -> None:
    mailto = parse_mailto("MAILTO:a@b.co?Subject=caf%C3%A9%20list&BODY=one%0D%0Atwo&x-y=1+2")
    assert mailto.to == ("a@b.co",)
    assert mailto.fields == (("subject", "café list"), ("body", "one\r\ntwo"), ("x-y", "1+2"))
    assert (mailto.subject, mailto.body, mailto.get("X-Y"), mailto.get("cc")) == (
        "café list",
        "one\r\ntwo",
        "1+2",
        None,
    )


def test_to_fields_are_merged_and_the_fragment_ignored() -> None:
    mailto = parse_mailto("mailto:a@x.test,b@x.test?to=c@x.test,d@x.test&cc=e@x.test#frag")
    assert mailto.to == ("a@x.test", "b@x.test", "c@x.test", "d@x.test")
    assert mailto.fields == (("cc", "e@x.test"),)


def test_the_first_value_of_a_repeated_field_wins() -> None:
    assert parse_mailto("mailto:a@b.co?subject=one&subject=two").subject == "one"


def test_lenient_parsing_skips_empty_parts_and_bad_fields() -> None:
    mailto = parse_mailto("mailto:,a@b.co,?novalue&&subject=x&body=%FF")
    assert mailto.to == ("a@b.co",)
    assert mailto.fields == (("subject", "x"), ("body", "�"))
    assert parse_mailto("mailto:") == Mailto(())


@pytest.mark.parametrize(
    "uri",
    [
        "mailto:a b@c.d",
        "mailto:a@b.co?subject=a b",
        "mailto:a@b.co?subject=x?y",
        "mailto:a@b.co?subject=a/b",
        "mailto:a@b.co?novalue",
        "mailto:a@b.co?subject=%FF",
        "mailto:nobody",
        "mailto:@b.co",
        "mailto:a@",
        "mailto:a@b.co?to=nobody",
        "mailto:a@b.co?subject=%C3",
    ],
)
def test_strict_parsing_refuses_grammar_errors(uri: str) -> None:
    with pytest.raises(ListUnsubscribeError):
        parse_mailto(uri, strict=True)


def test_strict_parsing_accepts_the_allowed_characters() -> None:
    uri = "mailto:a.b+c!$'()*@x.test?subject=a!$'()*+,;:@-._~%20&body="
    mailto = parse_mailto(uri, strict=True)
    assert mailto.to == ("a.b+c!$'()*@x.test",)
    assert mailto.fields == (("subject", "a!$'()*+,;:@-._~ "), ("body", ""))


@pytest.mark.parametrize("uri", ["https://a.test/", "mailtox:a@b.co", "a@b.co"])
def test_other_schemes_are_refused(uri: str) -> None:
    with pytest.raises(ListUnsubscribeError, match="not a mailto URI"):
        parse_mailto(uri)


def test_build_escapes_values_and_normalises_body_line_breaks() -> None:
    uri = build_mailto(
        "list@example.com",
        subject="café & more = 1+1? /#%",
        body="line one\nline two\rthree\r\n",
        fields=[("Keywords", "a,b;c:d@e")],
    )
    assert uri == (
        "mailto:list@example.com?Keywords=a,b;c:d@e"
        "&subject=caf%C3%A9%20%26%20more%20%3D%201%2B1%3F%20%2F%23%25"
        "&body=line%20one%0D%0Aline%20two%0D%0Athree%0D%0A"
    )
    assert parse_mailto(uri, strict=True).subject == "café & more = 1+1? /#%"


def test_build_escapes_delimiters_in_addresses() -> None:
    assert build_mailto(["a&b@x.test", "c,d;e=f@x.test"]) == (
        "mailto:a%26b@x.test,c%2Cd%3Be%3Df@x.test"
    )
    assert build_mailto("bill+ietf@example.org") == "mailto:bill+ietf@example.org"
    assert build_mailto("u@[192.0.2.1]") == "mailto:u@%5B192.0.2.1%5D"


def test_build_round_trips_through_strict_parse() -> None:
    addresses = ['"a b"@x.test', "café@é.test", "plain@x.test"]
    uri = build_mailto(addresses, subject="s?&=", body="b\r\nc")
    assert "@xn--9ca.test" in uri
    mailto = parse_mailto(uri, strict=True)
    assert mailto.to == (addresses[0], "caf\u00e9@xn--9ca.test", addresses[2])
    assert mailto.fields == (("subject", "s?&="), ("body", "b\r\nc"))


@pytest.mark.parametrize(
    ("to", "fields", "subject"),
    [
        ([], (), None),
        ("nobody", (), None),
        ("a@b.co", [("to", "c@d.co")], None),
        ("a@b.co", [("Subject", "x")], "y"),
        ("a@b.co", [("bad name", "x")], None),
        ("a@b.co", [("bad:name", "x")], None),
        ("a@b.co", [("", "x")], None),
        ("a@b.co", (), "a\r\nBcc: evil@x.test"),
        ("a@b.co", [("keywords", "a\nb")], None),
    ],
)
def test_build_refuses_unsafe_input(
    to: str | list[str], fields: list[tuple[str, str]], subject: str | None
) -> None:
    with pytest.raises(ListUnsubscribeError):
        build_mailto(to, subject=subject, fields=fields)


def test_to_message_keeps_only_safe_fields() -> None:
    uri = "mailto:a@x.test?to=b@x.test&subject=unsubscribe&from=evil@x.test&bcc=c@x.test"
    message = parse_mailto(uri + "&keywords=k&body=please%0D%0Aremove%20me").to_message("me@y.test")
    assert message["From"] == "me@y.test"
    assert message["To"] == "a@x.test, b@x.test"
    assert message["Subject"] == "unsubscribe"
    assert message["Keywords"] == "k"
    assert message["Bcc"] is None and message.get_all("From") == ["me@y.test"]
    assert message.get_content() == "please\nremove me\n"


def test_to_message_without_subject_or_body() -> None:
    message = parse_mailto("mailto:a@x.test").to_message("me@y.test")
    assert message["Subject"] is None and message.get_content() == "\n"


def test_to_message_refuses_injection_and_missing_recipients() -> None:
    with pytest.raises(ListUnsubscribeError, match="Subject"):
        parse_mailto("mailto:a@x.test?subject=x%0D%0ABcc:%20e@x.test").to_message("me@y.test")
    with pytest.raises(ListUnsubscribeError, match="no recipient"):
        parse_mailto("mailto:?subject=x").to_message("me@y.test")
    with pytest.raises(ListUnsubscribeError, match="From"):
        parse_mailto("mailto:a@x.test").to_message("me@y.test\nBcc: e@x.test")
