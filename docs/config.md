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
  cross_model_consensus: true
  fallback: cascade
  max_retries: 3
  decompose_queries: true
shield:
  enabled: true
  quality_threshold: 0.8
```

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
| `cross_model_consensus` | `true` | Ask a second provider to confirm low-confidence answers |
| `fallback` | `cascade` | Escalation order: free → mid → premium |
| `max_retries` | `3` | Max attempts before giving up on a query |
| `decompose_queries` | `true` | Split complex queries into sub-questions and merge answers |

### Empty Tiers

Fallback skips tiers that have no models configured. A config with only free and
premium models escalates free → premium without any mid model in between.

## Shield Options

| Option | Default | Meaning |
|--------|---------|---------|
| `enabled` | `true` | Enable quality monitoring |
| `quality_threshold` | `0.8` | Quality below this raises an alert |

## Environment Variables

Keys are read from environment variables named in each model's `api_key_env`
(e.g. `GROQ_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`).

ModelHop also loads a `.env` file from the current directory if present, so keys
defined there are available even when they are set after process start.

Known env-related notes:

- The Gemini adapter sets `GOOGLE_API_KEY` from the given key automatically.
- A missing key simply leaves that provider unavailable; no error is raised.