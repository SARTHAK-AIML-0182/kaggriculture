from typing import Dict, Any
from state import GameState
from planner import build_task_queue, solve_worker_actions
from market import generate_market_orders
from actions import format_step_action


def agent(obs: Dict[str, Any], config: Any = None) -> Dict[str, Any]:
    try:
        state = GameState.from_obs(obs)

        # 1. Build spatial task queue & solve worker movement/actions
        tasks = build_task_queue(state)
        farmer_act, hand_acts = solve_worker_actions(state, tasks)

        # 2. Generate market orders & town shop solver
        market_orders = generate_market_orders(
            day=state.day,
            turn=state.turn,
            money=state.money,
            shed=state.shed,
            seeds=state.seeds,
            animals=state.animals,
            tiles=state.tiles,
            unlocked_quads=state.unlocked_quadrants,
            unlocked_shops=state.unlocked_shops,
            hires_today=state.hires_today,
            hands_count=len(state.hands_pos),
            farmer_inv_items=state.farmer_inv_items,
            hand_inv_items=state.hand_inv_items
        )


        # 3. Format into exact Kaggle action response dictionary
        return format_step_action(
            farmer_action=farmer_act,
            hand_actions=hand_acts,
            market_orders=market_orders
        )

    except Exception:
        # Failsafe fallback dictionary prevents disqualification timeouts or exceptions
        return {
            "farmer": ["PASS"],
            "hands": [],
            "market": []
        }
