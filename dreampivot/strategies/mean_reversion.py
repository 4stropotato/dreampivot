"""
Mean Reversion Strategy

Assumes price will revert to its mean (moving average).
Uses Bollinger Bands for entry/exit signals.

- BUY: Price touches lower band (oversold)
- SELL: Price touches upper band (overbought)
- HOLD: Price is within bands
"""

from typing import Any

import pandas as pd
import numpy as np

from .base import BaseStrategy, Signal, TradeSignal
from ..utils.logger import get_logger

logger = get_logger("strategy")


class MeanReversionStrategy(BaseStrategy):
    """
    Mean reversion strategy using Bollinger Bands.

    Signals:
    - BUY: Price at/below lower band + RSI oversold
    - SELL: Price at/above upper band + RSI overbought
    - HOLD: Price within bands
    """

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        self._name = "mean_reversion"

        # Bollinger Band parameters
        self.bb_period = self.params.get("bb_period", 20)
        self.bb_std = self.params.get("bb_std", 2.0)

        # RSI for confirmation
        self.rsi_period = self.params.get("rsi_period", 14)
        self.rsi_overbought = self.params.get("rsi_overbought", 70)
        self.rsi_oversold = self.params.get("rsi_oversold", 30)

    def required_history(self) -> int:
        """Need enough data for Bollinger Bands."""
        return self.bb_period + 10

    def analyze(self, df: pd.DataFrame, symbol: str) -> TradeSignal:
        """Generate trading signal from price data."""
        if len(df) < self.required_history():
            return TradeSignal(
                signal=Signal.HOLD,
                symbol=symbol,
                confidence=0.0,
                reason="Insufficient data",
            )

        # Calculate indicators
        close = df["close"]

        # Bollinger Bands
        sma = close.rolling(window=self.bb_period).mean()
        std = close.rolling(window=self.bb_period).std()
        upper_band = sma + (std * self.bb_std)
        lower_band = sma - (std * self.bb_std)

        # RSI
        rsi = self._calculate_rsi(close)

        # Get latest values
        current_price = close.iloc[-1]
        current_sma = sma.iloc[-1]
        current_upper = upper_band.iloc[-1]
        current_lower = lower_band.iloc[-1]
        current_rsi = rsi.iloc[-1]

        # Band width (volatility measure)
        band_width = (current_upper - current_lower) / current_sma * 100

        # Position within bands (0 = lower, 1 = upper)
        band_position = (current_price - current_lower) / (current_upper - current_lower)

        # Determine signal
        signal = Signal.HOLD
        confidence = 0.0
        reasons = []

        # RSI conditions
        rsi_oversold = current_rsi < self.rsi_oversold
        rsi_overbought = current_rsi > self.rsi_overbought
        rsi_very_oversold = current_rsi < 25
        rsi_very_overbought = current_rsi > 75

        # === BUY SIGNALS ===

        # Strong: Price below lower band + RSI oversold
        if current_price <= current_lower and rsi_oversold:
            signal = Signal.BUY
            confidence = 0.85
            reasons.append("Price at lower band + RSI oversold")

        # Medium: Price near lower band + RSI very oversold
        elif band_position < 0.1 and rsi_very_oversold:
            signal = Signal.BUY
            confidence = 0.75
            reasons.append("Price near lower band + RSI very oversold")

        # Weak: Price below lower band (no RSI confirm)
        elif current_price < current_lower:
            signal = Signal.BUY
            confidence = 0.60
            reasons.append("Price below lower band")

        # === SELL SIGNALS ===

        # Strong: Price above upper band + RSI overbought
        elif current_price >= current_upper and rsi_overbought:
            signal = Signal.SELL
            confidence = 0.85
            reasons.append("Price at upper band + RSI overbought")

        # Medium: Price near upper band + RSI very overbought
        elif band_position > 0.9 and rsi_very_overbought:
            signal = Signal.SELL
            confidence = 0.75
            reasons.append("Price near upper band + RSI very overbought")

        # Weak: Price above upper band (no RSI confirm)
        elif current_price > current_upper:
            signal = Signal.SELL
            confidence = 0.60
            reasons.append("Price above upper band")

        # === HOLD ===
        else:
            reasons.append("Price within bands")
            if band_position > 0.7:
                reasons.append("Near upper band (watching)")
            elif band_position < 0.3:
                reasons.append("Near lower band (watching)")

        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)

        reason_text = " | ".join(reasons)

        logger.debug(
            f"{symbol}: Price={current_price:.2f}, SMA={current_sma:.2f}, "
            f"RSI={current_rsi:.1f} -> {signal.value} ({confidence:.0%})"
        )

        return TradeSignal(
            signal=signal,
            symbol=symbol,
            confidence=confidence,
            reason=reason_text,
            metadata={
                "sma": current_sma,
                "upper_band": current_upper,
                "lower_band": current_lower,
                "band_width": band_width,
                "band_position": band_position,
                "rsi": current_rsi,
            },
        )

    def _calculate_rsi(self, prices: pd.Series) -> pd.Series:
        """Calculate RSI indicator."""
        delta = prices.diff()

        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.rolling(window=self.rsi_period, min_periods=1).mean()
        avg_loss = loss.rolling(window=self.rsi_period, min_periods=1).mean()

        # Avoid division by zero
        avg_loss = avg_loss.replace(0, np.nan)
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.fillna(50)
