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
2. [CLI Reference](index.md#cli-commands)
3. [Python SDK](sdk.md)
4. [Configuration](config.md)
5. [Troubleshooting](troubleshooting.md)

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

### The Pipeline

1. **Feature Extraction** — local rules detect code keywords, algorithm terms,
   constraints (`O(n)`, `O(1)`), intent (explain / implement / debug / compare),
   and compute a 16-dimension feature vector.
2. **AI Analysis** — optional streaming analysis uses an available provider to
   estimate complexity and required capabilities (skipped when no provider is keyed).
3. **Learning Router** — with 3+ similar past experiences, historical quality and
   fallback rates select the model; otherwise complexity and capability rules decide.
4. **Model Selection** — cheapest capable model wins. Generate is verified; provider
   failures cascade to the next tier (free → mid → premium) up to `max_retries`.
5. **Confidence & Consensus** — if the response scores below the adaptive threshold,
   a cross-model consensus check can escalate the decision.
6. **Cost & Trace** — every query is logged for cost savings, hop score, and history.

### Key Behaviors

- **Empty mid-tier fallback**: if a tier has no models configured, fallback skips it
  (free → premium works without any mid model).
- **Query decomposition**: complex queries are optionally split into sub-questions and
  routed independently, then merged into one answer.
- **Cost estimation without logging**: CLI and SDK estimate savings even when
  cost logging is disabled.