# live.py — Live trading loop for --run live
from __future__ import annotations

import csv
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from backtest import _ensure_datetime_index, latest_reversal_signal
from broker_ibkr import IBKRBroker
from risk import validate_targets

LOG_DIR = "logs"
TRADES_CSV = "logs/live_trades.csv"
PORTFOLIO_CSV = "logs/live_portfolio.csv"
SNAPSHOT_CSV = "logs/live_snapshot.csv"


def _parse_portfolio_value(summary: Dict[str, str]) -> float:
    """Extract portfolio value (NetLiquidation) from account summary."""
    val = summary.get("NetLiquidation", "0")
    try:
        return float(str(val).split()[0])
    except (ValueError, IndexError):
        return 0.0


def _signals_to_weights(
    signals: Dict[str, float],
    max_position_pct: float,
    max_gross_exposure: float,
) -> Dict[str, float]:
    """
    Convert reversal signals (-1,0,1) to long-only weights.
    signal=1 -> allocate; signal in (0,-1) -> weight 0.
    Distribute max_gross among longs, cap each at max_position_pct.
    """
    longs = [s for s, sig in signals.items() if sig == 1]
    if not longs:
        return {s: 0.0 for s in signals}

    per_name = min(max_gross_exposure / len(longs), max_position_pct)
    return {s: (per_name if s in longs else 0.0) for s in signals}


