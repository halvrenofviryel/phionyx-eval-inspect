"""Unit tests for phionyx_eval_inspect.adapter.

Coverage:

    - Envelope chain → Inspect log dict shape (top-level fields, eval block)
    - Per-envelope sample entry shape (id, input, events, metadata.phionyx)
    - mcp_tool_audit branch emits both an event AND metadata entry
    - None values are scrubbed from output
    - Version pinning: unsupported schema version raises clearly
    - write_log persists under <logs_dir>/<task>/<run_id>.eval
    - envelope_chain_from_directory loads an audit directory in order
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from phionyx_eval_inspect import __version__ as pkg_version
from phionyx_eval_inspect import log_schema_v0_3 as sem
from phionyx_eval_inspect.adapter import (
    _resolve_schema_module,
    envelope_chain_from_directory,
    envelope_chain_to_inspect_log,
    write_log,
)


# ─── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def minimal_envelope() -> dict[str, Any]:
    return {
        "schema": "phionyx.governed_response_envelope.v0_2",
        "subject": {
            "runtime": "phionyx-core",
            "version": "0.4.0",
            "producer": "claude-opus-4-7",
            "turn_index": 1,
            "timestamp_utc": "2026-05-19T22:00:00+00:00",
            "trace_id": "trace-inspect-001",
        },
        "input": {"user_text": "hello"},
        "path": [
            {"block": "input_safety_gate", "disposition": "admit", "reason": None},
            {"block": "audit_layer", "disposition": "record"},
        ],
        "output": {"redacted": False, "text": "hi"},
        "metrics": {"phi_total": 0.5},
        "integrity": {
            "previous": "sha256:" + "0" * 64,
            "current": "sha256:" + "a" * 64,
            "signature": "demo-hmac:f00ba1",
            "canonical_json": True,
        },
    }


@pytest.fixture
def envelope_with_mcp(minimal_envelope: dict[str, Any]) -> dict[str, Any]:
    minimal_envelope["reasoning"] = {
        "runtime_decision": "release",
        "decision_reason": "no policy violation",
        "runtime_policy_basis": ["input_safety_gate"],
    }
    minimal_envelope["mcp_tool_audit"] = {
        "status": "active",
        "tool_descriptor_hash": "sha256:" + "b" * 64,
        "descriptor_change_detected": False,
        "tool_permission_scope": ["read"],
        "tool_call_io_hash": {
            "input_hash": "sha256:" + "c" * 64,
            "output_hash": "sha256:" + "d" * 64,
        },
        "user_approval_state": {"status": "approved"},
        "runtime_anomaly_flag": {"anomaly": False, "severity": "none"},
    }
    return minimal_envelope


# ─── Top-level log shape ─────────────────────────────────────────────


def test_log_top_level_fields(minimal_envelope):
    log = envelope_chain_to_inspect_log(
        [minimal_envelope], task_name="t", run_id="trace-inspect-001"
    )
    assert log[sem.FIELD_VERSION] == sem.DEFAULT_LOG_FORMAT_VERSION
    assert log[sem.FIELD_STATUS] == "success"
    assert sem.FIELD_EVAL in log
    assert sem.FIELD_SAMPLES in log


def test_log_eval_block_fields(minimal_envelope):
    log = envelope_chain_to_inspect_log(
        [minimal_envelope],
        task_name="my_task",
        run_id="trace-inspect-001",
        extra_metadata={"reviewer": "founder"},
    )
    eval_block = log[sem.FIELD_EVAL]
    assert eval_block[sem.FIELD_EVAL_TASK] == "my_task"
    assert eval_block[sem.FIELD_EVAL_RUN_ID] == "trace-inspect-001"
    assert eval_block[sem.FIELD_EVAL_MODEL] == "claude-opus-4-7"
    md = eval_block[sem.FIELD_EVAL_METADATA]
    assert md["phionyx_adapter_version"] == pkg_version
    assert md["phionyx_inspect_log_schema"] == "v0.3.x"
    assert md["envelope_count"] == 1
    assert md["reviewer"] == "founder"


def test_empty_chain_has_started_status():
    log = envelope_chain_to_inspect_log([], task_name="t", run_id="r")
    assert log[sem.FIELD_STATUS] == "started"
    assert log[sem.FIELD_SAMPLES] == []


# ─── Sample entry shape ──────────────────────────────────────────────


def test_sample_id_is_turn_index(minimal_envelope):
    log = envelope_chain_to_inspect_log(
        [minimal_envelope], task_name="t", run_id="r"
    )
    sample = log[sem.FIELD_SAMPLES][0]
    assert sample[sem.FIELD_SAMPLE_ID] == 1


def test_sample_input_pulled_from_user_text(minimal_envelope):
    log = envelope_chain_to_inspect_log(
        [minimal_envelope], task_name="t", run_id="r"
    )
    sample = log[sem.FIELD_SAMPLES][0]
    assert sample[sem.FIELD_SAMPLE_INPUT] == "hello"


def test_sample_output_pulled_from_output_text(minimal_envelope):
    log = envelope_chain_to_inspect_log(
        [minimal_envelope], task_name="t", run_id="r"
    )
    sample = log[sem.FIELD_SAMPLES][0]
    assert sample[sem.FIELD_SAMPLE_OUTPUT]["completion"] == "hi"


# ─── Events ──────────────────────────────────────────────────────────


def test_one_event_per_path_step(minimal_envelope):
    log = envelope_chain_to_inspect_log(
        [minimal_envelope], task_name="t", run_id="r"
    )
    events = log[sem.FIELD_SAMPLES][0][sem.FIELD_SAMPLE_EVENTS]
    block_events = [e for e in events if e[sem.FIELD_EVENT_DATA]["event_name"] == sem.PHIONYX_EVENT_PIPELINE_BLOCK]
    assert len(block_events) == 2
    assert block_events[0][sem.FIELD_EVENT_DATA]["block"] == "input_safety_gate"
    assert block_events[1][sem.FIELD_EVENT_DATA]["block"] == "audit_layer"


def test_mcp_event_present_when_block_populated(envelope_with_mcp):
    log = envelope_chain_to_inspect_log(
        [envelope_with_mcp], task_name="t", run_id="r"
    )
    events = log[sem.FIELD_SAMPLES][0][sem.FIELD_SAMPLE_EVENTS]
    mcp_events = [
        e for e in events if e[sem.FIELD_EVENT_DATA]["event_name"] == sem.PHIONYX_EVENT_MCP_TOOL_CALL
    ]
    assert len(mcp_events) == 1
    assert mcp_events[0][sem.FIELD_EVENT_TYPE] == "tool"
    assert mcp_events[0][sem.FIELD_EVENT_DATA]["descriptor_change_detected"] is False


def test_no_mcp_event_when_block_absent(minimal_envelope):
    log = envelope_chain_to_inspect_log(
        [minimal_envelope], task_name="t", run_id="r"
    )
    events = log[sem.FIELD_SAMPLES][0][sem.FIELD_SAMPLE_EVENTS]
    mcp_events = [
        e for e in events if e[sem.FIELD_EVENT_DATA].get("event_name") == sem.PHIONYX_EVENT_MCP_TOOL_CALL
    ]
    assert mcp_events == []


# ─── Phionyx metadata namespace ─────────────────────────────────────


def test_phionyx_metadata_carries_envelope_evidence(envelope_with_mcp):
    log = envelope_chain_to_inspect_log(
        [envelope_with_mcp], task_name="t", run_id="r"
    )
    md = log[sem.FIELD_SAMPLES][0][sem.FIELD_SAMPLE_METADATA][
        sem.METADATA_PHIONYX_KEY
    ]
    assert md["trace_id"] == "trace-inspect-001"
    assert md["turn_index"] == 1
    assert md["envelope_schema"] == "phionyx.governed_response_envelope.v0_2"
    assert md["decision"] == "release"
    assert md["policy_basis"] == ["input_safety_gate"]
    assert md["integrity"]["current"] == "sha256:" + "a" * 64
    assert md["mcp_tool_audit"]["descriptor_change_detected"] is False


# ─── None scrubbing ──────────────────────────────────────────────────


def test_none_values_scrubbed(minimal_envelope):
    """The adapter must not leave None entries in the persisted log."""
    log = envelope_chain_to_inspect_log(
        [minimal_envelope], task_name="t", run_id="r"
    )

    def assert_no_none(obj: Any) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert v is not None, f"Found None at key {k!r}"
                assert_no_none(v)
        elif isinstance(obj, list):
            for v in obj:
                assert_no_none(v)

    assert_no_none(log)


# ─── Schema version pinning ──────────────────────────────────────────


def test_unsupported_schema_raises():
    with pytest.raises(ValueError, match="does not yet support Inspect log schema"):
        _resolve_schema_module("v9.9.9")


def test_env_var_overrides_default(monkeypatch):
    monkeypatch.setenv("PHIONYX_INSPECT_LOG_SCHEMA_VERSION", "v9.9.9")
    with pytest.raises(ValueError, match="v9.9.9"):
        _resolve_schema_module()


# ─── write_log persistence ───────────────────────────────────────────


def test_write_log_creates_eval_file(tmp_path, minimal_envelope):
    log = envelope_chain_to_inspect_log(
        [minimal_envelope], task_name="my_task", run_id="trace-write-001"
    )
    target = write_log(log, logs_dir=tmp_path)
    assert target == tmp_path / "my_task" / "trace-write-001.eval"
    assert target.exists()
    persisted = json.loads(target.read_text(encoding="utf-8"))
    assert persisted[sem.FIELD_EVAL][sem.FIELD_EVAL_RUN_ID] == "trace-write-001"


def test_write_log_sanitises_run_id_path_traversal(tmp_path, minimal_envelope):
    log = envelope_chain_to_inspect_log(
        [minimal_envelope],
        task_name="t",
        run_id="../../etc/passwd",
    )
    target = write_log(log, logs_dir=tmp_path)
    assert ".." not in target.name
    # Confirm we stayed inside tmp_path.
    assert target.resolve().is_relative_to(tmp_path.resolve())


def test_write_log_requires_task_and_run_id():
    """When neither args nor log carry them, raise."""
    minimal_log = {sem.FIELD_EVAL: {}}
    with pytest.raises(ValueError, match=r"task_name \+ run_id"):
        write_log(minimal_log, logs_dir=Path("/tmp/will-not-be-created"))


# ─── envelope_chain_from_directory ──────────────────────────────────


def test_envelope_chain_from_directory_loads_in_order(tmp_path, minimal_envelope):
    trace_dir = tmp_path / "trace-load-001"
    trace_dir.mkdir()
    for i in range(1, 4):
        env = dict(minimal_envelope)
        env["subject"] = dict(env["subject"])
        env["subject"]["turn_index"] = i
        (trace_dir / f"{i:06d}.json").write_text(json.dumps(env))

    loaded = envelope_chain_from_directory(tmp_path, "trace-load-001")
    assert len(loaded) == 3
    assert [e["subject"]["turn_index"] for e in loaded] == [1, 2, 3]


def test_envelope_chain_from_directory_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        envelope_chain_from_directory(tmp_path, "trace-does-not-exist")
