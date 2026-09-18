import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from ..core.models import CostAnalysis, ModelConfig, ProviderResponse
from ..core.persistence import atomic_write_json


class PriceBook:
    """Versioned price book (rates plus price_effective_date)."""

    VERSION = 1

    def __init__(
        self,
        rates: Optional[dict] = None,
        effective_date: Optional[str] = None,
        reference: str = "max",
    ):
        # rates: {model_name: (in_per_1k, out_per_1k)}
        self.rates: dict = dict(rates or {})
        self.effective_date = effective_date or datetime.now(timezone.utc).date().isoformat()
        self.reference = reference

    @classmethod
    def from_models(cls, models: List[ModelConfig], reference: str = "max") -> "PriceBook":
        rates = {m.name: (m.cost_per_1k_input, m.cost_per_1k_output) for m in models}
        dates = [m.price_effective_date for m in models if m.price_effective_date]
        effective = max(dates) if dates else datetime.now(timezone.utc).date().isoformat()
        return cls(rates=rates, effective_date=effective, reference=reference)

    def to_dict(self) -> dict:
        return {
            "version": self.VERSION,
            "effective_date": self.effective_date,
            "reference": self.reference,
            "rates": self.rates,
        }

    def baseline_model_name(self, models: List[ModelConfig]) -> str:
        if not models:
            return "gpt-4"
        if self.reference != "max":
            # explicit model name reference
            for m in models:
                if m.name == self.reference or m.model == self.reference:
                    return m.name
            return models[0].name
        # "max": most expensive configured model
        best = max(models, key=lambda m: (m.cost_per_1k_input + m.cost_per_1k_output, m.name))
        return best.name

    def baseline_rates(self, models: List[ModelConfig]) -> tuple[str, float, float]:
        name = self.baseline_model_name(models)
        for m in models:
            if m.name == name:
                return name, m.cost_per_1k_input, m.cost_per_1k_output
        # Fallback to legacy GPT-4 reference when no models configured.
        return "gpt-4", CostTracker.GPT4_COST_PER_1K_INPUT, CostTracker.GPT4_COST_PER_1K_OUTPUT


def estimate_cost(
    response: ProviderResponse,
    model: ModelConfig,
    price_book: Optional[PriceBook] = None,
    all_models: Optional[List[ModelConfig]] = None,
) -> CostAnalysis:
    actual_cost = (response.tokens_in / 1000) * model.cost_per_1k_input + (
        response.tokens_out / 1000
    ) * model.cost_per_1k_output

    if price_book is not None and all_models:
        baseline_name, base_in, base_out = price_book.baseline_rates(all_models)
    else:
        baseline_name, base_in, base_out = (
            "gpt-4",
            CostTracker.GPT4_COST_PER_1K_INPUT,
            CostTracker.GPT4_COST_PER_1K_OUTPUT,
        )

    would_have_cost = (response.tokens_in / 1000) * base_in + (
        response.tokens_out / 1000
    ) * base_out

    savings = would_have_cost - actual_cost
    savings_percentage = (savings / would_have_cost * 100) if would_have_cost > 0 else 0

    return CostAnalysis(
        actual_cost=actual_cost,
        would_have_cost=would_have_cost,
        savings=savings,
        savings_percentage=savings_percentage,
        model_used=model.name,
        tier=model.tier.value,
        baseline_model=baseline_name,
        aux_calls=0,
        aux_cost=0.0,
        tokens_in=int(getattr(response, "tokens_in", 0) or 0),
        tokens_out=int(getattr(response, "tokens_out", 0) or 0),
    )


