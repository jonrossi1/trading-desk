import sys
import argparse
import logging
import os
from config_loader import load_config
from strategy import target_weights
from risk import validate_targets, print_risk_result
from scripts.risk_smoke import run_risk_smoke_tests
from broker_ibkr import IBKRBroker, IBKRBrokerReadOnly
from logging_setup import setup_logging
from dotenv import load_dotenv
from backtest import run_ibkr_reversal_backtest
from live import run_live
from datetime import datetime
load_dotenv()

TWS_PAPER_PORT = int(os.getenv("IBKR_PAPER_PORT", "7497"))
TWS_LIVE_PORT = int(os.getenv("IBKR_LIVE_PORT",  "7496"))


def parse_args():
    parser = argparse.ArgumentParser(description="MVP Trading Desk")

    parser.add_argument(
        "--mode",
        choices=["paper", "live"],
        default="paper",
        help="Trading mode: paper or live (default: paper)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without placing any trades",
    )

    parser.add_argument(
        "--config",
        default="configs/paper.yaml",
    )

    parser.add_argument(
        "--i-understand-live",
        action="store_true",
        help="Required to run in LIVE mode (prevents accidental live trading).",
    )

    parser.add_argument(
        "--test-risk",
        action="store_true",
        help="Run risk smoke tests and exit",
    )

    parser.add_argument(
        "--ibkr",
        action="store_true",
        help="Connect to IBKR (required for backtest and live modes)",
    )

    parser.add_argument(
        "--ibkr-port",
        type=int,
        default=int(os.getenv("IBKR_PAPER_PORT", str(TWS_PAPER_PORT))),
        help=(
            f"IBKR API port "
            f"(paper: {TWS_PAPER_PORT}, live: {TWS_LIVE_PORT})"
        ),
    )

    parser.add_argument(
        "--run",
        choices=["trade", "backtest", "live"],
        default="trade",
        help="Run mode: trade (default), backtest, or live (forward-looking paper/live via IBKR).",
    )

    parser.add_argument(
        "--duration",
        default="2 Y"
    )

    parser.add_argument(
        "--bar-size",
        default="1 day"
    )

    parser.add_argument(
        "--cost-bps",
        type=float,
        default=5.0
    )

    parser.add_argument(
        "--out",
        default="outputs/backtest.csv"
    )

    return parser.parse_args()

def enforce_ibkr_safety(mode: str, ibkr_port: int, understand_live: bool, log: logging.Logger) -> None:
    # If you point at the LIVE port, require explicit live mode + explicit acknowledgement.
    if ibkr_port == TWS_LIVE_PORT:
        if mode != "live":
            msg = f"Refusing to connect to LIVE TWS port {TWS_LIVE_PORT} unless --mode live is set."
            log.error(msg)
            raise SystemExit("!!! " + msg)

        if not understand_live:
            msg = "Refusing to connect to LIVE TWS without --i-understand-live."
            log.error(msg)
            raise SystemExit("!!! " + msg)

    # If you claim live mode but you're on the paper port, stop: it's confusing and likely a mistake.
    if mode == "live" and ibkr_port == TWS_PAPER_PORT:
        msg = (
            f"--mode live selected but IBKR port is {TWS_PAPER_PORT} (paper). "
            f"Use --ibkr-port {TWS_LIVE_PORT} for live, or switch back to --mode paper."
        )
        log.error(msg)
        raise SystemExit("!!! " + msg)

