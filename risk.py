import logging
from typing import Dict, List, Tuple, Iterable
from typing import List


# Logging setup
log = logging.getLogger("desk")

def validate_targets(
    targets: Dict[str, float],
    universe: Iterable[str],
    max_position_pct: float,
    max_gross_exposure: float,
) -> Tuple[bool, List[str]]:

    errors: List[str] = []

    universe_set = set(universe)
    unknown = [sym for sym in targets if sym not in universe_set]

    if unknown:
        errors.append(
            f"Unknown ticker(s) in targets: {', '.join(sorted(unknown))}"
        )

    # 1) Long-only: no negative weights
    for sym, w in targets.items():
        if w < 0:
            errors.append(f"Shorting not allowed: {sym} has weight {w}")

    # 2) Max position size (also catch negatives already, but this keeps it simple)
    for sym, w in targets.items():
        if w > max_position_pct:
            errors.append(
                f"Position too large: {sym} weight {w} exceeds max {max_position_pct}"
            )

    # 3) Gross exposure (sum of weights for long-only portfolios)
    gross = sum(targets.values())
    if gross > max_gross_exposure + 1e-9:
        errors.append(f"Gross exposure {gross:.4f} exceeds max {max_gross_exposure}")

    ok = len(errors) == 0
    return ok, errors

def print_risk_result(ok: bool, errors: List[str]) -> None:
    if ok:
        log.info("✅ Risk check passed")
    else:
        log.error(f"❌ Risk check failed ({len(errors)} issue(s)):")
        for e in errors:
            print(f"  - {e}")