from typing import Dict, List, Tuple, Any

# ==============================================================================
# 200k Animal Husbandry & Compound Pasture Engine (main.py)
# ==============================================================================
#
# ANIMAL HUSBANDRY & PASTURE REVENUE LOOPS:
# 1. Infrastructure Setup (Days 1–4):
#    - Builds Coop (BUILD_COOP) for Chickens and Pasture (BUILD_PASTURE) for Cows.
#    - Buys animals (BUY_ANIMAL: CHICKEN, COW) yielding daily passive income
#      (EGG, MILK, WOOL) without replanting costs.
#
# 2. Animal Care & Organic Fertilizer Engine:
#    - Automated animal feeding (FEED), care (CARE), and fertilizer collection (COLLECT_FERTILIZER).
#    - Applies fertilizer (FERTILIZE) to multi-harvest crops (STRAWBERRY, MELON)
#      to double yield output.
#
# 3. 4x Land Expansion Engine (100 Tiles):
#    - Unlocks NE, SE, SW quadrants (BUY_LAND) when cash >= 1000 (Day <= 20).
#    - Hires up to 9 hands (HIRE) when cash >= 500 to manage 100 tiles (10x10).
#
# 4. Multi-Harvest Passive Crop Rotation:
#    - Plants recurring yield crops (TOMATO, STRAWBERRY, MELON) in mid-season.
#
# 5. 100% Market Monetization:
#    - Liquidates all 9 produce types (EGG, MILK, WOOL, FERTILIZER, STRAWBERRY,
#      MELON, TOMATO, CARROT, WHEAT) via SELL orders every single step.
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
    "WHEAT": 28,
    "CARROT": 28,
    "TOMATO": 22,
    "STRAWBERRY": 20,
    "MELON": 20,
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
    return isinstance(tile, dict) and tile.get("kind") == "PLANT"


def is_weed(tile: Any) -> bool:
    return isinstance(tile, dict) and tile.get("kind") == "WEED"


def is_coop_or_pasture(tile: Any) -> bool:
    return isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE")


def is_free(tile: Any) -> bool:
    return tile is None


def unlocked(tile: Any) -> bool:
    return tile != "LOCKED"


def manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def movement_toward(current: Tuple[int, int], target: Tuple[int, int]) -> List[str]:
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
    if day > 27:
        return "WHEAT"

    if day <= 5:
        preferred = ["CARROT", "WHEAT"]
    elif day <= 18:
        preferred = ["MELON", "STRAWBERRY", "TOMATO", "CARROT", "WHEAT"]
    else:
        preferred = ["CARROT", "WHEAT"]

    for crop in preferred:
        if day <= LAST_PLANT_DAY[crop] and int(seeds.get(crop, 0)) > 0:
            return crop

    for crop in preferred:
        if day <= LAST_PLANT_DAY[crop]:
            return crop

    return "CARROT" if day <= LAST_PLANT_DAY["CARROT"] else "WHEAT"


