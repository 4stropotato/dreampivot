"""
Exchange Factory

Creates exchange instances based on configuration.
"""

from .base import BaseExchange
from .ccxt_exchange import CCXTExchange
from .paper import PaperExchange


def create_exchange(
    name: str,
    api_key: str = "",
    secret: str = "",
    testnet: bool = True,
    paper_mode: bool = False,
    paper_balance: float = 10000.0,
) -> BaseExchange:
    """
    Create an exchange instance.

    Args:
        name: Exchange name (binance, bybit, etc.)
        api_key: API key (optional for paper trading)
        secret: API secret (optional for paper trading)
        testnet: Use testnet/sandbox mode
        paper_mode: Use paper trading (simulated)
        paper_balance: Initial balance for paper trading

    Returns:
        Exchange instance
    """
    name = name.lower()

    if paper_mode:
        # Paper trading - wrap real exchange for price data
        real_exchange = CCXTExchange(name, api_key, secret, testnet)
        return PaperExchange(real_exchange, initial_balance=paper_balance)

    return CCXTExchange(name, api_key, secret, testnet)
