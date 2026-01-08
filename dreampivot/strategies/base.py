"""
Base Strategy Interface

All strategies implement this for consistency.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

import pandas as pd


class Signal(Enum):
    """Trading signals."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class TradeSignal:
    """Complete trade signal with metadata."""
    signal: Signal
    symbol: str
    confidence: float  # 0.0 - 1.0
    reason: str
    metadata: dict[str, Any] | None = None


class BaseStrategy(ABC):
    """
    Base class for trading strategies.

    Strategies analyze price data and generate signals.
    """

    def __init__(self, params: dict[str, Any] | None = None):
        self.params = params or {}
        self._name = "base"

    @property
    def name(self) -> str:
        """Strategy name."""
        return self._name

    @abstractmethod
    def analyze(self, df: pd.DataFrame, symbol: str) -> TradeSignal:
        """
        Analyze price data and generate signal.

        Args:
            df: DataFrame with OHLCV data (index=timestamp)
            symbol: Trading pair symbol

        Returns:
            TradeSignal with buy/sell/hold recommendation
        """
        pass

    def required_history(self) -> int:
        """Minimum number of candles needed for analysis."""
        return 50
