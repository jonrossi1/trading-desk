import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
import time
import os
import pandas as pd

from ib_insync import IB
from ib_insync import Stock, util
from ib_insync import MarketOrder, LimitOrder
from typing import Dict, List, Optional, Tuple


class IBKRBrokerReadOnly:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
        connect_timeout: float = 30.0,
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.connect_timeout = connect_timeout
        self.ib = IB()

    def connect(self) -> None:
        if not self.ib.isConnected():
            self.ib.connect(
                self.host,
                self.port,
                clientId=self.client_id,
                timeout=self.connect_timeout,
            )

    def disconnect(self) -> None:
        if self.ib.isConnected():
            self.ib.disconnect()

    def server_time(self):
        return self.ib.reqCurrentTime()

    def account_summary(self) -> Dict[str, str]:
        summary = {}
        for row in self.ib.accountSummary():
            summary[row.tag] = f"{row.value} {row.currency}".strip()
        return summary

    def positions(self) -> List[dict]:
        out = []
        for p in self.ib.positions():
            out.append(
                {
                    "symbol": p.contract.symbol,
                    "position": p.position,
                    "avg_cost": p.avgCost,
                    "currency": p.contract.currency,
                }
            )
        return out

    def historical_bars(
        self,
        symbol: str,
        duration: str = "2 Y",
        bar_size: str = "1 day",
        what_to_show: str = "TRADES",
        use_rth: bool = True,
        cache_dir: str = "outputs/ibkr_cache",
        use_cache: bool = True,
        sleep_seconds: float = 1.0,
    ) -> pd.DataFrame:
        """
        Fetch historical bars from IBKR and return a DataFrame.

        Returns columns: date, open, high, low, close, volume (when available).
        Notes:
          - Uses SMART routing and USD by default.
          - Uses TRADES data.
          - use_rth=True means Regular Trading Hours only (often cleaner for equities).
          - Adds a small sleep to reduce IBKR pacing issues.
          - Caches to disk by default (use_cache=False for live to get fresh data).
        """
        if not self.ib.isConnected():
            raise RuntimeError("IBKR is not connected. Call broker.connect() first.")

        safe_symbol = symbol.replace("/", "_")
        if use_cache:
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, f"{safe_symbol}__{duration}__{bar_size}.csv")
            if os.path.exists(cache_path):
                df = pd.read_csv(cache_path, parse_dates=["date"])
                return df

        contract = Stock(symbol, "SMART", "USD")

        # Qualify contract (ensures conId etc.)
        self.ib.qualifyContracts(contract)

        bars = self.ib.reqHistoricalData(
            contract,
            endDateTime="",
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow=what_to_show,
            useRTH=use_rth,
            formatDate=1,
        )

        if not bars:
            return pd.DataFrame()

        df = util.df(bars)

        # Normalize column name to 'date' for downstream code
        # ib_insync uses 'date' already; just ensure it's datetime.
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        else:
            # Extremely unlikely, but be defensive
            df = df.reset_index().rename(columns={"index": "date"})
            df["date"] = pd.to_datetime(df["date"])

        if use_cache:
            df.to_csv(cache_path, index=False)

        # Small sleep to reduce pacing issues when looping over symbols
        time.sleep(sleep_seconds)

        return df


class IBKRBroker(IBKRBrokerReadOnly):
    """
    IBKR broker with order placement. Extends read-only broker with
    place_order and wait_for_fill for live trading.
    """

    def place_order(
        self,
        symbol: str,
        quantity: int,
        side: str,  # "BUY" or "SELL"
        order_type: str = "market",
        limit_price: Optional[float] = None,
    ):
        """
        Place an order. Returns the Trade object from ib.placeOrder.
        Use ib.sleep(0) between multiple orders.
        """
        if not self.ib.isConnected():
            raise RuntimeError("IBKR is not connected. Call broker.connect() first.")
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        if side not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")

        contract = Stock(symbol, "SMART", "USD")
        self.ib.qualifyContracts(contract)

        if order_type == "market":
            order = MarketOrder(side, quantity)
        elif order_type == "limit":
            if limit_price is None:
                raise ValueError("limit_price required for limit order")
            order = LimitOrder(side, quantity, limit_price)
        else:
            raise ValueError(f"order_type must be 'market' or 'limit', got {order_type}")

        trade = self.ib.placeOrder(contract, order)
        self.ib.sleep(0)  # Allow framework to process
        return trade

    def wait_for_fill(
        self,
        trade,
        timeout_seconds: float = 60,
    ) -> Tuple[bool, float, float]:
        """
        Wait for order to fill (or timeout). Returns (filled, avg_price, filled_qty).
        """
        start = time.time()
        while time.time() - start < timeout_seconds:
            if trade.isDone():
                filled_qty = trade.filled()
                avg = trade.orderStatus.avgFillPrice if trade.orderStatus else 0.0
                return True, avg, filled_qty
            self.ib.sleep(0.5)
        filled_qty = trade.filled()
        avg = trade.orderStatus.avgFillPrice if trade.orderStatus else 0.0
        return False, avg, filled_qty
