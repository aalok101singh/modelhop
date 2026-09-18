# Troubleshooting

## Common Errors

### `No API keys found!` / `No provider for query analysis!`
**Cause:** No env var is set for any configured provider.
**Fix:** Run `modelhop setup`, or set `GROQ_API_KEY` / `GEMINI_API_KEY` /
`OPENAI_API_KEY`. ModelHop reads a `.env` file in the current directory and
never raises for missing keys — it just runs heuristically.

### `Provider not available for groq-qwen3-8-27b, trying next...`
**Cause:** A provider raised during generate (rate limit, invalid key, network).
**Fix:** None required. ModelHop automatically falls back to the next model,
cascading free → mid → premium up to `max_retries`.

### `rate limited or no credits` (429 / `credit_balance_exhausted`)
**Cause:** Provider is throttled or the account balance is exhausted.
**Fix:** Wait, add more free models to `modelhop.yaml`, or check the provider
console. Fallback handles this automatically.

### `invalid API key` (401)
**Cause:** The key is wrong or expired.
**Fix:** Run `modelhop setup` again with a valid key.

### `model not found` (404 / `model_not_found`)
**Cause:** The model name in config doesn't match a model available at the provider.
**Fix:** Update the `model` field in `modelhop.yaml` (providers change model ids
over time, e.g. Groq).

### `All models failed!`
**Cause:** Every provider raised on every attempt.
**Fix:** Check `.env` keys, provider status pages, and network connectivity.

### Setup says a provider "Failed" even though the key is correct
**Cause:** The wizard now prints the real reason. Common ones: the configured
model isn't accessible to the account (404 `model_not_found`, e.g. `gpt-4` on
new OpenAI accounts) or the account has no credits (429
`credit_balance_exhausted`).
**Fix:** When the default model fails, the wizard offers to switch that
provider to another available model (same offer for Groq and Gemini, whose
model ids change over time), tests it, and wires it into `modelhop.yaml`.
Declining leaves the provider unconfigured. No-credit accounts must add
billing before any model on that provider can work.

### `stats` shows more queries than you ran / Hop Score stuck at 0
**Cause:** `stats` reports lifetime totals from `cost_log.json`, which
accumulates across every session (old entries, including test models, stay
until cleared). The Hop Score aggregates the trace log the same way.
**Fix:** Run `modelhop stats --reset` to clear cost log, traces, ledger,
cache, and shield state (learning/bandit memory is kept). An "optimal" hop
means the response was confident AND money was saved (confident-only when no
priced baseline is configured, e.g. free-only setups).

### `degraded` badge after a response
**Meaning:** Fail-closed routing kept a low-confidence response but pinned it
to the safest fallback instead of escalating. The badge now reads
`degraded - low confidence (X < threshold); used safest fallback`. Short
greetings no longer trigger it (only sub-20-char stubs are penalized).

### Garbled output when piping (`modelhop welcome | ...`)
**Cause:** None anymore — when stdout is not a terminal, ModelHop renders
plain ASCII (no colors, ASCII frames, no emoji) so redirected output is clean
in any shell or code page. If you ever see mojibake from an older version,
set the console to UTF-8 (`[Console]::OutputEncoding = [Text.Encoding]::UTF8`).
Related knobs: `MODELHOP_WIDTH` caps frame width (default 100);
`MODELHOP_PLAIN=1` / `NO_COLOR` force plain output even on a terminal.

## Behavior Notes

- **Empty mid tier skips to premium.** If no `mid` model is configured, free-queries
  that need escalation go straight to premium.
- **Cost shown without logging.** CLI and SDK estimate savings using
  `estimate_cost()` even when cost tracking is disabled.
- **Zero-aux default.** The default route makes no paid auxiliary calls. If you see
  aux costs, you enabled `llm_analysis` or `cross_model_consensus`.
- **Fail-closed refusals.** `Request refused: no model satisfies trust policy` means
  your `trust_policy`/`trust_required` excludes every model. Loosen the policy or
  set `routing.fail_closed: false` to restore 1.0.9 behavior.
- **Tamper resets.** `StateIntegrityError` warnings mean on-disk state failed HMAC
  verification; ModelHop resets to empty rather than trusting poisoned state.
- **Consensus adds calls.** Only when `cross_model_consensus: true` with a separate
  provider; this costs extra API calls.
- **Gemini adapter** no longer mutates `os.environ` and suppresses its
  import-time `FutureWarning`.

## Testing

```bash
pytest            # run the test suite
black modelhop/   # format check
ruff check modelhop/
```

## Reporting

Security issues: see [SECURITY.md](../SECURITY.md).
Bugs and feature requests: open a GitHub issue at
https://github.com/aalok101singh/modelhop/issues.