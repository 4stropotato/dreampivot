"""
Configuration Management

Loads config from:
1. config.yaml (main config)
2. .env (secrets like API keys)
"""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# Load .env file
load_dotenv()


def get_project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """Load configuration from YAML file."""
    if config_path is None:
        config_path = get_project_root() / "config.yaml"

    config_path = Path(config_path)

    if not config_path.exists():
        # Return defaults if no config file
        return get_default_config()

    with open(config_path, "r") as f:
        config = yaml.safe_load(f) or {}

    # Merge with defaults
    defaults = get_default_config()
    return {**defaults, **config}


def get_default_config() -> dict[str, Any]:
    """Default configuration."""
    return {
        # Trading mode
        "mode": "paper",  # paper | live

        # Risk level (1-10 scale from DREAMPIVOT.md)
        "risk_level": 1,  # Start ultra-safe

        # Exchange settings
        "exchange": {
            "name": "binance",
            "testnet": True,  # Use testnet for safety
        },

        # Trading pairs
        "symbols": ["BTC/USDT"],

        # Data collection
        "timeframe": "1h",  # Candle timeframe
        "history_days": 30,  # Days of history to load

        # Strategy
        "strategy": {
            "name": "momentum",
            "params": {
                "fast_period": 12,
                "slow_period": 26,
                "signal_period": 9,
            },
        },

        # Paper trading
        "paper": {
            "initial_balance": 10000.0,  # USDT
            "fee_rate": 0.001,  # 0.1%
        },

        # Logging
        "log_level": "INFO",
    }


def get_api_keys(exchange: str) -> dict[str, str]:
    """Get API keys from environment variables."""
    exchange_upper = exchange.upper()
    return {
        "api_key": os.getenv(f"{exchange_upper}_API_KEY", ""),
        "secret": os.getenv(f"{exchange_upper}_SECRET", ""),
    }
