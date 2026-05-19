"""RGE envelope chain → Inspect AI ``.eval`` log adapter.

Public surface
--------------

::

    from phionyx_eval_inspect import envelope_chain_to_inspect_log

    log = envelope_chain_to_inspect_log(
        envelopes,
        task_name="phionyx_governed_replay",
        run_id="trace-abc-001",
    )
    # ``log`` is a dict matching the Inspect ``.eval`` JSON shape; write
    # it to disk under ``./logs/<task_name>/<run_id>.eval``.

The adapter is **read-only over the envelope chain**. It never modifies
the input, and it never tries to "score" the run — scoring stays in
Inspect's own solver/scorer chain. We surface the governance evidence
under ``sample.metadata.phionyx`` so external tooling can read it
without changing Inspect's data model.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable

from . import __version__

# ─── Schema resolver ─────────────────────────────────────────────────

ENV_SCHEMA_VERSION = "PHIONYX_INSPECT_LOG_SCHEMA_VERSION"
DEFAULT_SCHEMA_VERSION = "v0.3.x"


def _resolve_schema_module(version: str | None = None) -> ModuleType:
    """Return the pinned log-schema module for ``version``."""
    requested = version or os.environ.get(ENV_SCHEMA_VERSION, DEFAULT_SCHEMA_VERSION)
    if requested == "v0.3.x":
        from . import log_schema_v0_3 as mod

        return mod
    raise ValueError(
        f"phionyx-eval-inspect does not yet support Inspect log schema {requested!r}. "
        f"Supported: v0.3.x. To add a new pinned version, drop log_schema_v0_<minor>.py "
        f"alongside adapter.py and extend _resolve_schema_module. See "
        f"docs/conventions/inspect_log_schema_bump_policy.md in the umbrella repo."
    )


# ─── Conversion ──────────────────────────────────────────────────────


def _envelope_to_sample(envelope: dict[str, Any], schema_mod: ModuleType) -> dict[str, Any]:
    """Map one RGE envelope to one Inspect sample entry."""
    subject = envelope.get("subject", {}) or {}
    reasoning = envelope.get("reasoning", {}) or {}
    output = envelope.get("output", {}) or {}
    input_block = envelope.get("input", {}) or {}
    integrity = envelope.get("integrity", {}) or {}
    path = envelope.get("path", []) or []
    mcp = envelope.get("mcp_tool_audit")

    # Inspect "input" is the user-visible prompt for the sample.
    sample_input = input_block.get("user_text") or ""

    # Inspect "output" carries model completion text + completion fields.
    output_text = output.get("text") if isinstance(output, dict) else None

    # One event per pipeline block step + an MCP tool-call event when present.
    events: list[dict[str, Any]] = []
    for step in path:
        events.append(
            {
                schema_mod.FIELD_EVENT_TYPE: "info",
                schema_mod.FIELD_EVENT_TIMESTAMP: subject.get(
                    "timestamp_utc", _now_utc_iso()
                ),
                schema_mod.FIELD_EVENT_DATA: {
                    "event_name": schema_mod.PHIONYX_EVENT_PIPELINE_BLOCK,
                    "block": step.get("block"),
                    "disposition": step.get("disposition"),
                    "reason": step.get("reason"),
                },
            }
        )

    if isinstance(mcp, dict):
        events.append(
            {
                schema_mod.FIELD_EVENT_TYPE: "tool",
                schema_mod.FIELD_EVENT_TIMESTAMP: subject.get(
                    "timestamp_utc", _now_utc_iso()
                ),
                schema_mod.FIELD_EVENT_DATA: {
                    "event_name": schema_mod.PHIONYX_EVENT_MCP_TOOL_CALL,
                    "tool_descriptor_hash": mcp.get("tool_descriptor_hash"),
                    "descriptor_change_detected": mcp.get("descriptor_change_detected"),
                    "tool_permission_scope": mcp.get("tool_permission_scope"),
                    "tool_call_io_hash": mcp.get("tool_call_io_hash"),
                    "user_approval_state": mcp.get("user_approval_state"),
                    "runtime_anomaly_flag": mcp.get("runtime_anomaly_flag"),
                },
            }
        )

    # Phionyx-specific evidence is namespaced under metadata.phionyx so
    # native Inspect tools don't trip over unfamiliar top-level keys.
    phionyx_metadata = {
        "trace_id": subject.get("trace_id"),
        "turn_index": subject.get("turn_index"),
        "envelope_schema": envelope.get("schema"),
        "runtime": subject.get("runtime"),
        "version": subject.get("version"),
        "decision": reasoning.get("runtime_decision"),
        "decision_reason": reasoning.get("decision_reason"),
        "policy_basis": reasoning.get("runtime_policy_basis"),
        "path": [
            {
                "block": step.get("block"),
                "disposition": step.get("disposition"),
            }
            for step in path
        ],
        "integrity": {
            "previous": integrity.get("previous"),
            "current": integrity.get("current"),
            "signature": integrity.get("signature"),
        },
        "mcp_tool_audit": mcp if isinstance(mcp, dict) else None,
    }
    # Strip None values for cleaner JSON.
    phionyx_metadata = _strip_none(phionyx_metadata)

    sample: dict[str, Any] = {
        schema_mod.FIELD_SAMPLE_ID: subject.get("turn_index", 0),
        schema_mod.FIELD_SAMPLE_EPOCH: 1,
        schema_mod.FIELD_SAMPLE_INPUT: sample_input,
        schema_mod.FIELD_SAMPLE_OUTPUT: {"completion": output_text} if output_text else None,
        schema_mod.FIELD_SAMPLE_EVENTS: events,
        schema_mod.FIELD_SAMPLE_METADATA: {schema_mod.METADATA_PHIONYX_KEY: phionyx_metadata},
    }
    return _strip_none(sample)


def envelope_chain_to_inspect_log(
    envelopes: Iterable[dict[str, Any]],
    *,
    task_name: str,
    run_id: str,
    schema_version: str | None = None,
    model: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a single Inspect ``.eval`` log dict from a chain of envelopes.

    Args:
        envelopes: Ordered iterable of RGE envelope dicts (v0.1 or v0.2).
        task_name: Inspect task name (e.g. ``"phionyx_governed_replay"``).
        run_id: Inspect run identifier — typically the Phionyx trace_id.
        schema_version: Optional override for the pinned schema. Default
            uses ``PHIONYX_INSPECT_LOG_SCHEMA_VERSION`` env or ``v0.3.x``.
        model: Optional model identifier to surface as Inspect's
            ``eval.model``. Defaults to the first envelope's subject.producer.
        extra_metadata: Optional dict merged into ``eval.metadata``.

    Returns:
        A dict matching the Inspect ``.eval`` log shape. Use ``write_log``
        to persist it under ``./logs/<task_name>/<run_id>.eval``.
    """
    schema_mod = _resolve_schema_module(schema_version)
    envelope_list = list(envelopes)

    # Resolve model
    if not model and envelope_list:
        model = envelope_list[0].get("subject", {}).get("producer")

    # Build samples
    samples = [_envelope_to_sample(e, schema_mod) for e in envelope_list]

    # Eval config block
    eval_block: dict[str, Any] = {
        schema_mod.FIELD_EVAL_TASK: task_name,
        schema_mod.FIELD_EVAL_TASK_ID: task_name,
        schema_mod.FIELD_EVAL_RUN_ID: run_id,
        schema_mod.FIELD_EVAL_CREATED: _now_utc_iso(),
        schema_mod.FIELD_EVAL_MODEL: model,
        schema_mod.FIELD_EVAL_METADATA: _strip_none(
            {
                "phionyx_adapter_version": __version__,
                "phionyx_inspect_log_schema": schema_mod.SCHEMA_VERSION,
                "envelope_count": len(envelope_list),
                **(extra_metadata or {}),
            }
        ),
        schema_mod.FIELD_EVAL_PACKAGES: {
            "phionyx-eval-inspect": __version__,
        },
    }

    log: dict[str, Any] = {
        schema_mod.FIELD_VERSION: schema_mod.DEFAULT_LOG_FORMAT_VERSION,
        schema_mod.FIELD_STATUS: "success" if envelope_list else "started",
        schema_mod.FIELD_EVAL: eval_block,
        schema_mod.FIELD_SAMPLES: samples,
    }
    return _strip_none(log)