def _ensure_log_csv(path: str, columns: List[str]) -> None:
    """Create log file with header if it doesn't exist."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(columns)


def _append_trade_log(
    timestamp: str,
    symbol: str,
    side: str,
    quantity: int,
    fill_price: float,
    signal_value: float,
    reference_price: float = 0.0,
) -> None:
    """Log a trade. reference_price = latest close used for sizing (logged even when dry-run/unfilled)."""
    _ensure_log_csv(
        TRADES_CSV,
        ["timestamp", "symbol", "side", "quantity", "fill_price", "reference_price", "signal_value"],
    )
    with open(TRADES_CSV, "a", newline="") as f:
        csv.writer(f).writerow([timestamp, symbol, side, quantity, fill_price, reference_price, signal_value])


def _read_snapshot_history() -> List[Tuple[str, float]]:
    """Read existing snapshot file. Returns list of (timestamp, portfolio_value)."""
    if not os.path.exists(SNAPSHOT_CSV):
        return []
    rows = []
    with open(SNAPSHOT_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                val = float(row.get("portfolio_value", 0))
                rows.append((row.get("timestamp", ""), val))
            except (ValueError, KeyError):
                pass
    return rows


def _append_snapshot_log(
    portfolio_value: float,
) -> Tuple[Optional[float], Optional[float]]:
    """
    Append portfolio snapshot. Returns (daily_pnl, running_pnl) when computable, else (None, None).
    """
    _ensure_log_csv(SNAPSHOT_CSV, ["timestamp", "portfolio_value", "daily_pnl", "running_pnl"])
    ts = datetime.now().isoformat()
    history = _read_snapshot_history()

    daily_pnl: Optional[float] = None
    running_pnl: Optional[float] = None

    if history:
        _, first_value = history[0]
        _, prev_value = history[-1]
        daily_pnl = portfolio_value - prev_value
        running_pnl = portfolio_value - first_value

    with open(SNAPSHOT_CSV, "a", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            ts,
            f"{portfolio_value:.2f}",
            f"{daily_pnl:.2f}" if daily_pnl is not None else "",
            f"{running_pnl:.2f}" if running_pnl is not None else "",
        ])

    return daily_pnl, running_pnl


def _append_portfolio_log(positions: List[dict], latest_closes: Dict[str, float]) -> None:
    _ensure_log_csv(PORTFOLIO_CSV, ["timestamp", "symbol", "position", "avg_cost", "unrealized_pnl"])
    ts = datetime.now().isoformat()
    with open(PORTFOLIO_CSV, "a", newline="") as f:
        w = csv.writer(f)
        for p in positions:
            sym = p["symbol"]
            pos = p["position"]
            avg = p["avg_cost"]
            close = latest_closes.get(sym)
            if close is not None and avg and pos:
                upnl = (float(close) - float(avg)) * float(pos)
            else:
                upnl = 0.0
            w.writerow([ts, sym, pos, avg, upnl])


def run_live(
    broker: IBKRBroker,
    symbols: List[str],
    cfg: dict,
    cost_bps: float,
    dry_run: bool,
    log: logging.Logger,
) -> None:
    """
    Run one live trading iteration:
    1. Fetch positions and account summary
    2. Fetch ~20 days bars for universe (no cache)
    3. Compute reversal signals, convert to target weights
    4. Apply risk limits, compute required trades
    5. Place orders (or log in dry-run), wait for fills
    6. Log to live_trades.csv and live_portfolio.csv
    """
    risk_cfg = cfg["risk"]
    max_position_pct = risk_cfg["max_position_pct"]
    max_gross_exposure = risk_cfg["max_gross_exposure"]
    ibkr_cfg = cfg.get("ibkr", {})
    order_type = ibkr_cfg.get("order_type", "market")
    fill_timeout = float(ibkr_cfg.get("fill_timeout_seconds", 60))
    duration = "20 D"
    bar_size = "1 day"

    # 1. Fetch positions and portfolio value
    summary = broker.account_summary()
    positions_raw = broker.positions()
    portfolio_value = _parse_portfolio_value(summary)

    # Build current positions and latest closes
    current_positions: Dict[str, int] = {}
    for p in positions_raw:
        current_positions[p["symbol"]] = int(p["position"])

    # 2. Fetch bars for universe (no cache for live)
    latest_closes: Dict[str, float] = {}
    signals: Dict[str, float] = {}

    for sym in symbols:
        log.info(f"[LIVE] Fetching bars for {sym} ({duration})")
        bars = broker.historical_bars(
            symbol=sym,
            duration=duration,
            bar_size=bar_size,
            use_cache=False,
        )
        if bars is None or len(bars) == 0:
            log.warning(f"[LIVE] No data for {sym}. Skipping.")
            signals[sym] = 0.0
            continue

        bars = _ensure_datetime_index(bars)
        if "close" not in bars.columns:
            log.warning(f"[LIVE] No close column for {sym}. Skipping.")
            signals[sym] = 0.0
            continue

        prices = bars["close"].astype(float).dropna()
        signals[sym] = latest_reversal_signal(prices)
        latest_closes[sym] = float(prices.iloc[-1])

    # Ensure all symbols have closes (for position log)
    for sym in symbols:
        if sym not in latest_closes:
            latest_closes[sym] = 0.0

    # 3. Convert signals to weights and validate
    target_weights = _signals_to_weights(signals, max_position_pct, max_gross_exposure)
    longs = [s for s, sig in signals.items() if sig == 1]
    n_longs = len(longs)
    per_name = min(max_gross_exposure / n_longs, max_position_pct) if n_longs else 0.0
    ok, errors = validate_targets(target_weights, symbols, max_position_pct, max_gross_exposure)
    if not ok:
        log.error(f"[LIVE] Risk validation failed: {errors}")
        return

    # 4. Convert to target shares and compute required trades
    target_shares: Dict[str, int] = {}
    for sym in symbols:
        w = target_weights.get(sym, 0.0)
        price = latest_closes.get(sym)
        if not price or price <= 0:
            target_shares[sym] = 0
            continue
        raw = (portfolio_value * w) / price
        target_shares[sym] = max(0, int(round(raw)))

    trades_to_make: List[Tuple[str, str, int]] = []
    for sym in symbols:
        current = current_positions.get(sym, 0)
        target = target_shares.get(sym, 0)
        delta = target - current
        if delta > 0:
            trades_to_make.append((sym, "BUY", delta))
        elif delta < 0:
            trades_to_make.append((sym, "SELL", -delta))

    # Summary before execution
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log.info(f"\n=== LIVE RUN {ts} ===")
    log.info(f"Portfolio value: {portfolio_value:.2f}")
    log.info(f"Signals: {signals}")
    log.info(f"Raw target weights: n_longs={n_longs}, per_name={per_name:.4f} (min of max_gross/n_longs, max_position_pct)")
    log.info(f"Target weights: {target_weights}")
    log.info(f"Target shares: {target_shares}")
    log.info(f"Current positions: {current_positions}")
    log.info(f"Trades to make: {trades_to_make}")

    # 5. Place orders or dry-run
    fills: List[Tuple[str, str, int, float]] = []

    if dry_run:
        log.info("[LIVE] DRY RUN — no orders placed")
        for sym, side, qty in trades_to_make:
            sig = signals.get(sym, 0)
            ref_price = latest_closes.get(sym, 0.0)
            _append_trade_log(ts, sym, side, qty, fill_price=0.0, signal_value=sig, reference_price=ref_price)
        log.info(f"[LIVE] Would have placed {len(trades_to_make)} orders")
    else:
        for sym, side, qty in trades_to_make:
            try:
                ref_price = float(latest_closes.get(sym, 0))
                limit_price = ref_price if order_type == "limit" else None
                trade = broker.place_order(sym, qty, side, order_type=order_type, limit_price=limit_price)
                broker.ib.sleep(0)
                filled, avg_price, filled_qty = broker.wait_for_fill(trade, timeout_seconds=fill_timeout)
                sig = signals.get(sym, 0)
                if filled:
                    fills.append((sym, side, int(filled_qty), avg_price))
                    log.info(f"[LIVE] Filled {side} {qty} {sym} @ {avg_price:.2f}")
                else:
                    log.warning(f"[LIVE] Order not filled within timeout: {side} {qty} {sym}")
                    avg_price = trade.orderStatus.avgFillPrice if trade.orderStatus else 0.0
                _append_trade_log(ts, sym, side, qty, fill_price=avg_price, signal_value=sig, reference_price=ref_price)
            except Exception as e:
                log.exception(f"[LIVE] Order failed for {side} {qty} {sym}: {e}")
                # Continue with remaining orders per spec

    # 6. Log portfolio snapshot (refresh positions after fills)
    if not dry_run:
        positions_raw = broker.positions()
    _append_portfolio_log(positions_raw, latest_closes)

    # 7. Log P&L snapshot (use latest portfolio value after any fills)
    summary = broker.account_summary()
    portfolio_value = _parse_portfolio_value(summary)
    daily_pnl, running_pnl = _append_snapshot_log(portfolio_value)

    # Daily summary to stdout (for Task Scheduler)
    print(f"\n--- LIVE SUMMARY {ts} ---")
    print(f"Raw target weights: n_longs={n_longs}, per_name={per_name:.4f}")
    print(f"Signals: {signals}")
    print(f"Orders placed: {len(trades_to_make)}")
    print(f"Fills: {fills}")
    print(f"Portfolio value: {portfolio_value:.2f}")
    if daily_pnl is not None:
        print(f"Daily P&L: {daily_pnl:+.2f}")
    if running_pnl is not None:
        print(f"Running P&L: {running_pnl:+.2f}")
    print(f"Portfolio snapshot written to {PORTFOLIO_CSV}")
    print(f"Trade log appended to {TRADES_CSV}")
    print(f"P&L snapshot appended to {SNAPSHOT_CSV}")
