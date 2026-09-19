from typing import Dict, List, Any


def format_step_action(
    farmer_action: List[str],
    hand_actions: List[List[str]],
    market_orders: List[List[Any]],
) -> Dict[str, Any]:
    return {
        "farmer": farmer_action,
        "hands": hand_actions,
        "market": market_orders,
    }
