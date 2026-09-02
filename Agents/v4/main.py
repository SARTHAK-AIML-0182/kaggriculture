from typing import Dict, List, Tuple, Any

# ==============================================================================
# Kaggriculture Production Agent (main.py)
# ==============================================================================
#
# COORDINATE HANDLING:
# - Grid tiles are indexed as [y][x] in the observation farm matrix (y = row, x = col).
# - Worker positions are given as [x, y] tuples/lists (x = column, y = row).
# - Movement commands: "NORTH" (y-1), "SOUTH" (y+1), "EAST" (x+1), "WEST" (x-1).
# - Manhattan distance formula: |x1 - x2| + |y1 - y2| is used for worker navigation.
#
# WORKER ASSIGNMENT:
# - Farmer is worker index 0 (farm["farmer"]).
# - Hired hands are worker indexes 1..N (farm["hands"]).
# - Each worker is assigned a unique target tile/task based on priority and distance.
# - Strict tracking via used_tasks prevents duplicate worker assignments.
#
# CROP MATURITY & SEASON TIMING:
# - Season duration is 30 days (720 steps max).
# - One-time crops (WHEAT, CARROT, MELON) require minimum age thresholds before harvest.
# - Multi-harvest crops (TOMATO, STRAWBERRY) yield continuously once mature.
# - Late-season protection: Stop planting when crops cannot mature before season end (Day > 26).
#
# MARKET SELLING & CASH MANAGEMENT:
# - All harvested goods in private shed inventory are sold via SELL orders every turn.
# - Controlled hiring: Max 3 hands per day, cost 1+1+2=4 gold/day, only when cash >= 2500.
# - Delayed land purchase: BUY_LAND only when cash >= 5500 (land cost + seed/labor reserves).
#
# ENDGAME LOGIC:
# - Halt hiring after Day 25.
# - Stop new planting after Day 26.
# - Focus on final harvesting and liquidating 100% of shed inventory before Day 30.
# ==============================================================================

CROPS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]

# Conservative opening strategy focusing on fast, reliable crops
EARLY_CROPS = ["WHEAT", "CARROT"]

# Minimum age (in days) required before harvesting one-time crops
HARVEST_AGE = {
    "WHEAT": 2,
    "CARROT": 2,
    "MELON": 10,
    "TOMATO": 8,
    "STRAWBERRY": 10,
}

# Cutoff days after which new planting of a crop will not mature in time
LAST_PLANT_DAY = {
    "WHEAT": 26,
    "CARROT": 26,
    "TOMATO": 21,
    "STRAWBERRY": 19,
    "MELON": 19,
}


def tile_at(farm: Dict[str, Any], x: int, y: int) -> Any:
    """Return tile object or 'LOCKED' string if outside unlocked boundary."""
    tiles = farm.get("tiles", [])
    if y < 0 or y >= len(tiles):
        return "LOCKED"
    if x < 0 or x >= len(tiles[y]):
        return "LOCKED"
    return tiles[y][x]


def is_plant(tile: Any) -> bool:
    """Check if tile contains a active crop plant."""
    return isinstance(tile, dict) and tile.get("kind") == "PLANT"


def is_weed(tile: Any) -> bool:
    """Check if tile contains a weed blocking production."""
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
    """
    Generate step-by-step movement action towards target [x, y].
    Returns standard action list like ["EAST"], ["NORTH"], or ["PASS"].
    """
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
    """
    Verify crop maturity and yield availability before harvesting.
    Prevents harvesting immature wheat, carrot, or melon.
    """
    crop = tile.get("crop")
    yield_units = int(tile.get("yield_units", 0))

    if yield_units <= 0:
        return False

    # Multi-harvest crops (Tomato/Strawberry) produce recurring yield
    if crop in ("TOMATO", "STRAWBERRY"):
        return True

    # One-time crops (Wheat, Carrot, Melon) must meet minimum age threshold
    planted_day = int(tile.get("planted_day", day))
    age = day - planted_day
    min_age = HARVEST_AGE.get(crop, 2)

    return age >= min_age


def choose_crop(day: int, seeds: Dict[str, int]) -> str:
    """
    Select best crop to plant based on season day and available seed inventory.
    """
    candidates = []

    for crop in EARLY_CROPS:
        if day <= LAST_PLANT_DAY[crop]:
            count = int(seeds.get(crop, 0))
            candidates.append((count, crop))

    if not candidates:
        return "WHEAT"

    # Prioritize crops with highest seed inventory in hand
    candidates.sort(reverse=True)
    return candidates[0][1]


