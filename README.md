# DREAMPIVOT

**Version:** 0.0.1
**Status:** Paper Trading (Testing Phase)

An autonomous cryptocurrency trading bot with multi-exchange support.

## Features

- Multi-exchange support via CCXT (Binance, Bybit, Bitflyer, Kraken, etc.)
- Paper trading mode for safe testing
- Momentum strategy (MACD + RSI)
- Configurable risk levels (1-10 scale)
- Clean, extensible architecture

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv

# 2. Activate virtual environment
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp config.example.yaml config.yaml
# Edit config.yaml with your settings

# 5. Run
python -m dreampivot.main --once    # Single run
python -m dreampivot.main           # Continuous loop
```

## Project Structure

```
dreampivot/
├── __init__.py           # Package info & version
├── config.py             # Configuration loader
├── main.py               # Entry point
├── core/
│   └── engine.py         # Trading engine
├── exchanges/
│   ├── base.py           # Exchange interface
│   ├── ccxt_exchange.py  # Real exchange connector
│   ├── paper.py          # Paper trading simulator
│   └── factory.py        # Exchange factory
├── strategies/
│   ├── base.py           # Strategy interface
│   └── momentum.py       # MACD + RSI strategy
└── utils/
    └── logger.py         # Logging utilities
```

## Configuration

Edit `config.yaml`:

```yaml
mode: paper          # paper or live
risk_level: 3        # 1-10 (higher = more aggressive)
exchange:
  name: binance      # binance, bybit, bitflyer, etc.
  testnet: true      # use testnet for safety
symbols:
  - BTC/USDT
timeframe: 1h        # candle timeframe
```

## Risk Levels

| Level | Position Size | Min Confidence | Description |
|-------|---------------|----------------|-------------|
| 1 | 1% | 90% | Ultra conservative |
| 5 | 5% | 70% | Balanced |
| 10 | 10% | 50% | Aggressive |

## Versioning

- Patch: `+0.0.1` - Bug fixes and small improvements
- Minor: `+0.1.0` - New features and significant upgrades
- Major: `+1.0.0` - Breaking changes or major milestones

## License

MIT
