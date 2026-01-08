"""
Performance Tracker

Logs all signals and trades for analysis.
Tracks portfolio value over time.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .logger import get_logger

logger = get_logger("tracker")


class PerformanceTracker:
    """
    Tracks trading performance over time.

    Saves:
    - All signals generated
    - All trades executed
    - Portfolio value snapshots
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        # File paths
        self.signals_file = self.data_dir / "signals.jsonl"
        self.trades_file = self.data_dir / "trades.jsonl"
        self.portfolio_file = self.data_dir / "portfolio.jsonl"

        # In-memory stats
        self._session_signals = 0
        self._session_trades = 0
        self._session_start = datetime.now(timezone.utc)

    def log_signal(self, signal_data: dict[str, Any]) -> None:
        """Log a signal to file."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **signal_data,
        }
        self._append_jsonl(self.signals_file, record)
        self._session_signals += 1

    def log_trade(self, trade_data: dict[str, Any]) -> None:
        """Log a trade to file."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **trade_data,
        }
        self._append_jsonl(self.trades_file, record)
        self._session_trades += 1
        logger.info(f"Trade logged: {trade_data.get('side', 'N/A').upper()} {trade_data.get('symbol', 'N/A')}")

    def log_portfolio(self, balances: dict[str, float], total_value: float) -> None:
        """Log portfolio snapshot."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "balances": balances,
            "total_value_usdt": total_value,
        }
        self._append_jsonl(self.portfolio_file, record)

    def _append_jsonl(self, file_path: Path, record: dict) -> None:
        """Append a JSON record to a JSONL file."""
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def get_session_stats(self) -> dict[str, Any]:
        """Get current session statistics."""
        duration = datetime.now(timezone.utc) - self._session_start
        return {
            "session_start": self._session_start.isoformat(),
            "duration_minutes": duration.total_seconds() / 60,
            "signals_generated": self._session_signals,
            "trades_executed": self._session_trades,
        }

    def get_all_trades(self) -> list[dict]:
        """Load all trades from file."""
        return self._read_jsonl(self.trades_file)

    def get_all_signals(self) -> list[dict]:
        """Load all signals from file."""
        return self._read_jsonl(self.signals_file)

    def get_portfolio_history(self) -> list[dict]:
        """Load portfolio history from file."""
        return self._read_jsonl(self.portfolio_file)

    def _read_jsonl(self, file_path: Path) -> list[dict]:
        """Read all records from a JSONL file."""
        if not file_path.exists():
            return []

        records = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
        return records

    def get_performance_summary(self) -> dict[str, Any]:
        """Calculate performance summary from trade history."""
        trades = self.get_all_trades()

        if not trades:
            return {
                "total_trades": 0,
                "message": "No trades yet",
            }

        buys = [t for t in trades if t.get("side") == "buy"]
        sells = [t for t in trades if t.get("side") == "sell"]

        total_bought = sum(t.get("cost", 0) for t in buys)
        total_sold = sum(t.get("cost", 0) for t in sells)
        total_fees = sum(t.get("fee", 0) for t in trades)

        # Get portfolio history for P&L
        portfolio = self.get_portfolio_history()

        initial_value = portfolio[0]["total_value_usdt"] if portfolio else 10000.0
        current_value = portfolio[-1]["total_value_usdt"] if portfolio else initial_value

        pnl = current_value - initial_value
        pnl_pct = (pnl / initial_value) * 100 if initial_value > 0 else 0

        return {
            "total_trades": len(trades),
            "buys": len(buys),
            "sells": len(sells),
            "total_bought_usdt": total_bought,
            "total_sold_usdt": total_sold,
            "total_fees_usdt": total_fees,
            "initial_value_usdt": initial_value,
            "current_value_usdt": current_value,
            "pnl_usdt": pnl,
            "pnl_percent": pnl_pct,
        }
