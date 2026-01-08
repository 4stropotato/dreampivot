"""
DREAMPIVOT Main Entry Point

Run with:
    python -m dreampivot.main
    python -m dreampivot.main --once  (single run)
    python -m dreampivot.main --backtest  (backtest strategy)
"""

import asyncio
import argparse

from .config import load_config
from .core.engine import TradingEngine
from .core.backtest import BacktestEngine, format_backtest_result
from .strategies.momentum import MomentumStrategy
from .strategies.mean_reversion import MeanReversionStrategy
from .exchanges.factory import create_exchange
from .utils.logger import setup_logger, get_logger


async def main(once: bool = False, interval: int = 300) -> None:
    """Main entry point."""
    # Load config
    config = load_config()

    # Setup logging
    setup_logger(config.get("log_level", "INFO"))
    logger = get_logger("main")

    logger.info("=" * 60)
    logger.info("  DREAMPIVOT - Autonomous Trading Bot")
    logger.info("  Phase 1: Foundation")
    logger.info("=" * 60)

    # Create engine
    engine = TradingEngine(config)

    try:
        # Start engine
        await engine.start()

        if once:
            # Single run
            logger.info("Running single iteration...")
            results = await engine.run_once()

            for symbol, result in results.items():
                logger.info(f"\n{symbol}:")
                logger.info(f"  Signal: {result.get('signal', 'N/A').upper()}")
                logger.info(f"  Confidence: {result.get('confidence', 0):.0%}")
                logger.info(f"  Price: ${result.get('price', 0):.2f}")
                logger.info(f"  Reason: {result.get('reason', 'N/A')}")

                # Show indicator values
                indicators = result.get('indicators', {})
                if indicators:
                    logger.info(f"  MACD: {indicators.get('macd', 0):.2f} | Signal: {indicators.get('macd_signal', 0):.2f} | Histogram: {indicators.get('macd_histogram', 0):.2f}")
                    logger.info(f"  RSI: {indicators.get('rsi', 0):.1f}")

                if "order" in result:
                    order = result["order"]
                    logger.info(f"  Order: {order['side'].upper()} {order['amount']:.6f} @ ${order['price']:.2f}")

        else:
            # Continuous loop
            logger.info(f"Starting continuous trading (interval: {interval}s)")
            logger.info("Press Ctrl+C to stop")
            await engine.run_loop(interval_seconds=interval)

    except KeyboardInterrupt:
        logger.info("\nShutdown requested...")

    finally:
        # Show session stats
        stats = engine.get_session_stats()
        logger.info("\n" + "=" * 40)
        logger.info("SESSION SUMMARY")
        logger.info("=" * 40)
        logger.info(f"Duration: {stats['duration_minutes']:.1f} minutes")
        logger.info(f"Signals generated: {stats['signals_generated']}")
        logger.info(f"Trades executed: {stats['trades_executed']}")

        # Show performance if trades exist
        perf = engine.get_performance()
        if perf.get("total_trades", 0) > 0:
            logger.info(f"\nTotal trades: {perf['total_trades']}")
            logger.info(f"P&L: ${perf['pnl_usdt']:.2f} ({perf['pnl_percent']:.2f}%)")

        await engine.stop()
        logger.info("\nGoodbye!")


