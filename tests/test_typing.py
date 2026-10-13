"""The public API is typed: mypy infers the documented types and rejects wrong ones."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"

SNIPPET = """
from listunsub import actions, audit, build, build_mailto, choose, dkim_covers, header_line
from listunsub import one_click_request, parse, parse_header, parse_mailto, sender_headers
reveal_type(parse("<a:b>"))
reveal_type(parse_header("<a:b>").uris)
reveal_type(build(["a:b"]))
reveal_type(header_line("X", "y"))
reveal_type(sender_headers("https://a.test/u"))
reveal_type(one_click_request("https://a.test/u").headers)
reveal_type(choose("<a:b>"))
reveal_type(actions("<a:b>"))
reveal_type(parse_mailto("mailto:a@b.co").subject)
reveal_type(build_mailto("a@b.co"))
reveal_type(audit(None))
reveal_type(dkim_covers("h=a"))
parse(b"<a:b>")
parse("<a:b>", True)
choose("<a:b>", schemes=["ftp"])
one_click_request("https://a.test/u", form="json")
build_mailto(1)
"""


@pytest.fixture(scope="module")
def mypy_output(tmp_path_factory: pytest.TempPathFactory) -> str:
    folder = tmp_path_factory.mktemp("typing")
    target = folder / "snippet.py"
    target.write_text(SNIPPET, encoding="utf-8")
    config = folder / "mypy.ini"
    config.write_text(f"[mypy]\nmypy_path = {SRC.as_posix()}\n", encoding="utf-8")
    cache = str(folder / "cache")
    args = ["--strict", "--config-file", str(config), "--cache-dir", cache, str(target)]
    try:
        from mypy import api
    except ImportError:
        # The interpreter running pytest may lack mypy while the one on PATH has it.
        program = shutil.which("mypy")
        if program is None:
            pytest.skip("mypy is not installed")
        result = subprocess.run([program, *args], capture_output=True, text=True, check=False)
        return result.stdout + result.stderr
    out, err, _ = api.run(args)
    return str(out) + str(err)


def _revealed(output: str, line: int) -> str:
    match = re.search(rf":{line}: note: Revealed type is \"(.+)\"", output)
    assert match is not None, output
    return match.group(1)


def test_functions_return_plain_types(mypy_output: str) -> None:
    assert [_revealed(mypy_output, line) for line in range(4, 16)] == [
        "list[str]",
        "tuple[str, ...]",
        "str",
        "str",
        "dict[str, str]",
        "dict[str, str]",
        "listunsub._choose.Action | None",
        "list[listunsub._choose.Action]",
        "str | None",
        "str",
        "list[listunsub._audit.Problem]",
        "bool",
    ]


def test_misuse_is_rejected(mypy_output: str) -> None:
    errors = re.findall(r":(\d+): error:", mypy_output)
    assert sorted(set(map(int, errors))) == [16, 17, 18, 19, 20]
