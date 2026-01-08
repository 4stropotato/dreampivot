"""
Base Exchange Interface

All exchanges implement this interface for unified access.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import pandas as pd


@dataclass
class Ticker:
    """Current price data."""
    symbol: str
    bid: float
    ask: float
    last: float
    volume: float
    timestamp: datetime


@dataclass
class OHLCV:
    """Candlestick data."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Order:
    """Order information."""
    id: str
    symbol: str
    side: Literal["buy", "sell"]
    type: Literal["market", "limit"]
    amount: float
    price: float | None
    status: str
    timestamp: datetime


@dataclass
class Balance:
    """Account balance."""
    currency: str
    free: float
    used: float
    total: float


class BaseExchange(ABC):
    """
    Base class for all exchanges.

    Provides a unified interface for:
    - Fetching market data
    - Placing orders
    - Managing positions
    """

    def __init__(self, api_key: str = "", secret: str = "", testnet: bool = True):
        self.api_key = api_key
        self.secret = secret
        self.testnet = testnet
        self._name = "base"

    @property
    def name(self) -> str:
        """Exchange name."""
        return self._name

    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection to exchange."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection."""
        pass

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        """Get current price for symbol."""
        pass

    @abstractmethod
    async def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 100,
    ) -> list[OHLCV]:
        """Get candlestick data."""
        pass

    @abstractmethod
    async def get_balance(self, currency: str | None = None) -> list[Balance]:
        """Get account balance."""
        pass

    @abstractmethod
    async def create_order(
        self,
        symbol: str,
        side: Literal["buy", "sell"],
        order_type: Literal["market", "limit"],
        amount: float,
        price: float | None = None,
    ) -> Order:
        """Place an order."""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order."""
        pass

    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> Order:
        """Get order status."""
        pass

    def ohlcv_to_dataframe(self, ohlcv: list[OHLCV]) -> pd.DataFrame:
        """Convert OHLCV list to pandas DataFrame."""
        if not ohlcv:
            return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

        data = [
            {
                "timestamp": candle.timestamp,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }
            for candle in ohlcv
        ]
        df = pd.DataFrame(data)
        df.set_index("timestamp", inplace=True)
        return df
