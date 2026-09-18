"""Provider adapters with stubbed SDK clients (no network, no keys).

Covers BaseProvider._with_retries/stream and each provider's generate path
including tool passthrough, usage mapping, and validate_connection.
"""

from types import SimpleNamespace

import pytest

from modelhop.registry.providers.base import BaseProvider
from modelhop.registry.providers.gemini import GeminiProvider
from modelhop.registry.providers.groq import GroqProvider
from modelhop.registry.providers.openai import OpenAIProvider


class StubProvider(BaseProvider):
    def __init__(self, **kw):
        super().__init__("k", "m", **kw)

    async def generate(self, prompt, max_tokens=1000, temperature=0.7, **kwargs):
        from modelhop.core.models import ProviderResponse

        return ProviderResponse(
            content="y" * 500,
            model_used="m",
            provider="stub",
            tokens_in=1,
            tokens_out=1,
            latency_ms=1,
        )

    async def validate_connection(self) -> bool:
        return True


async def test_retry_transient_then_success():
    p = StubProvider(max_retries=2)
    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("429 rate limited, slow down")
        return "ok"

    assert await p._with_retries(flaky) == "ok"
    assert calls["n"] == 2


async def test_retry_auth_error_never_retried():
    p = StubProvider(max_retries=3)
    calls = {"n": 0}

    async def auth_fail():
        calls["n"] += 1
        raise RuntimeError("401 invalid api key")

    with pytest.raises(RuntimeError, match="401"):
        await p._with_retries(auth_fail)
    assert calls["n"] == 1


async def test_retry_exhausted_reraises():
    p = StubProvider(max_retries=1)
    calls = {"n": 0}

    async def always():
        calls["n"] += 1
        raise RuntimeError("503 overloaded, try later")

    with pytest.raises(RuntimeError, match="503"):
        await p._with_retries(always)
    assert calls["n"] == 2


async def test_stream_default_chunks_generate():
    p = StubProvider()
    chunks = [c async for c in p.stream("hi")]
    assert "".join(chunks) == "y" * 500
    assert len(chunks) == 3


def _chat_completion(content="hello world", prompt_tokens=5, completion_tokens=7):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


class _FakeCompletions:
    def __init__(self, response=None, exc=None):
        self.response = response if response is not None else _chat_completion()
        self.exc = exc
        self.last_kwargs = None

    async def create(self, **kw):
        self.last_kwargs = kw
        if self.exc:
            raise self.exc
        return self.response


class _FakeAsyncChatClient:
    def __init__(self, completions):
        self.chat = SimpleNamespace(completions=completions)


async def _check_openai_style(provider, completions, tools_expected=True):
    out = await provider.generate("hi there", tools=[{"type": "x"}] if tools_expected else None)
    assert out.content == "hello world"
    assert out.tokens_in == 5 and out.tokens_out == 7
    assert out.provider in ("groq", "openai")
    assert completions.last_kwargs["model"] == provider.model
    if tools_expected:
        assert completions.last_kwargs["tools"] == [{"type": "x"}]
    chunks = [c async for c in provider.stream("hi")]
    assert "".join(chunks) == "hello world"


async def test_groq_generate(monkeypatch):
    completions = _FakeCompletions()

    class FakeAsyncGroq:
        def __init__(self, api_key=None, timeout=None, max_retries=None):
            self.chat = SimpleNamespace(completions=completions)

    monkeypatch.setattr("modelhop.registry.providers.groq.AsyncGroq", FakeAsyncGroq)
    p = GroqProvider("k", model="llama-test", timeout_s=5, max_retries=1)
    await _check_openai_style(p, completions)
    assert await p.validate_connection() is True


async def test_openai_generate(monkeypatch):
    completions = _FakeCompletions()

    class FakeAsyncOpenAI:
        def __init__(self, api_key=None, timeout=None, max_retries=None):
            self.chat = SimpleNamespace(completions=completions)

    monkeypatch.setattr("modelhop.registry.providers.openai.AsyncOpenAI", FakeAsyncOpenAI)
    p = OpenAIProvider("k", model="gpt-test")
    await _check_openai_style(p, completions)
    assert p.model == "gpt-test"


async def test_anthropic_generate(monkeypatch):
    pytest.importorskip("anthropic")  # [anthropic] extra; skipped in CI dev job
    from modelhop.registry.providers.anthropic import AnthropicProvider

    captured = {}

    class FakeMessages:
        async def create(self, **kw):
            captured.update(kw)
            return SimpleNamespace(
                content=[SimpleNamespace(text="anthropic says hi")],
                usage=SimpleNamespace(input_tokens=3, output_tokens=4),
            )

    class FakeAsyncAnthropic:
        def __init__(self, api_key=None, timeout=None, max_retries=None):
            self.messages = FakeMessages()

    monkeypatch.setattr("modelhop.registry.providers.anthropic.AsyncAnthropic", FakeAsyncAnthropic)
    p = AnthropicProvider("k", model="claude-test")
    out = await p.generate("hi", tools=[{"type": "t"}])
    assert out.content == "anthropic says hi"
    assert out.tokens_in == 3 and out.tokens_out == 4
    assert out.provider == "anthropic"
    assert captured["tools"] == [{"type": "t"}]
    assert captured["model"] == "claude-test"
    chunks = [c async for c in p.stream("hi")]
    assert "".join(chunks) == "anthropic says hi"


async def test_gemini_generate(monkeypatch):
    captured = {}

    class FakeGenerationConfig:
        def __init__(self, **kw):
            captured.update(kw)

    class FakeModel:
        async def generate_content_async(self, prompt, generation_config=None):
            captured["prompt"] = prompt
            return SimpleNamespace(
                text="gemini says hi",
                usage_metadata=SimpleNamespace(prompt_token_count=2, candidates_token_count=3),
            )

    fake_genai = SimpleNamespace(
        configure=lambda api_key=None: None,
        GenerativeModel=lambda model: FakeModel(),
        types=SimpleNamespace(GenerationConfig=FakeGenerationConfig),
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("modelhop.registry.providers.gemini.genai", fake_genai)
    p = GeminiProvider("k", model="gemini-test")
    # v1.1 security: constructor must not mutate os.environ.
    import os

    assert "GEMINI_API_KEY" not in os.environ
    out = await p.generate("hi", tools=[{"type": "t"}])
    assert out.content == "gemini says hi"
    assert out.tokens_in == 2 and out.tokens_out == 3
    assert out.provider == "gemini"
    assert captured["tools"] == [{"type": "t"}]
    assert captured["prompt"] == "hi"
    chunks = [c async for c in p.stream("hi")]
    assert "".join(chunks) == "gemini says hi"


async def test_validate_connection_false_on_failure(monkeypatch):
    completions = _FakeCompletions(exc=RuntimeError("401 invalid api key"))

    class FakeAsyncGroq:
        def __init__(self, api_key=None, timeout=None, max_retries=None):
            self.chat = SimpleNamespace(completions=completions)

    monkeypatch.setattr("modelhop.registry.providers.groq.AsyncGroq", FakeAsyncGroq)
    p = GroqProvider("k", max_retries=0)
    assert await p.validate_connection() is False


def test_provider_defaults():
    assert GroqProvider.__init__.__defaults__[0] == "llama-3.1-8b-instant"
