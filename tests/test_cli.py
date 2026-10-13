from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

from listunsub._cli import main, report

MESSAGE = (
    b"From: news@a.test\r\n"
    b"DKIM-Signature: v=1; d=a.test; s=s;\r\n"
    b"\th=from:list-unsubscribe:list-unsubscribe-post; b=x\r\n"
    b"List-Unsubscribe: (=?UTF-8?Q?d=C3=A9sabonner?=)\r\n"
    b" <mailto:u@a.test?subject=unsubscribe>,\r\n <https://a.test/u/opaque>\r\n"
    b"List-Unsubscribe-Post: List-Unsubscribe=One-Click\r\n"
    b"Subject: hi\r\n\r\nbody\r\n"
)


def test_report_summarises_the_message() -> None:
    assert report(MESSAGE) == {
        "uris": ["mailto:u@a.test?subject=unsubscribe", "https://a.test/u/opaque"],
        "comments": ["désabonner"],
        "one_click": True,
        "actions": [
            {"kind": "mailto", "uri": "mailto:u@a.test?subject=unsubscribe"},
            {"kind": "web", "uri": "https://a.test/u/opaque"},
        ],
        "problems": [],
    }
    first = report(MESSAGE, dkim_verified=True)["actions"]
    assert first[0] == {"kind": "one-click", "uri": "https://a.test/u/opaque"}  # type: ignore[index]


def test_report_on_a_message_without_the_fields() -> None:
    result = report(b"From: a@b.test\r\n\r\nhello\r\n")
    assert result["uris"] == [] and result["actions"] == [] and result["one_click"] is False
    codes = [problem["code"] for problem in result["problems"]]  # type: ignore[attr-defined]
    assert codes == ["missing-list-unsubscribe", "missing-post", "missing-dkim"]


def test_main_reads_a_file_and_exits_zero_when_clean(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "message.eml"
    path.write_bytes(MESSAGE)
    assert main([str(path), "--dkim-verified"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["actions"][0]["kind"] == "one-click"
    assert printed["comments"] == ["désabonner"]


def test_main_reads_standard_input_and_exits_one_on_problems(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stdin = io.TextIOWrapper(io.BytesIO(b"List-Unsubscribe: <http://a.test/u>\r\n\r\n"))
    monkeypatch.setattr(sys, "stdin", stdin)
    assert main([]) == 1
    printed = json.loads(capsys.readouterr().out)
    assert [p["code"] for p in printed["problems"]] == ["no-https", "missing-post", "missing-dkim"]


def test_main_exits_two_on_an_unreadable_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(tmp_path / "missing.eml")]) == 2
    assert capsys.readouterr().err.startswith("listunsub: ")
