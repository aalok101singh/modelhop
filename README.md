<p align="center">
  <img src="https://img.shields.io/badge/-frog-green?style=for-the-badge&logo=python&logoColor=white" alt="ModelHop Frog"/>
</p>

<h1 align="center">
  <br>
  ModelHop
  <br>
</h1>

<h4 align="center">Save 60-90% on LLM costs by hopping to the right model.</h4>

<p align="center">
  <a href="https://github.com/aalok101singh/modelhop/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/aalok101singh/modelhop/ci.yml?style=flat-square" alt="CI Status"/>
  </a>
  <a href="https://pypi.org/project/modelhop/">
    <img src="https://img.shields.io/pypi/v/modelhop?style=flat-square" alt="PyPI Version"/>
  </a>
  <a href="https://pypi.org/project/modelhop/">
    <img src="https://img.shields.io/pypi/pyversions/modelhop?style=flat-square" alt="Python Versions"/>
  </a>
  <a href="https://github.com/aalok101singh/modelhop/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/aalok101singh/modelhop?style=flat-square" alt="License"/>
  </a>
</p>

---

**ModelHop** is an intelligent LLM router that automatically picks the cheapest capable model for each query. It uses multi-signal feature extraction, experience-based learning, and adaptive confidence thresholds to route simple queries to free models while reserving premium models for complex tasks.

## Documentation

Detailed guides live in the [`docs/`](docs/) folder:

- [Index & How Routing Works](docs/index.md)
- [Python SDK](docs/sdk.md)
- [Configuration](docs/config.md)
- [Troubleshooting](docs/troubleshooting.md)

## Quick Start

```bash
# Install
pip install modelhop

# Run — shows setup guide, validates API keys, and gives you next steps
modelhop
```

That's it. Running `modelhop` with no arguments shows a welcome panel that:

- Validates your API keys against live provider endpoints
- Shows which providers are connected and which are missing
- Generates a default `modelhop.yaml` if one doesn't exist
- Gives you quick-start examples to try immediately

### Setup API Keys

Get at least one key from a free provider and set it before running `modelhop`:

| Provider | Key | Free Tier |
|----------|-----|-----------|
| Groq | [console.groq.com](https://console.groq.com) | Yes |
| Google Gemini | [aistudio.google.com](https://aistudio.google.com/apikey) | Yes |
| OpenAI | [platform.openai.com](https://platform.openai.com/api-keys) | Paid |

```bash
# Option 1: Interactive setup (recommended)
modelhop setup

# Option 2: Manual .env file
cp .env.example .env
# Edit .env with your keys
```

## Commands

| Command | Alias | Description |
|---------|-------|-------------|
| `modelhop` | - | Welcome guide — validate keys, show quick start |
| `modelhop route <query>` | `modelhop r` | Route a query to the cheapest capable model |
| `modelhop setup` | `modelhop set` | Interactive API key setup wizard |
| `modelhop init` | `modelhop i` | Generate default config file |
| `modelhop stats` | `modelhop s` | Show routing statistics |
| `modelhop history` | `modelhop h` | Show recent query history |
| `modelhop providers` | `modelhop p` | List available providers and models |
| `modelhop benchmark` | `modelhop b` | Run benchmark queries |
| `modelhop config` | `modelhop c` | Show current configuration |
| `modelhop example` | `modelhop e` | Show example usage |
| `modelhop shield` | - | Show quality monitoring status |
| `modelhop hub` | - | Show community hub configs |

## How It Works

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

**Multi-Signal Analysis:**
- Code keyword detection (algorithm, debugging, implementation)
- Query intent classification (explain, implement, debug, compare)
- Constraint detection (O(n), O(1), time/space complexity)
- Experience memory (past routing outcomes)
- Per-model performance tracking
- Adaptive confidence thresholds

**Fallback & Decomposition:**
- Provider failures cascade free → mid → premium (empty tiers are skipped, so
  free → premium works even with no mid model configured)
- `decompose_queries: true` (default) splits complex queries into sub-questions,
  routes each, and merges the answers

**Examples:**

```bash
# Simple query → Free model
modelhop r "What is Python?"
# Routes to: groq-qwen3-8-27b (FREE)

# Complex query → Premium model
modelhop r "Implement a red-black tree with O(log n) insertion"
# Routes to: openai-gpt-4 (PREMIUM)

# Failed premium → Automatic fallback
modelhop r "Complex query" # GPT-4 fails → falls back to Groq
```

## Cost Tracking

Every query shows cost savings:

```
╭────────────────────── Cost Analysis ──────────────────────╮
│ Actual cost:          $0.0000                             │
│ Would cost (GPT-4):  $0.0625                             │
│ You saved:            $0.0625 (100%)                      │
│ AMAZING SAVINGS                                           │
╰──────────────────────────────────────────────────────────╯
```

Savings are estimated with `estimate_cost()` and shown even when cost logging is
turned off. The `benchmark` command reports measured model quality (from heuristic
confidence checks), not pre-baked numbers.

## Verbose Mode

Add `--verbose` for full intelligence stats:

```bash
modelhop r "Implement quicksort" --verbose
```

Shows: feature extraction, AI analysis, experience memory, routing decision, hop score, and system intelligence stats.

## Configuration

ModelHop uses a `modelhop.yaml` config file. Generate the default with:

```bash
modelhop init
```

**Default models:**

| Model | Provider | Tier | Cost |
|-------|----------|------|------|
| `qwen/qwen3.8-27b` | Groq | Free | $0.00 |
| `gemini-3.6-flash` | Google | Free | $0.00 |
| `gpt-4` | OpenAI | Premium | $0.03/$0.06 per 1K |

Key routing option: `decompose_queries: true` (default) — complex queries are
split into sub-questions, routed independently, and merged. See
[Configuration](docs/config.md) for the full schema.

## Development

```bash
# Clone the repo
git clone https://github.com/aalok101singh/modelhop.git
cd modelhop

# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black modelhop/

# Lint
ruff check modelhop/
```

## Publishing

```bash
# Build
python -m build

# Upload to PyPI
twine upload dist/*
```

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Security

For security vulnerabilities, please see [SECURITY.md](SECURITY.md).

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

<p align="center">
  Made with love by <a href="https://github.com/aalok101singh">Aalok</a>
</p>
