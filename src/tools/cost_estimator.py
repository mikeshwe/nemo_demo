"""GPU Cost Estimator Tool"""
from src.tools.base import BaseTool

class CostEstimator(BaseTool):
    """Estimate GPU inference costs for different model sizes"""

    # Mock pricing per 1M tokens (example rates)
    PRICING_TABLE = {
        "small": {
            "price_per_1m_tokens": 0.20,
            "gpu_type": "NVIDIA A10",
            "typical_models": "7B parameter models"
        },
        "medium": {
            "price_per_1m_tokens": 0.50,
            "gpu_type": "NVIDIA A100",
            "typical_models": "13B-70B parameter models"
        },
        "large": {
            "price_per_1m_tokens": 1.50,
            "gpu_type": "NVIDIA H100",
            "typical_models": "70B-180B parameter models"
        },
        "xlarge": {
            "price_per_1m_tokens": 3.00,
            "gpu_type": "NVIDIA H100 x4",
            "typical_models": "340B+ parameter models"
        }
    }

    @property
    def name(self):
        return "cost_estimator"

    @property
    def description(self):
        return "Estimate GPU inference costs for different model sizes and usage patterns. Provides monthly cost estimates based on token usage."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {
                "model_size": {
                    "type": "string",
                    "enum": ["small", "medium", "large", "xlarge"],
                    "description": "Model size category (small: 7B, medium: 13B-70B, large: 70B-180B, xlarge: 340B+)"
                },
                "tokens_per_month": {
                    "type": "integer",
                    "description": "Expected monthly token usage (input + output tokens)"
                }
            },
            "required": ["model_size", "tokens_per_month"]
        }

    def execute(self, model_size, tokens_per_month):
        """Calculate cost estimate

        Args:
            model_size: Size category (small/medium/large/xlarge)
            tokens_per_month: Monthly token usage

        Returns:
            dict with success, data (cost breakdown), and error fields
        """
        try:
            if model_size not in self.PRICING_TABLE:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Invalid model_size: {model_size}. Must be one of: {list(self.PRICING_TABLE.keys())}"
                }

            if tokens_per_month < 0:
                return {
                    "success": False,
                    "data": None,
                    "error": "tokens_per_month must be a positive number"
                }

            pricing = self.PRICING_TABLE[model_size]
            cost_per_million = pricing["price_per_1m_tokens"]
            monthly_cost = (tokens_per_month / 1_000_000) * cost_per_million

            return {
                "success": True,
                "data": {
                    "model_size": model_size,
                    "gpu_type": pricing["gpu_type"],
                    "typical_models": pricing["typical_models"],
                    "tokens_per_month": tokens_per_month,
                    "cost_per_1m_tokens_usd": cost_per_million,
                    "estimated_monthly_cost_usd": round(monthly_cost, 2),
                    "breakdown": {
                        "daily_cost_usd": round(monthly_cost / 30, 2),
                        "yearly_cost_usd": round(monthly_cost * 12, 2)
                    },
                    "pricing_version": "2025-Q1",
                    "note": "These are estimated costs. Actual pricing may vary based on deployment configuration and volume discounts."
                },
                "error": None
            }

        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }
