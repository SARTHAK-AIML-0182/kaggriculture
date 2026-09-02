from typing import Dict, List, Tuple, Any

# ==============================================================================
# Upgraded High-Velocity Kaggriculture Agent (main.py)
# ==============================================================================
#
# REVENUE MAXIMIZATION STRATEGY:
# - Focus on fast 2-day turnaround high-margin crops (CARROT and WHEAT).
# - Rapid harvest-to-cash cycles allow constant reinvestment in seeds & farm expansion.
# - Dynamic worker assignment ensures 0 wasted turns on watering and harvesting.
# - Controlled expansion: Early land purchase when cash >= 3000 (Day <= 14).
# - Continuous 100% liquidation of shed inventory via SELL orders every turn.
# ==============================================================================

CROPS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]

HARVEST_AGE = {
    "WHEAT": 2,
    "CARROT": 2,
    "MELON": 10,
    "TOMATO": 8,
    "STRAWBERRY": 10,
}

LAST_PLANT_DAY = {
    "WHEAT": 26,
    "CARROT": 26,
    "TOMATO": 21,
    "STRAWBERRY": 19,
    "MELON": 19,
}


def tile_at(farm: Dict[str, Any], x: int, y: int) -> Any:
    """Return tile object or 'LOCKED' string if outside boundary."""
    tiles = farm.get("tiles", [])
    if y < 0 or y >= len(tiles):
        return "LOCKED"
    if x < 0 or x >= len(tiles[y]):
        return "LOCKED"
    return tiles[y][x]


def is_plant(tile: Any) -> bool:
    """Check if tile contains an active crop plant."""
    return isinstance(tile, dict) and tile.get("kind") == "PLANT"


def is_weed(tile: Any) -> bool:
    """Check if tile contains a weed."""
    return isinstance(tile, dict) and tile.get("kind") == "WEED"


def is_free(tile: Any) -> bool:
    """Check if tile is unlocked and empty."""
    return tile is None


def unlocked(tile: Any) -> bool:
    """Check if tile is accessible (not locked)."""
    return tile != "LOCKED"


def manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    """Compute Manhattan distance between two [x, y] coordinates."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def movement_toward(
    current: Tuple[int, int],
    target: Tuple[int, int]
) -> List[str]:
    """Generate step movement action towards target [x, y]."""
    x, y = current
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


def crop_ready_to_harvest(tile: Dict[str, Any], day: int) -> bool:
    """Verify crop maturity and yield availability before harvesting."""
    crop = tile.get("crop")
    yield_units = int(tile.get("yield_units", 0))

    if yield_units <= 0:
        return False

    if crop in ("TOMATO", "STRAWBERRY"):
        return True

    planted_day = int(tile.get("planted_day", day))
    age = day - planted_day
    min_age = HARVEST_AGE.get(crop, 2)

    return age >= min_age


def choose_crop(day: int, seeds: Dict[str, int]) -> str:
    """
    Select optimal crop. Prefer CARROT for higher profit, WHEAT for budget fallback.
    """
    if day > 26:
        return "WHEAT"

    carrot_seeds = int(seeds.get("CARROT", 0))
    wheat_seeds = int(seeds.get("WHEAT", 0))

    if carrot_seeds > 0 and day <= LAST_PLANT_DAY["CARROT"]:
        return "CARROT"
    if wheat_seeds > 0 and day <= LAST_PLANT_DAY["WHEAT"]:
        return "WHEAT"

    return "CARROT" if day <= LAST_PLANT_DAY["CARROT"] else "WHEAT"


def build_tasks(
    obs: Dict[str, Any],
    farm: Dict[str, Any],
    day: int
) -> List[Dict[str, Any]]:
    """Construct prioritized task queue for farm tiles."""
    tasks: List[Dict[str, Any]] = []
    tiles = farm.get("tiles", [])

    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if not unlocked(tile):
                continue

            pos = (x, y)

            if is_weed(tile):
                tasks.append({
                    "priority": 40,
                    "pos": pos,
                    "action": ["DIG"],
                })
                continue

            if is_plant(tile):
                watered = bool(tile.get("watered_today", False))
                unwatered = int(tile.get("consecutive_unwatered", 0))

                if not watered:
                    prio = 0 if unwatered >= 1 else 10
                    tasks.append({
                        "priority": prio,
                        "pos": pos,
                        "action": ["WATER"],
                    })

                if crop_ready_to_harvest(tile, day):
                    tasks.append({
                        "priority": 20,
                        "pos": pos,
                        "action": ["HARVEST"],
                    })

                continue

            if is_free(tile):
                if day <= 26:
                    tasks.append({
                        "priority": 50,
                        "pos": pos,
                        "action": ["PLANT"],
                    })

    tasks.sort(key=lambda t: (t["priority"], t["pos"][1], t["pos"][0]))
    return tasks


def assign_worker_actions(
    obs: Dict[str, Any],
    farm: Dict[str, Any],
    tasks: List[Dict[str, Any]],
    crop_to_plant: str
) -> Tuple[List[str], List[List[str]]]:
    """Assign unique worker-to-tile tasks using Manhattan distance matching."""
    workers: List[Tuple[int, int]] = []

    farmer = farm.get("farmer", [4, 4])
    workers.append((int(farmer[0]), int(farmer[1])))

    for hand in farm.get("hands", []):
        if isinstance(hand, list) and len(hand) >= 2:
            workers.append((int(hand[0]), int(hand[1])))

    actions: List[List[str]] = [["PASS"] for _ in workers]
    used_task_indexes = set()

    for worker_idx, worker_pos in enumerate(workers):
        best_idx = None
        best_key = None

        for task_idx, task in enumerate(tasks):
            if task_idx in used_task_indexes:
                continue

            target = task["pos"]
            dist = manhattan(worker_pos, target)
            key = (int(task["priority"]), dist, target[1], target[0])

            if best_key is None or key < best_key:
                best_key = key
                best_idx = task_idx

        if best_idx is None:
            continue

        task = tasks[best_idx]
        target = task["pos"]
        task_action = task["action"]

        if worker_pos != target:
            actions[worker_idx] = movement_toward(worker_pos, target)
        else:
            if task_action[0] == "PLANT":
                actions[worker_idx] = ["PLANT", crop_to_plant]
            else:
                actions[worker_idx] = task_action

        used_task_indexes.add(best_idx)

    farmer_action = actions[0]
    hand_actions = actions[1:]

    return farmer_action, hand_actions


def make_market_orders(
    obs: Dict[str, Any],
    farm: Dict[str, Any],
    day: int
) -> List[List[Any]]:
    """Construct market orders for fast velocity cash flow."""
    private = obs.get("private", {})
    shed = private.get("shed", {})
    seeds = private.get("seeds", {})
    money = float(farm.get("money", 0.0))

    orders: List[List[Any]] = []

    # 1. Liquidate 100% of shed inventory
    sellable = [
        "WHEAT",
        "CARROT",
        "TOMATO",
        "STRAWBERRY",
        "MELON",
        "EGG",
        "MILK",
        "WOOL",
        "FERTILIZER",
    ]

    for item in sellable:
        amount = int(shed.get(item, 0))
        if amount > 0:
            orders.append(["SELL", item, amount])

    hires_today = int(farm.get("hires_today", 0))

    # 2. Worker Hiring: Max 3 hands per day when cash >= 2000
    if day <= 25 and hires_today == 0 and money >= 2000:
        orders.extend([
            ["HIRE"],
            ["HIRE"],
            ["HIRE"],
        ])

    # 3. Seed Procurement: Keep steady seed inventory of CARROT and WHEAT
    if day <= 25:
        carrot_seeds = int(seeds.get("CARROT", 0))
        wheat_seeds = int(seeds.get("WHEAT", 0))

        if carrot_seeds < 3 and money >= 150:
            orders.append(["BUY_SEED", "CARROT", 5])

        if wheat_seeds < 3 and money >= 100:
            orders.append(["BUY_SEED", "WHEAT", 5])

    # 4. Land Expansion (Threshold = 4500 gold)
    unlocked_quadrants = farm.get("unlocked_quadrants", [])
    if (
        day <= 14
        and "NE" not in unlocked_quadrants
        and money >= 4500
        and len(orders) < 9
    ):
        orders.append(["BUY_LAND"])

    return orders[:10]


def agent(obs: Dict[str, Any], config: Any = None) -> Dict[str, Any]:
    """Kaggle entry point."""
    try:
        player = int(obs.get("player", 0))
        farms = obs.get("farms", [])

        if player < 0 or player >= len(farms):
            return {
                "farmer": ["PASS"],
                "hands": [],
                "market": [],
            }

        farm = farms[player]
        day = int(obs.get("day", 0))
        private = obs.get("private", {})
        seeds = private.get("seeds", {})

        crop_to_plant = choose_crop(day, seeds)
        tasks = build_tasks(obs, farm, day)

        farmer_action, hand_actions = assign_worker_actions(
            obs=obs,
            farm=farm,
            tasks=tasks,
            crop_to_plant=crop_to_plant,
        )

        market_orders = make_market_orders(obs, farm, day)

        return {
            "farmer": farmer_action,
            "hands": hand_actions,
            "market": market_orders,
        }

    except Exception:
        return {
            "farmer": ["PASS"],
            "hands": [],
            "market": [],
        }
