# Python SDK

ModelHop can be used as a Python library from anywhere, not just the CLI.

## Install

```bash
pip install modelhop
```

Requires Python 3.9+.

## Minimal Example

```python
import asyncio

from modelhop import ModelHop


async def main():
    modelhop = ModelHop()

    response = await modelhop.route("Explain the difference between SQL and NoSQL")
    print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
```

`ModelHop().__init__(config_path=None)` loads `modelhop.yaml` from the current
directory when present, otherwise falls back to the built-in default config.

## Response Object

`route(query: str) -> ProviderResponse` returns a Pydantic model with fields:

| Field | Type | Description |
|-------|------|-------------|
| `content` | `str` | The generated answer |
| `model_used` | `str` | Name of the model that produced it |
| `provider` | `str` | Provider name (groq / gemini / openai / ...) |
| `tokens_in` | `int` | Input token count |
| `tokens_out` | `int` | Output token count |

## Error Handling

`route()` never raises for a single provider failure — it falls back across tiers.
If every provider fails on every attempt, it raises a `RuntimeError`.

```python
try:
    response = await modelhop.route("...")
except RuntimeError as exc:
    print("All models failed:", exc)
```

## Cost Estimation

`estimate_cost(response, model)` returns the estimated USD cost of a response
without needing a configured cost tracker:

```python
from modelhop.tracking.cost_tracker import estimate_cost

cost = estimate_cost(response, model)
print(f"${cost:.6f}")
```

## Async Only

All I/O methods are async (`route`, analyze, etc.). Call them from an asyncio
event loop, or wrap with `asyncio.run()` as shown above.