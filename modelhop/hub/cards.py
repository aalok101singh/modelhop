"""Community PerformanceCard publisher (v1.1 W4).

k-anonymized aggregate cards only; never raw query text or features.
Allowlist serializer hard-blocks text/features. Signed cards seed bandit priors.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from collections import defaultdict
from typing import Dict, List, Optional

from ..core.models import PerformanceCard

K_MIN = 5
_FORBIDDEN = {"query", "query_text", "text", "features", "feature_vector", "prompt", "response"}


def allowlist_card(data: dict) -> dict:
    allowed = {
        "schema_version",
        "model",
        "query_type",
        "sample_count",
        "avg_quality",
        "avg_latency_ms",
        "fallback_rate",
        "region",
        "mac",
    }
    out = {k: v for k, v in data.items() if k in allowed}
    for bad in _FORBIDDEN:
        out.pop(bad, None)
    return out


def _key() -> bytes:
    env = os.environ.get("MODELHOP_STATE_KEY", "")
    return env.encode() if env else b"modelhop-community"


def sign_card(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hmac.new(_key(), canonical.encode(), hashlib.sha256).hexdigest()


def verify_card(card: PerformanceCard) -> bool:
    payload = {
        "schema_version": card.schema_version,
        "model": card.model,
        "query_type": card.query_type,
        "sample_count": card.sample_count,
        "avg_quality": card.avg_quality,
        "avg_latency_ms": card.avg_latency_ms,
        "fallback_rate": card.fallback_rate,
        "region": card.region,
    }
    expected = sign_card(payload)
    try:
        return hmac.compare_digest(expected, card.mac or "")
    except Exception:
        return False


def publish_cards(
    experiences, k: int = K_MIN, region: Optional[str] = None
) -> List[PerformanceCard]:
    """Aggregate experiences into k-anonymized cards. Refuses groups below K."""
    groups: Dict[tuple, list] = defaultdict(list)
    for exp in experiences:
        qtype = getattr(exp.query_type, "value", str(exp.query_type))
        groups[(exp.model_name, qtype)].append(exp)
    cards: List[PerformanceCard] = []
    for (model, qtype), items in groups.items():
        if len(items) < k:
            continue
        avg_q = sum(e.response_quality for e in items) / len(items)
        avg_lat = int(sum(e.latency_ms for e in items) / len(items))
        fb = sum(1 for e in items if e.fallback_used) / len(items)
        payload = {
            "schema_version": 1,
            "model": model,
            "query_type": qtype,
            "sample_count": len(items),
            "avg_quality": avg_q,
            "avg_latency_ms": avg_lat,
            "fallback_rate": fb,
            "region": region,
        }
        payload = allowlist_card(payload)
        payload["mac"] = sign_card(payload)
        cards.append(PerformanceCard(**payload))
    return cards
