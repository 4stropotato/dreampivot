"""
CCXT-based Exchange Implementation

Supports all exchanges that ccxt supports:
- Binance, Bybit, Bitflyer, Kraken, etc.
- Unified interface for all
"""

from datetime import datetime, timezone
from typing import Literal

import ccxt.async_support as ccxt

from .base import BaseExchange, Ticker, OHLCV, Order, Balance
from ..utils.logger import get_logger

logger = get_logger("exchange")


class CCXTExchange(BaseExchange):
    """
    Exchange implementation using CCXT library.

    Supports 100+ crypto exchanges with unified API.
    """

    # Supported exchanges
    SUPPORTED = {
        "binance": ccxt.binance,
        "bybit": ccxt.bybit,
        "bitflyer": ccxt.bitflyer,
        "kraken": ccxt.kraken,
        "coinbase": ccxt.coinbase,
        "okx": ccxt.okx,
        "kucoin": ccxt.kucoin,
        "gate": ccxt.gate,
        "huobi": ccxt.huobi,
        "mexc": ccxt.mexc,
    }

    def __init__(
        self,
        exchange_id: str,
        api_key: str = "",
        secret: str = "",
        testnet: bool = True,
    ):
        super().__init__(api_key, secret, testnet)

        self._name = exchange_id.lower()

        if self._name not in self.SUPPORTED:
            raise ValueError(
                f"Exchange '{exchange_id}' not supported. "
                f"Available: {list(self.SUPPORTED.keys())}"
            )

        self._exchange_class = self.SUPPORTED[self._name]
        self._exchange: ccxt.Exchange | None = None

    async def connect(self) -> None:
        """Initialize connection to exchange."""
        config = {
            "enableRateLimit": True,
        }

        if self.api_key and self.secret:
            config["apiKey"] = self.api_key
            config["secret"] = self.secret

        # Note: We don't use sandbox mode even for testnet because:
        # 1. Sandbox has limited/no OHLCV data
        # 2. Paper trading already simulates orders safely
        # 3. We want REAL price data for accurate analysis

        self._exchange = self._exchange_class(config)

        # Load markets
        await self._exchange.load_markets()
        logger.info(f"Connected to {self._name} ({'testnet' if self.testnet else 'live'})")
        logger.info(f"Available symbols: {len(self._exchange.symbols)}")

    async def disconnect(self) -> None:
        """Close connection."""
        if self._exchange:
            await self._exchange.close()
            self._exchange = None
            logger.info(f"Disconnected from {self._name}")

    def _ensure_connected(self) -> None:
        """Ensure exchange is connected."""
        if not self._exchange:
            raise RuntimeError("Exchange not connected. Call connect() first.")

    async def get_ticker(self, symbol: str) -> Ticker:
        """Get current price for symbol."""
        self._ensure_connected()

        ticker = await self._exchange.fetch_ticker(symbol)

        return Ticker(
            symbol=symbol,
            bid=float(ticker.get("bid", 0) or 0),
            ask=float(ticker.get("ask", 0) or 0),
            last=float(ticker.get("last", 0) or 0),
            volume=float(ticker.get("baseVolume", 0) or 0),
            timestamp=datetime.fromtimestamp(
                ticker["timestamp"] / 1000, tz=timezone.utc
            ) if ticker.get("timestamp") else datetime.now(timezone.utc),
        )

    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> list[OHLCV]:
        """Get candlestick data."""
        self._ensure_connected()

        data = await self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

        return [
            OHLCV(
                timestamp=datetime.fromtimestamp(candle[0] / 1000, tz=timezone.utc),
                open=float(candle[1]),
                high=float(candle[2]),
                low=float(candle[3]),
                close=float(candle[4]),
                volume=float(candle[5]),
            )
            for candle in data
        ]

    async def get_balance(self, currency: str | None = None) -> list[Balance]:
        """Get account balance."""
        self._ensure_connected()

        balance = await self._exchange.fetch_balance()

        result = []
        for curr, data in balance.get("total", {}).items():
            if data and float(data) > 0:
                if currency and curr != currency:
                    continue

                result.append(Balance(
                    currency=curr,
                    free=float(balance["free"].get(curr, 0) or 0),
                    used=float(balance["used"].get(curr, 0) or 0),
                    total=float(data),
                ))

        return result

    async def create_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        order_type: Literal["market", "limit"],
        amount: float,
        price: float | None = None,
    ) -> Order:
        """Place an order."""
        self._ensure_connected()

        order = await self._exchange.create_order(
            symbol=symbol,
            type=order_type,
            side=side,
            amount=amount,
            price=price,
        )

        logger.info(f"Order created: {side} {amount} {symbol} @ {price or 'market'}")

        return Order(
            id=order["id"],
            symbol=symbol,
            side=side,
            type=order_type,
            amount=amount,
            price=price or float(order.get("price", 0) or 0),
            status=order["status"],
            timestamp=datetime.fromtimestamp(
                order["timestamp"] / 1000, tz=timezone.utc
            ) if order.get("timestamp") else datetime.now(timezone.utc),
        )

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order."""
        self._ensure_connected()

        try:
            await self._exchange.cancel_order(order_id, symbol)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def get_order(self, order_id: str, symbol: str) -> Order:
        """Get order status."""
        self._ensure_connected()

        order = await self._exchange.fetch_order(order_id, symbol)

        return Order(
            id=order["id"],
            symbol=symbol,
            side=order["side"],
            type=order["type"],
            amount=float(order["amount"]),
            price=float(order.get("price", 0) or 0),
            status=order["status"],
            timestamp=datetime.fromtimestamp(
                order["timestamp"] / 1000, tz=timezone.utc
            ) if order.get("timestamp") else datetime.now(timezone.utc),
        )

    async def get_all_tickers(self) -> dict[str, Ticker]:
        """Get all tickers (for finding hot pairs)."""
        self._ensure_connected()

        tickers = await self._exchange.fetch_tickers()

        result = {}
        for symbol, ticker in tickers.items():
            if ticker.get("last"):
                result[symbol] = Ticker(
                    symbol=symbol,
                    bid=float(ticker.get("bid", 0) or 0),
                    ask=float(ticker.get("ask", 0) or 0),
                    last=float(ticker.get("last", 0) or 0),
                    volume=float(ticker.get("quoteVolume", 0) or 0),
                    timestamp=datetime.fromtimestamp(
                        ticker["timestamp"] / 1000, tz=timezone.utc
                    ) if ticker.get("timestamp") else datetime.now(timezone.utc),
                )

        return result
