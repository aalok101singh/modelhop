# Changelog

All notable changes to ModelHop will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Token accounting surfaced: `CostAnalysis.tokens_in/tokens_out` (additive),
  shown in the route cost panel and returned by `route --json` / `history --json`
- `modelhop stats --reset` clears lifetime counters (cost log, traces, ledger,
  cache, shield); stats panels are labeled "(lifetime)"
- Setup wizard offers alternative models when a provider's default model fails
  (all providers: Groq, Gemini, OpenAI), tests the replacement, and wires it
  into `modelhop.yaml`; declining treats the provider as not configured
- Honest provider errors everywhere (`setup`, `welcome`, `providers`): invalid
  key (401), no credits (429), model not accessible (404), network — instead of
  a bare "Failed - check your key"

### Fixed
- Hop Score rehydrates from `trace_log.jsonl` (was reading the dead legacy
  `trace_log.json`, so every CLI run showed "1 total"); optimal now means
  confident AND money saved (confident-only when no priced baseline exists)
- Confidence heuristic no longer tanks normal short answers (only sub-20-char
  stubs are penalized), so greetings stop flipping to `degraded`
- `degraded` badge now explains itself (confidence vs threshold, safest
  fallback kept); Cost Analysis panel uses a green border and bright-green
  savings line when savings > 0, and an honest "n/a (free tier only) + add a
  premium model to measure savings" note when no priced baseline exists
- Test suite is hermetic: live keys from a repo-root `.env` no longer leak
  into tests (autouse fixture clears secret env vars and neutralizes `.env`
  reloads); piped CLI output keeps its ASCII guarantee for all chrome strings
- Fresh-install gaps closed: `.env.example` ships inside the wheel
  (hatchling `force-include`); `modelhop setup` creates `modelhop.yaml` from
  defaults when missing so model switches are never silently dropped; README
  no longer claims welcome auto-generates config or that pip users can
  `cp .env.example .env`; `docs/index.md` gains the missing Quick Start and
  CLI Commands sections
- Pre-commit audit fixes: `from __future__ import annotations` added wherever
  PEP 604 unions are used (Python 3.9 CI matrix); `is_optimal_hop` exported in
  `__all__`; `hub download` defaults to `<name>.yaml` instead of silently
  overwriting `modelhop.yaml`; SBOM upload tolerates missing files; dead
  `os.getenv` line removed; `.gitattributes` normalizes line endings;
  `test_w4` spec path anchored to repo root; `test_v11_core` stubs embedding
  loads for hermetic runs
- Qodo review (21 findings) fixes: serve auth fails closed on secret-backend
  errors; fallbacks and decomposed subqueries stay inside policy-eligible
  sets; `zdr` alias honored; jurisdiction allowlists reject unknown regions;
  `no_raw_cache` gates all persistence; task sessions reused by `task_id`;
  aux costs counted once (per-route fields); ledger append raises on write
  failure and traces link to audit entries; cache hits logged to stats;
  trust/tenant-aware caches with re-filtering on hit; rubric skips fail
  closed; Gemini tools sent as request fields; breaker probe accounting;
  hub subdirectories preserved and configs structurally validated; zero
  propensity rows excluded; exact-match `.env` key removal

## [1.1.0] - 2026-09-17

### Added
- Zero-API default routing: feature-only analysis, calibrated confidence, contextual
  bandit, policy engine, exact + semantic cache, generic verifier pipeline
- `RouteResult` SDK return with reasoning, confidence, cost, candidates, degraded,
  cached, trust, verifier, ledger_id; `ModelHop.explain()`; task-scoped budgets,
  model coherence, provider health, spend/latency awareness, MCP hook
- Trust first-class on `ModelConfig` (`TrustProfile`), hard-constraint filtering in
  routers and policy engine, fail-closed by default (`routing.fail_closed: false`
  restores 1.0.9 behavior)
- Signed state (`SignedStore` HMAC-SHA256), hash-chained `DecisionLedger`, atomic
  JSONL traces, `SecretsProvider` abstraction (env default), `PriceBook` with
  configurable `cost_savings_reference`, `HealthRegistry` circuit breakers
- FastAPI OpenAI-compatible server (`POST /v1/chat/completions` with `model="auto"`,
  SSE streaming, `GET /v1/models`), JS/TS client, LlamaIndex wrapper, OTel export
- Community `PerformanceCard` publisher (k-anonymized, signed), hub schema +
  signature validation with confined writes, offline IPS/doubly-robust eval,
  shadow→canary→rollout harness, drift detection with auto-rollback
