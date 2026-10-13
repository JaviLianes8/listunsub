"""Build the wheel, install it in a throwaway venv and drive the installed package.

Slow and needs the build backend, so it runs only with LISTUNSUB_E2E=1.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import venv
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("LISTUNSUB_E2E") != "1", reason="set LISTUNSUB_E2E=1 to build and install"
)

PROGRAM = r"""
import importlib.metadata, importlib.resources
import listunsub
from listunsub import (
    Action, ListUnsubscribeError, actions, audit, build, build_mailto, choose, dkim_covers,
    header_line, is_one_click, one_click_request, parse, parse_header, parse_mailto,
    sender_headers,
)

assert "site-packages" in listunsub.__file__, listunsub.__file__
assert importlib.metadata.version("listunsub") == listunsub.__version__
assert importlib.resources.files("listunsub").joinpath("py.typed").is_file()

field = "(=?UTF-8?Q?d=C3=A9sabonner?=)\r\n <mailto:u@a.test?subject=x>,\r\n <https://a.test/u>"
header = parse_header(field, strict=True)
assert header.uris == ("mailto:u@a.test?subject=x", "https://a.test/u")
assert header.comments == ("désabonner",)
assert parse("junk, <https://a.test/u>") == []
post = "List-Unsubscribe=One-Click"
assert choose(field, post, dkim_verified=True) == Action("one-click", "https://a.test/u")
assert [a.kind for a in actions(field, post)] == ["mailto", "web"]
request = one_click_request("https://a.test/u", boundary="b")
assert request.headers["Content-Length"] == str(len(request.body)) and is_one_click(post)
fields = sender_headers("https://a.test/u", "mailto:u@a.test")
assert audit(fields["List-Unsubscribe"], fields["List-Unsubscribe-Post"]) == []
assert dkim_covers("h=list-unsubscribe:list-unsubscribe-post")
uri = build_mailto("u@a.test", subject="café")
assert parse_mailto(uri, strict=True).subject == "café"
assert header_line("X", "a b", width=4) == "X: a\r\n b"
for call in (
    lambda: build(["https://a.test/u>, <https://evil.test/"]),
    lambda: header_line("X", "a\r\nBcc: e@x.test"),
    lambda: one_click_request("http://a.test/u"),
    lambda: parse("<a:b> junk", strict=True),
    lambda: parse_mailto("mailto:a@x.test?subject=x%0ABcc:e").to_message("me@y.test"),
):
    try:
        call()
    except ListUnsubscribeError as error:
        assert isinstance(error, ValueError)
    else:
        raise AssertionError("expected ListUnsubscribeError")
print("e2e ok")
"""

MESSAGE = (
    b"DKIM-Signature: v=1; d=a.test; h=from:list-unsubscribe:list-unsubscribe-post; b=x\r\n"
    b"List-Unsubscribe: <https://a.test/u>\r\n"
    b"List-Unsubscribe-Post: List-Unsubscribe=One-Click\r\n\r\n"
)


def _run(
    *cmd: str | Path, cwd: Path | None = None, stdin: bytes = b""
) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(c) for c in cmd], cwd=cwd, input=stdin, capture_output=True, check=False
    )


def test_installed_wheel_end_to_end(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    built = _run(sys.executable, "-m", "build", "--outdir", dist, ROOT)
    assert built.returncode == 0, built.stderr
    (wheel,) = dist.glob("listunsub-*.whl")
    (sdist,) = dist.glob("listunsub-*.tar.gz")
    names = zipfile.ZipFile(wheel).namelist()
    assert "listunsub/py.typed" in names and "listunsub/__main__.py" in names
    assert not any(name.startswith(("tests/", "scripts/")) for name in names)
    entry_points = next(name for name in names if name.endswith("entry_points.txt"))
    text = zipfile.ZipFile(wheel).read(entry_points).decode()
    assert "listunsub = listunsub._cli:main" in text
    listing = _run(sys.executable, "-m", "tarfile", "-l", sdist).stdout.decode()
    assert "IMPROVEMENTS-round" not in listing and ".github" not in listing
    assert "tests/upstream/MANIFEST.json" in listing
    for number in ("2369", "8058", "6068", "5322", "2047", "6376"):
        assert f"rfc{number}.txt" not in listing, number
    assert "tests/test_sources_lists.py" in listing and "scripts/fetch_upstream.py" in listing

    env_dir = tmp_path / "venv"
    venv.create(env_dir, with_pip=True)
    bindir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
    python = bindir / "python"
    installed = _run(python, "-m", "pip", "install", "-q", wheel)
    assert installed.returncode == 0, installed.stderr

    # Run from an empty folder so the source tree cannot shadow the install.
    work = tmp_path / "work"
    work.mkdir()
    result = _run(python, "-I", "-c", PROGRAM, cwd=work)
    assert result.returncode == 0, result.stderr
    assert result.stdout.decode().strip() == "e2e ok"

    script = bindir / ("listunsub.exe" if sys.platform == "win32" else "listunsub")
    commands: list[list[str | Path]] = [[script], [python, "-m", "listunsub"]]
    for command in commands:
        shown = _run(*command, "--dkim-verified", cwd=work, stdin=MESSAGE)
        assert shown.returncode == 0, shown.stderr
        report = json.loads(shown.stdout)
        assert report["actions"][0] == {"kind": "one-click", "uri": "https://a.test/u"}
        assert report["problems"] == []
    failed = _run(script, cwd=work, stdin=b"List-Unsubscribe: <http://a.test/u>\r\n\r\n")
    assert failed.returncode == 1
    codes = [problem["code"] for problem in json.loads(failed.stdout)["problems"]]
    assert codes == ["no-https", "missing-post", "missing-dkim"]
    missing = _run(script, str(work / "absent.eml"), cwd=work)
    assert missing.returncode == 2 and missing.stderr.startswith(b"listunsub: ")
