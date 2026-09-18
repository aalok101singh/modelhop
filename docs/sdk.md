# 🐸 ModelHop Python SDK (v1.1)

ModelHop can be used as a Python library from anywhere, not just the CLI.
The SDK is the brain — the CLI and the HTTP server are thin shells over it.

## Install

```bash
pip install modelhop          # SDK + CLI, Python 3.9+
pip install "modelhop[server]"      # + OpenAI-compatible HTTP server
pip install "modelhop[llamaindex]"  # + LlamaIndex wrapper
pip install "modelhop[cache]"       # + local-embedding semantic cache
pip install "modelhop[secrets]"     # + AWS / Vault secret providers
pip install "modelhop[anthropic]"   # + Anthropic provider
```

## Minimal Example

```python
import asyncio

from modelhop import ModelHop


async def main():
    modelhop = ModelHop()

    response = await modelhop.route("Explain the difference between SQL and NoSQL")
    print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
```

`ModelHop(config_path=None)` loads `modelhop.yaml` from the current
directory when present, otherwise falls back to the built-in default config.
Keys come from the environment (or a `.env` file) via the model's
`api_key_env` — see [Configuration](config.md).

## Response Object (v1.1)

`route(query, *, task_id=None, budget=None, trust_required=None, context=None) -> RouteResult`:

| Field | Type | Description |
|-------|------|-------------|
| `response` | `str` | The generated answer (alias `content` for 1.0 compat) |
| `model` | `str` | Model name (alias `model_used`) |
| `tier` | `str` | `free`, `mid`, or `premium` |
| `reasoning` | `str` | Full routing rationale (learning-router logic + signals) |
| `confidence` | `ConfidenceResult` | Score, threshold, `calibrated`, `method`, `ece`, `degraded` |
| `cost` | `CostAnalysis` | Actual/would-have/savings, `baseline_model`, `tokens_in`, `tokens_out`, `aux_calls`, `aux_cost` |
| `candidates` | `list` | Policy-eligible candidates |
| `degraded` | `bool` | Fail-closed escalation marker |
| `cached` | `bool` | Cache hit |
| `trust` | `TrustProfile` | Effective trust of the chosen model |
| `verifier` | `VerifierResult \| None` | Gate outcome |
| `ledger_id` | `str` | Audit position (`seq:hash`) |

Backward compat: `content`, `model_used`, `provider`, `tokens_in`,
`tokens_out`, `latency_ms` properties still work on `RouteResult`, so 1.0
code keeps running. `ModelHop.explain(result)` renders a one-line rationale.

## Budgets & Sessions

Cap spend per task. When the budget is exhausted and `fail_closed` is on,
the route is refused instead of overspending:

```python
result = await mh.route(
    "Summarize these 200 tickets",
    task_id="nightly-triage",   # groups spend + pins model coherence
    budget=0.50,                # hard USD cap for this task
)
```

## Trust Per Call

Hard constraints filter models *before* ranking. If nothing satisfies them,
the call is refused (fail-closed) rather than leaking data somewhere unsafe:

```python
result = await mh.route(
    "Summarize this patient note",
    trust_required={"zdr": True, "allowed_jurisdictions": ["EU"]},
)
```

See [Configuration](config.md) for the full trust schema (`data_classes`,
`max_sensitivity`, `zdr`, `jurisdiction`, `safety_tier`).

## Call Context

Pass spend/latency/tenant hints without changing config:

```python
result = await mh.route(
    "Draft the release notes",
    context={
        "cost_ceiling": 0.01,      # skip candidates predicted above this
        "latency_slo_ms": 3000,    # skip candidates likely to breach this
        "tenant_tier": "premium",  # isolates cache + bandit learning
    },
)
```

## Error Handling

`route()` never raises for a single provider failure — it falls back across
tiers. It raises `RuntimeError` only when every provider fails on every
attempt, or when trust/policy constraints exclude everything:

```python
try:
    response = await modelhop.route("...")
except RuntimeError as exc:
    print("No route possible:", exc)
```

## Cost Estimation

`estimate_cost(response, model)` returns the estimated USD cost of a response
without needing a configured cost tracker:

```python
from modelhop.tracking.cost_tracker import estimate_cost

cost = estimate_cost(response, model)
print(f"${cost.actual_cost:.6f}")
print(cost.tokens_in, cost.tokens_out)
```

## Agent Integrations

**MCP tool hook** — route one tool-invocation turn with spend/latency
awareness. Tool output is treated as DATA, never spliced into prompts:

```python
from modelhop.clients.mcp import mcp_tool_hook

out = await mcp_tool_hook(query, tool_name="web_search", tool_args=args, mh=mh)
# {"response": str, "model": str, "degraded": bool}
```

**LlamaIndex** (`pip install "modelhop[llamaindex]"`):

```python
from modelhop.clients.llamaindex import ModelHopLlamaIndex

llm = ModelHopLlamaIndex()          # model="auto" routes every prompt
print(llm.complete("What is a vector index?"))
```

**HTTP server** (`pip install "modelhop[server]"`) — OpenAI-compatible
endpoint for any framework or language:

```bash
modelhop serve   # 127.0.0.1:8000, model="auto", SSE streaming
```

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="not-needed-locally")
client.chat.completions.create(model="auto", messages=[{"role": "user", "content": "hi"}])
```

Set `MODELHOP_API_KEY` to require a Bearer token. Rate limited
(120 req/min) with a 256 KB body cap.

## Async Only

All I/O methods are async (`route`, analyze, etc.). Call them from an asyncio
event loop, or wrap with `asyncio.run()` as shown above.
