from typing import Dict, List, Tuple, Any, Optional, Set
from dataclasses import dataclass, field
import math
from collections import deque

# ==============================================================================
# Kaggriculture v25 Autonomous Engine
# (10 Cows, 2 Geese, 2 Quadrants, Fast Cultivation, 6 Workers)
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
    farmer_inv_items: Dict[str, int] = field(default_factory=dict)
    hands_pos: List[Tuple[int, int]] = field(default_factory=list)
    hand_inventories: List[int] = field(default_factory=list)
    hand_inv_items: List[Dict[str, int]] = field(default_factory=list)
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
        hand_inv_items: List[Dict[str, int]] = []

        private = obs.get("private", {})
        raw_inventories = private.get("inventories", [])
        farmer_inv_items = dict(raw_inventories[0]) if (isinstance(raw_inventories, list) and len(raw_inventories) > 0 and isinstance(raw_inventories[0], dict)) else {}
        farmer_inventory = sum(farmer_inv_items.values())

        for idx, h in enumerate(raw_hands):
            if isinstance(h, (list, tuple)) and len(h) >= 2:
                hands_pos.append((int(h[0]), int(h[1])))
                if isinstance(raw_inventories, list) and (idx + 1) < len(raw_inventories) and isinstance(raw_inventories[idx + 1], dict):
                    inv_dict = dict(raw_inventories[idx + 1])
                    hand_inv_items.append(inv_dict)
                    hand_inventories.append(sum(inv_dict.values()))
                else:
                    hand_inv_items.append({})
                    hand_inventories.append(0)
            elif isinstance(h, dict):
                pos = h.get("pos", [4, 4])
                hands_pos.append((int(pos[0]), int(pos[1])))
                inv = dict(h.get("items", {}))
                hand_inv_items.append(inv)
                hand_inventories.append(sum(inv.values()))

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
            farmer_inv_items=farmer_inv_items,
            hands_pos=hands_pos,
            hand_inventories=hand_inventories,
            hand_inv_items=hand_inv_items,
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
    "WHEAT": 25,
    "CARROT": 25,
    "TOMATO": 15,
    "STRAWBERRY": 15,
    "MELON": 13,
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


QUADRANT_SHED_TILES = {
    "NW": (4, 4),
    "NE": (5, 4),
    "SW": (4, 5),
    "SE": (5, 5),
}

# 1 Goose (Coop), 2 Sheep (Pastures), 10 Cows (Pastures) clustered around shed (4,4), (5,4), (4,5)
STRUCTURE_TILES = {
    # NW Quadrant (1 Goose, 1 Sheep, 3 Cows)
    (4, 2): ("COOP", "GOOSE", "NW"),
    (3, 4): ("PASTURE", "SHEEP", "NW"),
    (2, 4): ("PASTURE", "COW", "NW"),
    (3, 3): ("PASTURE", "COW", "NW"),
    (4, 3): ("PASTURE", "COW", "NW"),
    # NE Quadrant (1 Sheep, 4 Cows)
    (6, 4): ("PASTURE", "SHEEP", "NE"),
    (7, 4): ("PASTURE", "COW", "NE"),
    (6, 3): ("PASTURE", "COW", "NE"),
    (5, 3): ("PASTURE", "COW", "NE"),
    (7, 3): ("PASTURE", "COW", "NE"),
    # SW Quadrant (3 Cows)
    (3, 5): ("PASTURE", "COW", "SW"),
    (4, 6): ("PASTURE", "COW", "SW"),
    (3, 6): ("PASTURE", "COW", "SW"),
}

ANIMALS_CONFIG = {
    "SHEEP": {"cost": 500, "structure": "PASTURE", "product": "WOOL", "interval": 3},
    "COW": {"cost": 400, "structure": "PASTURE", "product": "MILK", "interval": 2},
    "GOOSE": {"cost": 300, "structure": "COOP", "product": "EGG", "interval": 1},
}


def count_free_unlocked_tiles(tiles: List[List[Any]]) -> int:
    cnt = 0
    for row in tiles:
        if isinstance(row, list):
            for t in row:
                if unlocked(t) and is_free(t):
                    cnt += 1
    return cnt


def has_animal(tile: Any) -> bool:
    return isinstance(tile, dict) and "animal" in tile


