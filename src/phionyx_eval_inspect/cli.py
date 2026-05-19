"""Command-line entry point for phionyx-eval-inspect.

Subcommands
-----------

``convert``
    Convert a Phionyx envelope chain (filesystem directory) into an
    Inspect AI ``.eval`` log file.

``show``
    Pretty-print the converted log to stdout (no file write).

Usage
-----

::

    phionyx-eval-inspect convert \\
        --trace trace-abc-001 \\
        --task phionyx_governed_replay \\
        --audit-root ~/.phionyx/mcp_audit \\
        --logs-dir ./logs

    phionyx-eval-inspect show \\
        --trace trace-abc-001 \\
        --audit-root ~/.phionyx/mcp_audit
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .adapter import (
    envelope_chain_from_directory,
    envelope_chain_to_inspect_log,
    write_log,
)


def _default_audit_root() -> Path:
    return Path(
        os.environ.get("PHIONYX_MCP_AUDIT_ROOT", "~/.phionyx/mcp_audit")
    ).expanduser()


def cmd_convert(args: argparse.Namespace) -> int:
    audit_root = Path(args.audit_root).expanduser()
    try:
        envelopes = envelope_chain_from_directory(audit_root, args.trace)
    except FileNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    log = envelope_chain_to_inspect_log(
        envelopes,
        task_name=args.task,
        run_id=args.trace,
        schema_version=args.schema_version,
    )
    target = write_log(log, logs_dir=Path(args.logs_dir).expanduser())
    print(f"Wrote {len(envelopes)} envelopes → {target}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    audit_root = Path(args.audit_root).expanduser()
    try:
        envelopes = envelope_chain_from_directory(audit_root, args.trace)
    except FileNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2

    log = envelope_chain_to_inspect_log(
        envelopes,
        task_name=args.task,
        run_id=args.trace,
        schema_version=args.schema_version,
    )
    print(json.dumps(log, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phionyx-eval-inspect",
        description="Bridge Phionyx envelope chains into Inspect AI log format.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--trace", required=True, help="Phionyx trace_id (envelope chain identifier)."
    )
    common.add_argument(
        "--task",
        default="phionyx_governed_replay",
        help="Inspect task name (default: phionyx_governed_replay).",
    )
    common.add_argument(
        "--audit-root",
        default=str(_default_audit_root()),
        help="Phionyx audit root (default: $PHIONYX_MCP_AUDIT_ROOT or ~/.phionyx/mcp_audit).",
    )
    common.add_argument(
        "--schema-version",
        default=None,
        help="Pinned Inspect log schema version (default: v0.3.x).",
    )

    p_convert = sub.add_parser(
        "convert",
        parents=[common],
        help="Write a .eval log to disk under ./logs/<task>/<trace>.eval.",
    )
    p_convert.add_argument(
        "--logs-dir",
        default="./logs",
        help="Inspect logs directory (default: ./logs).",
    )
    p_convert.set_defaults(func=cmd_convert)

    p_show = sub.add_parser(
        "show",
        parents=[common],
        help="Print the converted log to stdout (no file write).",
    )
    p_show.set_defaults(func=cmd_show)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
