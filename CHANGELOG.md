# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0]

### Changed

- `parse` follows the client rules of RFC 2369 section 2: a field that does not start
  with `<` is ignored, text after a URI ends the list unless a comma follows, and a
  sub-item that is not a bracketed URI ends the list. Comments (nested, with quoted
  pairs) are understood, so a `<` inside one is no longer read as a URI.
- `build` validates each URI (scheme, RFC 3986 characters) and raises
  `ListUnsubscribeError` for an empty list or a bad URI instead of stripping or dropping.
- `is_one_click` accepts the exact RFC 8058 value in any case with surrounding white
  space only; white space inside the value no longer matches.
- `mailto_links` and `http_links` compare schemes case-insensitively.

### Added

- `parse_header` returning `ListUnsubscribe` (URIs, decoded comments, `ignored`, scheme
  filters) and `strict=True` on both parsers, raising `ListUnsubscribeError` with an
  offset.
- RFC 2047 encoded words decoded inside comments.
- `header_line` folds a field to 78 columns and refuses the 998-character hard limit,
  bad names and control characters; `sender_headers` returns both one-click fields.
- `one_click_request` builds the RFC 8058 POST, multipart or urlencoded.
- `actions` and `choose` pick how to unsubscribe; one-click only with a verified DKIM
  signature.
- `signed_headers` and `dkim_covers` read the DKIM `h=` tag.
- `parse_mailto`, `build_mailto` and `Mailto.to_message` for RFC 6068 URIs.
- `audit` lists problems against RFC 2369, RFC 8058 and the bulk sender rules.
- The `listunsub` command and `python -m listunsub`.
- Tests against the RFC texts, fetched on demand by `scripts/fetch_upstream.py`.

### Security

- Control characters, line separators and bidi overrides are replaced in decoded
  comments; only real MIME charsets are decoded in encoded words.
- `to_message` and `build_mailto` refuse controls and stray white space in addresses
  and header values; strict `mailto:` parsing checks decoded addresses.
- `one_click_request` and `choose` turn a bad authority into `ListUnsubscribeError`.

## [0.1.0]

- Parse a List-Unsubscribe header value into its URIs (RFC 2369), tolerant of
  folding whitespace and malformed entries.
- Build a List-Unsubscribe header value from a list of URIs.
- Classify URIs into mailto and http links.
- Produce and recognise the one-click List-Unsubscribe-Post value (RFC 8058).
