# Configuration

ModelHop reads a `modelhop.yaml` file from the current directory. Generate one with:

```bash
modelhop init
```

If no file exists, the built-in default (`EXAMPLE_CONFIG`) is used.

## Top-Level Layout

```yaml
models:
  - name: groq-qwen3-8-27b
    provider: groq
    model: qwen/qwen3.8-27b
    tier: free
    capabilities: [general, reasoning, coding]
    cost_per_1k_input: 0.0
    cost_per_1k_output: 0.0
    api_key_env: GROQ_API_KEY
routing:
  confidence_threshold: 0.7
  cross_model_consensus: false   # opt-in only
  llm_analysis: false            # opt-in only; default is zero-API heuristic
  fail_closed: true              # false restores 1.0.9 fail-open behavior
  fallback: cascade
  max_retries: 3
  decompose_queries: true
  trust_policy: {}               # e.g. {require_zdr: true, allowed_jurisdictions: [EU]}
  cost_savings_reference: max    # or an explicit model name
  policy_version: '1'
shield:
  enabled: true
  quality_threshold: 0.8
tracking:
  log_queries: true   # persist JSONL traces + ledger entries per route
  log_costs: true     # persist cost entries; estimates still shown when false
```

> `modelhop setup` creates `modelhop.yaml` from the built-in defaults when no
> file exists, so a model switch accepted in the wizard is always wired in. A
> successful switch rewrites that provider's `model` **and** its derived `name`
> (`provider-slug`, e.g. `openai-gpt-4o-mini`); declining removes the
> provider's key and models (treated as not configured).

## Models

Each model entry:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Unique identifier shown in logs |
| `provider` | yes | `groq`, `gemini`, `openai`, or `anthropic` |
| `model` | yes | Provider model id (e.g. `qwen/qwen3.8-27b`, `gpt-4`) |
| `tier` | yes | `free`, `mid`, or `premium` |
| `capabilities` | yes | e.g. `general`, `reasoning`, `coding`, `creative`, `analysis`, `technical`, `faq` |
| `cost_per_1k_input` | yes | USD per 1K input tokens |
| `cost_per_1k_output` | yes | USD per 1K output tokens |
| `api_key_env` | yes | Env var holding this model's API key |

A provider is only instantiated if its API key env var is set. With no keys,
ModelHop runs in fully-heuristic mode and every model is treated as unavailable.

## Routing Options

| Option | Default | Meaning |
|--------|---------|---------|
| `confidence_threshold` | `0.7` | Below this confidence score, escalation may occur |
| `cross_model_consensus` | `false` | Opt-in: ask a separate provider + judge to confirm |
| `llm_analysis` | `false` | Opt-in: paid LLM query analysis (default heuristic, 0 calls) |
| `fail_closed` | `true` | Unresolved confidence escalates/`degraded`; `false` restores 1.0.9 fail-open |
| `fallback` | `cascade` | Escalation order: free → mid → premium |
| `max_retries` | `3` | Max attempts before giving up on a query |
| `decompose_queries` | `true` | Split complex queries into sub-questions and merge answers |
| `trust_policy` | `{}` | Hard constraints (ZDR, jurisdiction, sensitivity, safety, data classes) |
| `cost_savings_reference` | `max` | Baseline = most expensive model, or explicit model name |
| `policy_version` | `'1'` | Bumps invalidate caches |

Declare per-model trust via `models[].trust` (`data_classes`, `max_sensitivity`,
`zdr`, `jurisdiction`, `safety_tier`) plus `timeout_s`, `max_retries`,
`context_window`, `supports_tools`, `price_effective_date`.

### Empty Tiers

Fallback skips tiers that have no models configured. A config with only free and
premium models escalates free → premium without any mid model in between.

## Shield Options

| Option | Default | Meaning |
|--------|---------|---------|
| `enabled` | `true` | Enable quality monitoring |
| `quality_threshold` | `0.8` | Quality below this raises an alert |

## Tracking Options

| Option | Default | Meaning |
|--------|---------|---------|
| `log_queries` | `true` | Append JSONL traces, ledger entries, memory/performance learning |
| `log_costs` | `true` | Append cost entries to `cost_log.json` |

With both off, routing still works and `estimate_cost()` still powers the
per-query panels — nothing is persisted. `modelhop stats` reads these files
as lifetime totals; `modelhop stats --reset` clears them (learning/bandit
memory is kept).

## Environment Variables

Keys are read from environment variables named in each model's `api_key_env`
(e.g. `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`).

ModelHop also loads a `.env` file from the current directory if present, so keys
defined there are available even when they are set after process start.

Known env-related notes:

- The Gemini adapter sets `GOOGLE_API_KEY` from the given key automatically.
- A missing key simply leaves that provider unavailable; no error is raised.