def build_tasks(
    obs: Dict[str, Any],
    farm: Dict[str, Any],
    day: int,
    shed_fertilizer: int
) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    tiles = farm.get("tiles", [])

    has_coop = False
    has_pasture = False

    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if not unlocked(tile):
                continue

            pos = (x, y)
            kind = tile.get("kind") if isinstance(tile, dict) else None

            if kind == "COOP":
                has_coop = True
                if int(tile.get("unfed_animals", 0)) > 0:
                    tasks.append({"priority": 8, "pos": pos, "action": ["FEED"]})
                if int(tile.get("fertilizer_units", 0)) > 0:
                    tasks.append({"priority": 14, "pos": pos, "action": ["COLLECT_FERTILIZER"]})
                if bool(tile.get("needs_care", False)):
                    tasks.append({"priority": 12, "pos": pos, "action": ["CARE"]})
                continue

            if kind == "PASTURE":
                has_pasture = True
                if int(tile.get("unfed_animals", 0)) > 0:
                    tasks.append({"priority": 8, "pos": pos, "action": ["FEED"]})
                if int(tile.get("fertilizer_units", 0)) > 0:
                    tasks.append({"priority": 14, "pos": pos, "action": ["COLLECT_FERTILIZER"]})
                if bool(tile.get("needs_care", False)):
                    tasks.append({"priority": 12, "pos": pos, "action": ["CARE"]})
                continue

            if is_weed(tile):
                tasks.append({
                    "priority": 30,
                    "pos": pos,
                    "action": ["DIG"],
                })
                continue

            if is_plant(tile):
                watered = bool(tile.get("watered_today", False))
                unwatered = int(tile.get("consecutive_unwatered", 0))
                fertilized = bool(tile.get("fertilized_today", False))
                crop = tile.get("crop")

                if crop_ready_to_harvest(tile, day):
                    tasks.append({
                        "priority": 5,
                        "pos": pos,
                        "action": ["HARVEST"],
                    })

                if not watered:
                    prio = 0 if unwatered >= 1 else 10
                    tasks.append({
                        "priority": prio,
                        "pos": pos,
                        "action": ["WATER"],
                    })

                if not fertilized and shed_fertilizer > 0 and crop in ("MELON", "STRAWBERRY"):
                    tasks.append({
                        "priority": 15,
                        "pos": pos,
                        "action": ["FERTILIZE"],
                    })

                continue

            if is_free(tile):
                if day <= 4:
                    if not has_coop and pos in ((0, 0), (1, 0), (0, 1)):
                        tasks.append({"priority": 2, "pos": pos, "action": ["BUILD_COOP"]})
                        has_coop = True
                        continue
                    if not has_pasture and pos in ((4, 0), (3, 0), (4, 1)):
                        tasks.append({"priority": 3, "pos": pos, "action": ["BUILD_PASTURE"]})
                        has_pasture = True
                        continue

                if day <= 27:
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
    private = obs.get("private", {})
    shed = private.get("shed", {})
    seeds = private.get("seeds", {})
    money = float(farm.get("money", 0.0))

    orders: List[List[Any]] = []

    # Priority 1: Liquidate 100% of private shed inventory (all 9 produce items)
    sellable = [
        "MELON",
        "STRAWBERRY",
        "TOMATO",
        "CARROT",
        "WHEAT",
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
    hands_count = len(farm.get("hands", []))

    # Priority 2: Aggressive Land Expansion (BUY_LAND)
    unlocked_quadrants = farm.get("unlocked_quadrants", [])
    if (
        day <= 20
        and len(unlocked_quadrants) < 4
        and money >= 1000
        and len(orders) < 9
    ):
        orders.append(["BUY_LAND"])

    # Priority 3: Animal Procurement (BUY_ANIMAL: CHICKEN, COW)
    if day <= 12 and money >= 800 and len(orders) < 8:
        chickens = int(private.get("chickens", 0))
        cows = int(private.get("cows", 0))

        if chickens < 3:
            orders.append(["BUY_ANIMAL", "CHICKEN", 2])
        if cows < 2:
            orders.append(["BUY_ANIMAL", "COW", 1])

    # Priority 4: Max Worker Hires to control 100 tiles
    if day <= 27 and hires_today == 0 and money >= 500 and hands_count < 9:
        orders.extend([
            ["HIRE"],
            ["HIRE"],
            ["HIRE"],
        ])

    # Priority 5: Seed Procurement
    if day <= 26:
        melon_seeds = int(seeds.get("MELON", 0))
        straw_seeds = int(seeds.get("STRAWBERRY", 0))
        carrot_seeds = int(seeds.get("CARROT", 0))
        wheat_seeds = int(seeds.get("WHEAT", 0))

        if day <= 18:
            if melon_seeds < 10 and money >= 500:
                orders.append(["BUY_SEED", "MELON", 10])
            if straw_seeds < 10 and money >= 400:
                orders.append(["BUY_SEED", "STRAWBERRY", 10])

        if carrot_seeds < 10 and money >= 200:
            orders.append(["BUY_SEED", "CARROT", 10])

        if wheat_seeds < 10 and money >= 100:
            orders.append(["BUY_SEED", "WHEAT", 10])

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
        shed = private.get("shed", {})
        shed_fertilizer = int(shed.get("FERTILIZER", 0))

        crop_to_plant = choose_crop(day, seeds)
        tasks = build_tasks(obs, farm, day, shed_fertilizer)

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