def is_empty_structure(tile: Any) -> bool:
    return isinstance(tile, dict) and tile.get("kind") in ("PASTURE", "COOP") and "animal" not in tile


def animal_ready_to_harvest(tile: Any) -> bool:
    return has_animal(tile) and int(tile.get("yield_units", 0)) > 0


def animal_has_fertilizer(tile: Any) -> bool:
    return has_animal(tile) and bool(tile.get("fertilizer_available", False))


def animal_needs_care(tile: Any) -> bool:
    return has_animal(tile) and not bool(tile.get("cared_today", False))


def animal_needs_feed(tile: Any) -> bool:
    return has_animal(tile) and not bool(tile.get("fed_today", False))


def crop_ready_to_harvest(tile: Dict[str, Any], day: int) -> bool:
    if not isinstance(tile, dict) or tile.get("kind") != "PLANT":
        return False
    crop = tile.get("crop")
    if not crop:
        return False
    planted_day = int(tile.get("planted_day", day))
    age = day - planted_day

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
    """
    Determine optimal daily hired hands count.
    Increased workforce (+2-3 workers):
    5 hired hands + 1 farmer = 6 workers total across 48 tiles (~8 tiles per worker).
    Provides rapid watering, planting, and 12-animal care/harvest cycles.
    """
    if day >= 29:
        return 5 if money >= 600 else 3

    # Days 0-1: Fast start (4-5 hands funded by starting cash)
    if day <= 1:
        return 5 if money >= 1200 else (4 if money >= 600 else 2)

    # Days 2 to 28: Strong workforce of 5-6 hands (6-7 workers total across 72 tiles)
    max_target = 6 if (quad_count >= 3 and money >= 2500) else 5
    for target in range(max_target, 1, -1):
        cost = get_cumulative_hire_cost(target)
        if money >= cost + 200:
            return target

    return 2 if money >= 100 else 1