# ─── Persistence helpers ─────────────────────────────────────────────


def write_log(
    log: dict[str, Any],
    *,
    logs_dir: Path | str = "./logs",
    task_name: str | None = None,
    run_id: str | None = None,
) -> Path:
    """Persist an Inspect log dict to ``<logs_dir>/<task_name>/<run_id>.eval``.

    ``task_name`` and ``run_id`` default to the values inside the log's
    eval block. Raises if both the args and the log lack the values.
    """
    schema_mod = _resolve_schema_module()
    eval_block = log.get(schema_mod.FIELD_EVAL, {}) or {}
    task_name = task_name or eval_block.get(schema_mod.FIELD_EVAL_TASK)
    run_id = run_id or eval_block.get(schema_mod.FIELD_EVAL_RUN_ID)
    if not task_name or not run_id:
        raise ValueError(
            "write_log requires task_name + run_id (either as args or "
            "inside log['eval']). Got task_name=%r, run_id=%r." % (task_name, run_id)
        )

    target_dir = Path(logs_dir) / task_name
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_run_id = run_id.replace("/", "_").replace("..", "__")
    target = target_dir / f"{safe_run_id}.eval"
    target.write_text(json.dumps(log, indent=2, sort_keys=True), encoding="utf-8")
    return target


def envelope_chain_from_directory(audit_root: Path | str, trace_id: str) -> list[dict[str, Any]]:
    """Load all envelopes for ``trace_id`` from a Phionyx audit directory.

    Mirrors the layout the ``phionyx-mcp-server`` package writes:
    ``<audit_root>/<trace_id>/<turn:06d>.json``.
    """
    audit_path = Path(audit_root) / trace_id
    if not audit_path.exists():
        raise FileNotFoundError(f"No envelope chain found at {audit_path}")
    envelope_files = sorted(audit_path.glob("[0-9]*.json"))
    envelopes: list[dict[str, Any]] = []
    for f in envelope_files:
        envelopes.append(json.loads(f.read_text(encoding="utf-8")))
    return envelopes


# ─── Utilities ───────────────────────────────────────────────────────


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_none(value: Any) -> Any:
    """Recursively drop None values from dicts; leave lists/tuples intact."""
    if isinstance(value, dict):
        return {k: _strip_none(v) for k, v in value.items() if v is not None}
    if isinstance(value, list):
        return [_strip_none(v) for v in value]
    return value


__all__ = [
    "ENV_SCHEMA_VERSION",
    "DEFAULT_SCHEMA_VERSION",
    "envelope_chain_to_inspect_log",
    "envelope_chain_from_directory",
    "write_log",
]
