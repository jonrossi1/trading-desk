import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())
import time
import os
import pandas as pd

from ib_insync import IB
from typing import Dict, List
from ib_insync import Stock, util


class IBKRBrokerReadOnly:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 1,
    ):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()

    def connect(self) -> None:
        if not self.ib.isConnected():
            self.ib.connect(self.host, self.port, clientId=self.client_id)

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
          - Caches to disk by default to avoid repeated IBKR requests.
        """
        if not self.ib.isConnected():
            raise RuntimeError("IBKR is not connected. Call broker.connect() first.")

        os.makedirs(cache_dir, exist_ok=True)
        safe_symbol = symbol.replace("/", "_")
        cache_path = os.path.join(cache_dir, f"{safe_symbol}__{duration}__{bar_size}.csv")

        # Cache hit
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

        # Save cache
        df.to_csv(cache_path, index=False)

        # Small sleep to reduce pacing issues when looping over symbols
        time.sleep(sleep_seconds)

        return df