def choose_crop(day: int, seeds: Dict[str, int]) -> str:
    """
    Seasonal Crop Choice Engine:
    - Phase 1 (Days 0-6): CARROT (fast cash compounding to build 10 Cows & 2 Geese)
    - Phase 2 (Days 7-13): MELON (base $250 jackpot) / CARROT
    - Phase 3 (Days 14-20): CARROT (3-day turnaround)
    - Phase 4 (Days > 20): Stop planting / clear remainder
    """
    if day > 20:
        return "CARROT"

    if day <= 6:
        preferred = ["CARROT", "WHEAT"]
    elif day <= 13:
        preferred = ["MELON", "CARROT", "WHEAT"]
    else:
        preferred = ["CARROT", "WHEAT"]

    for crop in preferred:
        if day <= LAST_PLANT_DAY.get(crop, 20) and int(seeds.get(crop, 0)) > 0:
            return crop

    for crop in preferred:
        if day <= LAST_PLANT_DAY.get(crop, 20):
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
    tiles: List[List[Any]],
    unlocked_quads: List[str],
    unlocked_shops: List[Dict[str, Any]],
    hires_today: int,
    hands_count: int,
    farmer_inv_items: Dict[str, int] = None,
    hand_inv_items: List[Dict[str, int]] = None,
) -> List[List[Any]]:
    orders: List[List[Any]] = []
    cur_money = float(money)

    if farmer_inv_items is None:
        farmer_inv_items = {}
    if hand_inv_items is None:
        hand_inv_items = []

    # 1. Animal presence check & town shop demand lookup
    has_any_animal = any(
        has_animal(tile_at(tiles, p[0], p[1])) for p in STRUCTURE_TILES.keys()
    )
    town_demands = extract_town_demands(unlocked_shops)

    # 2. Drip-Selling Engine (Guarantees zero unsold goods by Day 29)
    ordered_items = [item for item in SELL_PRIORITY_ORDER if item in town_demands]
    ordered_items.extend([item for item in SELL_PRIORITY_ORDER if item not in town_demands])

    for item in ordered_items:
        count = int(shed.get(item, 0))
        # Keep at least 10 wheat as feed during season for 13 livestock
        if item == "WHEAT" and has_any_animal and day < 28:
            count = max(0, count - 10)

        if count > 0 and len(orders) < 6:
            # Final days of the game: sell 100% of shed inventory immediately
            if day >= 28:
                orders.append(["SELL", item, count])
            else:
                if item in BULK_ITEMS:
                    batch = min(count, 35 if item in town_demands else 25)
                elif item in MEDIUM_ELASTICITY_ITEMS:
                    batch = min(count, 12 if item in town_demands else 8)
                else:  # High elasticity: MELON, WOOL
                    batch = min(count, 6 if day >= 25 else (4 if item in town_demands else 3))

                if batch > 0:
                    orders.append(["SELL", item, batch])

    # 3. Worker Hiring (Maintains 5-7 workers across 72 tiles)
    quad_count = len(unlocked_quads) if unlocked_quads else 1
    target_hires = determine_target_hires(day, cur_money, quad_count)
    needed_hires = max(0, target_hires - hires_today)
    for _ in range(min(needed_hires, 8 - len(orders))):
        if cur_money >= 50:
            orders.append(["HIRE"])
            cur_money -= 50

    # 4. Land Expansion: Up to THREE quadrants (NW, NE, SW = 72 tiles)
    # Save $4,000 by never buying Land 3!
    if quad_count < 3 and len(orders) < 9:
        if quad_count == 1 and day <= 2 and cur_money >= 1100:
            orders.append(["BUY_LAND"])
            cur_money -= 1000
            quad_count += 1
        elif quad_count == 2 and day >= 3 and cur_money >= 2600:
            orders.append(["BUY_LAND"])
            cur_money -= 2000
            quad_count += 1

    # 5. Livestock Acquisition: 1 Goose ($300), 2 Sheep ($500), 3 Cows ($400)
    # Never drain cash below 2050 before Land 2 is bought!
    if day >= 1 and day <= 24 and len(orders) < 9:
        min_reserve = 300
        for struct_pos, (struct_type, animal_name, quad) in STRUCTURE_TILES.items():
            tx, ty = struct_pos
            t = tile_at(tiles, tx, ty)
            if not unlocked(t):
                continue
            if has_animal(t):
                continue
            # Already in shed?
            if int(shed.get(animal_name, 0)) > 0:
                continue
            # Carried by farmer or hands?
            carried = (farmer_inv_items.get(animal_name, 0) > 0) or any(
                h.get(animal_name, 0) > 0 for h in hand_inv_items
            )
            if carried:
                continue

            cost = ANIMALS_CONFIG[animal_name]["cost"]
            # Buy when structure exists or is free tile scheduled to be built
            if is_empty_structure(t) or is_free(t):
                if cur_money >= cost + min_reserve:
                    orders.append(["BUY_ANIMAL", animal_name, 1])
                    cur_money -= cost
                    break  # Order 1 animal at a time for orderly placement

    # Animal Feed (Wheat) purchasing for 6 livestock
    current_shed_wheat = int(shed.get("WHEAT", 0))
    if has_any_animal and current_shed_wheat < 6 and cur_money >= 80 and len(orders) < 9:
        buy_qty = min(6, 8 - current_shed_wheat)
        if buy_qty > 0 and cur_money >= buy_qty * 12:
            orders.append(["BUY_PRODUCT", "WHEAT", buy_qty])
            cur_money -= buy_qty * 12

    # 6. Zero-Waste Dynamic Seed Purchasing Engine
    # Strictly buy seeds up to Day 18 for 59 crop tiles, capped to workforce planting capacity
    if day <= 18 and len(orders) < 9:
        unplanted_tiles = count_free_unlocked_tiles(tiles)
        empty_struct_reserved = sum(
            1 for p in STRUCTURE_TILES.keys()
            if unlocked(tile_at(tiles, p[0], p[1])) and is_free(tile_at(tiles, p[0], p[1]))
        )
        unplanted_crop_tiles = max(0, unplanted_tiles - empty_struct_reserved)

        total_seeds_owned = sum(int(v) for v in seeds.values())

        if day <= 14:
            target_seed_pocket = 18
        elif day <= 16:
            target_seed_pocket = 12
        elif day <= 18:
            target_seed_pocket = 6
        else:
            target_seed_pocket = 0

        needed_seeds = max(0, min(target_seed_pocket, unplanted_crop_tiles) - total_seeds_owned)
        needed_seeds = min(needed_seeds, 14)

        if needed_seeds > 0 and cur_money >= 20:
            if day <= 6:
                # Phase 1: Fast Carrot compounding to fund Land 2 & 13 Animals
                can_buy = min(needed_seeds, int(max(0, cur_money - 50) // 20))
                if can_buy > 0:
                    orders.append(["BUY_SEED", "CARROT", can_buy])
                    cur_money -= can_buy * 20
            elif day <= 10:
                # Phase 2: Melons (jackpot $250) up to 24 max on 59 crop tiles, rest Carrots
                current_melons_growing = sum(
                    1 for row in tiles if isinstance(row, list)
                    for tile in row if isinstance(tile, dict) and tile.get("crop") == "MELON"
                )
                melon_seeds = int(seeds.get("MELON", 0))
                target_melons = 24
                can_buy_melon = min(
                    needed_seeds,
                    8,
                    max(0, target_melons - (current_melons_growing + melon_seeds)),
                    int(max(0, cur_money - 100) // 80)
                )
                if can_buy_melon > 0:
                    orders.append(["BUY_SEED", "MELON", can_buy_melon])
                    cur_money -= can_buy_melon * 80
                    needed_seeds -= can_buy_melon

                if needed_seeds > 0 and cur_money >= 20:
                    can_buy_carrot = min(needed_seeds, int(max(0, cur_money - 50) // 20))
                    if can_buy_carrot > 0:
                        orders.append(["BUY_SEED", "CARROT", can_buy_carrot])
                        cur_money -= can_buy_carrot * 20
            elif day <= 18:
                # Phase 3: Final Carrot sprint (3-day cycle, stop buying after day 18)
                can_buy = min(needed_seeds, int(max(0, cur_money - 50) // 20))
                if can_buy > 0:
                    orders.append(["BUY_SEED", "CARROT", can_buy])
                    cur_money -= can_buy * 20

    return orders[:10]


# --- Module: planner.py ---


def build_task_queue(state: GameState) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    day = state.day
    tiles = state.tiles

    # General Farm Tiles (Crops, Weeds, Planting)
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, tile in enumerate(row):
            if not unlocked(tile):
                continue

            pos = (x, y)
            # Reserved structure positions are handled via worker local animal engine
            if pos in STRUCTURE_TILES:
                continue

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
                # Plant up to Day 24 to exhaust all pocket seeds
                if day <= 24 and state.turn <= 21:
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

    available_seeds = {k: int(v) for k, v in state.seeds.items() if int(v) > 0}
    actions: List[List[str]] = [["PASS"] for _ in workers]
    used_tasks: Set[int] = set()
    claimed_structures: Set[Tuple[int, int]] = set()

    unlocked_quads = state.unlocked_quadrants if state.unlocked_quadrants else ["NW"]

    for worker_idx, worker_pos in enumerate(workers):
        # Determine worker inventory items
        if worker_idx == 0:
            w_inv = state.farmer_inv_items
        else:
            h_idx = worker_idx - 1
            w_inv = state.hand_inv_items[h_idx] if h_idx < len(state.hand_inv_items) else {}

        assigned_quad = unlocked_quads[worker_idx % len(unlocked_quads)]
        q_xmin, q_xmax, q_ymin, q_ymax = QUADRANTS.get(assigned_quad, (0, 9, 0, 9))
        local_shed_tile = QUADRANT_SHED_TILES.get(assigned_quad, (4, 4))

        # 1. Local Quadrant Livestock Engine (Supports 1 Goose, 2 Sheep, 3 Cows across NW, NE, SW)
        # Each quadrant has at most 2 animals located 1 step from that quadrant's shed tile.
        # Workers service their quadrant's animal in 1-2 turns, then spend 22 turns on CROP CULTIVATION!
        handled_animal = False
        for spos, (stype, aname, squad) in STRUCTURE_TILES.items():
            if squad != assigned_quad:
                continue
            if spos in claimed_structures:
                continue
            if not unlocked(tile_at(state.tiles, spos[0], spos[1])):
                continue

            stile = tile_at(state.tiles, spos[0], spos[1])

            # A. If carrying this animal, walk to empty structure & place
            if w_inv.get(aname, 0) > 0 and is_empty_structure(stile):
                if worker_pos != spos:
                    actions[worker_idx] = move_towards(worker_pos, spos)
                else:
                    actions[worker_idx] = ["PLACE", aname]
                claimed_structures.add(spos)
                handled_animal = True
                break

            # B. If structure is empty and animal is waiting in shed, pick it up!
            elif is_empty_structure(stile) and int(state.shed.get(aname, 0)) > 0:
                is_carrying = any(w_inv.get(a, 0) > 0 for a in ANIMALS_CONFIG.keys())
                if not is_carrying:
                    if worker_pos != local_shed_tile:
                        actions[worker_idx] = move_towards(worker_pos, local_shed_tile)
                    else:
                        actions[worker_idx] = ["PICKUP", aname, 1]
                    claimed_structures.add(spos)
                    handled_animal = True
                    break

            # C. If structure is free, construct it!
            elif is_free(stile):
                if worker_pos != spos:
                    actions[worker_idx] = move_towards(worker_pos, spos)
                else:
                    actions[worker_idx] = ["BUILD_" + stype]
                claimed_structures.add(spos)
                handled_animal = True
                break

            # D. Placed animal maintenance (FEED, FERTILIZER, HARVEST) - NO CARE!
            elif has_animal(stile):
                # Priority 1: Feed if unfed
                if animal_needs_feed(stile):
                    if w_inv.get("WHEAT", 0) > 0:
                        if worker_pos != spos:
                            actions[worker_idx] = move_towards(worker_pos, spos)
                        else:
                            actions[worker_idx] = ["FEED"]
                        claimed_structures.add(spos)
                        handled_animal = True
                        break
                    elif int(state.shed.get("WHEAT", 0)) > 0:
                        if worker_pos != local_shed_tile:
                            actions[worker_idx] = move_towards(worker_pos, local_shed_tile)
                        else:
                            actions[worker_idx] = ["PICKUP", "WHEAT", 2]
                        claimed_structures.add(spos)
                        handled_animal = True
                        break

                # Priority 2: Harvest mature animal products (Milk, Wool, Eggs)
                elif animal_ready_to_harvest(stile):
                    if worker_pos != spos:
                        actions[worker_idx] = move_towards(worker_pos, spos)
                    else:
                        actions[worker_idx] = ["HARVEST"]
                    claimed_structures.add(spos)
                    handled_animal = True
                    break

                # Priority 3: Collect daily fertilizer
                elif animal_has_fertilizer(stile):
                    if worker_pos != spos:
                        actions[worker_idx] = move_towards(worker_pos, spos)
                    else:
                        actions[worker_idx] = ["COLLECT_FERTILIZER"]
                    claimed_structures.add(spos)
                    handled_animal = True
                    break

                # Priority 4: Animal care (yields bonus product units)
                elif animal_needs_care(stile):
                    if worker_pos != spos:
                        actions[worker_idx] = move_towards(worker_pos, spos)
                    else:
                        actions[worker_idx] = ["CARE"]
                    claimed_structures.add(spos)
                    handled_animal = True
                    break

        if handled_animal:
            continue

        # Day 29 shed drop: if carrying harvested goods and near shed, deposit
        if state.day == 29 and sum(w_inv.values()) > 0:
            if worker_pos == local_shed_tile:
                for itm in w_inv.keys():
                    if w_inv[itm] > 0:
                        actions[worker_idx] = ["DROP", itm, w_inv[itm]]
                        break
                continue
            elif manhattan(worker_pos, local_shed_tile) == 1:
                actions[worker_idx] = move_towards(worker_pos, local_shed_tile)
                continue

        # 2. General Quadrant Crop Tasks (Fast cultivation across 36 crop tiles)
        best_idx = None
        best_key = None

        for task_idx, task in enumerate(tasks):
            if task_idx in used_tasks:
                continue

            target = task["pos"]
            tx, ty = target
            action_op = task["action"][0]

            # If task is PLANT, ensure we have seeds
            if action_op == "PLANT":
                current_crop = choose_crop(state.day, available_seeds)
                if available_seeds.get(current_crop, 0) <= 0:
                    continue

            # Strong quadrant locality keeps workers focused on their 18 crop tiles
            out_of_bounds_penalty = 0 if (q_xmin <= tx <= q_xmax and q_ymin <= ty <= q_ymax) else 50
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
            if task_action[0] == "PLANT":
                current_crop = choose_crop(state.day, available_seeds)
                if available_seeds.get(current_crop, 0) > 0:
                    available_seeds[current_crop] -= 1
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

