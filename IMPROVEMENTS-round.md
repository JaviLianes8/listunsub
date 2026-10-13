# listunsub improvement round

Progress:
- [x] Brainstorm ranked improvements (this file)
- [x] Pin the ground truth: RFC 2369, 8058 (with errata), 6068, 5322, 2047, 6376
- [x] RFC 2369 parser: comments, folding, the three "ignore the rest" rules, strict mode
- [x] RFC 2047 encoded words decoded inside comments
- [x] Safe builder: URI check, header folding, sender headers for one-click
- [x] One-click: exact post value, the POST request (urlencoded and multipart)
- [x] mailto: parse and build per RFC 6068, a safe unsubscribe message
- [x] Choose the method a receiver should use; DKIM `h=` coverage check
- [x] Audit a message's headers against RFC 8058 and the Gmail and Yahoo rules
- [x] Command line: read a message, print JSON
- [x] Contracts: pinned sources, README examples, typing, installed wheel
- [x] Docs and packaging: README, CHANGELOG, metadata, sdist contents
- [x] Gates: ruff format, ruff check, mypy --strict, pytest
- [ ] Mutation run: removing guarded logic makes the suite fail
- [ ] Independent review findings fixed with regression tests
- [ ] Pull request opened, guard clean

## Starting point

`0.1.0` gives `parse`, `build`, `mailto_links`, `http_links`, `one_click_post` and
`is_one_click`. Compared with the sources below:

- `parse` takes every `<...>` anywhere in the value. RFC 2369 section 2 says a field that
  does not start with `<` (after whitespace and comments) is ignored, that text after a
  bracketed URI is ignored unless a comma follows, and that a sub-item which is not a
  bracketed URI ends the list. So `garbage, <mailto:a@b.co>` yields a URI where the RFC
  yields none, and a comment such as `(see <https://x>)` is read as a URI.
- Comments are dropped without being read: nested comments and quoted pairs are not
  understood, so a `)` or `<` inside a comment breaks the parse.
- There is no strict mode, so a sender cannot lint what it is about to send.
- `build` only refuses `<`, `>` and line breaks. It accepts spaces, control characters,
  non-ASCII text and strings with no scheme, and it never folds, so a long list breaks the
  RFC 5322 line length limits.
- `is_one_click` removes internal whitespace, so `List-Unsubscribe = One-Click` passes,
  although RFC 8058 section 5 allows only the exact key and value (ABNF strings are case
  insensitive, so case may differ).
- Nothing builds the POST request a receiver sends (RFC 8058 section 3.2), nothing checks
  that one-click is allowed (an HTTPS URI must be present, DKIM must cover both fields),
  and nothing picks which URI to use.
- `mailto:` URIs are returned as raw strings: no percent decoding, no `to` list, no
  header fields, no safe way to turn one into the unsubscribe message.

## Sources (fetched 2026-10-13)

- RFC 2369, https://www.rfc-editor.org/rfc/rfc2369.txt: section 2 (bracketed URLs,
  internal whitespace ignored, left to right preference, the three client rules), section
  3 (at most one of each field), 3.2 examples. Errata page: no errata.
- RFC 8058, https://www.rfc-editor.org/rfc/rfc8058.txt: sender rules (3.1: one HTTPS URI,
  exact post value, DKIM covering both fields, no redirect), receiver rules (3.2:
  multipart/form-data SHOULD, urlencoded MAY, no POST without consent), 4 (no one-click
  without the DKIM signature), 5 (ABNF), 8 (examples). Errata page
  https://www.rfc-editor.org/errata/rfc8058 read: 5559 (verified) fixes the request target
  of example 8.3; 5117 and 8927 (verified 2026-05-28) fix its boundary parameter to
  `-FormBoundaryjWmhtjORrn`; 5558 (rejected) confirms Content-Length 124.
- RFC 6068, https://www.rfc-editor.org/rfc/rfc6068.txt: ABNF (2), encoding rules (2, 5),
  unsafe header fields (3, 4), examples (6). Errata page read: 7919 (verified) drops the
  rule that `&`, `;` and `=` must be encoded inside the address; 4020 (verified, editorial).
