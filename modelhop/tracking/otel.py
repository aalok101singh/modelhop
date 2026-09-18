"""OpenTelemetry spans + modelhop.* attributes (v1.1 W2). Configurable OTLP exporter."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Optional

_tracer = None
_provider_set = False


def _get_tracer():
    global _tracer, _provider_set
    if _tracer is not None:
        return _tracer
    try:
        from opentelemetry import trace as _trace  # type: ignore
        from opentelemetry.sdk.resources import Resource  # type: ignore
        from opentelemetry.sdk.trace import TracerProvider  # type: ignore

        if not _provider_set:
            endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
            resource = Resource.create({"service.name": "modelhop"})
            provider = TracerProvider(resource=resource)
            if endpoint:
                try:
                    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # type: ignore
                        OTLPSpanExporter,
                    )
                    from opentelemetry.sdk.trace.export import BatchSpanProcessor  # type: ignore

                    provider.add_span_processor(
                        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
                    )
                except Exception:
                    pass
            try:
                _trace.set_tracer_provider(provider)
            except Exception:
                pass
            _provider_set = True
        _tracer = _trace.get_tracer("modelhop")
        return _tracer
    except Exception:
        return None


@contextmanager
def span(name: str, attributes: Optional[dict] = None):
    tracer = _get_tracer()
    if tracer is None:
        yield None
        return
    try:
        with tracer.start_as_current_span(name) as s:
            if attributes:
                for k, v in attributes.items():
                    try:
                        s.set_attribute(k, v)
                    except Exception:
                        pass
            yield s
    except Exception:
        yield None


def record_route(
    query: str, model: str, confidence: float, cost: float, degraded: bool = False
) -> None:
    with span(
        "modelhop.route",
        {
            "modelhop.model": str(model),
            "modelhop.confidence": float(confidence or 0.0),
            "modelhop.cost": float(cost or 0.0),
            "modelhop.degraded": bool(degraded),
            "modelhop.query_len": len(query or ""),
        },
    ):
        pass
