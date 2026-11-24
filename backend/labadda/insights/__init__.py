"""Console insights: feature momentum over weeks and request performance over a period."""

from .performance import SPANS, Span, build_performance
from .trends import HORIZONS, build_trends

__all__ = ["HORIZONS", "SPANS", "Span", "build_performance", "build_trends"]