- Routing Policy spec (`spec/routing-policy.schema.json`) and OpenTelemetry schema,
  `modelhop eval` and `modelhop calibrate` CLI, CLI refactored onto the SDK

### Fixed
- Greedy JSON parse replaced with balanced-brace scanner; no query interpolation
  into control prompts; self-reported scores never trusted; fail-open 0.85 defaults
  removed (fail-closed); `raw_response` excluded from persistence; Gemini global
  `os.environ` mutation removed; decay-weighted average corrected; dead `query_type`
  kwarg removed; provider timeouts/retries bounded with jitter
- Hardened `.env` parsing (quotes/BOM, `export` prefix, comments, no eval)

### Changed
- Version bumped to 1.1.0. Default flip from fail-open to fail-closed is a behavior
  change documented prominently; `routing.fail_closed: false` is the escape hatch.
- Defaults: `routing.llm_analysis: false`, `routing.cross_model_consensus: false`
  (both explicit opt-ins); savings baseline resolved from `cost_savings_reference`

## [1.0.9] - 2026-09-15

### Added
- SDK `route()` now handles provider failures with cascade fallback instead of
  raising — errors escalate to the next available provider like the CLI path
- SDK `route()` now runs cross-model consensus checks (previously CLI-only)
- `QueryDecomposer` wired into `ModelHop.route()` for multi-part complex queries
  (config: `routing.decompose_queries`, default true)
- `ReasoningEngine.explain()` shown in `route --verbose` output
- Full test suite for all placeholder test files (router, confidence, fallback,
  providers, cost tracker, shield, hub) plus new unit tests for feature
  extractor, memory, performance tracker, adaptive threshold, model registry
  and learning router
- `docs/` directory with user-facing documentation (usage, SDK, config,
  troubleshooting)
- Shared tier color/emoji constants in `modelhop/cli/display.py`
- `estimate_cost()` helper reused by the cost tracker and CLI/SDK

### Fixed
- Cascade fallback no longer gets stuck at empty tiers: `get_next_tier` skips
  tiers with no models, so free → premium escalation works without a mid model
- Hardcoded `v1.0.0` display panels now read the installed package version
- `benchmark` no longer reports fabricated 98/97 quality scores — it measures
  actual confidence on each routed query
- `max_retries` config is respected by both CLI and SDK fallback loops
- `setup` Groq entry now includes the `coding` capability like the default config
- `setup` reuses `config._load_env_file` instead of its own duplicate loader
- `.env` is re-read on every `Config()` construction, so keys added after import
  are seen immediately
- JSON persistence (memory/performance/adaptive) writes atomically — a crash
  mid-write can no longer leave an empty/corrupt store
- Example configs and community configs updated with `decompose_queries`; the
  three community configs are now genuinely different per use case

### Changed
- Version bumped to 1.0.9

## [1.0.8] - 2026-09-15

### Added
- Example configs for support bot, code review, and creative writing use cases
- `examples/support_desk.py` — support desk bot example using the SDK
- `examples/custom_agent.py` — custom agent example with its own decision loop

### Fixed
- Example config files now contain valid YAML instead of Python stubs

### Changed
- Example configs give the free Groq model `coding` and `creative` capabilities
  where appropriate for each use case

## [1.0.7] - 2026-09-14

### Added
- Multi-layer intelligence system with feature extraction
- Experience memory for learning from past queries
- Performance tracking per model
- Adaptive confidence thresholds
- Natural language reasoning for routing decisions
- Query decomposition for complex queries
- Interactive setup wizard with connection testing
- Provider fallback on error
- Hop Score display after successful routing
- First-run welcome experience
- Community hub for sharing routing configs
- Shield quality monitoring

### Fixed
- `modelhop init` setup command crash
- Gemini provider `GOOGLE_API_KEY` environment variable
- Groq model changed to working `qwen/qwen3.8-27b`
- Gemini model updated to `gemini-3.6-flash`
- Panel display on terminal resize

### Changed
- Removed forced panel expansion for better terminal compatibility
- Improved error handling with provider fallback loop

## [1.0.6] - 2026-09-14

### Fixed
- Setup command invocation from init
- Provider fallback infinite recursion

## [1.0.5] - 2026-09-14

### Added
- Auto-welcome on `modelhop` without arguments
- Clean panel display without forced width

## [1.0.0] - 2026-09-14

### Added
- Initial release
- Core routing engine
- Provider adapters (Groq, Gemini, OpenAI, Anthropic)
- CLI with 21 commands
- Cost tracking and history
- Benchmark capabilities
- Configuration management
- Example queries and quick start
