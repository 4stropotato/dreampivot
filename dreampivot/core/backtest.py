"""
Backtesting Engine

Test strategies on historical data to evaluate performance
before risking real money.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from ..strategies.base import BaseStrategy, Signal
from ..utils.logger import get_logger

logger = get_logger("backtest")


@dataclass
class BacktestTrade:
    """Record of a backtested trade."""
    timestamp: datetime
    symbol: str
    side: str  # buy or sell
    price: float
    amount: float
    value: float
    reason: str


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_balance: float
    final_balance: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    pnl_percent: float
    max_drawdown: float
    win_rate: float
    trades: list[BacktestTrade]


class BacktestEngine:
    """
    Backtesting engine for strategy evaluation.

    Simulates trading on historical data to measure
    strategy performance before live trading.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        initial_balance: float = 10000.0,
        position_size_pct: float = 0.03,  # 3% per trade
        fee_rate: float = 0.001,  # 0.1%
        stop_loss_pct: float = 0.02,  # 2% stop loss
        take_profit_pct: float = 0.04,  # 4% take profit
    ):
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.position_size_pct = position_size_pct
        self.fee_rate = fee_rate
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    def run(self, df: pd.DataFrame, symbol: str) -> BacktestResult:
        """
        Run backtest on historical data.

        Args:
            df: DataFrame with OHLCV data (must have: open, high, low, close, volume)
            symbol: Trading pair symbol

        Returns:
            BacktestResult with performance metrics
        """
        if len(df) < self.strategy.required_history():
            raise ValueError(f"Need at least {self.strategy.required_history()} candles")

        # State
        balance = self.initial_balance
        position = 0.0  # Amount of base currency held
        entry_price = 0.0
        trades: list[BacktestTrade] = []
        balance_history = [balance]

        # Walk through data
        start_idx = self.strategy.required_history()

        for i in range(start_idx, len(df)):
            # Get data up to current candle
            current_data = df.iloc[:i+1].copy()
            current_candle = df.iloc[i]
            current_price = current_candle["close"]
            current_high = current_candle["high"]
            current_low = current_candle["low"]
            current_time = current_data.index[-1] if isinstance(current_data.index[-1], datetime) else datetime.now(timezone.utc)

            # Check stop-loss and take-profit first (if in position)
            if position > 0 and entry_price > 0:
                stop_price = entry_price * (1 - self.stop_loss_pct)
                take_price = entry_price * (1 + self.take_profit_pct)

                # Check if stop-loss hit (price went below stop)
                if current_low <= stop_price:
                    trade_value = position * stop_price
                    fee = trade_value * self.fee_rate
                    balance += trade_value - fee

                    trades.append(BacktestTrade(
                        timestamp=current_time,
                        symbol=symbol,
                        side="sell",
                        price=stop_price,
                        amount=position,
                        value=trade_value,
                        reason=f"Stop-loss hit ({self.stop_loss_pct:.1%})",
                    ))

                    position = 0
                    entry_price = 0

                # Check if take-profit hit (price went above target)
                elif current_high >= take_price:
                    trade_value = position * take_price
                    fee = trade_value * self.fee_rate
                    balance += trade_value - fee

                    trades.append(BacktestTrade(
                        timestamp=current_time,
                        symbol=symbol,
                        side="sell",
                        price=take_price,
                        amount=position,
                        value=trade_value,
                        reason=f"Take-profit hit ({self.take_profit_pct:.1%})",
                    ))

                    position = 0
                    entry_price = 0

            # Get signal (only if not in position or position was just closed)
            signal = self.strategy.analyze(current_data, symbol)

            # Execute based on signal
            if signal.signal == Signal.BUY and position == 0:
                # Buy
                trade_value = balance * self.position_size_pct
                fee = trade_value * self.fee_rate
                amount = (trade_value - fee) / current_price

                position = amount
                entry_price = current_price
                balance -= trade_value

                trades.append(BacktestTrade(
                    timestamp=current_time,
                    symbol=symbol,
                    side="buy",
                    price=current_price,
                    amount=amount,
                    value=trade_value,
                    reason=signal.reason,
                ))

            elif signal.signal == Signal.SELL and position > 0:
                # Sell (strategy exit)
                trade_value = position * current_price
                fee = trade_value * self.fee_rate
                balance += trade_value - fee

                trades.append(BacktestTrade(
                    timestamp=current_time,
                    symbol=symbol,
                    side="sell",
                    price=current_price,
                    amount=position,
                    value=trade_value,
                    reason=signal.reason,
                ))

                position = 0
                entry_price = 0

            # Track balance (including unrealized P&L)
            total_value = balance + (position * current_price)
            balance_history.append(total_value)

        # Close any open position at end
        if position > 0:
            final_price = df["close"].iloc[-1]
            trade_value = position * final_price
            fee = trade_value * self.fee_rate
            balance += trade_value - fee
            position = 0

        # Calculate metrics
        final_balance = balance
        total_pnl = final_balance - self.initial_balance
        pnl_percent = (total_pnl / self.initial_balance) * 100

        # Calculate win/loss
        winning = 0
        losing = 0
        buy_trades = [t for t in trades if t.side == "buy"]
        sell_trades = [t for t in trades if t.side == "sell"]

        for i, sell in enumerate(sell_trades):
            if i < len(buy_trades):
                buy = buy_trades[i]
                if sell.price > buy.price:
                    winning += 1
                else:
                    losing += 1

        # Max drawdown
        peak = balance_history[0]
        max_drawdown = 0.0
        for value in balance_history:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        win_rate = (winning / len(sell_trades) * 100) if sell_trades else 0.0

        return BacktestResult(
            symbol=symbol,
            start_date=df.index[0] if isinstance(df.index[0], datetime) else datetime.now(timezone.utc),
            end_date=df.index[-1] if isinstance(df.index[-1], datetime) else datetime.now(timezone.utc),
            initial_balance=self.initial_balance,
            final_balance=final_balance,
            total_trades=len(trades),
            winning_trades=winning,
            losing_trades=losing,
            total_pnl=total_pnl,
            pnl_percent=pnl_percent,
            max_drawdown=max_drawdown * 100,
            win_rate=win_rate,
            trades=trades,
        )


def format_backtest_result(result: BacktestResult) -> str:
    """Format backtest result for display."""
    # Count stop-loss and take-profit exits
    sl_count = len([t for t in result.trades if "Stop-loss" in t.reason])
    tp_count = len([t for t in result.trades if "Take-profit" in t.reason])

    lines = [
        "=" * 50,
        f"BACKTEST RESULTS: {result.symbol}",
        "=" * 50,
        f"Period: {result.start_date.strftime('%Y-%m-%d')} to {result.end_date.strftime('%Y-%m-%d')}",
        f"Initial Balance: ${result.initial_balance:,.2f}",
        f"Final Balance: ${result.final_balance:,.2f}",
        "",
        f"Total P&L: ${result.total_pnl:,.2f} ({result.pnl_percent:+.2f}%)",
        f"Max Drawdown: {result.max_drawdown:.2f}%",
        "",
        f"Total Trades: {result.total_trades}",
        f"Winning: {result.winning_trades} | Losing: {result.losing_trades}",
        f"Win Rate: {result.win_rate:.1f}%",
    ]

    if sl_count > 0 or tp_count > 0:
        lines.append(f"Stop-Loss: {sl_count} | Take-Profit: {tp_count}")

    lines.append("=" * 50)
    return "\n".join(lines)