class CostTracker:
    GPT4_COST_PER_1K_INPUT = 0.03
    GPT4_COST_PER_1K_OUTPUT = 0.06

    def __init__(
        self,
        log_path: Optional[str] = None,
        price_book: Optional[PriceBook] = None,
        all_models: Optional[List[ModelConfig]] = None,
        cost_savings_reference: str = "max",
    ):
        self.log_path = Path(log_path) if log_path else Path("cost_log.json")
        self.history: List[CostAnalysis] = []
        self.aux_calls = 0
        self.aux_cost_total = 0.0
        self.price_book = price_book
        self.all_models: List[ModelConfig] = list(all_models or [])
        self.cost_savings_reference = cost_savings_reference
        if self.price_book is None and self.all_models:
            self.price_book = PriceBook.from_models(
                self.all_models, reference=cost_savings_reference
            )
        self._load_existing()

    def _effective_book(self) -> Optional[PriceBook]:
        if self.price_book is not None and self.all_models:
            return self.price_book
        if self.all_models:
            return PriceBook.from_models(self.all_models, reference=self.cost_savings_reference)
        return self.price_book

    def _load_existing(self) -> None:
        if not self.log_path.exists():
            return
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                log = json.load(f)
            for entry in log.get("entries", []):
                self.history.append(
                    CostAnalysis(
                        actual_cost=entry["actual_cost"],
                        would_have_cost=entry["would_have_cost"],
                        savings=entry["savings"],
                        savings_percentage=(
                            (entry["savings"] / entry["would_have_cost"] * 100)
                            if entry["would_have_cost"] > 0
                            else 0
                        ),
                        model_used=entry["model"],
                        tier=entry["tier"],
                        baseline_model=entry.get("baseline_model", ""),
                        aux_calls=int(entry.get("aux_calls", 0)),
                        aux_cost=float(entry.get("aux_cost", 0.0)),
                        tokens_in=int(entry.get("tokens_in", 0) or 0),
                        tokens_out=int(entry.get("tokens_out", 0) or 0),
                    )
                )
        except Exception:
            pass

    def record_aux(self, provider: str, response: ProviderResponse) -> None:
        """Aggregate auxiliary (non-routing-decision) call counts and cost."""
        # Resolve the model config for this aux response if known.
        model = None
        for m in self.all_models:
            if m.name == response.model_used or m.model == response.model_used:
                model = m
                break
        if model is None:
            # Unknown aux model: cost unknown, count only.
            self.aux_calls += 1
            return
        base = estimate_cost(
            response, model, price_book=self._effective_book(), all_models=self.all_models or None
        )
        self.aux_calls += 1
        self.aux_cost_total += base.actual_cost

    def calculate(
        self,
        response: ProviderResponse,
        model: ModelConfig,
        extra_actual: float = 0.0,
        extra_would: float = 0.0,
        extra_aux_calls: int = 0,
    ) -> CostAnalysis:
        book = self._effective_book()
        base = estimate_cost(response, model, price_book=book, all_models=self.all_models or None)
        total_actual = base.actual_cost + extra_actual
        total_would = base.would_have_cost + extra_would
        savings = total_would - total_actual
        # Single counting point: this call's aux feeds the lifetime totals
        # once, and the analysis carries per-route (not cumulative) aux.
        new_count = int(extra_aux_calls or 0)
        new_cost = float(extra_actual or 0.0)
        self.aux_calls += new_count
        self.aux_cost_total += new_cost

        analysis = CostAnalysis(
            actual_cost=total_actual,
            would_have_cost=total_would,
            savings=savings,
            savings_percentage=(savings / total_would * 100) if total_would > 0 else 0,
            model_used=model.name,
            tier=model.tier.value,
            baseline_model=base.baseline_model,
            aux_calls=new_count,
            aux_cost=new_cost,
            tokens_in=int(getattr(response, "tokens_in", 0) or 0),
            tokens_out=int(getattr(response, "tokens_out", 0) or 0),
        )

        self.history.append(analysis)
        self._log_cost(analysis)
        return analysis

    def _log_cost(self, analysis: CostAnalysis) -> None:
        try:
            if self.log_path.exists():
                with open(self.log_path, "r", encoding="utf-8") as f:
                    log = json.load(f)
            else:
                log = {"total_cost": 0, "total_savings": 0, "entries": []}

            log["total_cost"] = sum(c.actual_cost for c in self.history)
            log["total_savings"] = sum(c.savings for c in self.history)
            log["entries"].append(
                {
                    "model": analysis.model_used,
                    "tier": analysis.tier,
                    "actual_cost": analysis.actual_cost,
                    "would_have_cost": analysis.would_have_cost,
                    "savings": analysis.savings,
                    "baseline_model": analysis.baseline_model,
                    "aux_calls": analysis.aux_calls,
                    "aux_cost": analysis.aux_cost,
                    "tokens_in": analysis.tokens_in,
                    "tokens_out": analysis.tokens_out,
                }
            )

            atomic_write_json(str(self.log_path), log)
        except Exception:
            pass

    def get_summary(self) -> dict:
        if not self.history:
            return {"total_cost": 0, "total_savings": 0, "savings_percentage": 0, "query_count": 0}

        total_cost = sum(c.actual_cost for c in self.history)
        total_savings = sum(c.savings for c in self.history)
        total_would_have = sum(c.would_have_cost for c in self.history)

        return {
            "total_cost": total_cost,
            "total_savings": total_savings,
            "savings_percentage": (
                (total_savings / total_would_have * 100) if total_would_have > 0 else 0
            ),
            "query_count": len(self.history),
        }
