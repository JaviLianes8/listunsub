"""Check the library against RFC 6068, RFC 5322 and RFC 2047.

The RFC texts are read from tests/upstream (URL, size and sha256 in MANIFEST.json); these
tests skip until `python scripts/fetch_upstream.py` has fetched them.
"""

from __future__ import annotations

import re
import string

from conftest import section

from listunsub import ListUnsubscribeError, build_mailto, header_line, parse, parse_header
from listunsub import parse_mailto as mailto


def _bracketed(text: str) -> list[str]:
    # The RFC folds some URIs; RFC 2369 parsing drops that white space, as a client must.
    return [parse(f"<{uri}>")[0] for uri in re.findall(r"<(mailto:[^>]*)>", text)]


def test_the_rfc_6068_basic_examples(rfc6068: str) -> None:
    body = section(rfc6068, "6.1.  Basic Examples", "6.2.  Examples of Complicated")
    uris = _bracketed(body)
    assert len(uris) == 11
    wrong = uris.pop(7)
    # Expected values from https://www.rfc-editor.org/rfc/rfc6068.txt section 6.1.
    assert wrong == "mailto:joe@example.com?cc=bob@example.com?body=hello"
    try:
        mailto(wrong, strict=True)
    except ListUnsubscribeError:
        pass
    else:
        raise AssertionError("the example marked WRONG passed")
    decoded = [mailto(uri, strict=True) for uri in uris]
    assert [m.to for m in decoded] == [
        ("chris@example.com",),
        ("infobot@example.com",),
        ("infobot@example.com",),
        ("infobot@example.com",),
        ("list@example.org",),
        ("majordomo@example.com",),
        ("joe@example.com",),
        ("gorby%kremvax@example.com",),
        ("unlikely?address@example.com",),
        ("Mike&family@example.org",),
    ]
    assert decoded[1].subject == "current-issue"
    assert decoded[3].body == "send current-issue\r\nsend index"
    assert decoded[4].get("in-reply-to") == "<3469A91.D10AF4C@example.com>"
    assert decoded[6].fields == (("cc", "bob@example.com"), ("body", "hello"))
    assert decoded[8].fields == (("blat", "foop"),)
    for uri in (uris[0], uris[7], uris[9]):
        assert build_mailto(mailto(uri).to) == uri


def test_the_rfc_6068_complicated_addresses(rfc6068: str) -> None:
    body = section(rfc6068, "6.2.  Examples of Complicated", "6.3.  Examples Using")
    pairs = re.findall(r"Email address: (.+?); corresponding\s+'mailto' URI:\s+<([^>]+)>", body)
    assert len(pairs) == 3
    for address, uri in pairs:
        assert mailto(uri, strict=True).to == (address,)
        assert build_mailto(address) == uri


def test_the_rfc_6068_utf8_examples(rfc6068: str) -> None:
    body = section(rfc6068, "6.3.  Examples Using", "7.  Security Considerations")
    plain, word, latin, both, natto = (mailto(uri, strict=True) for uri in _bracketed(body))
    assert plain.subject == both.subject == both.body == "café"
    # Encoded words in a value are kept as text; composing the message decides on them.
    assert word.subject == "=?utf-8?Q?caf=C3=A9?="
    assert latin.subject == "=?iso-8859-1?Q?caf=E9?="
    code_points = re.findall(r"U\+([0-9A-F]{4})", body)
    assert natto.to == ("user@" + "".join(chr(int(c, 16)) for c in code_points) + ".example.org",)
    assert build_mailto(both.to, subject="café", body="café") == _bracketed(body)[3]


def test_the_rfc_6068_equivalent_to_forms(rfc6068: str) -> None:
    body = section(rfc6068, "2.  Syntax of a 'mailto' URI", "3.  Semantics and Operations")
    forms = [mailto(uri, strict=True) for uri in _bracketed(body)]
    assert len(forms) == 3
    assert {m.to for m in forms} == {("addr1@an.example", "addr2@an.example")}
    assert all(m.fields == () for m in forms)


def test_strict_field_values_accept_exactly_qchar(rfc6068: str) -> None:
    body = section(rfc6068, "2.  Syntax of a 'mailto' URI", "3.  Semantics and Operations")
    rule = re.findall(r"some-delims  = (.+\n.+)", body)[0]
    qchar = set(re.findall(r'"(.)"', rule)) | set(string.ascii_letters + string.digits + "-._~")
    assert len(qchar) == 66 + 11
    for code in range(0x21, 0x7F):
        char = chr(code)
        if char in "%&=#":
            continue
        try:
            mailto(f"mailto:a@b.co?x={char}", strict=True)
        except ListUnsubscribeError:
            assert char not in qchar, char
        else:
            assert char in qchar, char


def test_strict_comments_accept_exactly_ctext_and_white_space(rfc5322: str) -> None:
    rule = re.findall(r"ctext +=(.+\n.+\n.+)", rfc5322)[0]
    ranges = [tuple(map(int, pair)) for pair in re.findall(r"%d(\d+)-(\d+)", rule)]
    assert ranges == [(33, 39), (42, 91), (93, 126)]
    ctext = {code for low, high in ranges for code in range(low, high + 1)}
    for code in range(0x80):
        if code == 0x5C:  # a backslash starts a quoted pair
            continue
        try:
            parse_header(f"(a{chr(code)}b) <a:b>", strict=True)
        except ListUnsubscribeError:
            assert code not in ctext | {9, 32}, code
        else:
            assert code in ctext | {9, 32}, code


def test_the_rfc_5322_line_limit(rfc5322: str) -> None:
    body = section(rfc5322, "2.1.1.  Line Length Limits", "2.2.  Header Fields")
    assert "MUST be no more than 998 characters" in " ".join(body.split())
    header_line("X", "a" * 995)
    try:
        header_line("X", "a" * 996)
    except ListUnsubscribeError:
        return
    raise AssertionError("a 999 character line was accepted")


def _rfc2047_comment_examples(rfc2047: str) -> list[tuple[str, str]]:
    body = section(rfc2047, "8. Examples", "9. References")
    lines = body.splitlines()
    pairs = []
    for index, line in enumerate(lines):
        if not line.startswith("   (=?"):
            continue
        encoded, displayed = re.split(r"\s{2,}(?=\()", line.strip())
        if encoded.count("(") != encoded.count(")"):
            encoded += "\r\n" + lines[index + 1]
        pairs.append((encoded, displayed))
    return pairs


def test_the_rfc_2047_comment_examples(rfc2047: str) -> None:
    pairs = _rfc2047_comment_examples(rfc2047)
    assert len(pairs) == 7
    for encoded, displayed in pairs:
        header = parse_header(f"{encoded} <mailto:a@b.co>", strict=True)
        assert header.uris == ("mailto:a@b.co",)
        assert header.comments == (displayed[1:-1],), encoded
