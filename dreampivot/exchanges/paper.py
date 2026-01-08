"""
Paper Trading Exchange

Simulates trading without real money.
Uses real price data from underlying exchange.
"""

from datetime import datetime, timezone
from typing import Literal
import uuid

from .base import BaseExchange, Ticker, OHLCV, Order, Balance
from ..utils.logger import get_logger

logger = get_logger("paper")


class PaperExchange(BaseExchange):
    """
    Paper trading wrapper.

    Uses real price data but simulates orders.
    Perfect for testing strategies without risk.
    """

    def __init__(
        self,
        real_exchange: BaseExchange,
        initial_balance: float = 10000.0,
        fee_rate: float = 0.001,  # 0.1%
    ):
        super().__init__()
        self._real = real_exchange
        self._name = f"paper_{real_exchange.name}"

        self._fee_rate = fee_rate

        # Simulated balances (quote currency, usually USDT)
        self._balances: dict[str, Balance] = {
            "USDT": Balance(
                currency="USDT",
                free=initial_balance,
                used=0.0,
                total=initial_balance,
            )
        }

        # Order tracking
        self._orders: dict[str, Order] = {}
        self._order_counter = 0

        # Trade history
        self._trades: list[dict] = []

    async def connect(self) -> None:
        """Connect underlying exchange for price data."""
        await self._real.connect()
        logger.info(f"Paper trading mode: ${self._balances['USDT'].total:.2f} USDT")

    async def disconnect(self) -> None:
        """Disconnect."""
        await self._real.disconnect()

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get real price data."""
        return await self._real.get_ticker(symbol)

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> list[OHLCV]:
        """Get real candle data."""
        return await self._real.get_ohlcv(symbol, timeframe, limit)

    async def get_balance(self, currency: str | None = None) -> list[Balance]:
        """Get simulated balance."""
        if currency:
            if currency in self._balances:
                return [self._balances[currency]]
            return []

        return list(self._balances.values())

    async def create_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        order_type: Literal["market", "limit"],
        amount: float,
        price: float | None = None,
    ) -> Order:
        """Simulate order execution."""
        # Get current price
        ticker = await self.get_ticker(symbol)
        exec_price = price if order_type == "limit" else ticker.last

        # Parse symbol (e.g., "BTC/USDT" -> base="BTC", quote="USDT")
        base, quote = symbol.split("/")

        # Calculate cost
        cost = amount * exec_price
        fee = cost * self._fee_rate

        # Check balance
        if side == "buy":
            required = cost + fee
            if self._balances.get(quote, Balance(quote, 0, 0, 0)).free < required:
                raise ValueError(f"Insufficient {quote} balance. Need {required:.2f}")

            # Update balances
            self._update_balance(quote, -required)
            self._update_balance(base, amount)

        else:  # sell
            if self._balances.get(base, Balance(base, 0, 0, 0)).free < amount:
                raise ValueError(f"Insufficient {base} balance. Need {amount}")

            # Update balances
            self._update_balance(base, -amount)
            self._update_balance(quote, cost - fee)

        # Create order record
        self._order_counter += 1
        order_id = f"paper_{uuid.uuid4().hex[:8]}"

        order = Order(
            id=order_id,
            symbol=symbol,
            side=side,
            type=order_type,
            amount=amount,
            price=exec_price,
            status="closed",  # Immediately filled for paper
            timestamp=datetime.now(timezone.utc),
        )

        self._orders[order_id] = order

        # Record trade
        self._trades.append({
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": exec_price,
            "cost": cost,
            "fee": fee,
            "timestamp": order.timestamp,
        })

        logger.info(
            f"[PAPER] {side.upper()} {amount:.6f} {base} @ ${exec_price:.2f} "
            f"(cost: ${cost:.2f}, fee: ${fee:.2f})"
        )

        return order

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel order (paper orders are instant, so this is no-op)."""
        if order_id in self._orders:
            logger.info(f"[PAPER] Order {order_id} already executed")
            return False
        return False

    async def get_order(self, order_id: str, symbol: str) -> Order:
        """Get order status."""
        if order_id not in self._orders:
            raise ValueError(f"Order {order_id} not found")
        return self._orders[order_id]

    def _update_balance(self, currency: str, delta: float) -> None:
        """Update balance for a currency."""
        if currency not in self._balances:
            self._balances[currency] = Balance(
                currency=currency,
                free=0.0,
                used=0.0,
                total=0.0,
            )

        bal = self._balances[currency]
        new_free = bal.free + delta
        new_total = bal.total + delta

        self._balances[currency] = Balance(
            currency=currency,
            free=max(0, new_free),
            used=bal.used,
            total=max(0, new_total),
        )

    def get_portfolio_value(self, prices: dict[str, float]) -> float:
        """
        Calculate total portfolio value in USDT.

        Args:
            prices: Dict of symbol -> price (e.g., {"BTC": 50000})
        """
        total = 0.0

        for currency, balance in self._balances.items():
            if currency == "USDT":
                total += balance.total
            elif currency in prices:
                total += balance.total * prices[currency]

        return total

    def get_trade_history(self) -> list[dict]:
        """Get all paper trades."""
        return self._trades.copy()

    def get_stats(self) -> dict:
        """Get trading statistics."""
        if not self._trades:
            return {
                "total_trades": 0,
                "total_volume": 0,
                "total_fees": 0,
            }

        return {
            "total_trades": len(self._trades),
            "total_volume": sum(t["cost"] for t in self._trades),
            "total_fees": sum(t["fee"] for t in self._trades),
            "buys": len([t for t in self._trades if t["side"] == "buy"]),
            "sells": len([t for t in self._trades if t["side"] == "sell"]),
        }
