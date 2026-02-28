# Trading Desk (IBKR / ib_insync)

This repository contains a Python-based trading desk project built on the **Interactive Brokers (IBKR)** API broker, using `ib_insync`.

The project is designed for collaborative development where each contributor:
- runs their own local Trader Workstation (TWS)
- uses their own IBKR account
- shares strategy, risk, and execution logic via this repository

Local runtime configuration (ports, client IDs, credentials) is intentionally kept out of version control.

---

## Getting Started (Local Setup)

### 1. Clone the repository

    git clone https://github.com/<your-username>/trading_desk.git
    cd trading_desk

### 2. Create and activate a virtual environment

    python3 -m venv .venv
    source .venv/bin/activate

You should see `(.venv)` in your terminal prompt once activated.

You only need to create the virtual environment once.
Each time you reopen a terminal, re-run:

    source .venv/bin/activate

### 3. Install dependencies

    pip install -r requirements.txt

---

## Environment Variables

This project uses a `.env` file for local, machine-specific configuration.
The `.env` file is **not committed to Git**.

### 1. Create your local `.env`

    cp .env.example .env

### 2. Edit `.env`

Set values appropriate for your machine and IBKR setup, including:
- IBKR host
- paper vs live ports
- client ID

**Never commit `.env`.**

---

## IBKR / TWS Prerequisites

To run this project, you must have:

