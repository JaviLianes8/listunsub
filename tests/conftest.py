from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

UPSTREAM = Path(__file__).resolve().parent / "upstream"


def read_upstream(name: str) -> str:
    """Return a third-party reference file as text.

    The files are not committed: `python scripts/fetch_upstream.py` fetches them. Their
    tests skip while a file is absent and fail if it differs from the manifest.
    """
    path = UPSTREAM / name
    if not path.is_file():
        pytest.skip(f"{name} is not fetched; run python scripts/fetch_upstream.py")
    entry = json.loads((UPSTREAM / "MANIFEST.json").read_text(encoding="utf-8"))[name]
    body = path.read_bytes()
    assert hashlib.sha256(body).hexdigest() == entry["sha256"], f"{name} differs from MANIFEST"
    return body.decode("utf-8")


@pytest.fixture(scope="session")
def rfc2369() -> str:
    """RFC 2369, see tests/upstream/MANIFEST.json for its source."""
    return read_upstream("rfc2369.txt")


@pytest.fixture(scope="session")
def rfc8058() -> str:
    """RFC 8058, see tests/upstream/MANIFEST.json for its source."""
    return read_upstream("rfc8058.txt")


@pytest.fixture(scope="session")
def rfc6068() -> str:
    """RFC 6068, see tests/upstream/MANIFEST.json for its source."""
    return read_upstream("rfc6068.txt")


@pytest.fixture(scope="session")
def rfc5322() -> str:
    """RFC 5322, see tests/upstream/MANIFEST.json for its source."""
    return read_upstream("rfc5322.txt")


@pytest.fixture(scope="session")
def rfc2047() -> str:
    """RFC 2047, see tests/upstream/MANIFEST.json for its source."""
    return read_upstream("rfc2047.txt")


@pytest.fixture(scope="session")
def rfc6376() -> str:
    """RFC 6376, see tests/upstream/MANIFEST.json for its source."""
    return read_upstream("rfc6376.txt")


def section(text: str, title: str, end: str) -> str:
    """The body of an RFC section: its last heading (the first is in the contents) to ``end``.

    The page footers and headers that interrupt the text are removed.
    """
    body = text.rsplit(title, 1)[1].split(end, 1)[0]
    return re.sub(r"\n+[^\n]*\[Page \d+\]\n\x0c?\n*RFC \d+ [^\n]*\n+", "\n\n", body)
