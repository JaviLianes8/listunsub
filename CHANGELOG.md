# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

- Parse a List-Unsubscribe header value into its URIs (RFC 2369), tolerant of
  folding whitespace and malformed entries.
- Build a List-Unsubscribe header value from a list of URIs.
- Classify URIs into mailto and http links.
- Produce and recognise the one-click List-Unsubscribe-Post value (RFC 8058).