async def run_backtest(days: int = 30, compare: bool = False) -> None:
    """Run backtest on historical data."""
    config = load_config()
    setup_logger(config.get("log_level", "INFO"))
    logger = get_logger("backtest")

    logger.info("=" * 60)
    if compare:
        logger.info("  DREAMPIVOT - Strategy Comparison")
    else:
        logger.info("  DREAMPIVOT - Backtesting Mode")
    logger.info("=" * 60)

    # Create exchange for data
    exchange_config = config.get("exchange", {})
    exchange = create_exchange(
        name=exchange_config.get("name", "binance"),
        testnet=False,
        paper_mode=False,
    )

    await exchange.connect()

    # Risk settings
    risk_level = config.get("risk_level", 3)
    risk_config = config.get("risk", {})
    initial_balance = config.get("paper", {}).get("initial_balance", 10000.0)
    fee_rate = config.get("paper", {}).get("fee_rate", 0.001)
    stop_loss = risk_config.get("stop_loss", 0.02)
    take_profit = risk_config.get("take_profit", 0.04)

    logger.info(f"Risk: SL={stop_loss:.1%} | TP={take_profit:.1%}")

    # Strategies to test
    if compare:
        strategies = [
            ("momentum", MomentumStrategy(config.get("strategy", {}).get("params", {}))),
            ("mean_reversion", MeanReversionStrategy(config.get("strategy", {}).get("params", {}))),
        ]
    else:
        strategy_config = config.get("strategy", {})
        strategy_name = strategy_config.get("name", "momentum")
        if strategy_name == "momentum":
            strategy = MomentumStrategy(strategy_config.get("params", {}))
        elif strategy_name == "mean_reversion":
            strategy = MeanReversionStrategy(strategy_config.get("params", {}))
        else:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        strategies = [(strategy_name, strategy)]
        logger.info(f"Strategy: {strategy_name}")

    # Run backtest for each symbol
    symbols = config.get("symbols", ["BTC/USDT"])
    timeframe = config.get("timeframe", "1h")

    # Calculate limit based on days and timeframe
    hours_per_day = 24
    if timeframe == "1h":
        limit = days * hours_per_day
    elif timeframe == "4h":
        limit = days * (hours_per_day // 4)
    elif timeframe == "1d":
        limit = days
    else:
        limit = days * hours_per_day

    # Store results for comparison
    all_results = {name: {} for name, _ in strategies}

    for symbol in symbols:
        logger.info(f"\nFetching {days} days of {timeframe} data for {symbol}...")

        ohlcv = await exchange.get_ohlcv(symbol, timeframe, limit=limit)
        df = exchange.ohlcv_to_dataframe(ohlcv)

        for strategy_name, strategy in strategies:
            if len(df) < strategy.required_history():
                logger.warning(f"Not enough data for {symbol}")
                continue

            backtest = BacktestEngine(
                strategy=strategy,
                initial_balance=initial_balance,
                position_size_pct=risk_level / 100.0,
                fee_rate=fee_rate,
                stop_loss_pct=stop_loss,
                take_profit_pct=take_profit,
            )

            if not compare:
                logger.info(f"Running backtest on {len(df)} candles...")

            result = backtest.run(df, symbol)
            all_results[strategy_name][symbol] = result

            if not compare:
                print("\n" + format_backtest_result(result))

    # Show comparison table if comparing
    if compare:
        print("\n" + "=" * 70)
        print("STRATEGY COMPARISON")
        print("=" * 70)
        print(f"{'Symbol':<12} {'Strategy':<16} {'P&L':>10} {'Win Rate':>10} {'Trades':>8}")
        print("-" * 70)

        for symbol in symbols:
            for strategy_name, _ in strategies:
                if symbol in all_results[strategy_name]:
                    r = all_results[strategy_name][symbol]
                    pnl_str = f"${r.total_pnl:+.2f}"
                    print(f"{symbol:<12} {strategy_name:<16} {pnl_str:>10} {r.win_rate:>9.1f}% {r.total_trades:>8}")
            print("-" * 70)

        # Summary
        print("\nSUMMARY (Total across all symbols):")
        for strategy_name, _ in strategies:
            total_pnl = sum(r.total_pnl for r in all_results[strategy_name].values())
            avg_win = sum(r.win_rate for r in all_results[strategy_name].values()) / len(all_results[strategy_name]) if all_results[strategy_name] else 0
            print(f"  {strategy_name}: ${total_pnl:+.2f} | Avg Win Rate: {avg_win:.1f}%")

    await exchange.disconnect()


def cli() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="DREAMPIVOT Trading Bot")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run single iteration instead of loop",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Seconds between iterations (default: 300)",
    )
    parser.add_argument(
        "--backtest",
        action="store_true",
        help="Run backtesting on historical data",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days of history for backtest (default: 30)",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Compare all strategies in backtest",
    )

    args = parser.parse_args()

    if args.backtest:
        asyncio.run(run_backtest(days=args.days, compare=args.compare))
    else:
        asyncio.run(main(once=args.once, interval=args.interval))


if __name__ == "__main__":
    cli()
