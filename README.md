# phionyx-eval-inspect

> Interoperability bridge — export Phionyx Reasoned Governance Envelope (RGE) evidence into Inspect AI evaluation logs.

**Where this sits in the stack:** `phionyx-eval-inspect` (v0.1.0) is an **adapter**, not the engine, the gate, or the Standard. It is a read-only bridge that converts the signed evidence chain produced by the Phionyx runtime into Inspect AI's native log format. The three core components it sits alongside are the SDK/engine [`phionyx-core`](https://pypi.org/project/phionyx-core/) (v0.7.2), the self-governance gate [`phionyx-pipeline-mcp`](https://github.com/halvrenofviryel/phionyx-pipeline-mcp) (stable v0.2.0 / alpha v0.3.0a1), and the vendor-neutral [`phionyx-evaluation-standard`](https://github.com/halvrenofviryel/phionyx-evaluation-standard). See [Companion packages](#companion-packages--the-wider-stack) and [Evaluation Standard](#evaluation-standard) below.

[Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) is the open-source frontier-model evaluation framework maintained by UK AISI. Several government AI safety institutes have publicly described using it as a frontier-eval framework; verify the current adoption picture at [`inspect.aisi.org.uk`](https://inspect.aisi.org.uk) before citing specifics.

This package is **not an endorsement by or partnership with** any of those organisations. It is a **read-only interoperability adapter** that lets Phionyx-governed runs become natively inspectable in Inspect AI's tooling.

## What this package does

Two complementary bridges:

1. **Storage adapter:** convert a Phionyx RGE envelope chain (the per-turn signed evidence records the [`phionyx-mcp-server`](https://github.com/halvrenofviryel/phionyx-mcp-server) writes under `~/.phionyx/mcp_audit/<trace_id>/`) into a single Inspect AI `.eval` log file under `./logs/<task>/<run_id>.eval`. The log is then viewable with `inspect view`, queryable with Inspect's standard tooling, and joinable with any other Inspect log in your eval workflow.

2. **MCP tool wiring documentation:** [`docs/wiring_phionyx_mcp_in_inspect_task.md`](docs/wiring_phionyx_mcp_in_inspect_task.md) walks through how to register the companion `phionyx-mcp-server` MCP server as a tool inside an Inspect AI eval task, so the agent under evaluation goes through Phionyx's runtime governance on every tool call.

## Install

```bash
pip install phionyx-eval-inspect

# To also view the resulting .eval logs in Inspect's UI:
pip install "phionyx-eval-inspect[inspect]"
```

The adapter itself has **zero runtime dependencies on inspect-ai** — it emits the `.eval` JSON shape directly. The `[inspect]` extra exists only for when you want `inspect view` or a live Inspect task.

## Use — CLI

```bash
# Convert a Phionyx envelope chain into an Inspect log file:
phionyx-eval-inspect convert \
    --trace trace-abc-001 \
    --task phionyx_governed_replay \
    --audit-root ~/.phionyx/mcp_audit \
    --logs-dir ./logs

# Show the converted log without writing to disk:
phionyx-eval-inspect show \
    --trace trace-abc-001 \
    --audit-root ~/.phionyx/mcp_audit
```

Then view it with Inspect AI:

```bash
inspect view ./logs/phionyx_governed_replay/trace-abc-001.eval
```

## Use — Python

```python
from phionyx_eval_inspect import (
    envelope_chain_from_directory,
    envelope_chain_to_inspect_log,
    write_log,
)

envelopes = envelope_chain_from_directory(
    "~/.phionyx/mcp_audit", "trace-abc-001"
)
log = envelope_chain_to_inspect_log(
    envelopes,
    task_name="phionyx_governed_replay",
    run_id="trace-abc-001",
)
write_log(log, logs_dir="./logs")
```

The function is **read-only** over the envelope chain. It never modifies the input, and it never scores the run — scoring stays in Inspect's own solver/scorer chain.

## What the log carries

Each envelope becomes one Inspect *sample*. The sample carries:

- `id`: Phionyx turn index.
- `input`: the user text (envelope `input.user_text`).
- `output.completion`: the released text (envelope `output.text`).
- `events`: one per pipeline block step (`phionyx.pipeline.block`) plus an event per MCP tool call (`phionyx.mcp.tool_call`) when present.
- `metadata.phionyx`: the governance evidence — trace id, decision, decision reason, policy basis, pipeline path, integrity chain (previous + current + signature), and the full `mcp_tool_audit` block when populated.

Phionyx-specific fields live under `metadata.phionyx` so native Inspect tooling sees them without colliding with Inspect's native data model.

## Where this fits on phionyx.ai

This package surfaces under [**phionyx.ai/evidence**](https://phionyx.ai/evidence) — the Reviewer Evidence pillar. It is the bridge that turns a Phionyx envelope chain into a format the wider eval ecosystem (Inspect AI) reads natively, so Phionyx-governed runs are inspectable in the tools reviewers already use.

## Companion packages — the wider stack

Each component below has its own independent version line — do not cross-attribute one component's version to another.

| Package | Role | Version |
|---|---|---|
| [phionyx-core](https://pypi.org/project/phionyx-core/) | **Engine (SDK).** Deterministic AI runtime governance — 46-block pipeline, kill switch, ethics + safety gates, signed audit envelopes. Reference implementation scoring L3 + D3 on the Evaluation Standard. | v0.7.2 |
| [phionyx-mcp-server](https://github.com/halvrenofviryel/phionyx-mcp-server) | MCP trust boundary: descriptor hash, signed RGE envelope, audit chain (outward layer) | v0.1.0 |
| [phionyx-pipeline-mcp](https://github.com/halvrenofviryel/phionyx-pipeline-mcp) | **Gate.** Self-governance MCP for Claude Code: verifies the agent's own "fixed / tested / changed" claims against git-diff truth (inward layer). This is the component the Evaluation Standard's claim-governance ladder (CG-L0…CG-L5) rates: stable = CG-L2, alpha = CG-L3 (opt-in / default-off). | stable v0.2.0 / alpha v0.3.0a1 |
| [**phionyx-eval-inspect**](https://github.com/halvrenofviryel/phionyx-eval-inspect) | **(this)** Interoperability bridge into Inspect AI eval logs | v0.1.0 |
| [phionyx-langchain-langgraph](https://github.com/halvrenofviryel/phionyx-langchain-langgraph) | LangChain + LangGraph adapters — every chain / tool / LLM event + supervisor handoff → signed envelopes | v0.1.0a1 (alpha) |
| [phionyx-openai-agents](https://github.com/halvrenofviryel/phionyx-openai-agents) | OpenAI Agents SDK tracing bridge — every Trace and Span → signed envelopes | v0.1.0a1 (alpha) |

When the two MCP packages are installed, a single Claude Code session emits Phionyx envelopes (outward + inward) → both packages share one `trace_id` → this adapter converts the chain into an Inspect `.eval` log → `inspect view` shows the full run. The framework adapters (langchain-langgraph + openai-agents) emit envelopes from non-MCP workflows; the same Inspect conversion path applies once those chains land on disk.

## Evaluation Standard

The vendor-neutral [`phionyx-evaluation-standard`](https://github.com/halvrenofviryel/phionyx-evaluation-standard) (released v0.1.1 / v0.2.0; v0.3 in draft) defines the scales that place every component on common ground: **L0-L3** (evaluation maturity) and **D0-D3** (determinism), both released, and **CG-L0…CG-L5** (claim-governance), which is the v0.3 layer and currently a draft. The CG ladder rates the gate (`phionyx-pipeline-mcp`); L0-L3 / D0-D3 rate any runtime, with `phionyx-core` as the reference implementation (L3 + D3). This adapter is the bridge that makes that evidence inspectable — it does not itself carry a CG/L/D grade.

## Schema pinning

The adapter is pinned to the Inspect AI log format **v0.3.x** line. Confirm the current Inspect log-format version at [`inspect.aisi.org.uk`](https://inspect.aisi.org.uk) if you need an exact pin. Override the pin with:

```bash
PHIONYX_INSPECT_LOG_SCHEMA_VERSION=v0.3.x phionyx-eval-inspect convert ...
```

To support a new Inspect schema, drop `log_schema_v0_<minor>.py` next to `adapter.py` and extend `_resolve_schema_module`. Bump-policy doc forthcoming in the umbrella repo under `docs/conventions/inspect_log_schema_bump_policy.md`.

## Framing — what this package does NOT claim

- It is **not** an endorsement, accreditation, or partnership with UK AISI or any other AI safety institute or government body.
- It does **not** validate or score the Phionyx-governed run — it surfaces evidence so Inspect's own scorers can be applied.
- It does **not** require Inspect AI to be installed at runtime — only at view time.
- It does **not** modify Inspect AI; the adapter writes a standard `.eval` file the framework's native tools read.

The framing is **interoperability**, not endorsement.

## Tests

```bash
pip install -e ".[test]"
pytest -q
```

## License

AGPL-3.0-or-later. See [`LICENSE`](LICENSE).

## See also

- [phionyx.ai/evidence](https://phionyx.ai/evidence) — entry pillar this package surfaces under (the Evidence Matrix)
- [phionyx.ai/bounded-authority](https://phionyx.ai/bounded-authority) — entry pillar for the runtime + MCP siblings that produce the envelopes this adapter consumes
- Project hub: [github.com/halvrenofviryel/phionyx-research](https://github.com/halvrenofviryel/phionyx-research)
- Evaluation Standard: [github.com/halvrenofviryel/phionyx-evaluation-standard](https://github.com/halvrenofviryel/phionyx-evaluation-standard) — the L0-L3 / D0-D3 / CG-L0…CG-L5 scales this component is placed on
- Phionyx Core SDK: [pypi.org/project/phionyx-core](https://pypi.org/project/phionyx-core/)
- Inspect AI: [github.com/UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai)
- Inspect AI documentation: [inspect.aisi.org.uk](https://inspect.aisi.org.uk)
- Reasoned Governance Envelope (RGE) v0.2 RFC: [phionyx-mcp-server/specs/rge_v0_2](https://github.com/halvrenofviryel/phionyx-mcp-server/tree/main/specs/rge_v0_2)
