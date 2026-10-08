"""Personalization from explicit ratings; no Telegram entry points."""
from .service import RecommendationService
from .types import Recommendation, RecommendationResult

__all__ = ["RecommendationService", "Recommendation", "RecommendationResult"]
