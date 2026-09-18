<p align="center">
  <img src="https://img.shields.io/badge/%F0%9F%90%B8-ModelHop-green?style=for-the-badge&logo=python&logoColor=white" alt="ModelHop Frog"/>
</p>

<h1 align="center">
  <br>
  🐸 ModelHop
  <br>
</h1>

<h4 align="center">Stop overpaying for AI. Every query hops to the cheapest model that can handle it.</h4>

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

<p align="center">
  <b>CLI</b> · <b>Python SDK</b> · <b>OpenAI-compatible server</b> — one brain, many bodies 🐸
</p>

---

Asking GPT-4 "what is Python?" is like taking a taxi to your mailbox. **ModelHop routes each query to the cheapest model capable of answering it** — free models for the easy stuff, premium muscle only when it earns its keep — and shows you exactly what you saved on every single call.

```
$ modelhop r "What is Python?"

  🎯 Routed to groq-qwen3-8-27b 🆓 FREE

  💸 Cost Analysis
  💰 Actual cost:               $0.0000
  ❌ Would cost (openai-gpt-4):  $0.0010
  ✨ You saved:                 $0.0010 (100%)
  🎉 AMAZING SAVINGS
```

## Start hopping in 60 seconds 🐸

**1. Install**
```bash
pip install modelhop
```

