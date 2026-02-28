# backtest.py
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import List

import numpy as np
import pandas as pd


################################
### Metrics                  ###
################################
def annualized_sharpe(daily_returns: pd.Series) -> float:
    """
    Annualized Sharpe ratio using daily returns, assuming 252 trading days/year.
    """
    r = daily_returns.dropna()
    if len(r) < 2:
        return float("nan")
    vol = r.std(ddof=1)
    if vol == 0 or np.isnan(vol):
        return float("nan")
    return float(math.sqrt(252) * r.mean() / vol)


def max_drawdown(equity_curve: pd.Series) -> float:
    """
    Max drawdown of an equity curve (as a negative number, e.g. -0.23 = -23%).
    """
    ec = equity_curve.dropna()
    if ec.empty:
        return float("nan")
    peak = ec.cummax()
    dd = (ec / peak) - 1.0
    return float(dd.min())


################################
### Backtest core            ###
################################
def latest_reversal_signal(prices: pd.Series) -> float:
    """
    Return the latest short-term reversal signal (-1, 0, or 1) given price history.
    Reuses the same logic as short_term_reversal_backtest: signal_t = -sign(ret_{t-1}).
    """
    df = pd.DataFrame({"close": prices}).dropna()
    if len(df) < 2:
        return 0.0
    df["ret"] = df["close"].pct_change()
    signal = -np.sign(df["ret"].shift(1)).fillna(0.0)
    return float(signal.iloc[-1])


def short_term_reversal_backtest(
    prices: pd.Series,
    cost_bps: float = 5.0,
) -> pd.DataFrame:
    """
    Simple daily short-term reversal strategy:

      ret_t    = close_t / close_{t-1} - 1
      signal_t = -sign(ret_{t-1})   (uses yesterday's return; avoids look-ahead)
      pnl_t    = signal_t * ret_t - cost * turnover

    Transaction cost model:
      cost_bps is applied per unit of turnover, where turnover_t = |signal_t - signal_{t-1}|.
      Example: going from -1 to +1 => turnover = 2.
    """
    df = pd.DataFrame({"close": prices}).dropna()
    df["ret"] = df["close"].pct_change()

    # Signal uses ONLY information available at t-1 (!! Avoids lookahead bias !!)
    # Reversal strategy
    df["signal"] = -np.sign(df["ret"].shift(1)).fillna(0.0)

    # Momentum strategy (opposite of reversal)
    #df["signal_momentum"] = np.sign(df["ret"].shift(1))

    # Turnover: how much we change position day-to-day
    df["turnover"] = (df["signal"] - df["signal"].shift(1)).abs().fillna(0.0)

    # Costs in decimal terms
    cost = float(cost_bps) / 10_000.0
    df["cost"] = cost * df["turnover"]

    df["pnl"] = (df["signal"] * df["ret"]).fillna(0.0) - df["cost"]
    df["equity"] = (1.0 + df["pnl"]).cumprod()

    return df


def _ensure_datetime_index(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize bars to have a datetime index named 'date' and a 'close' column.
    Accepts either:
      - a 'date' column, or
      - datetime index already
    """
    if bars is None or len(bars) == 0:
        return bars

    if "date" in bars.columns:
        out = bars.copy()
        out["date"] = pd.to_datetime(out["date"])
        out = out.set_index("date")
        return out

    # If no date column, assume index is datetime-like
    out = bars.copy()
    out.index = pd.to_datetime(out.index)
    out.index.name = "date"
    return out


################################
### Runner                   ###
################################
@dataclass(frozen=True)
class BacktestSummary:
    symbol: str
    sharpe: float
    max_dd: float
    total_return: float


def run_ibkr_reversal_backtest(
    broker,
    symbols: List[str],
    duration: str,
    bar_size: str,
    cost_bps: float,
    out_csv: str,
    log,
) -> List[BacktestSummary]:
    """
    Runs a short-term reversal backtest for each symbol, using IBKR historical bars.

    Requires: broker.historical_bars(symbol, duration, bar_size) -> DataFrame with:
      - 'close' column
      - and either a 'date' column or a datetime index

    Writes a single CSV containing all symbols with columns:
      date, close, ret, signal, turnover, cost, pnl, equity, symbol
    """
    if not symbols:
        raise ValueError("No symbols provided for backtest.")

    # Avoid IBKR pacing issues during the deadline:
    if len(symbols) > 10:
        raise ValueError(
            "Too many symbols for a quick IBKR backtest. "
            "Use <= 10 symbols (recommend 1–5 for the deadline)."
        )

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)

    all_rows = []
    summaries: List[BacktestSummary] = []

    for sym in symbols:
        log.info(f"[BACKTEST] Fetching IBKR bars for {sym} (duration={duration}, bar_size={bar_size})")
        bars = broker.historical_bars(symbol=sym, duration=duration, bar_size=bar_size)

        if bars is None or len(bars) == 0:
            log.warning(f"[BACKTEST] No data returned for {sym}. Skipping.")
            continue

        bars = _ensure_datetime_index(bars)
        if "close" not in bars.columns:
            raise ValueError(f"IBKR bars for {sym} missing 'close' column. Columns: {list(bars.columns)}")

        prices = bars["close"].astype(float).dropna()
        bt = short_term_reversal_backtest(prices, cost_bps=cost_bps)

        sharpe = annualized_sharpe(bt["pnl"])
        mdd = max_drawdown(bt["equity"])
        total_ret = float(bt["equity"].iloc[-1] - 1.0)

        summaries.append(BacktestSummary(symbol=sym, sharpe=sharpe, max_dd=mdd, total_return=total_ret))
        log.info(f"[BACKTEST] {sym}: Sharpe={sharpe:.2f} | MaxDD={mdd:.2%} | TotalRet={total_ret:.2%}")

        out = bt.copy()
        out["symbol"] = sym
        out = out.reset_index()  # index is date
        all_rows.append(out)

    if not all_rows:
        raise RuntimeError("Backtest produced no results (no symbols returned data).")

    result = pd.concat(all_rows, ignore_index=True)
    result.to_csv(out_csv, index=False)
    log.info(f"[BACKTEST] Wrote results CSV: {out_csv}")

    return summaries