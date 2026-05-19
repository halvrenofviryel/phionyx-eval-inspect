# Wiring `phionyx-mcp-server` into an Inspect AI eval task

This document walks through registering the companion package `phionyx-mcp-server` as an MCP tool inside an Inspect AI evaluation task. After wiring, every third-party tool call the agent under evaluation makes flows through Phionyx's trust boundary governance — descriptor hash, change detection, signed RGE envelope, audit chain.

## Prerequisites

```bash
pip install phionyx-mcp-server inspect-ai
phionyx-mcp --help   # verify the CLI installed
inspect --help       # verify Inspect installed
```

You also need an OpenAI- or Anthropic-compatible API key (or a local provider) for the model under evaluation. Set the corresponding env var per Inspect's documentation.

## Minimal task

```python
# task.py
from inspect_ai import Task, eval, task
from inspect_ai.dataset import Sample
from inspect_ai.solver import generate, system_message, use_tools
from inspect_ai.tool import mcp_tools


@task
def phionyx_governed_eval() -> Task:
    # The phionyx-mcp-server exposes four production tools:
    #   verify_tool_descriptor, record_tool_call,
    #   verify_chain_integrity, query_audit_history
    # When registered here, the solver agent gets them as native MCP tools.
    phionyx_tools = mcp_tools(
        server="phionyx-mcp-server",
        # Inspect spawns the MCP server as a subprocess over stdio.
        # The shared-trace contract (ADR-0006) means PHIONYX_TRACE_ID
        # propagates automatically when both this task and the pipeline
        # MCP are wired in the same parent process.
    )

    return Task(
        dataset=[
            Sample(input="Summarise the meeting notes.", target="See notes"),
        ],
        solver=[
            system_message(
                "You are a research assistant. Use the phionyx-mcp-server "
                "tools to record evidence for every action you take."
            ),
            use_tools(phionyx_tools),
            generate(),
        ],
    )
```

Run it:

```bash
PHIONYX_TRACE_ID=trace-eval-001 inspect eval task.py
```

After the run completes, two artefacts exist:

- Inspect's native `.eval` log under `./logs/phionyx_governed_eval/<timestamp>.eval`.
- Phionyx's envelope chain under `~/.phionyx/mcp_audit/trace-eval-001/`.

## Joining the two surfaces

The two artefacts share the **trace identifier** you set in `PHIONYX_TRACE_ID`. To produce a single Inspect log that includes the Phionyx evidence under `sample.metadata.phionyx`:

```bash
phionyx-eval-inspect convert \
    --trace trace-eval-001 \
    --task phionyx_governed_replay \
    --logs-dir ./logs
```

You now have an Inspect-viewable log at `./logs/phionyx_governed_replay/trace-eval-001.eval` whose samples carry the full governance evidence — descriptor hashes, change-detection flags, permission scopes, signed envelope chain integrity, decision rationale.

Open it:

```bash
inspect view ./logs/phionyx_governed_replay/trace-eval-001.eval
```

## What flows where

```
┌─────────────────┐
│ Inspect Task    │  defines dataset + solver + scorer
└────────┬────────┘
         │ spawns
         ▼
┌─────────────────┐
│ phionyx-mcp-    │  stdio MCP server
│ server          │  emits RGE envelopes per tool call
└────────┬────────┘
         │ persists
         ▼
┌─────────────────┐
│ ~/.phionyx/     │  envelope chain on disk
│ mcp_audit/      │  one .json file per turn + chain.jsonl index
│ <trace_id>/     │
└────────┬────────┘
         │ read
         ▼
┌─────────────────┐
│ phionyx-eval-   │  reads chain, writes one .eval log
│ inspect convert │  with samples + events + metadata.phionyx
└────────┬────────┘
         │ writes
         ▼
┌─────────────────┐
│ ./logs/<task>/  │  Inspect-native log
│ <run_id>.eval   │  → viewable with `inspect view`
└─────────────────┘
```

## Multi-MCP wiring

If you also run [`phionyx-pipeline-mcp`](https://github.com/halvrenofviryel/phionyx-pipeline-mcp) (the self-governance gate for the agent's own claims), register both servers in the same task:

```python
phionyx_tools = mcp_tools(servers=["phionyx-mcp-server", "phionyx-pipeline-mcp"])
```

Both servers honour the shared-trace contract (ADR-0006). Setting `PHIONYX_TRACE_ID` ensures their telemetry joins on a single trace identifier; the Inspect log carries evidence from both layers.

## Caveats

- The adapter is pinned to Inspect log schema **v0.3.x**. If your installed `inspect-ai` is a newer major version, `phionyx-eval-inspect convert` may still produce a viewable log but native fields could drift. See the schema bump policy in the umbrella repo.
- This is an interoperability adapter, not an Inspect AI plugin in the official sense. It writes the standard `.eval` shape; it does not register itself as a custom log writer.
- The `mcp_tools(server=...)` helper above is the documented Inspect AI MCP integration as of v0.3.x. If the Inspect API has shifted, consult the Inspect documentation; the principle (register an MCP stdio server as a tool source) remains the same.

## See also

- README at the top of this repo
- Inspect AI documentation: https://inspect.aisi.org.uk
- ADR-0006 (Phionyx shared-trace contract): https://github.com/halvrenofviryel/phionyx-research/blob/main/docs/adr/0006-mcp-integration.md
- `phionyx-mcp-server` README: https://github.com/halvrenofviryel/phionyx-mcp-server
