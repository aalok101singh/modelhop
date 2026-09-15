# Changelog

All notable changes to ModelHop will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
