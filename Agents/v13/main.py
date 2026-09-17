from typing import Dict, List, Tuple, Any, Optional, Set
from dataclasses import dataclass, field
import math
from collections import deque

# ==============================================================================
# Kaggriculture v13 Autonomous Engine (Target: ≥$150,000 Revenue by Day 30)
# ==============================================================================

# --- Module: state.py ---

@dataclass
class GameState:
    player: int = 0
    day: int = 0         # 0-indexed 0..29
    step: int = 0        # 0..719
    turn: int = 0        # 0..23
    money: float = 3000.0
    farmer_pos: Tuple[int, int] = (4, 4)
    farmer_inventory: int = 0
    hands_pos: List[Tuple[int, int]] = field(default_factory=list)
    hand_inventories: List[int] = field(default_factory=list)
    unlocked_quadrants: List[str] = field(default_factory=lambda: ["NW"])
    tiles: List[List[Any]] = field(default_factory=list)
    shed: Dict[str, int] = field(default_factory=dict)
    seeds: Dict[str, int] = field(default_factory=dict)
    animals: Dict[str, int] = field(default_factory=dict)
    market_prices: Dict[str, float] = field(default_factory=dict)
    market_inventory: Dict[str, float] = field(default_factory=dict)
    unlocked_shops: List[Dict[str, Any]] = field(default_factory=list)
    hires_today: int = 0

    @classmethod
    def from_obs(cls, obs: Dict[str, Any]) -> "GameState":
        player_idx = int(obs.get("player", 0))
        farms = obs.get("farms", [])
        if not farms or player_idx >= len(farms):
            return cls(player=player_idx)

        farm = farms[player_idx]
        step = int(obs.get("step", 0))
        day = int(obs.get("day", step // 24))
        turn = step % 24
        money = float(farm.get("money", 0.0))

        farmer_raw = farm.get("farmer", [4, 4])
        farmer_pos = (int(farmer_raw[0]), int(farmer_raw[1])) if isinstance(farmer_raw, (list, tuple)) else (4, 4)

        raw_hands = farm.get("hands", [])
        hands_pos: List[Tuple[int, int]] = []
        hand_inventories: List[int] = []

        private = obs.get("private", {})
        raw_inventories = private.get("inventories", [])
        farmer_inv_dict = raw_inventories[0] if (isinstance(raw_inventories, list) and len(raw_inventories) > 0 and isinstance(raw_inventories[0], dict)) else {}
        farmer_inventory = sum(farmer_inv_dict.values())

        for idx, h in enumerate(raw_hands):
            if isinstance(h, (list, tuple)) and len(h) >= 2:
                hands_pos.append((int(h[0]), int(h[1])))
                # Hand inventory index in private["inventories"] is idx + 1 (idx 0 is farmer)
                if isinstance(raw_inventories, list) and (idx + 1) < len(raw_inventories):
                    inv_dict = raw_inventories[idx + 1]
                    hand_inventories.append(sum(inv_dict.values()) if isinstance(inv_dict, dict) else 0)
                else:
                    hand_inventories.append(0)
            elif isinstance(h, dict):
                pos = h.get("pos", [4, 4])
                hands_pos.append((int(pos[0]), int(pos[1])))
                inv = h.get("items", {})
                hand_inventories.append(sum(inv.values()) if isinstance(inv, dict) else 0)


        unlocked_quadrants = farm.get("unlocked_quadrants", ["NW"])
        if not isinstance(unlocked_quadrants, list):
            unlocked_quadrants = ["NW"]

        tiles = farm.get("tiles", [])

        shed = private.get("shed", {}) if isinstance(private.get("shed"), dict) else {}
        seeds = private.get("seeds", {}) if isinstance(private.get("seeds"), dict) else {}
        animals = private.get("animals", {}) if isinstance(private.get("animals"), dict) else {}

        market_info = obs.get("market", {})
        market_prices = market_info.get("prices", {}) if isinstance(market_info, dict) else {}
        market_inventory = market_info.get("inventory", {}) if isinstance(market_info, dict) else {}

        town_info = obs.get("town", {})
        unlocked_shops = town_info.get("unlocked_shops", []) if isinstance(town_info, dict) else []

        hires_today = int(farm.get("hires_today", 0))

        return cls(
            player=player_idx,
            day=day,
            step=step,
            turn=turn,
            money=money,
            farmer_pos=farmer_pos,
            farmer_inventory=farmer_inventory,
            hands_pos=hands_pos,
            hand_inventories=hand_inventories,
            unlocked_quadrants=unlocked_quadrants,
            tiles=tiles,
            shed=shed,
            seeds=seeds,
            animals=animals,
            market_prices=market_prices,
            market_inventory=market_inventory,
            unlocked_shops=unlocked_shops,
            hires_today=hires_today
        )


# --- Module: board.py ---

SHED_TILES = [(4, 4), (5, 4), (4, 5), (5, 5)]

QUADRANTS = {
    "NW": (0, 4, 0, 4),
    "NE": (5, 9, 0, 4),
    "SW": (0, 4, 5, 9),
    "SE": (5, 9, 5, 9),
}

HARVEST_AGE = {
    "WHEAT": 3,
    "CARROT": 3,
    "MELON": 12,
    "TOMATO": 8,
    "STRAWBERRY": 10,
}

LAST_PLANT_DAY = {
    "WHEAT": 26,
    "CARROT": 26,
    "TOMATO": 15,
    "STRAWBERRY": 15,
    "MELON": 17,
}


def manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def nearest_shed_tile(curr: Tuple[int, int]) -> Tuple[int, int]:
    return min(SHED_TILES, key=lambda st: manhattan(curr, st))


def move_towards(curr: Tuple[int, int], target: Tuple[int, int]) -> List[str]:
    x, y = curr
    tx, ty = target
    if x < tx:
        return ["EAST"]
    if x > tx:
        return ["WEST"]
    if y < ty:
        return ["SOUTH"]
    if y > ty:
        return ["NORTH"]
    return ["PASS"]


def tile_at(tiles: List[List[Any]], x: int, y: int) -> Any:
    if y < 0 or y >= len(tiles):
        return "LOCKED"
    if x < 0 or x >= len(tiles[y]):
        return "LOCKED"
    return tiles[y][x]


def unlocked(tile: Any) -> bool:
    return tile != "LOCKED"


def is_free(tile: Any) -> bool:
    return tile is None or tile == "EMPTY" or tile == {}


def is_plant(tile: Any) -> bool:
    return isinstance(tile, dict) and tile.get("kind") == "PLANT"


def is_weed(tile: Any) -> bool:
    return isinstance(tile, dict) and tile.get("kind") == "WEED"


def is_pasture(tile: Any) -> bool:
    return isinstance(tile, dict) and tile.get("kind") == "PASTURE"


def is_coop(tile: Any) -> bool:
    return isinstance(tile, dict) and tile.get("kind") == "COOP"


def crop_ready_to_harvest(tile: Dict[str, Any], day: int) -> bool:
    if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
        return False
    crop = tile.get("crop")
    if not crop:
        return False
    planted_day = int(tile.get("planted_day", day))
    age = day - planted_day

    # In end-game (Day 28+), harvest whenever first_yield_day is reached
    if day >= 28:
        if crop in ("CARROT", "WHEAT"):
            min_age = 2
        elif crop == "MELON":
            min_age = 10
        else:
            min_age = HARVEST_AGE.get(crop, 2)
    else:
        min_age = HARVEST_AGE.get(crop, 2)

    yield_units = int(tile.get("yield_units", 0))
    return age >= min_age and yield_units > 0



# --- Module: economy.py ---

FIBONACCI_HIRE = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]


def get_cumulative_hire_cost(num_hires: int) -> int:
    total = 0
    for i in range(num_hires):
        idx = min(i, len(FIBONACCI_HIRE) - 1)
        total += FIBONACCI_HIRE[idx] * 50
    return total


def determine_target_hires(day: int, money: float, quad_count: int) -> int:
    """Determine optimal daily hired hands count based on day, money, and farm size."""
    if day >= 29:
        return 0

    if day <= 1:
        return 2 if money >= 300 else 1

    if day <= 3:
        return 3 if money >= 1000 else 2

    # Days 4 to 27: High-efficiency workforce (2 hands for 48 tiles, 3 for 72, 4 for 96)
    # Minimizes cumulative hire overhead while fully covering watering and harvesting
    desired_by_quad = {1: 2, 2: 2, 3: 3, 4: 4}
    target_desired = desired_by_quad.get(quad_count, 3)

    for target in range(target_desired, 0, -1):
        cost = get_cumulative_hire_cost(target)
        if money >= cost + 150:
            return target

    return 1 if money >= 50 else 0


def choose_crop(day: int, seeds: Dict[str, int]) -> str:
    """
    Seasonal Crop Choice Engine:
    - Phase 1 (Days 0-6): CARROT (fast cash compounding to unlock all 4 quadrants)
    - Phase 2 (Days 7-16): MELON (base $250 jackpot) / CARROT
    - Phase 3 (Days 17-25): CARROT (3-day turnaround)
    - Phase 4 (Days > 25): Stop planting
    """
    if day > 25:
        return "CARROT"

    if day <= 6:
        preferred = ["CARROT", "WHEAT"]
    elif day <= 16:
        preferred = ["MELON", "CARROT", "WHEAT"]
    else:
        preferred = ["CARROT", "WHEAT"]

    for crop in preferred:
        if day <= LAST_PLANT_DAY.get(crop, 26) and int(seeds.get(crop, 0)) > 0:
            return crop

    for crop in preferred:
        if day <= LAST_PLANT_DAY.get(crop, 26):
            return crop

    return "CARROT"





# --- Module: market.py ---

HIGH_ELASTICITY_ITEMS = {"MELON", "WOOL"}
MEDIUM_ELASTICITY_ITEMS = {"MILK", "STRAWBERRY", "TOMATO"}
BULK_ITEMS = {"CARROT", "WHEAT", "EGG", "FERTILIZER"}

SELL_PRIORITY_ORDER = [
    "MELON",
    "STRAWBERRY",
    "WOOL",
    "MILK",
    "TOMATO",
    "CARROT",
    "EGG",
    "WHEAT",
    "FERTILIZER",
]


def extract_town_demands(unlocked_shops: List[Dict[str, Any]]) -> Set[str]:
    demands = set()
    if isinstance(unlocked_shops, list):
        for shop in unlocked_shops:
            if isinstance(shop, dict):
                item = shop.get("item") or shop.get("demand")
                if item:
                    demands.add(item)
                shop_demands = shop.get("demands", [])
                if isinstance(shop_demands, list):
                    for d in shop_demands:
                        demands.add(d)
    return demands


def generate_market_orders(
    day: int,
    turn: int,
    money: float,
    shed: Dict[str, int],
    seeds: Dict[str, int],
    animals: Dict[str, int],
    unlocked_quads: List[str],
    unlocked_shops: List[Dict[str, Any]],
    hires_today: int,
    hands_count: int
) -> List[List[Any]]:
    orders: List[List[Any]] = []

    # 1. Town shop demand lookup
    town_demands = extract_town_demands(unlocked_shops)

    # 2. Drip-Selling Engine
    ordered_items = [item for item in SELL_PRIORITY_ORDER if item in town_demands]
    ordered_items.extend([item for item in SELL_PRIORITY_ORDER if item not in town_demands])

    for item in ordered_items:
        count = int(shed.get(item, 0))
        if count > 0 and len(orders) < 6:
            # Final turns of the game: dump everything remaining in shed to guarantee zero unsold
            if day == 29 and turn >= 20:
                orders.append(["SELL", item, count])
            else:
                if item in BULK_ITEMS:
                    batch = min(count, 30 if item in town_demands else 25)
                elif item in MEDIUM_ELASTICITY_ITEMS:
                    batch = min(count, 10 if item in town_demands else 6)
                else:  # High elasticity: MELON, WOOL
                    batch = min(count, 6 if day >= 27 else (4 if item in town_demands else 3))

                if batch > 0:
                    orders.append(["SELL", item, batch])

    # 3. Worker Hiring (Issued early in the day)
    quad_count = len(unlocked_quads)
    target_hires = determine_target_hires(day, money, quad_count)
    needed_hires = max(0, target_hires - hires_today)
    for _ in range(min(needed_hires, 8 - len(orders))):
        orders.append(["HIRE"])

    # 4. Land Expansion (NE $1k, SW $2k, SE $4k) - Rapid expansion compounds production
    if day <= 22 and quad_count < 4 and len(orders) < 9:
        if quad_count == 1 and money >= 1800:
            orders.append(["BUY_LAND"])
        elif quad_count == 2 and money >= 2400:
            orders.append(["BUY_LAND"])
        elif quad_count == 3 and money >= 4500:
            orders.append(["BUY_LAND"])

    # 5. Dynamic Seed Purchasing Engine (Guarantees orders never exceed liquid cash)
    if day <= 25 and len(orders) < 9:
        carrot_seeds = int(seeds.get("CARROT", 0))
        wheat_seeds = int(seeds.get("WHEAT", 0))
        melon_seeds = int(seeds.get("MELON", 0))
        target_farm_seeds = min(quad_count * 24, 96)

        if day <= 6:
            # Phase 1 & 2 (Days 0-6): Rapid capital accumulation via Carrots to buy all 4 quads
            target_carrots = target_farm_seeds
            if carrot_seeds < target_carrots:
                can_buy = min(target_carrots - carrot_seeds, int(max(0, money - 200) // 20))
                if can_buy > 0:
                    orders.append(["BUY_SEED", "CARROT", can_buy])
            elif wheat_seeds < 10:
                can_buy = min(10 - wheat_seeds, int(max(0, money - 100) // 10))
                if can_buy > 0:
                    orders.append(["BUY_SEED", "WHEAT", can_buy])
        elif day <= 16:
            # Phase 3 (Days 7-16): With all 4 quads unlocked, plant up to 64 Melons and keep Carrots on the rest
            target_melons = min(int(target_farm_seeds * 0.65), 64)
            target_carrots = max(24, target_farm_seeds - target_melons)
            if (quad_count == 4 or (day >= 10 and quad_count >= 3)) and melon_seeds < target_melons:
                can_buy = min(target_melons - melon_seeds, int(max(0, money - 300) // 80))
                if can_buy > 0:
                    orders.append(["BUY_SEED", "MELON", can_buy])
            elif carrot_seeds < target_carrots:
                can_buy = min(target_carrots - carrot_seeds, int(max(0, money - 150) // 20))
                if can_buy > 0:
                    orders.append(["BUY_SEED", "CARROT", can_buy])
        elif day <= 25:
            # Phase 4 (Days 17-25): Carrots to the finish line
            if carrot_seeds < target_farm_seeds:
                can_buy = min(target_farm_seeds - carrot_seeds, int(max(0, money - 150) // 20))
                if can_buy > 0:
                    orders.append(["BUY_SEED", "CARROT", can_buy])
            elif wheat_seeds < 15:
                can_buy = min(15 - wheat_seeds, int(max(0, money - 50) // 10))
                if can_buy > 0:
                    orders.append(["BUY_SEED", "WHEAT", can_buy])


    return orders[:10]


def private_animals_count(animals: Dict[str, int], shed: Dict[str, int], animal_name: str) -> int:
    return int(animals.get(animal_name, 0)) + int(shed.get(animal_name, 0))




# --- Module: planner.py ---


def build_task_queue(state: GameState) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    day = state.day
    tiles = state.tiles

    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, tile in enumerate(row):
            if not unlocked(tile):
                continue

            pos = (x, y)

            if is_weed(tile):
                tasks.append({
                    "priority": 25,
                    "pos": pos,
                    "action": ["DIG"],
                })
                continue

            if is_plant(tile):
                watered = bool(tile.get("watered_today", False))
                unwatered = int(tile.get("consecutive_unwatered", 0))
                planted_day = int(tile.get("planted_day", day))
                age = day - planted_day
                crop = tile.get("crop", "")
                is_ongoing = (crop in ("TOMATO", "STRAWBERRY"))
                ready_to_harvest = crop_ready_to_harvest(tile, day)

                # Priority 1: Harvest Ready Crop
                if ready_to_harvest:
                    tasks.append({
                        "priority": 1,
                        "pos": pos,
                        "action": ["HARVEST"],
                    })

                # Priority 0 / 10: Water (urgent if unwatered >= 1 or planted today)
                if not watered and (not ready_to_harvest or is_ongoing):
                    prio = 0 if (unwatered >= 1 or age == 0) else 10
                    tasks.append({
                        "priority": prio,
                        "pos": pos,
                        "action": ["WATER"],
                    })

                continue

            if is_free(tile):
                # Plant up to Day 25 and within turns 0-21 (leaves turn 22-23 to water)
                if day <= 25 and state.turn <= 21:
                    tasks.append({
                        "priority": 30,
                        "pos": pos,
                        "action": ["PLANT"],
                    })

    tasks.sort(key=lambda t: (t["priority"], t["pos"][1], t["pos"][0]))
    return tasks




def solve_worker_actions(
    state: GameState,
    tasks: List[Dict[str, Any]]
) -> Tuple[List[str], List[List[str]]]:
    workers: List[Tuple[int, int]] = [state.farmer_pos]
    workers.extend(state.hands_pos)

    turn_in_day = state.turn
    available_seeds = {k: int(v) for k, v in state.seeds.items() if int(v) > 0}

    actions: List[List[str]] = [["PASS"] for _ in workers]
    used_tasks: Set[int] = set()

    unlocked_quads = state.unlocked_quadrants if state.unlocked_quadrants else ["NW"]

    for worker_idx, worker_pos in enumerate(workers):
        # On days 0-28, end-of-day engine automatically drops all worker inventories to shed.
        # Workers can continuously work their quadrants without wasting turns walking to shed.

        assigned_quad = unlocked_quads[worker_idx % len(unlocked_quads)]
        q_xmin, q_xmax, q_ymin, q_ymax = QUADRANTS.get(assigned_quad, (0, 9, 0, 9))

        best_idx = None
        best_key = None

        for task_idx, task in enumerate(tasks):
            if task_idx in used_tasks:
                continue

            target = task["pos"]
            tx, ty = target

            # If task is PLANT, ensure we actually have seeds in available_seeds
            if task["action"][0] == "PLANT":
                current_crop = choose_crop(state.day, available_seeds)
                if available_seeds.get(current_crop, 0) <= 0:
                    continue

            if worker_idx > 0:
                out_of_bounds_penalty = 0 if (q_xmin <= tx <= q_xmax and q_ymin <= ty <= q_ymax) else 40
            else:
                out_of_bounds_penalty = 0

            dist = manhattan(worker_pos, target)
            key = (int(task["priority"]) + out_of_bounds_penalty, dist, ty, tx)

            if best_key is None or key < best_key:
                best_key = key
                best_idx = task_idx

        if best_idx is None:
            continue

        task = tasks[best_idx]
        target = task["pos"]
        task_action = task["action"]

        if worker_pos != target:
            actions[worker_idx] = move_towards(worker_pos, target)
        else:
            if task_action[0] == "PLANT":
                current_crop = choose_crop(state.day, available_seeds)
                if available_seeds.get(current_crop, 0) > 0:
                    available_seeds[current_crop] -= 1
                    actions[worker_idx] = ["PLANT", current_crop]
                else:
                    actions[worker_idx] = ["PASS"]
            else:
                actions[worker_idx] = task_action

        used_tasks.add(best_idx)

    farmer_action = actions[0] if actions else ["PASS"]
    hand_actions = actions[1:] if len(actions) > 1 else []

    return farmer_action, hand_actions



# --- Module: actions.py ---


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


# --- Module: agent.py ---


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
            unlocked_quads=state.unlocked_quadrants,
            unlocked_shops=state.unlocked_shops,
            hires_today=state.hires_today,
            hands_count=len(state.hands_pos)
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