- RFC 5322, https://www.rfc-editor.org/rfc/rfc5322.txt: line limits 998 and 78 (2.1.1),
  folding and unfolding (2.2.3), comments, quoted pairs and CFWS (3.2.2).
- RFC 2047, https://www.rfc-editor.org/rfc/rfc2047.txt: encoded words (2, 4), where they
  may appear in structured fields (5: only in comments and phrases, never in a URI), and
  the comment examples of section 8.
- RFC 6376, https://www.rfc-editor.org/rfc/rfc6376.txt: tag-list syntax (3.2) and the
  `h=` tag (3.5), compared case-insensitively; signed example in appendix A.2.
- Google, Email sender guidelines https://support.google.com/a/answer/81126 and FAQ
  https://support.google.com/a/answer/14229414 (read 2026-10-13): bulk senders (5,000 a
  day to personal accounts, status permanent) must offer one-click per RFC 8058 on
  marketing and subscribed mail, a visible body link too, honour requests within 48 hours;
  mailto and plain URL unsubscribe do not meet the one-click requirement.
- Yahoo, Sender best practices https://senders.yahooinc.com/best-practices/ (read
  2026-10-13): a working List-Unsubscribe with one-click for marketing and subscribed mail,
  a visible body link, honour within 2 days.

The six RFC texts are pinned in `tests/upstream/MANIFEST.json` (URL, size, sha256) and
fetched by `scripts/fetch_upstream.py`; they are never committed. The vendor pages change
without notice, so they are cited here and not pinned; nothing is tested against them.

## Ranked improvements

1. **RFC 2369 parser** (correctness, biggest gap). A real CFWS scanner: folding, nested
   comments, quoted pairs. Apply rules 1 to 3 of section 2. Keep the comments (decoded) in
   a typed `ListUnsubscribe` result. `strict=True` raises `ListUnsubscribeError` with an
   offset for anything the rules would ignore, whitespace inside brackets, empty items and
   invalid URIs. `parse` keeps returning the URI list.
2. **One-click done right.** `is_one_click` per the ABNF (case-insensitive, surrounding
   whitespace only). `one_click_request(uri)` returns the exact POST a receiver sends, as
   urlencoded (example 8.1, Content-Length 26) or multipart (example 8.3 with errata,
   Content-Length 124); it refuses non-HTTPS URIs and userinfo (no authorization context).
3. **Choose the method.** `choose(...)` returns one-click when the post value is valid, an
   HTTPS URI exists and the caller has verified a DKIM signature; otherwise the left-most
   supported URI (RFC 2369 preference order). One-click is never chosen by default.
4. **DKIM coverage.** `dkim_covers(signature)` reads the `h=` tag (tag-list grammar, FWS
   around colons, case-insensitive) and reports whether both fields are signed.
5. **Safe builder.** `build` validates each URI against the RFC 3986 character set with a
   scheme, refuses non-ASCII, whitespace and controls, and can fold to 78 columns after
   commas. `sender_headers(https=..., mailto=...)` returns both fields for one-click.
6. **mailto per RFC 6068.** `parse_mailto` (UTF-8 percent decoding, `to` path and hfield,
   case-insensitive names, fragment ignored, `+` kept as plus), `build_mailto` (encodes
   delimiters, spaces as `%20`, CRLF line breaks in the body only), and
   `Mailto.to_message(sender)` that keeps only To, Subject, Keywords and the body and
   refuses line breaks in header values.
7. **Audit.** `audit(list_unsubscribe, post, dkim_signature)` lists problems with stable
   codes: missing field, nothing parsable, no HTTPS URI, invalid post value, post without
   HTTPS, DKIM not covering both fields, duplicate fields.
8. **RFC 2047 in comments.** Decode encoded words in comments (section 5 allows them only
   there in this field), joining adjacent words as section 8 shows.
9. **Command line.** `listunsub [file]` reads a message and prints the parsed URIs,
   comments, the chosen action and the audit as JSON; exit 1 when the audit finds problems.
10. **Contracts and packaging.** Tests against the fetched RFC texts, README examples run,
    typing test, installed-wheel e2e, sdist excludes the fetched files, CHANGELOG 0.2.0.

Out of scope: sending mail or HTTP requests, verifying DKIM signatures (needs DNS and
crypto), List-Help and the other RFC 2369 fields.
