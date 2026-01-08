"""
Trading Engine

The heart of DREAMPIVOT - coordinates everything:
- Connects to exchange
- Collects price data
- Runs strategy
- Executes trades
- Manages risk
"""

import asyncio
from datetime import datetime, timezone
from typing import Any

from ..exchanges.base import BaseExchange
from ..exchanges.factory import create_exchange
from ..strategies.base import BaseStrategy, Signal
from ..strategies.momentum import MomentumStrategy
from ..strategies.mean_reversion import MeanReversionStrategy
from ..utils.logger import get_logger
from ..utils.tracker import PerformanceTracker

logger = get_logger("engine")


class TradingEngine:
    """
    Main trading engine.

    Orchestrates:
    1. Exchange connection
    2. Data collection
    3. Strategy execution
    4. Order management
    5. Risk control
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config

        # Components
        self._exchange: BaseExchange | None = None
        self._strategy: BaseStrategy | None = None
        self._tracker = PerformanceTracker()

        # State
        self._running = False
        self._positions: dict[str, float] = {}  # symbol -> amount

        # Risk settings (from 1-10 knob, start at 1 = ultra safe)
        self._risk_level = config.get("risk_level", 1)
        self._position_size_pct = self._get_position_size()

    def _get_position_size(self) -> float:
        """Get position size based on risk level (1-10)."""
        # Map risk level to position size %
        # Level 1 = 1%, Level 5 = 5%, Level 10 = 10%
        return self._risk_level / 100.0

    async def start(self) -> None:
        """Initialize and start the engine."""
        logger.info("=" * 50)
        logger.info("DREAMPIVOT Trading Engine Starting")
        logger.info("=" * 50)

        # Create exchange
        exchange_config = self.config.get("exchange", {})
        paper_config = self.config.get("paper", {})

        self._exchange = create_exchange(
            name=exchange_config.get("name", "binance"),
            testnet=exchange_config.get("testnet", True),
            paper_mode=self.config.get("mode", "paper") == "paper",
            paper_balance=paper_config.get("initial_balance", 10000.0),
        )

        await self._exchange.connect()

        # Create strategy
        strategy_config = self.config.get("strategy", {})
        strategy_name = strategy_config.get("name", "momentum")

        if strategy_name == "momentum":
            self._strategy = MomentumStrategy(strategy_config.get("params", {}))
        elif strategy_name == "mean_reversion":
            self._strategy = MeanReversionStrategy(strategy_config.get("params", {}))
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}. Available: momentum, mean_reversion")

        logger.info(f"Strategy: {self._strategy.name}")
        logger.info(f"Risk Level: {self._risk_level}/10 (position size: {self._position_size_pct:.1%})")
        logger.info(f"Symbols: {self.config.get('symbols', [])}")

        self._running = True

    async def stop(self) -> None:
        """Stop the engine."""
        logger.info("Stopping engine...")
        self._running = False

        if self._exchange:
            await self._exchange.disconnect()

        logger.info("Engine stopped")

    async def run_once(self) -> dict[str, Any]:
        """
        Run one iteration of the trading loop.

        Returns:
            Dict with results for each symbol
        """
        if not self._running:
            raise RuntimeError("Engine not started")

        results = {}
        symbols = self.config.get("symbols", ["BTC/USDT"])
        timeframe = self.config.get("timeframe", "1h")

        for symbol in symbols:
            try:
                result = await self._process_symbol(symbol, timeframe)
                results[symbol] = result
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")
                results[symbol] = {"error": str(e)}

        return results

    async def _process_symbol(self, symbol: str, timeframe: str) -> dict[str, Any]:
        """Process a single trading pair."""
        # Get price data
        ohlcv = await self._exchange.get_ohlcv(
            symbol,
            timeframe,
            limit=self._strategy.required_history() + 10,
        )
        df = self._exchange.ohlcv_to_dataframe(ohlcv)

        if df.empty:
            return {"signal": "hold", "reason": "No data"}

        # Run strategy
        trade_signal = self._strategy.analyze(df, symbol)

        result = {
            "symbol": symbol,
            "signal": trade_signal.signal.value,
            "confidence": trade_signal.confidence,
            "reason": trade_signal.reason,
            "price": df["close"].iloc[-1],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "indicators": trade_signal.metadata or {},
        }

        # Log signal to tracker
        self._tracker.log_signal(result)

        # Execute trade if signal is strong enough
        min_confidence = self._get_min_confidence()

        if trade_signal.signal != Signal.HOLD and trade_signal.confidence >= min_confidence:
            try:
                order = await self._execute_signal(trade_signal)
                result["order"] = {
                    "id": order.id,
                    "side": order.side,
                    "amount": order.amount,
                    "price": order.price,
                }

                # Log trade to tracker
                self._tracker.log_trade({
                    "symbol": symbol,
                    "side": order.side,
                    "amount": order.amount,
                    "price": order.price,
                    "cost": order.amount * order.price,
                    "order_id": order.id,
                })

                logger.info(
                    f"Trade executed: {order.side.upper()} {order.amount:.6f} {symbol} "
                    f"@ ${order.price:.2f}"
                )
            except Exception as e:
                result["order_error"] = str(e)
                logger.warning(f"Trade failed: {e}")
        else:
            if trade_signal.signal != Signal.HOLD:
                logger.debug(
                    f"Signal too weak: {trade_signal.confidence:.0%} < {min_confidence:.0%}"
                )

        return result

    def _get_min_confidence(self) -> float:
        """Get minimum confidence threshold based on risk level."""
        # Higher risk = lower confidence threshold
        # Level 1 = 90%, Level 5 = 70%, Level 10 = 50%
        return 1.0 - (self._risk_level * 0.05)

    async def _execute_signal(self, signal) -> Any:
        """Execute a trade signal."""
        # Get balance
        balances = await self._exchange.get_balance()
        usdt_balance = next(
            (b for b in balances if b.currency == "USDT"),
            None
        )

        if not usdt_balance:
            raise ValueError("No USDT balance")

        # Get current price
        ticker = await self._exchange.get_ticker(signal.symbol)
        price = ticker.last

        # Calculate position size
        position_value = usdt_balance.free * self._position_size_pct
        amount = position_value / price

        if signal.signal == Signal.BUY:
            return await self._exchange.create_order(
                symbol=signal.symbol,
                side="buy",
                order_type="market",
                amount=amount,
            )
        elif signal.signal == Signal.SELL:
            # Check if we have position to sell
            base_currency = signal.symbol.split("/")[0]
            base_balance = next(
                (b for b in balances if b.currency == base_currency),
                None
            )
            if base_balance and base_balance.free > 0:
                return await self._exchange.create_order(
                    symbol=signal.symbol,
                    side="sell",
                    order_type="market",
                    amount=base_balance.free,
                )
            else:
                raise ValueError(f"No {base_currency} to sell")

    async def run_loop(self, interval_seconds: int = 60) -> None:
        """
        Run continuous trading loop.

        Args:
            interval_seconds: Seconds between iterations
        """
        logger.info(f"Starting trading loop (interval: {interval_seconds}s)")

        while self._running:
            try:
                results = await self.run_once()

                for symbol, result in results.items():
                    if "error" not in result:
                        logger.info(
                            f"{symbol}: {result['signal'].upper()} "
                            f"({result['confidence']:.0%}) @ ${result['price']:.2f}"
                        )

                await asyncio.sleep(interval_seconds)

            except Exception as e:
                logger.error(f"Loop error: {e}")
                await asyncio.sleep(10)  # Wait before retry

    def get_status(self) -> dict[str, Any]:
        """Get current engine status."""
        return {
            "running": self._running,
            "exchange": self._exchange.name if self._exchange else None,
            "strategy": self._strategy.name if self._strategy else None,
            "risk_level": self._risk_level,
            "position_size_pct": self._position_size_pct,
            "symbols": self.config.get("symbols", []),
        }

    def get_performance(self) -> dict[str, Any]:
        """Get performance summary."""
        return self._tracker.get_performance_summary()

    def get_session_stats(self) -> dict[str, Any]:
        """Get current session statistics."""
        return self._tracker.get_session_stats()
