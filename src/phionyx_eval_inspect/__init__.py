"""Phionyx ↔ Inspect AI interoperability bridge.

This companion package exports Phionyx governance evidence (Reasoned
Governance Envelopes) into Inspect AI's evaluation log format so that
Phionyx-governed runs become natively inspectable via ``inspect view``
and other Inspect-aware tooling.

Scope
-----

- **Adapter:** RGE envelope chain (v0.1 / v0.2) → Inspect AI ``.eval``
  log entries with Phionyx-specific evidence carried under
  ``sample.metadata.phionyx``.
- **CLI:** ``phionyx-eval-inspect convert`` — read an envelope chain
  directory, emit a single ``.eval`` log under ``./logs/<task>/<run-id>``.
- **Pinned schema:** the adapter is pinned to inspect-ai v0.3.x log
  format. Newer schemas can be supported by adding a sibling
  ``log_schema_v0_<minor>.py`` module and extending the resolver.

Framing
-------

This is an **interoperability bridge**. It exports runtime governance
evidence into evaluation workflows. It is **not** an endorsement by, or
partnership with, UK AISI, US CAISI, EU AI Office, Japan AISI, or
Korea AISI — although Inspect AI is the framework those organisations
have converged on for frontier-model evaluations.

See README.md for the wiring doc covering how to register the
companion package ``phionyx-mcp-server`` as a tool inside an Inspect AI
eval task.
"""
from __future__ import annotations

__version__ = "0.1.0-dev"

from .adapter import (
    DEFAULT_SCHEMA_VERSION,
    ENV_SCHEMA_VERSION,
    envelope_chain_from_directory,
    envelope_chain_to_inspect_log,
    write_log,
)

__all__ = [
    "__version__",
    "DEFAULT_SCHEMA_VERSION",
    "ENV_SCHEMA_VERSION",
    "envelope_chain_from_directory",
    "envelope_chain_to_inspect_log",
    "write_log",
]