- An Interactive Brokers account (https://www.interactivebrokers.com/)
- Trader Workstation (TWS) installed (download the latest *stable* version here: https://www.interactivebrokers.com/en/trading/download-tws.php?p=stable)
- IBKR API access enabled in TWS:
  - Settings → API → Enable ActiveX and Socket Clients
- TWS running in Paper Trading mode (strongly recommended)

Default paper trading port:
- 7497 (can be overridden via `.env`)

Each collaborator runs their own local TWS instance.
Client IDs only need to be unique per machine, not across people.

---

## Safe First Run (Smoke Tests)

Before running any strategy logic, verify connectivity:

    python scripts/ibkr_smoke.py

This script connects to TWS, verifies API access, and places **no trades**.

You can also validate risk logic independently:

    python scripts/risk_smoke.py

---

## Live Trading Warning

Running in live mode can place **real trades**.

Safety guidelines:
- Always start in paper mode
- Use `--dry-run` when testing new logic
- Carefully review the configuration printed at startup

If you are unsure, **do not run in live mode**.

---

## Collaboration Protocol (Important)

This repository uses a pull-request–based workflow to reduce the risk of accidental changes to `main`.

### Rules
- **Do not push directly to `main`.**
- All changes should be made on a **feature branch** and merged via a **pull request**.
- **Always pull the latest `main` before starting new work or pushing a branch.**
- Use **Squash and merge** for PRs unless there is a specific reason not to.
- Live trading code should never be merged without explicit review and confirmation.

### Typical Flow

1. Pull latest changes:

       git checkout main
       git pull

2. Create a feature branch (e.g., `feature-example`):

       git checkout -b feature-example

3. Make changes and commit:

       git commit -m "Commit message"

4. Pull latest `main` into your branch **before pushing**!

       git pull origin main

5. Push your branch. When pushing a new branch for the first time (e.g., `feature-example`), use:

       git push -u origin feature-example

6. The `-u` flag sets the upstream tracking relationship so that future pushes can be done with:

       git push

7. Go to GitHub, open a pull request, and merge via GitHub after review.

### Branch Naming
- Use **kebab-case** for branch names (e.g. `feature-risk-limits`, `test-pr-flow`).

### Deleting branches after merge

After a pull request is merged, the feature branch should be deleted to keep the repository clean.

#### Delete the branch on GitHub
- When merging a PR, GitHub will prompt you to **Delete branch**
- This removes the remote branch (e.g. `origin/feat-example`)

#### Delete the branch locally
After switching back to `main` and pulling the latest changes:

    git checkout main
    git pull
    git branch -d feat-example

If Git warns that the branch is not fully merged (rare if the PR was merged), you can force delete:

    git branch -D feat-example

#### Clean up stale remote references (optional)

    git fetch --prune

This removes references to remote branches that were deleted on GitHub.



### Notes
Branch protection may not be strictly enforced by GitHub on private repositories.
These rules are therefore enforced by **team convention** and should be followed consistently.

---

## Repository Structure (High Level)

    trade.py              # CLI entrypoint (trading + backtesting + live)
    broker_ibkr.py        # IBKR connection + historical data + order placement
    backtest.py           # Historical simulation engine + reversal signal logic
    live.py               # Live trading loop (--run live)
    config_loader.py      # YAML + env config loading
    risk.py               # Risk checks and limits
    strategy.py           # Strategy definitions
    configs/              # Shared YAML configs
    scripts/              # Smoke tests and utilities
    outputs/              # Backtest result CSVs (local only)

---

## Backtesting Mode (Historical Simulation)

In addition to paper/live trading modes, the trading desk supports a **historical backtest mode** using IBKR historical bar data.

Backtest mode allows you to:

- Fetch historical daily bar data directly from IBKR
- Simulate a trading strategy over a specified duration
- Model proportional transaction costs
- Compute performance metrics (Sharpe ratio, max drawdown, total return)
- Write timestamped output files for reproducibility

### Example: Run a Backtest

    python trade.py --run backtest --mode paper --ibkr --config configs/paper.yaml --duration "1 Y" --bar-size "1 day" --cost-bps 5

### Key Parameters

- `--run backtest`  
  Switches from trading mode to historical simulation mode.

- `--duration`  
  Historical lookback window (e.g., `"1 Y"`, `"2 Y"`).

- `--bar-size`  
  Bar frequency (e.g., `"1 day"`, `"1 hour"`).

- `--cost-bps`  
  Proportional transaction cost in basis points applied to turnover.

- `--out`  
  Optional output file path. If not specified, timestamped CSV output is written to:
  
      outputs/backtest_<timestamp>.csv

### Output

Each backtest run generates:

- Daily equity curve
- Signal and turnover information
- Transaction cost impact
- Performance summary logged to console
- CSV output saved to `outputs/`

---

### Architecture Notes (Backtesting)

Backtesting is implemented modularly:

- `broker_ibkr.py` → historical bar data access via IBKR
- `backtest.py` → simulation engine and performance metrics
- `strategy.py` → strategy definitions (static and extensible)
- `trade.py` → CLI orchestration for both trading and backtesting

This design allows strategies to be tested historically and later deployed in paper or live mode with minimal structural changes.

---

## Live Mode (Forward-Looking Paper/Live via IBKR)

The `--run live` mode runs the short-term reversal strategy on a forward-looking basis, designed to be called once daily (e.g. via Task Scheduler):

1. Connects to TWS/IB Gateway using `configs/paper.yaml` (host/port; env override via `IBKR_HOST`, `IBKR_PAPER_PORT`)
2. Fetches current portfolio positions from IBKR
3. Pulls latest ~20 days of daily bars for the universe (same as backtest)
4. Runs the same reversal signal logic to generate target positions
5. Compares target vs current positions, computes required trades
6. Submits orders (market or limit, configurable in YAML) or logs in dry-run
7. Logs to `logs/live_trades.csv` and `logs/live_portfolio.csv`

### Example: Dry Run (see what it would trade)

    python trade.py --run live --mode paper --ibkr --config configs/paper.yaml --cost-bps 5 --dry-run

### Example: Actual Paper Trading

    python trade.py --run live --mode paper --ibkr --config configs/paper.yaml --cost-bps 5

### Safety

- **Max position size** and **max gross exposure** are configurable in YAML (`risk` section)
- If an order fails, the error is logged and execution continues with remaining orders
- Use `--dry-run` to compute signals and log intended trades without placing orders

### Log Files

| File | Columns |
|------|---------|
| `logs/live_trades.csv` | timestamp, symbol, side, quantity, fill_price, reference_price, signal_value |
| `logs/live_portfolio.csv` | timestamp, symbol, position, avg_cost, unrealized_pnl |
| `logs/live_snapshot.csv` | timestamp, portfolio_value, daily_pnl, running_pnl |

**Raw target weights:** Only symbols with reversal signal = 1 get allocation (long-only). Each long gets `per_name = min(max_gross_exposure / n_longs, max_position_pct)`. Example: 2 longs, `max_gross_exposure=1.0`, `max_position_pct=0.2` → each gets 0.2, total 0.4.

**Share sizing:** `quantity = round((portfolio_value × target_weight) / price)`. `reference_price` is the latest daily close used for sizing; it is logged even when dry-run or unfilled.

**Running P&L:** When there are at least 2 runs, `logs/live_snapshot.csv` records `daily_pnl` (change vs previous run) and `running_pnl` (current portfolio value minus first-run value). Printed to stdout in the live summary.

### IBKR Config (paper.yaml)

    ibkr:
      host: "127.0.0.1"
      port: 7497
      order_type: "market"   # or "limit"
      fill_timeout_seconds: 60

---

## Logging

Runtime logs are written locally to:

    logs/desk.log

Logs are intended for local debugging only and are not committed to Git.
Each developer has their own log files.

If the `logs/` directory or log file does not exist, it will be created automatically at runtime.

---

## Local-only Files

The following files and directories are intentionally local and not shared:

- `.env`        (local IBKR and runtime configuration)
- `.venv/`      (Python virtual environment)
- `logs/`       (runtime logs, live_trades.csv, live_portfolio.csv, live_snapshot.csv)
- `__pycache__/`

These are ignored via `.gitignore`.

---

## Design Notes

This project intentionally separates:
- shared logic (committed to GitHub)
- local runtime configuration (via `.env`)
- execution environment (local TWS per developer)

This keeps collaboration safe, reproducible, and minimizes the risk of accidental live trading.
