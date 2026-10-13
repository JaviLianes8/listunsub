"""Command line: read a message, print its unsubscribe options and problems as JSON."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from email.message import Message
from email.parser import BytesHeaderParser
from email.policy import compat32

from ._audit import audit
from ._choose import actions
from ._header import parse_header
from ._oneclick import is_one_click


def _fields(message: Message, name: str) -> list[str]:
    # compat32 keeps the raw field body, folding and encoded words included.
    return [str(value) for value in message.get_all(name) or []]


def report(raw: bytes, *, dkim_verified: bool = False) -> dict[str, object]:
    """The JSON-ready summary of the unsubscribe fields in a raw message or header block."""
    message = BytesHeaderParser(policy=compat32).parsebytes(raw)
    fields = _fields(message, "List-Unsubscribe")
    posts = _fields(message, "List-Unsubscribe-Post")
    header = parse_header(fields[0]) if fields else None
    post = posts[0] if posts else None
    found = actions(header, post, dkim_verified=dkim_verified) if header else []
    problems = audit(fields, posts, dkim_signatures=_fields(message, "DKIM-Signature"))
    return {
        "uris": list(header.uris) if header else [],
        "comments": list(header.comments) if header else [],
        "one_click": post is not None and is_one_click(post),
        "actions": [{"kind": action.kind, "uri": action.uri} for action in found],
        "problems": [{"code": p.code, "message": p.message} for p in problems],
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line; return 0 when the audit is clean, 1 when not, 2 on bad input."""
    parser = argparse.ArgumentParser(
        prog="listunsub",
        description="Show the List-Unsubscribe options of an email message as JSON.",
    )
    parser.add_argument("file", nargs="?", help="message file (default: standard input)")
    parser.add_argument(
        "--dkim-verified",
        action="store_true",
        help="the message's DKIM signature was verified, so one-click may be offered",
    )
    args = parser.parse_args(argv)
    try:
        if args.file is None:
            raw = sys.stdin.buffer.read()
        else:
            with open(args.file, "rb") as handle:
                raw = handle.read()
    except OSError as error:
        print(f"listunsub: {error}", file=sys.stderr)
        return 2
    result = report(raw, dkim_verified=args.dkim_verified)
    # Write UTF-8 bytes: the console or pipe encoding may not hold every decoded comment.
    sys.stdout.flush()
    sys.stdout.buffer.write(json.dumps(result, indent=2, ensure_ascii=False).encode() + b"\n")
    sys.stdout.buffer.flush()
    return 1 if result["problems"] else 0