def main():
    # Logging setup
    log = logging.getLogger("desk")
    log.info("Starting trading desk")

    # Load command arguments
    args = parse_args()

    # Log ports
    log.info(f"IBKR ports: paper={TWS_PAPER_PORT}, live={TWS_LIVE_PORT}, selected={args.ibkr_port}")

    # Check for live vs. paper mode
    mode = args.mode
    if mode == "live" and not args.i_understand_live:
        log.error("Refusing to run in LIVE mode without --i-understand-live")
        raise SystemExit("!!! Refusing to run in LIVE mode without --i-understand-live")

    if args.ibkr:
        enforce_ibkr_safety(args.mode, args.ibkr_port, args.i_understand_live, log)

    # Load configs
    cfg = load_config(args.config)
    symbols = cfg['universe']['symbols']
    strategy_name = cfg['strategy']['name']
    risk_cfg = cfg['risk']
    max_position_pct = risk_cfg['max_position_pct']
    max_gross_exposure = risk_cfg['max_gross_exposure']

    # Run risk check smoke tests
    if args.test_risk:
        run_risk_smoke_tests(
            symbols,
            max_position_pct,
            max_gross_exposure)
        sys.exit(0)

    ################################
    ### Run main trading program ###
    ################################

    broker = None

    # Live mode: use IBKRBroker (writable) with host/port from config
    if args.run == "live":
        if not args.ibkr:
            log.error("Live mode requires --ibkr.")
            sys.exit(2)
        ibkr_cfg = cfg.get("ibkr", {})
        host = os.getenv("IBKR_HOST") or ibkr_cfg.get("host", "127.0.0.1")
        port = ibkr_cfg.get("port") or args.ibkr_port
        client_id = int(ibkr_cfg.get("client_id", 1))
        connect_timeout = float(ibkr_cfg.get("connect_timeout", 30))
        broker = IBKRBroker(host=host, port=port, client_id=client_id, connect_timeout=connect_timeout)
        try:
            broker.connect()
        except TimeoutError:
            log.error(
                f"Connection to TWS/IB Gateway timed out (host={host}, port={port}). "
                "Check that TWS or IB Gateway is running, API is enabled (Settings → API), "
                "and the port matches (paper: 7497, live: 7496)."
            )
            raise SystemExit(1)
        log.info(f"\n=== IBKR Live (host={host}, port={port}) ===")
        log.info(f"Server time: {broker.server_time()}")
        log.info(f"Dry run: {args.dry_run}")
        run_live(
            broker=broker,
            symbols=symbols,
            cfg=cfg,
            cost_bps=args.cost_bps,
            dry_run=args.dry_run,
            log=log,
        )
        log.info("Live run complete. Exiting.")
        if broker:
            try:
                broker.disconnect()
            except Exception as e:
                log.warning(f"Error during broker disconnect: {e}")
        log.info("Trading desk shutdown complete")
        return

    # IBKR connection for backtest or trade
    if args.ibkr:
        ibkr_cfg = cfg.get("ibkr", {})
        host = os.getenv("IBKR_HOST") or ibkr_cfg.get("host", "127.0.0.1")
        connect_timeout = float(ibkr_cfg.get("connect_timeout", 30))
        broker = IBKRBrokerReadOnly(host=host, port=args.ibkr_port, connect_timeout=connect_timeout)
        try:
            broker.connect()
        except TimeoutError:
            log.error(
                f"Connection to TWS/IB Gateway timed out (host={host}, port={args.ibkr_port}). "
                "Check that TWS or IB Gateway is running, API is enabled (Settings → API), "
                "and the port matches (paper: 7497, live: 7496)."
            )
            raise SystemExit(1)

        log.info("\n=== IBKR (read-only) ===")
        log.info(f"Server time: {broker.server_time()}")

        summary = broker.account_summary()
        for k in ["NetLiquidation", "AvailableFunds", "BuyingPower"]:
            if k in summary:
                log.info(f"{k}: {summary[k]}")

        positions = broker.positions()
        log.info("\nCurrent positions:")
        if not positions:
            log.info("(none)")
        else:
            for p in positions:
                log.info(f"{p['symbol']}: {p['position']} @ {p['avg_cost']}")

        # Backtest mode: run historical simulation and exit early
        if args.run == "backtest":
            if not broker:
                log.error("Backtest mode requires --ibkr (IBKR connection) to fetch historical data.")
                sys.exit(2)

            # For now, keep the universe small to avoid IBKR pacing limits
            bt_symbols = symbols[:3]

            # Backtest output
            out_path = args.out
            if out_path == "outputs/backtest.csv":  # default
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                base, ext = os.path.splitext(out_path)
                out_path = f"{base}_{ts}{ext}"

            run_ibkr_reversal_backtest(
                broker=broker,
                symbols=bt_symbols,
                duration=args.duration,
                bar_size=args.bar_size,
                cost_bps=args.cost_bps,
                out_csv=out_path,
                log=log,
            )

            log.info("Backtest complete. Exiting.")
            return

    # Load trading strategy (weights)
    targets = target_weights(strategy_name, symbols)

    # Risk check to ensure no shorting, etc.
    ok, errors = validate_targets(
        targets,
        symbols,
        max_position_pct,
        max_gross_exposure,
    )

    print_risk_result(ok, errors)
    if not ok:
        log.error(f"Risk validation failed: {errors}")
        sys.exit(1)

    # Display output
    log.info("Trading desk is running ✅")
    log.info(f"Mode: {mode.upper()}")
    log.info(f"Dry run: {'ON ✅' if args.dry_run else 'OFF ❌'}")
    log.info(f"Max position size: {cfg['risk']['max_position_pct'] * 100:.0f}%")

    log.info(f"Universe: {symbols}")
    log.info(f"Strategy name: {strategy_name}")
    log.info(f"Target weights: {targets}")

    if mode == "live" and args.dry_run:
        log.warning("⚠️  Live mode + dry run enabled (safe)")
    elif mode == "live":
        log.warning("⚠️  LIVE MODE ENABLED — real orders would be placed")
    else:
        log.info("Paper trading mode (safe)")

    # Disconnect IBKR
    if broker:
        log.info("Disconnecting from IBKR")
        try:
            broker.disconnect()
            log.info("Disconnected from IBKR")
        except Exception as e:
            log.warning(f"Error during broker disconnect: {e}")

    log.info("Trading desk shutdown complete")
    log.info("To fully stop IBKR API access, quit TWS now (File → Exit)")

# Execute main
if __name__ == "__main__":
    setup_logging()
    log = logging.getLogger("desk")

    try:
        main()
    except SystemExit as e:
        log.error(f"SystemExit: {e}")
        raise
    except Exception:
        log.exception("Unhandled exception")
        raise

# See PyCharm help at https://www.jetbrains.com/help/pycharm/