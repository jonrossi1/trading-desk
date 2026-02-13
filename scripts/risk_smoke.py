from risk import validate_targets, print_risk_result


def run_risk_smoke_tests(symbols, max_position_pct: float, max_gross_exposure: float) -> None:
    scenarios = {
        "PASS": {"SPY": 0.2, "QQQ": 0.2, "IWM": 0.2},
        "SHORT": {"SPY": 0.6, "QQQ": -0.1, "IWM": 0.5},
        "MAX_POSITION": {"SPY": max_position_pct + 0.01, "QQQ": 0.2, "IWM": 0.1},
        "GROSS": {"SPY": 0.6, "QQQ": 0.6, "IWM": 0.2},
        "MULTI": {"SPY": max_position_pct + 0.2, "QQQ": -0.1, "IWM": 0.8},
        "UNKNOWN": {"SPY": 0.1, "QQQ": 0.1, "NOT_A_TICKER": 0.1},
    }

    for name, targets in scenarios.items():
        print(f"\n=== {name} ===")
        ok, errors = validate_targets(
            targets,
            symbols,
            max_position_pct,
            max_gross_exposure
        )
        print_risk_result(ok, errors)
