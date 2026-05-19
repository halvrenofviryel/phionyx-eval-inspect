"""Worked example: build an envelope chain in memory + emit one Inspect .eval log.

Useful as a quick smoke test of the adapter without needing the live
phionyx-mcp-server or inspect-ai installations. Run it with:

    python examples/governed_run_to_inspect_log.py

The resulting log is written under ``./logs/phionyx_governed_replay/example.eval``
and can be opened with ``inspect view`` if Inspect AI is installed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from phionyx_eval_inspect import (
    envelope_chain_to_inspect_log,
    write_log,
)


def _envelope(turn: int) -> dict:
    return {
        "schema": "phionyx.governed_response_envelope.v0_2",
        "subject": {
            "runtime": "phionyx-core",
            "version": "0.4.0",
            "producer": "claude-opus-4-7",
            "turn_index": turn,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "trace_id": "example",
        },
        "input": {"user_text": f"example prompt {turn}"},
        "path": [
            {"block": "input_safety_gate", "disposition": "admit"},
            {"block": "mcp_tool_descriptor_verify", "disposition": "admit"},
            {"block": "audit_layer", "disposition": "record"},
        ],
        "output": {"redacted": False, "text": f"example completion {turn}"},
        "metrics": {"phi_total": 0.6},
        "reasoning": {
            "runtime_decision": "release",
            "decision_reason": "no policy violation",
            "runtime_policy_basis": ["input_safety_gate"],
        },
        "mcp_tool_audit": {
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
            "signed_envelope_ref": None,
        },
        "integrity": {
            "previous": "sha256:" + "0" * 64,
            "current": "sha256:" + f"{turn}" * 64,
            "signature": "demo-hmac:dead",
            "canonical_json": True,
        },
    }


def main() -> int:
    envelopes = [_envelope(i) for i in range(1, 4)]
    log = envelope_chain_to_inspect_log(
        envelopes,
        task_name="phionyx_governed_replay",
        run_id="example",
    )
    target = write_log(log, logs_dir="./logs")
    print(f"Wrote example log: {target.resolve()}")
    print("If you have Inspect AI installed, open it with:")
    print(f"    inspect view {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
