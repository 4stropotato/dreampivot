"""
Momentum Strategy

Enhanced momentum-based trading:
- Uses MACD for trend direction and crossovers
- Uses RSI for overbought/oversold conditions
- Adds trend strength detection
- Multiple signal conditions for more opportunities
"""

from typing import Any

import pandas as pd
import numpy as np

from .base import BaseStrategy, Signal, TradeSignal
from ..utils.logger import get_logger

logger = get_logger("strategy")


class MomentumStrategy(BaseStrategy):
    """
    Momentum-based trading strategy.

    Signals:
    - BUY: MACD bullish crossover + RSI not overbought
    - SELL: MACD bearish crossover + RSI not oversold
    - HOLD: Unclear signals or neutral market
    """

    def __init__(self, params: dict[str, Any] | None = None):
        super().__init__(params)
        self._name = "momentum"

        # MACD parameters
        self.fast_period = self.params.get("fast_period", 12)
        self.slow_period = self.params.get("slow_period", 26)
        self.signal_period = self.params.get("signal_period", 9)

        # RSI parameters
        self.rsi_period = self.params.get("rsi_period", 14)
        self.rsi_overbought = self.params.get("rsi_overbought", 70)
        self.rsi_oversold = self.params.get("rsi_oversold", 30)

        # Trend filter (EMA)
        self.trend_period = self.params.get("trend_period", 50)

    def required_history(self) -> int:
        """Need enough data for trend EMA."""
        return max(self.trend_period, self.slow_period + self.signal_period) + 10

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

        # MACD
        macd_line, signal_line, histogram = self._calculate_macd(close)

        # RSI
        rsi = self._calculate_rsi(close)

        # Trend EMA
        trend_ema = close.ewm(span=self.trend_period, adjust=False).mean()

        # Get latest values
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]
        current_histogram = histogram.iloc[-1]
        prev_histogram = histogram.iloc[-2]
        current_rsi = rsi.iloc[-1]
        current_price = close.iloc[-1]
        current_trend_ema = trend_ema.iloc[-1]

        # Trend direction
        uptrend = current_price > current_trend_ema
        downtrend = current_price < current_trend_ema

        # Determine signal
        signal = Signal.HOLD
        confidence = 0.0
        reasons = []

        # MACD crossover detection
        macd_bullish_cross = current_histogram > 0 and prev_histogram <= 0
        macd_bearish_cross = current_histogram < 0 and prev_histogram >= 0

        # MACD trend conditions
        macd_bullish = current_histogram > 0
        macd_bearish = current_histogram < 0
        macd_strengthening = abs(current_histogram) > abs(prev_histogram)

        # RSI conditions
        rsi_oversold = current_rsi < self.rsi_oversold
        rsi_overbought = current_rsi > self.rsi_overbought
        rsi_very_oversold = current_rsi < 25
        rsi_very_overbought = current_rsi > 75

        # === BUY SIGNALS (only in uptrend or neutral) ===

        # Strong: MACD crossover in uptrend
        if macd_bullish_cross and uptrend and not rsi_overbought:
            signal = Signal.BUY
            confidence = 0.85
            reasons.append("MACD bullish crossover + uptrend")
            if rsi_oversold:
                confidence = 0.90
                reasons.append("RSI oversold")

        # Medium: MACD crossover (no trend requirement)
        elif macd_bullish_cross and not rsi_overbought:
            signal = Signal.BUY
            confidence = 0.70
            reasons.append("MACD bullish crossover")
            if rsi_oversold:
                confidence += 0.10
                reasons.append("RSI oversold")

        # Weak: RSI very oversold in uptrend
        elif rsi_very_oversold and uptrend and macd_bullish:
            signal = Signal.BUY
            confidence = 0.65
            reasons.append("RSI very oversold + uptrend")

        # === SELL SIGNALS (only in downtrend or neutral) ===

        # Strong: MACD crossover in downtrend
        elif macd_bearish_cross and downtrend and not rsi_oversold:
            signal = Signal.SELL
            confidence = 0.85
            reasons.append("MACD bearish crossover + downtrend")
            if rsi_overbought:
                confidence = 0.90
                reasons.append("RSI overbought")

        # Medium: MACD crossover (no trend requirement)
        elif macd_bearish_cross and not rsi_oversold:
            signal = Signal.SELL
            confidence = 0.70
            reasons.append("MACD bearish crossover")
            if rsi_overbought:
                confidence += 0.10
                reasons.append("RSI overbought")

        # Weak: RSI very overbought in downtrend
        elif rsi_very_overbought and downtrend and macd_bearish:
            signal = Signal.SELL
            confidence = 0.65
            reasons.append("RSI very overbought + downtrend")

        # === HOLD ===
        else:
            reasons.append("No clear signal")
            if uptrend:
                reasons.append("Uptrend (waiting for entry)")
            elif downtrend:
                reasons.append("Downtrend (waiting for exit)")
            else:
                reasons.append("Trend neutral")

        # Cap confidence at 1.0
        confidence = min(confidence, 1.0)

        reason_text = " | ".join(reasons)

        logger.debug(
            f"{symbol}: MACD={current_macd:.4f}, Signal={current_signal:.4f}, "
            f"RSI={current_rsi:.1f} -> {signal.value} ({confidence:.0%})"
        )

        return TradeSignal(
            signal=signal,
            symbol=symbol,
            confidence=confidence,
            reason=reason_text,
            metadata={
                "macd": current_macd,
                "macd_signal": current_signal,
                "macd_histogram": current_histogram,
                "rsi": current_rsi,
                "trend_ema": current_trend_ema,
                "trend": "up" if uptrend else ("down" if downtrend else "neutral"),
            },
        )

    def _calculate_macd(
        self, prices: pd.Series
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD indicator."""
        fast_ema = prices.ewm(span=self.fast_period, adjust=False).mean()
        slow_ema = prices.ewm(span=self.slow_period, adjust=False).mean()

        macd_line = fast_ema - slow_ema
        signal_line = macd_line.ewm(span=self.signal_period, adjust=False).mean()
        histogram = macd_line - signal_line

        return macd_line, signal_line, histogram

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

        return rsi.fillna(50)  # Default to neutral