**2. Add one free key** — grab one at [console.groq.com](https://console.groq.com) or [aistudio.google.com](https://aistudio.google.com/apikey), then:
```bash
modelhop init     # creates modelhop.yaml, then offers to run setup
modelhop setup    # paste your key; broken models get tested alternatives
```

**3. Route your first query**
```bash
modelhop r "How do I reset my password?"
modelhop stats    # lifetime savings, hop score, latency
```

That's it. No config editing, no SDK keys to juggle — if a provider renames a model or your key lacks access, setup tells you the real reason and offers a working alternative.

## Three ways to hop — pick yours 🐸

| | 🖥️ CLI | 🐍 Python SDK | 🌐 Server |
|---|---|---|---|
| **Use it for** | Daily questions, quick checks | Your app or agent | Any framework, any language |
| **Install** | `pip install modelhop` | `pip install modelhop` | `pip install "modelhop[server]"` |
| **First run** | `modelhop r "hi"` | `await ModelHop().route("hi")` | `modelhop serve` → `model="auto"` |
| **Best at** | Zero-friction routing + savings dashboard | Budgets, trust rules, tool context per call | Drop-in OpenAI-compatible endpoint |

**CLI** — beautiful terminal output with cost panels, hop scores, token counts, and `--json` for scripts:
```bash
modelhop r "Implement quicksort" --verbose   # full routing rationale
modelhop r "Summarize this log" --json       # machine-readable + tokens
modelhop providers                           # live status with real failure reasons
```

**Python SDK** — async-first, same brain as the CLI:
```python
import asyncio
from modelhop import ModelHop

async def main():
    mh = ModelHop()
    r = await mh.route(
        "Explain SQL vs NoSQL",
        budget=0.05,                      # hard spend cap for this task
        trust_required={"zdr": True},     # hard privacy constraint
    )
    print(r.response)                     # the answer
    print(r.model, r.cost.savings)        # where it went, what you saved
    print(mh.explain(r))                  # one-line why

asyncio.run(main())
```

**Server** — point any OpenAI client at it, change nothing else:
```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="not-needed-locally")
client.chat.completions.create(model="auto", messages=[{"role": "user", "content": "hi"}])
```
Streaming, `/v1/models`, optional Bearer auth (`MODELHOP_API_KEY`), rate limits and body caps included.

## Why frogs hop smarter 🐸

- **🧠 Cheapest *capable* model, every time** — multi-signal analysis (intent, complexity, code cues, constraints) plus experience memory picks the tier; premium models only fire when the query earns it.
- **💰 Savings on every call** — actual vs would-have cost, tokens in/out, and a hop score, printed per query and aggregated in `stats` (lifetime totals, `--reset` to clear).
- **🛡️ Fail-closed by default** — low-confidence answers pin to the safest fallback and say so (`degraded - low confidence…`, never silent); cascade fallback rides through provider outages.
- **📚 Self-improving** — outcomes feed a contextual bandit + adaptive confidence threshold; calibration, shadow→canary rollouts, and drift auto-rollback keep it honest.
- **🔍 Auditable** — hash-chained signed ledger, JSONL traces, quality shield, OTel spans. Your keys never touch logs or traces.
- **🤖 Agent-ready** — MCP tool hook (`mcp_tool_hook`), LlamaIndex wrapper (`pip install "modelhop[llamaindex]"`), task budgets, session pinning, and trust policies.
- **🔌 Honest wiring** — setup probes live endpoints and reports the *real* error (bad key? no credits? model retired?) instead of "check your key", then offers tested replacements.

## Providers 🐸

| Model | Provider | Tier | Cost |
|-------|----------|------|------|
| `qwen/qwen3.8-27b` | Groq | 🆓 Free | $0.00 |
| `gemini-3.6-flash` | Google | 🆓 Free | $0.00 |
| `gpt-4` | OpenAI | 👑 Premium | $0.03 / $0.06 per 1K tokens |

Free tier covers everyday questions; complex reasoning and code escalate to premium automatically. No mid tier? Fallback skips straight from free to premium. OpenAI needs prepaid billing credits before any of its models respond — setup will tell you exactly that.

## Commands at a glance 🐸

| Command | Alias | What it does |
|---------|-------|--------------|
| `modelhop` | – | Welcome guide — validates keys live, shows next steps |
| `modelhop route <query>` | `r` | Route a query (`--json`, `--verbose`, `--model`) |
| `modelhop setup` | `set` | Interactive key wizard with model fallback |
| `modelhop init` | `i` | Generate `modelhop.yaml` |
| `modelhop stats` | `s` | Lifetime stats (`--reset` to clear) |
| `modelhop history` | `h` | Recent routing decisions (+ tokens in JSON) |
| `modelhop providers` | `p` | Provider status with honest failure reasons |
| `modelhop benchmark` | `b` | Cost comparison test |
| `modelhop config` | `c` | Show current configuration |
| `modelhop example` | `e` | Example queries |
| `modelhop cheat` | – | Quick reference card |
| `modelhop shield` | – | Quality monitoring status |
| `modelhop hub` | – | Community configs |
| `modelhop eval` | – | Offline eval + drift check |
| `modelhop calibrate` | – | Confidence calibration |
| `modelhop serve` | – | OpenAI-compatible HTTP server |

Piped output stays clean everywhere: no ANSI colors, ASCII frames, and emoji stripped when stdout isn't a terminal (plus `NO_COLOR` / `MODELHOP_PLAIN=1` support).

## Documentation 🐸

- [How routing works](docs/index.md) — pipeline, behaviors, CLI reference
- [Python SDK](docs/sdk.md) — response object, budgets, trust, errors
- [Configuration](docs/config.md) — full `modelhop.yaml` schema
- [Troubleshooting](docs/troubleshooting.md) — setup failures, stats, hop score, `degraded`

## Development 🐸

```bash
git clone https://github.com/aalok101singh/modelhop.git
cd modelhop
pip install -e ".[dev,server]"

pytest --cov=modelhop --cov-fail-under=60   # 255 tests, hermetic (no live keys needed)
ruff check modelhop/ tests/
black --check modelhop/ tests/
```

## Contributing 🐸

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License 🐸

MIT License — see [LICENSE](LICENSE) for details.

## Security 🐸

Found a vulnerability? Please see [SECURITY.md](SECURITY.md) — don't open a public issue.

## Changelog 🐸

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

<p align="center">
  🐸 Made with love by <a href="https://github.com/aalok101singh">Aalok</a> — hop smart, pay less.
</p>
