"""Verifier plugins: schema, grounding, consistency, code, custom, rubric, pipeline."""

from modelhop.core.models import VerifierResult
from modelhop.core.verifier.base import VerifierPipeline
from modelhop.core.verifier.code import CodeVerifier
from modelhop.core.verifier.consistency import ConsistencyVerifier
from modelhop.core.verifier.custom import CustomVerifier
from modelhop.core.verifier.grounding import GroundingVerifier
from modelhop.core.verifier.rubric import RubricVerifier
from modelhop.core.verifier.schema import SchemaVerifier


def test_pipeline_empty_passes():
    out = VerifierPipeline().verify("q", "r")
    assert out.passed is True and out.verifier_name == "pipeline"


def test_pipeline_short_circuits_on_first_failure():
    good = SchemaVerifier(pattern="hello")
    bad = SchemaVerifier(pattern="zzz-no-match")
    pipe = VerifierPipeline([good, bad])
    out = pipe.verify("q", "hello world")
    assert out.passed is False
    assert out.verifier_name == "schema"
    assert "schema" in out.details


def test_pipeline_fail_closed_on_crash():
    class Boom:
        name = "boom"

        def verify(self, q, r, ctx=None):
            raise RuntimeError("kaput")

    out = VerifierPipeline([Boom()]).verify("q", "r")
    assert out.passed is False
    assert out.details["error"] == "kaput"


def test_schema_json_and_pattern():
    v = SchemaVerifier(require_json=True)
    assert v.verify("q", '{"a": 1}').passed is True
    out = v.verify("q", "not json")
    assert out.passed is False and out.details["reason"] == "invalid json"
    v2 = SchemaVerifier(pattern=r"\d+")
    assert v2.verify("q", "abc 123").passed is True
    assert v2.verify("q", "no digits").details["reason"] == "pattern mismatch"
    # ctx override wins over constructor.
    assert v2.verify("q", "no digits", {"pattern": r"\w+"}).passed is True


def test_grounding_overlap():
    v = GroundingVerifier(min_overlap=0.2)
    assert v.verify("q", "anything").passed is True  # no context: vacuous pass
    ctx = {"context": "the quick brown fox jumps over the lazy dog"}
    out = v.verify("q", "quick brown fox", ctx)
    assert out.passed is True and out.score > 0.5
    out = v.verify("q", "totally unrelated zebra quantum", ctx)
    assert out.passed is False
    out = v.verify("q", "", ctx)
    assert out.passed is False and out.details["reason"] == "empty"


def test_consistency_jaccard():
    v = ConsistencyVerifier()
    assert v.verify("q", "anything").passed is True  # no other: vacuous pass
    same = "the cat sat on the mat"
    out = v.verify("q", same, {"other_response": same})
    assert out.passed is True and out.score == 1.0
    out = v.verify("q", "apples oranges bananas", {"other_response": "cars trains planes"})
    assert out.passed is False
    out = v.verify("q", "", {"other_response": "something"})
    assert out.passed is False


def test_code_verifier():
    v = CodeVerifier()
    assert v.verify("q", "x = 1\nprint(x)").passed is True
    assert v.verify("q", "```python\ndef f():\n    return 1\n```").passed is True
    out = v.verify("q", "def broken(:\n  ???")
    assert out.passed is False


def test_custom_verifier_shapes():
    assert CustomVerifier(lambda q, r, c: True).verify("q", "r").passed is True
    out = CustomVerifier(lambda q, r, c: (True, 0.7)).verify("q", "r")
    assert out.passed is True and out.score == 0.7
    out = CustomVerifier(lambda q, r, c: False).verify("q", "r")
    assert out.passed is False and out.score == 0.0
    vr = VerifierResult(verifier_name="x", passed=True, score=0.9)
    assert CustomVerifier(lambda q, r, c: vr).verify("q", "r").score == 0.9
    assert CustomVerifier(lambda q, r, c: True, name="mine").name == "mine"


class _Judge:
    def __init__(self, content=None, exc=None):
        self._content = content
        self._exc = exc

    async def generate(self, prompt, max_tokens=150, temperature=0.1):
        if self._exc:
            raise self._exc
        from types import SimpleNamespace

        return SimpleNamespace(content=self._content)


async def test_rubric_sync_skips():
    out = RubricVerifier().verify("q", "r")
    assert out.passed is True


async def test_rubric_no_provider_skips():
    out = await RubricVerifier().averify("q", "r")
    assert out.passed is True


async def test_rubric_judge_pass_and_fail():
    ok = await RubricVerifier(provider=_Judge('{"pass": true, "score": 0.9}')).averify("q", "r")
    assert ok.passed is True and ok.score == 0.9
    bad = await RubricVerifier(provider=_Judge('{"pass": false, "score": 0.1}')).averify("q", "r")
    assert bad.passed is False


async def test_rubric_unparseable_and_error():
    out = await RubricVerifier(provider=_Judge("definitely not json")).averify("q", "r")
    assert out.passed is False
    out = await RubricVerifier(provider=_Judge(exc=RuntimeError("down"))).averify("q", "r")
    assert out.passed is False and "error" in out.details


async def test_rubric_threshold_ctx_async():
    out = await RubricVerifier(provider=_Judge('{"score": 0.5}')).averify(
        "q", "r", {"threshold": 0.4}
    )
    assert out.passed is True
