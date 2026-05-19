"""Inspect AI log format — frozen at v0.3.x.

This module captures the Inspect AI evaluation log schema as observed in
the **inspect-ai v0.3.x line** (the line UK AISI's public guidance points
to as of 2026-05-19). Inspect AI is **MCP-native** and writes per-run
`.eval` log files under `./logs/<task-name>/<run-id>.eval` — a JSONL-like
format with task config, samples, events, and scores.

Why a frozen module
-------------------

Inspect AI ships under active development. Log entry shapes and field
names can shift between minor releases. Pinning the adapter to a specific
schema version keeps emitted logs predictable for downstream tooling
(``inspect view``, custom dashboards), and lets us bump the schema in a
controlled way per ``docs/conventions/inspect_log_schema_bump_policy.md``.

To support a newer schema, add a sibling module
(``log_schema_v0_4.py``, etc.) and extend the dispatch in
``adapter._resolve_schema_module``. The default pinned version bumps in
phionyx-eval-inspect minor releases.

Verification note
-----------------

The constants below reflect the v0.3.x schema. When you align this
package against a specific inspect-ai release on your machine, please
re-verify the field names + types against ``inspect-ai``'s
``log.schema.json`` (or its Pydantic models) and open a PR if anything
has drifted. The integration is intentionally narrow so drift is small.
"""
from __future__ import annotations

# ─── Identification ──────────────────────────────────────────────────

SCHEMA_VERSION = "v0.3.x"
SOURCE_PROJECT = "https://github.com/UKGovernmentBEIS/inspect_ai"
LAST_REVIEWED = "2026-05-19"

# ─── Top-level log entry fields ──────────────────────────────────────
# Each `.eval` file is a header object followed by a stream of sample +
# event entries. We model the header here and capture the subset of
# fields the adapter populates from a Phionyx envelope chain.

FIELD_VERSION = "version"           # int — log format version
FIELD_STATUS = "status"             # "started" | "success" | "cancelled" | "error"
FIELD_EVAL = "eval"                 # eval config block
FIELD_PLAN = "plan"                 # solver / scorer chain plan
FIELD_RESULTS = "results"           # summary of scorer outputs
FIELD_SAMPLES = "samples"           # array of sample entries
FIELD_LOGGING = "logging"           # logger config
FIELD_ERROR = "error"               # error object if status != success

# ─── Eval config sub-fields ──────────────────────────────────────────

FIELD_EVAL_TASK = "task"
FIELD_EVAL_TASK_ID = "task_id"
FIELD_EVAL_RUN_ID = "run_id"
FIELD_EVAL_CREATED = "created"
FIELD_EVAL_DATASET = "dataset"
FIELD_EVAL_MODEL = "model"
FIELD_EVAL_MODEL_BASE_URL = "model_base_url"
FIELD_EVAL_METADATA = "metadata"
FIELD_EVAL_PACKAGES = "packages"

# ─── Sample-entry sub-fields ─────────────────────────────────────────

FIELD_SAMPLE_ID = "id"
FIELD_SAMPLE_EPOCH = "epoch"
FIELD_SAMPLE_INPUT = "input"
FIELD_SAMPLE_TARGET = "target"
FIELD_SAMPLE_OUTPUT = "output"
FIELD_SAMPLE_MESSAGES = "messages"
FIELD_SAMPLE_EVENTS = "events"
FIELD_SAMPLE_SCORES = "scores"
FIELD_SAMPLE_METADATA = "metadata"

# ─── Event-entry sub-fields ──────────────────────────────────────────

FIELD_EVENT_TYPE = "event"           # "tool" | "model" | "info" | "subtask" | ...
FIELD_EVENT_TIMESTAMP = "timestamp"
FIELD_EVENT_DATA = "data"

# ─── Phionyx-specific extension under sample.metadata ────────────────
# Inspect AI's metadata is free-form. We namespace Phionyx-specific
# fields under "phionyx" so external tools see them, but they don't
# collide with native Inspect fields.

METADATA_PHIONYX_KEY = "phionyx"
METADATA_PHIONYX_FIELDS = (
    "trace_id",
    "turn_index",
    "envelope_schema",
    "runtime",
    "version",
    "decision",
    "decision_reason",
    "policy_basis",
    "path",
    "integrity",
    "mcp_tool_audit",
)

# ─── Default + supported values ──────────────────────────────────────

DEFAULT_LOG_FORMAT_VERSION = 2
"""Inspect AI's `version` field in v0.3.x logs is 2."""

SUPPORTED_STATUSES = ("started", "success", "cancelled", "error")
SUPPORTED_EVENT_TYPES = ("tool", "model", "info", "subtask", "score")

# ─── Event-name conventions (Phionyx side) ──────────────────────────

PHIONYX_EVENT_PIPELINE_BLOCK = "phionyx.pipeline.block"
PHIONYX_EVENT_MCP_TOOL_CALL = "phionyx.mcp.tool_call"

__all__ = [
    "SCHEMA_VERSION",
    "SOURCE_PROJECT",
    "LAST_REVIEWED",
    "FIELD_VERSION",
    "FIELD_STATUS",
    "FIELD_EVAL",
    "FIELD_PLAN",
    "FIELD_RESULTS",
    "FIELD_SAMPLES",
    "FIELD_LOGGING",
    "FIELD_ERROR",
    "FIELD_EVAL_TASK",
    "FIELD_EVAL_TASK_ID",
    "FIELD_EVAL_RUN_ID",
    "FIELD_EVAL_CREATED",
    "FIELD_EVAL_DATASET",
    "FIELD_EVAL_MODEL",
    "FIELD_EVAL_MODEL_BASE_URL",
    "FIELD_EVAL_METADATA",
    "FIELD_EVAL_PACKAGES",
    "FIELD_SAMPLE_ID",
    "FIELD_SAMPLE_EPOCH",
    "FIELD_SAMPLE_INPUT",
    "FIELD_SAMPLE_TARGET",
    "FIELD_SAMPLE_OUTPUT",
    "FIELD_SAMPLE_MESSAGES",
    "FIELD_SAMPLE_EVENTS",
    "FIELD_SAMPLE_SCORES",
    "FIELD_SAMPLE_METADATA",
    "FIELD_EVENT_TYPE",
    "FIELD_EVENT_TIMESTAMP",
    "FIELD_EVENT_DATA",
    "METADATA_PHIONYX_KEY",
    "METADATA_PHIONYX_FIELDS",
    "DEFAULT_LOG_FORMAT_VERSION",
    "SUPPORTED_STATUSES",
    "SUPPORTED_EVENT_TYPES",
    "PHIONYX_EVENT_PIPELINE_BLOCK",
    "PHIONYX_EVENT_MCP_TOOL_CALL",
]
