from typing import Dict, List


def target_weights(strategy_name: str, symbols: List[str]) -> Dict[str, float]:
    """
    Return desired portfolio weights for each symbol.
    For now: 'noop' means hold nothing (all zeros).
    """
    if strategy_name == "noop":
        return {s: 0.0 for s in symbols}

    raise ValueError(f"Unknown strategy: {strategy_name}")