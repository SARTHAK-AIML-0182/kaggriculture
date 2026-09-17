from typing import Dict, List, Any


def format_step_action(
    farmer_action: List[str],
    hand_actions: List[List[str]],
    market_orders: List[List[Any]]
) -> Dict[str, Any]:
    """
    Formats farmer, hands, and market commands into exact Kaggle environment schema.
    """
    valid_farmer = farmer_action if isinstance(farmer_action, list) and len(farmer_action) > 0 else ["PASS"]
    
    valid_hands = []
    if isinstance(hand_actions, list):
        for h in hand_actions:
            if isinstance(h, list) and len(h) > 0:
                valid_hands.append(h)
            else:
                valid_hands.append(["PASS"])

    valid_market = []
    if isinstance(market_orders, list):
        for o in market_orders:
            if isinstance(o, list) and len(o) > 0:
                valid_market.append(o)

    return {
        "farmer": valid_farmer,
        "hands": valid_hands,
        "market": valid_market[:10]
    }
