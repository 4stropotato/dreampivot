"""
Exchange Abstraction Layer

Supports multiple exchanges through a unified interface.
Uses ccxt for crypto exchanges.
"""

from .base import BaseExchange
from .factory import create_exchange

__all__ = ["BaseExchange", "create_exchange"]
