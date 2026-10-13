# listunsub

Typed, zero-dependency parser and builder for the email List-Unsubscribe and
List-Unsubscribe-Post headers: RFC 2369 parsing, RFC 8058 one-click, RFC 6068 `mailto:`
URIs, and a check against the rules Gmail and Yahoo apply to bulk senders.

## Install

```
pip install listunsub
```

## Reading the header (mail receivers, clients, tools)

```python
from listunsub import choose, one_click_request, parse_header

field = """(Unsubscribe)
 <mailto:list-request@example.com?subject=unsubscribe>,
 <https://example.com/unsubscribe/opaque123>"""
header = parse_header(field)
print(header.uris)
# ('mailto:list-request@example.com?subject=unsubscribe', 'https://example.com/unsubscribe/opaque123')
print(header.comments)
# ('Unsubscribe',)

# One-click only when the post value is right and you verified the DKIM signature.
action = choose(header, "List-Unsubscribe=One-Click", dkim_verified=True)
print(action)
# Action(kind='one-click', uri='https://example.com/unsubscribe/opaque123')

request = one_click_request(action.uri, form="urlencoded")
print(request.method, request.url)
# POST https://example.com/unsubscribe/opaque123
print(request.headers, request.body)
# {'Content-Type': 'application/x-www-form-urlencoded', 'Content-Length': '26'} b'List-Unsubscribe=One-Click'
```

Parsing follows the client rules of RFC 2369 section 2: folding and comments are
understood, a field that does not start with `<` is ignored, text after a URI ends the
list unless a comma follows, and white space inside the brackets is dropped. Pass
`strict=True` to get a `ListUnsubscribeError` (a `ValueError` with `reason` and `offset`)
instead of silently ignoring anything:

```python
from listunsub import ListUnsubscribeError, parse

print(parse("<https://example.com/u> trailing text, <mailto:u@example.com>"))
# ['https://example.com/u']
try:
    parse("<https://example.com/u> trailing text", strict=True)
except ListUnsubscribeError as error:
    print(error.reason, error.offset)
# expected ',' after '>' 24
```

Comments are decoded for display but remain untrusted text: control characters, line
separators and bidi overrides in them are replaced by U+FFFD.

Without a verified DKIM signature `choose` never returns one-click: RFC 8058 section 4
says not to offer it. `actions` lists every usable way, best first, so you can fall back
when one fails. `one_click_request` refuses anything but an HTTPS URI with a host and no
user information, drops the fragment, and builds `multipart/form-data` by default (the
RFC's SHOULD). Send it without cookies or credentials and do not follow redirects.

## Writing the header (mail senders)

```python
from listunsub import dkim_covers, header_line, sender_headers

fields = sender_headers(
    "https://example.com/unsubscribe/7f3a9c",
    "mailto:unsubscribe@example.com?subject=unsubscribe",
)
for name, value in fields.items():
    print(header_line(name, value, width=60))
# List-Unsubscribe: <https://example.com/unsubscribe/7f3a9c>,
#  <mailto:unsubscribe@example.com?subject=unsubscribe>
# List-Unsubscribe-Post: List-Unsubscribe=One-Click

# Both fields must be in the h= tag of your DKIM signature.
print(dkim_covers("v=1; d=example.com; h=from:to:list-unsubscribe:list-unsubscribe-post"))
# True
```

`build` refuses a URI that would break the header or inject another one: no scheme,
white space, angle brackets, control characters or raw non-ASCII text. `header_line`
refuses a bad field name, control characters and Unicode line separators, and a line
over the 998-octet limit.

## mailto URIs

```python
from listunsub import build_mailto, parse_mailto

uri = build_mailto("list-request@example.com", subject="unsubscribe café", body="remove me")
print(uri)
# mailto:list-request@example.com?subject=unsubscribe%20caf%C3%A9&body=remove%20me
mailto = parse_mailto(uri, strict=True)
print(mailto.to, mailto.subject)
# ('list-request@example.com',) unsubscribe café
message = mailto.to_message("reader@example.org")
print(message["To"], "|", message["Subject"])
# list-request@example.com | unsubscribe café
```

`to_message` keeps only To, Subject, Keywords and the body, as RFC 6068 sections 3 and 4
advise, writes an internationalized domain in its IDNA form, and refuses a header value
holding a line break or a control character. `build_mailto` also prefers the IDNA form.

## Checking a message

```python
from listunsub import audit

for problem in audit("<http://example.com/u>", None, dkim_signatures=[]):
    print(problem.code)
# no-https
# missing-post
# missing-dkim
```

The codes are `missing-list-unsubscribe`, `duplicate-list-unsubscribe`, `duplicate-post`,
`invalid-list-unsubscribe`, `invalid-mailto`, `unusable-https`, `no-https`,
`missing-post`, `invalid-post`, `missing-dkim` and `dkim-not-covering`. Since February
2024 Gmail and Yahoo expect one-click on marketing and subscribed mail from bulk senders,
so an empty list is what such a sender wants.

## Command line

```
listunsub message.eml [--dkim-verified]
python -m listunsub < message.eml
```

It reads a message (or just its header block), prints the URIs, comments, one-click
status, usable actions and audit problems as JSON, and exits 0 when the audit is clean,
1 when it is not and 2 when the file cannot be read.

## API

| Name | What it does |
| --- | --- |
| `parse(value, *, strict=False)` | URIs of a List-Unsubscribe field body, as a list |
| `parse_header(value, *, strict=False)` | `ListUnsubscribe`: `uris`, `comments`, `ignored`, `https`, `mailto`, `by_scheme()` |
| `build(uris)` | the field body for a list of URIs, validated |
| `header_line(name, value, *, width=78)` | `Name: value` folded with CRLF and a space |
| `sender_headers(https, mailto=None)` | both one-click fields for a sender |
| `ONE_CLICK_POST`, `one_click_post()` | `List-Unsubscribe=One-Click` |
| `is_one_click(value)` | whether a List-Unsubscribe-Post body asks for one-click |
| `one_click_request(uri, *, form, boundary)` | the `OneClickRequest` (method, url, content type, body, headers) |
| `actions(...)`, `choose(...)` | every usable `Action`, best first, or the best one |
| `signed_headers(signature)`, `dkim_covers(signature, fields)` | the DKIM `h=` list and whether it signs the fields |
| `parse_mailto(uri, *, strict=False)`, `build_mailto(to, ...)` | `Mailto` (`to`, `fields`, `subject`, `body`, `get()`, `to_message()`) and its inverse |
| `audit(list_unsubscribe, post, *, dkim_signatures)` | a list of `Problem` (`code`, `message`) |
| `mailto_links(uris)`, `http_links(uris)` | filter URIs by scheme |
| `ListUnsubscribeError` | the `ValueError` raised for anything invalid |

## Why

Every bulk sender has to produce these headers and every mailbox provider, client and
deliverability tool has to read them, yet the parsing is usually a regular expression
that takes any `<...>` anywhere, including inside comments, and the one-click POST is
assembled by hand. This library does the standard parts exactly and nothing else:
it sends no mail and no HTTP request, and it reads the DKIM `h=` tag without verifying
the signature (that needs DNS and cryptography).

## Standards

RFC 2369 (list header fields), RFC 8058 (one-click, with its verified errata), RFC 6068
(`mailto:`), RFC 5322 (folding, comments), RFC 2047 (encoded words in comments) and RFC
6376 (the DKIM tag list). The tests check the library against the examples and grammar
rules of those texts; `python scripts/fetch_upstream.py` downloads them into
`tests/upstream`, verified against the sizes and hashes in `MANIFEST.json`.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
