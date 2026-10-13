"""Check the library against RFC 2369, RFC 8058 (with its errata) and RFC 6376.

The RFC texts are read from tests/upstream (URL, size and sha256 in MANIFEST.json); these
tests skip until `python scripts/fetch_upstream.py` has fetched them.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from conftest import section

from listunsub import (
    ONE_CLICK_POST,
    Action,
    build,
    choose,
    dkim_covers,
    header_line,
    is_one_click,
    one_click_request,
    parse,
    parse_header,
    signed_headers,
)


def _rfc2369_examples(rfc2369: str) -> list[tuple[str, str]]:
    body = section(rfc2369, "3. The List Header Fields", "4. Supporting Nested Lists")
    found = re.findall(r"^     (List-[A-Za-z]+): (.+(?:\n {9}\S.*)*)", body, flags=re.MULTILINE)
    return [(name, value) for name, value in found]


def test_every_rfc_2369_example_parses_strictly_except_the_no_value(rfc2369: str) -> None:
    examples = _rfc2369_examples(rfc2369)
    assert len(examples) == 24
    for name, value in examples:
        written = re.findall(r"<([^>]*)>", value)
        if value.startswith("NO "):
            # Section 3.4: List-Post may say NO; rule 1 makes a client ignore it.
            assert name == "List-Post" and parse_header(value).ignored and not written
            continue
        assert parse(value, strict=True) == written, value
        assert parse(build(written), strict=True) == written


def test_the_rfc_2369_unsubscribe_examples(rfc2369: str) -> None:
    examples = [value for name, value in _rfc2369_examples(rfc2369) if name == "List-Unsubscribe"]
    parsed = [parse_header(value, strict=True) for value in examples]
    # Expected values from https://www.rfc-editor.org/rfc/rfc2369.txt section 3.2.
    assert [header.uris for header in parsed] == [
        ("mailto:list@host.com?subject=unsubscribe",),
        ("mailto:list-manager@host.com?body=unsubscribe%20list",),
        ("mailto:list-off@host.com",),
        (
            "http://www.host.com/list.cgi?cmd=unsub&lst=list",
            "mailto:list-request@host.com?subject=unsubscribe",
        ),
    ]
    assert parsed[1].comments == ("Use this command to get off the list",)
    assert choose(examples[3]) == Action("web", "http://www.host.com/list.cgi?cmd=unsub&lst=list")


def _rfc8058_examples(rfc8058: str) -> list[dict[str, str]]:
    body = section(rfc8058, "8.  Examples", "9.  Normative References")
    examples = []
    for part in re.split(r"\n8\.\d\.  ", body)[1:]:
        email, request = part.split("Resulting POST request")
        field = re.search(r"List-Unsubscribe:((?:.|\n)*?)\n   List-Unsubscribe-Post:", email)
        post = re.search(r"List-Unsubscribe-Post: (.*)", email)
        assert field is not None and post is not None
        head, _, payload = request.strip("\n").partition("\n\n")
        lines = [line.strip() for line in head.splitlines()]
        examples.append(
            {
                "field": field.group(1),
                "post": post.group(1),
                "target": lines[0].split()[1],
                "host": lines[1].split(": ")[1],
                "content-type": lines[2].split(": ", 1)[1],
                "content-length": lines[3].split(": ")[1],
                "body": "\r\n".join(line.strip() for line in payload.strip("\n").splitlines()),
            }
        )
    return examples


def _one_click(example: dict[str, str]) -> str:
    action = choose(example["field"], example["post"], dkim_verified=True)
    assert action is not None and action.kind == "one-click"
    assert is_one_click(example["post"])
    return action.uri


def test_rfc_8058_urlencoded_examples_produce_the_printed_requests(rfc8058: str) -> None:
    for example in _rfc8058_examples(rfc8058)[:2]:
        request = one_click_request(_one_click(example), form="urlencoded")
        parts = urlsplit(request.url)
        assert parts.path + ("?" + parts.query if parts.query else "") == example["target"]
        assert parts.hostname == example["host"]
        assert request.headers == {
            "Content-Type": example["content-type"],
            "Content-Length": example["content-length"],
        }
        assert request.body.decode() == example["body"] == ONE_CLICK_POST


def test_rfc_8058_multipart_example_with_its_errata(rfc8058: str) -> None:
    example = _rfc8058_examples(rfc8058)[2]
    delimiter = example["body"].split("\r\n")[0]
    request = one_click_request(_one_click(example), boundary=delimiter[2:])
    assert request.body.decode() == example["body"]
    assert request.headers["Content-Length"] == example["content-length"] == "124"
    # Errata 5117 and 8927 (verified): the printed boundary parameter repeats the two
    # leading hyphens of the delimiter line, https://www.rfc-editor.org/errata/rfc8058.
    assert example["content-type"] == "multipart/form-data; boundary=" + delimiter
    assert request.content_type == "multipart/form-data; boundary=" + delimiter[2:]
    # Erratum 5559 (verified): the printed request target has a stray "=".
    assert urlsplit(request.url).path == example["target"].replace("opaque=", "opaque")
    assert urlsplit(request.url).path != example["target"]


def test_rfc_8058_examples_fold_back_to_the_same_field(rfc8058: str) -> None:
    for example in _rfc8058_examples(rfc8058):
        uris = parse(example["field"], strict=True)
        line = header_line("List-Unsubscribe", build(uris), width=60)
        assert parse(line.split(":", 1)[1], strict=True) == uris


def test_the_rfc_8058_abnf_value(rfc8058: str) -> None:
    body = section(rfc8058, "5.  Header Syntax", "6.  Security Considerations")
    (value,) = re.findall(r'postarg = "([^"]+)"', body)
    assert value == ONE_CLICK_POST and is_one_click(value.upper())


def test_the_rfc_6376_signed_example(rfc6376: str) -> None:
    body = section(rfc6376, "A.2.  The Email is Signed", "A.3.  The Email Signature")
    match = re.search(r"DKIM-Signature: (.+(?:\n {6,}\S.*)*)", body)
    assert match is not None
    signature = match.group(1)
    # Expected list from https://www.rfc-editor.org/rfc/rfc6376.txt appendix A.2.
    assert signed_headers(signature) == ("received", "from", "to", "subject", "date", "message-id")
    assert dkim_covers(signature, ("From", "SUBJECT"))
    assert not dkim_covers(signature)