def build_tasks(
    obs: Dict[str, Any],
    farm: Dict[str, Any],
    day: int
) -> List[Dict[str, Any]]:
    """
    Construct prioritized task queue for farm tiles.
    Priority values: lower number = higher priority.
    1. Urgent watering (unwatered >= 1 or unwatered today)
    2. Harvesting ready crops (mature yield available)
    3. Clearing weeds (DIG)
    4. Planting confirmed empty unlocked tiles (Day <= 26)
    """
    tasks: List[Dict[str, Any]] = []
    tiles = farm.get("tiles", [])

    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if not unlocked(tile):
                continue

            pos = (x, y)

            # Weeds: clear to free up land
            if is_weed(tile):
                tasks.append({
                    "priority": 40,
                    "pos": pos,
                    "action": ["DIG"],
                })
                continue

            # Plants: water or harvest
            if is_plant(tile):
                watered = bool(tile.get("watered_today", False))
                unwatered = int(tile.get("consecutive_unwatered", 0))

                # Priority 0 (Urgent Water): consecutive_unwatered >= 1 (close to dying)
                # Priority 10 (Routine Water): unwatered today
                if not watered:
                    prio = 0 if unwatered >= 1 else 10
                    tasks.append({
                        "priority": prio,
                        "pos": pos,
                        "action": ["WATER"],
                    })

                # Priority 20 (Harvest): Mature crop ready for harvest
                if crop_ready_to_harvest(tile, day):
                    tasks.append({
                        "priority": 20,
                        "pos": pos,
                        "action": ["HARVEST"],
                    })

                continue

            # Free tiles: plant if before season cutoff (Day <= 26)
            if is_free(tile):
                if day <= 26:
                    tasks.append({
                        "priority": 50,
                        "pos": pos,
                        "action": ["PLANT"],
                    })

    # Sort tasks primarily by priority score, then spatially for stability
    tasks.sort(key=lambda t: (t["priority"], t["pos"][1], t["pos"][0]))
    return tasks


def assign_worker_actions(
    obs: Dict[str, Any],
    farm: Dict[str, Any],
    tasks: List[Dict[str, Any]],
    crop_to_plant: str
) -> Tuple[List[str], List[List[str]]]:
    """
    Assign unique worker-to-tile tasks using Manhattan distance matching.
    Guarantees no two workers target or perform duplicate actions on the same tile.
    """
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
    """
    Construct safe market orders.
    - Sell all private shed items to convert inventory to cash.
    - Buy seed buffers conservatively without draining emergency cash.
    - Hire controlled hands (max 3/day) only when cash >= 2500 and day <= 25.
    - Buy land only when cash >= 5500 (delayed expansion reserve threshold).
    """
    private = obs.get("private", {})
    shed = private.get("shed", {})
    seeds = private.get("seeds", {})
    money = float(farm.get("money", 0.0))

    orders: List[List[Any]] = []

    # 1. Liquidate all harvested crops and produce from shed inventory
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

    # 2. Controlled Hiring: Max 3 hands per day, stopped after day 25
    if day <= 25 and hires_today == 0 and money >= 2500:
        orders.extend([
            ["HIRE"],
            ["HIRE"],
            ["HIRE"],
        ])

    # 3. Seed Purchases: Small buffer, preserve emergency cash
    if day <= 25:
        wheat_seeds = int(seeds.get("WHEAT", 0))
        carrot_seeds = int(seeds.get("CARROT", 0))

        if wheat_seeds < 3 and money >= 100:
            orders.append(["BUY_SEED", "WHEAT", 5])

        if carrot_seeds < 2 and money >= 150:
            orders.append(["BUY_SEED", "CARROT", 3])

    # 4. Land Expansion: Delayed until cash reserve threshold >= 5500 met
    unlocked_quadrants = farm.get("unlocked_quadrants", [])
    if (
        day <= 14
        and "NE" not in unlocked_quadrants
        and money >= 5500
        and len(orders) < 9
    ):
        orders.append(["BUY_LAND"])

    # Kaggle environment limit: max 10 market orders per step
    return orders[:10]


def agent(obs: Dict[str, Any], config: Any = None) -> Dict[str, Any]:
    """
    Kaggle competition entry point.
    Handles observations safely and returns formatted action dictionary.
    """
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
        # Fallback safe response prevents timeout or crash disqualification
        return {
            "farmer": ["PASS"],
            "hands": [],
            "market": [],
        }
