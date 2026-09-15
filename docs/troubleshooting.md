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

## Behavior Notes

- **Empty mid tier skips to premium.** If no `mid` model is configured, free-queries
  that need escalation go straight to premium.
- **Cost shown without logging.** CLI and SDK estimate savings using
  `estimate_cost()` even when cost tracking is disabled.
- **Consensus adds a second call.** Low-confidence answers trigger a cross-model
  check; this costs an extra API call but catches bad free-tier output.
- **Gemini adapter** sets `GOOGLE_API_KEY` in the environment and suppresses its
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