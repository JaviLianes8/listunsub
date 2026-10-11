# listunsub

Typed, zero-dependency parser and builder for the email List-Unsubscribe and List-Unsubscribe-Post headers (RFC 2369 and RFC 8058)

## Install

```
pip install listunsub
```

## Usage

```python
from listunsub import build, http_links, is_one_click, mailto_links, one_click_post, parse

# Parse an incoming List-Unsubscribe header into its URIs.
uris = parse("<mailto:unsub@example.com>, <https://example.com/unsub?id=1>")
# ['mailto:unsub@example.com', 'https://example.com/unsub?id=1']

mailto_links(uris)  # ['mailto:unsub@example.com']
http_links(uris)    # ['https://example.com/unsub?id=1']

# Build a header from a list of URIs.
build(["mailto:unsub@example.com", "https://example.com/unsub"])
# '<mailto:unsub@example.com>, <https://example.com/unsub>'

# Offer RFC 8058 one-click unsubscribe.
one_click_post()  # 'List-Unsubscribe=One-Click'
is_one_click("List-Unsubscribe=One-Click")  # True
```

Parsing is tolerant: it strips folding whitespace, removes the angle brackets,
and ignores anything that is not a bracketed URI. Building rejects a URI that
would break the header (one holding an angle bracket or a line break).

## Why

Every email sender has to produce a List-Unsubscribe header, and every mailbox
provider has to read one, yet Python has no small library for it: the only
published package is a Rust crate, so projects hand-roll the bracket parsing and
the RFC 8058 `List-Unsubscribe=One-Click` value inline. This is that primitive on
its own, typed and dependency-free. It handles the header syntax (RFC 2369) and
the one-click post value (RFC 8058); DKIM signing and transport are out of scope.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
