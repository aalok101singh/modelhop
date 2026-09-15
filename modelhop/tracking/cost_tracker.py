import json
from pathlib import Path
from typing import List, Optional

from ..core.models import CostAnalysis, ModelConfig, ProviderResponse


def estimate_cost(response: ProviderResponse, model: ModelConfig) -> CostAnalysis:
    actual_cost = (response.tokens_in / 1000) * model.cost_per_1k_input + (
        response.tokens_out / 1000
    ) * model.cost_per_1k_output

    would_have_cost = (response.tokens_in / 1000) * CostTracker.GPT4_COST_PER_1K_INPUT + (
        response.tokens_out / 1000
    ) * CostTracker.GPT4_COST_PER_1K_OUTPUT

    savings = would_have_cost - actual_cost
    savings_percentage = (savings / would_have_cost * 100) if would_have_cost > 0 else 0

    return CostAnalysis(
        actual_cost=actual_cost,
        would_have_cost=would_have_cost,
        savings=savings,
        savings_percentage=savings_percentage,
        model_used=model.name,
        tier=model.tier.value,
    )


class CostTracker:
    GPT4_COST_PER_1K_INPUT = 0.03
    GPT4_COST_PER_1K_OUTPUT = 0.06

    def __init__(self, log_path: Optional[str] = None):
        self.log_path = Path(log_path) if log_path else Path("cost_log.json")
        self.history: List[CostAnalysis] = []
        self._load_existing()

    def _load_existing(self) -> None:
        if not self.log_path.exists():
            return
        try:
            with open(self.log_path, "r") as f:
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
                    )
                )
        except Exception:
            pass

    def calculate(self, response: ProviderResponse, model: ModelConfig) -> CostAnalysis:
        analysis = estimate_cost(response, model)

        self.history.append(analysis)
        self._log_cost(analysis)
        return analysis

    def _log_cost(self, analysis: CostAnalysis) -> None:
        try:
            if self.log_path.exists():
                with open(self.log_path, "r") as f:
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
                }
            )

            with open(self.log_path, "w") as f:
                json.dump(log, f, indent=2)
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
