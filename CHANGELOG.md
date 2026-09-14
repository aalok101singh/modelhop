# Changelog

All notable changes to ModelHop will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
