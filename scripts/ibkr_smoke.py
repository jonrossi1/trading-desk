import asyncio
asyncio.set_event_loop(asyncio.new_event_loop())

from ib_insync import IB

HOST = "127.0.0.1"
PORT = 7497
CLIENT_ID = 1

def main() -> None:
    ib = IB()
    print(f"Connecting to TWS at {HOST}:{PORT} ...")
    ib.connect(HOST, PORT, clientId=CLIENT_ID)

    try:
        print("✅ Connected")
        print("Server time:", ib.reqCurrentTime())

        print("\n=== Account Summary (selected) ===")
        wanted = {"NetLiquidation", "TotalCashValue", "AvailableFunds", "BuyingPower"}
        rows = ib.accountSummary()
        found_any = False
        for r in rows:
            if r.tag in wanted:
                found_any = True
                suffix = f" {r.currency}".strip()
                print(f"{r.tag}: {r.value}{suffix}")
        if not found_any:
            print("(No matching fields returned — still OK)")

        print("\n=== Positions ===")
        positions = ib.positions()
        if not positions:
            print("(none)")
        else:
            for p in positions:
                print(f"{p.contract.symbol}: {p.position} @ avgCost={p.avgCost}")

    finally:
        ib.disconnect()
        print("\nDisconnected.")

if __name__ == "__main__":
    main()
