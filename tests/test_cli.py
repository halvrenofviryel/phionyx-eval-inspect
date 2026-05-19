"""CLI smoke tests for phionyx-eval-inspect."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from phionyx_eval_inspect.cli import main


def _envelope(turn: int) -> dict[str, Any]:
    return {
        "schema": "phionyx.governed_response_envelope.v0_2",
        "subject": {
            "runtime": "phionyx-core",
            "version": "0.4.0",
            "producer": "claude-opus-4-7",
            "turn_index": turn,
            "timestamp_utc": "2026-05-19T22:00:00+00:00",
            "trace_id": "trace-cli-001",
        },
        "input": {"user_text": f"prompt {turn}"},
        "path": [{"block": "input_safety_gate", "disposition": "admit"}],
        "output": {"redacted": False, "text": f"response {turn}"},
        "metrics": {},
        "integrity": {
            "previous": "sha256:" + "0" * 64,
            "current": "sha256:" + f"{turn}" * 64,
            "signature": "demo-hmac:dead",
            "canonical_json": True,
        },
    }


def _seed_audit(audit_root: Path, trace_id: str, count: int) -> None:
    trace_dir = audit_root / trace_id
    trace_dir.mkdir(parents=True)
    for turn in range(1, count + 1):
        (trace_dir / f"{turn:06d}.json").write_text(json.dumps(_envelope(turn)))


def test_cli_convert_writes_eval_file(tmp_path, capsys):
    audit_root = tmp_path / "audit"
    logs_dir = tmp_path / "logs"
    _seed_audit(audit_root, "trace-cli-001", 3)

    exit_code = main(
        [
            "convert",
            "--trace",
            "trace-cli-001",
            "--task",
            "smoke_task",
            "--audit-root",
            str(audit_root),
            "--logs-dir",
            str(logs_dir),
        ]
    )
    assert exit_code == 0

    captured = capsys.readouterr()
    assert "3 envelopes" in captured.out

    target = logs_dir / "smoke_task" / "trace-cli-001.eval"
    assert target.exists()


def test_cli_show_prints_json(tmp_path, capsys):
    audit_root = tmp_path / "audit"
    _seed_audit(audit_root, "trace-cli-002", 1)

    exit_code = main(
        [
            "show",
            "--trace",
            "trace-cli-002",
            "--audit-root",
            str(audit_root),
        ]
    )
    assert exit_code == 0

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["eval"]["run_id"] == "trace-cli-002"


def test_cli_convert_missing_trace_returns_2(tmp_path, capsys):
    audit_root = tmp_path / "audit"
    audit_root.mkdir()

    exit_code = main(
        [
            "convert",
            "--trace",
            "trace-does-not-exist",
            "--audit-root",
            str(audit_root),
            "--logs-dir",
            str(tmp_path / "logs"),
        ]
    )
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "No envelope chain found" in captured.err


def test_cli_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
