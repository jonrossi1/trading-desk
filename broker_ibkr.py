import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())

from ib_insync import IB
from typing import Dict, List


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
