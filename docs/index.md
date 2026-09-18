# ModelHop Documentation

ModelHop is an intelligent LLM router that automatically picks the cheapest capable
model for each query. It combines zero-cost feature extraction, experience-based
learning, and adaptive confidence thresholds to send simple queries to free models
(Groq / Gemini) while reserving premium models (GPT-4) for complex work.

- **Save 60-90%** on LLM costs by default.
- **Zero-API analysis**: query intent, complexity, constraints, and similarity are
  computed locally before any token is spent.
- **Self-improving**: past outcomes (quality, fallback use, latency) steer future
  routing, and the confidence threshold adapts over time.

## Getting Started

1. [Quick Start](index.md#quick-start)
2. [CLI Commands](index.md#cli-commands)
3. [Python SDK](sdk.md)
4. [Configuration](config.md)
5. [Troubleshooting](troubleshooting.md)

## Quick Start

```bash
pip install modelhop   # or: pip install -e ".[dev,server]" from source
modelhop               # welcome panel: validates keys, points to init
modelhop init          # creates modelhop.yaml, offers to run setup
modelhop setup         # interactive keys; offers tested model alternatives
modelhop r "How do I reset my password?"
modelhop stats         # lifetime totals; --reset to clear
```

Get a free key at [console.groq.com](https://console.groq.com) or
[aistudio.google.com](https://aistudio.google.com/apikey) first. OpenAI is
paid and needs billing credits before any model on it works.

## CLI Commands

| Command | Description |
|---------|-------------|
| `modelhop` / `welcome` | Setup guide, live key validation, quick start |
| `route` (`r`) | Route a query (`--json`, `--verbose`, `--model`) |
| `setup` (`set`) | Interactive API key wizard |
| `init` (`i`) | Generate `modelhop.yaml` |
| `stats` (`s`) | Lifetime statistics (`--reset` to clear) |
| `history` (`h`) | Recent routing decisions |
| `providers` (`p`) | Provider/model status with failure reasons |
| `benchmark` (`b`) | Cost comparison test |
| `config` (`c`) | Show current configuration |
| `example` (`e`) | Example queries |
| `cheat` | Quick reference card |
| `shield` | Quality monitoring status |
| `hub` | Community configs |
| `eval` | Offline eval + drift check |
| `calibrate` | Confidence calibration |
| `serve` | OpenAI-compatible HTTP server |

## How Routing Works

```
Query → Feature Extraction → AI Analysis → Learning Router → Model Selection
                                                                    |
                                                            ┌───────┴───────┐
                                                            │   Free Tier   │
                                                            │  (Groq/Gemini)│
                                                            └───────┬───────┘
                                                                    │
                                                            If complex/failed
                                                                    │
                                                            ┌───────┴───────┐
                                                            │ Premium Tier  │
                                                            │   (GPT-4)     │
                                                            └───────────────┘
```

### The Pipeline (v1.1: zero-API default)

```
query + context + policy + telemetry
        │
 FeatureExtractor  (0 API calls)
        │
 hard constraints: trust · budget · SLO · health
        │
 cache (exact → semantic) ──► hit? return (≈0 cost)
        │ miss
 calibrated confidence ──► reward model ──► bandit ──► decision
        │
 verifier gate (generic) ──► pass? deliver : escalate
        │
 ledger (hash-chained, signed) ──► OTel export ──► reward ◄── outcomes
```

1. **Feature Extraction** — local rules detect code keywords, algorithm terms,
   constraints (`O(n)`, `O(1)`), intent, and compute a 16-dimension vector. Zero API calls.
2. **Policy constraints** — trust, budget, latency SLO, health filter candidates first.
3. **Cache** — SQLite exact cache, then local-embedding semantic cache.
4. **Bandit + reward** — contextual Thompson sampling over
   `query_type × complexity × tenant`, fed by a calibrated reward model.
5. **Verifier gate** — generic pipeline (schema, grounding, consistency, rubric,
   custom; code is one optional plugin). Failures escalate.
6. **Ledger + telemetry** — hash-chained, signed audit trail plus OTel spans.
7. **Learning loop** — outcome → reward → calibration/bandit, promoted only via
   offline eval → shadow → canary with auto-rollback.

LLM analysis (`routing.llm_analysis`) and cross-model consensus
(`routing.cross_model_consensus`) are explicit opt-ins. The default route makes
**zero auxiliary paid calls**.

### Key Behaviors

- **Empty mid-tier fallback**: if a tier has no models configured, fallback skips it
  (free → premium works without any mid model).
- **Query decomposition**: complex queries are optionally split into sub-questions and
  routed independently, then merged into one answer.
- **Cost estimation without logging**: CLI and SDK estimate savings even when
  cost logging is disabled.