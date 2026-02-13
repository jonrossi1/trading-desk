# Trading Desk (IBKR / ib_insync)

This repository contains a Python-based trading desk project built on **Interactive Brokers (IBKR)** using `ib_insync`.

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

---

### 2. Create and activate a virtual environment

    python3 -m venv .venv
    source .venv/bin/activate

You should see `(.venv)` in your terminal prompt once activated.

You only need to create the virtual environment once.
Each time you reopen a terminal, re-run:

    source .venv/bin/activate

---

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

## Collaboration Notes

- All development happens on feature branches
- Changes are merged via pull requests
- Local environment files (`.env`, `.venv`, logs) are not shared
- Strategy and risk logic should remain deterministic and reviewable

---

## Repository Structure (High Level)

    trade.py              # CLI entrypoint
    broker_ibkr.py        # IBKR connection wrapper
    config_loader.py      # YAML + env config loading
    risk.py               # Risk checks and limits
    strategy.py           # Strategy logic
    configs/              # Shared YAML configs
    scripts/              # Smoke tests and utilities

---

## Design Notes

This project intentionally separates:
- shared logic (committed to GitHub)
- local runtime configuration (via `.env`)
- execution environment (local TWS per developer)

This keeps collaboration safe, reproducible, and minimizes the risk of accidental live trading.

## Logging

Runtime logs are written locally to:

    logs/desk.log

Logs are intended for local debugging only and are not committed to Git.
Each developer has their own log files.

If the `logs/` directory or log file does not exist, it will be created automatically at runtime.

## Local-only Files

The following files and directories are intentionally local and not shared:

- `.env`        (local IBKR and runtime configuration)
- `.venv/`      (Python virtual environment)
- `logs/`       (runtime logs)
- `__pycache__/`

These are ignored via `.gitignore`.
