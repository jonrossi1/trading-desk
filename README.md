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
- Use **kebab-case** for branch names (e.g. `feat-risk-limits`, `test-pr-flow`).

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

    trade.py              # CLI entrypoint
    broker_ibkr.py        # IBKR connection wrapper
    config_loader.py      # YAML + env config loading
    risk.py               # Risk checks and limits
    strategy.py           # Strategy logic
    configs/              # Shared YAML configs
    scripts/              # Smoke tests and utilities

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
- `logs/`       (runtime logs)
- `__pycache__/`

These are ignored via `.gitignore`.

---

## Design Notes

This project intentionally separates:
- shared logic (committed to GitHub)
- local runtime configuration (via `.env`)
- execution environment (local TWS per developer)

This keeps collaboration safe, reproducible, and minimizes the risk of accidental live trading.
