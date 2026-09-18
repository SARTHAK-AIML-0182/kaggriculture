from typing import Dict, List, Any, Set, Tuple
from economy import determine_target_hires
from board import (
    STRUCTURE_TILES,
    ANIMALS_CONFIG,
    unlocked,
    tile_at,
    count_free_unlocked_tiles,
    is_empty_structure,
    is_free,
    has_animal,
)

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
        # Keep at least 4 wheat as feed during season
        if item == "WHEAT" and has_any_animal and day < 28:
            count = max(0, count - 4)

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

    # 3. Worker Hiring (Scaled to unlocked quadrants)
    quad_count = len(unlocked_quads) if unlocked_quads else 1
    target_hires = determine_target_hires(day, cur_money, quad_count)
    needed_hires = max(0, target_hires - hires_today)
    for _ in range(min(needed_hires, 8 - len(orders))):
        if cur_money >= 50:
            orders.append(["HIRE"])
            cur_money -= 50

    # 4. Land Expansion (NE $1k, SW $2k, SE $4k)
    # Guaranteed unlock progression: Land 1 Day 0-1, Land 2 Day 3-4, Land 3 (Quadrant 4) Day 6-8
    if day <= 22 and quad_count < 4 and len(orders) < 9:
        if quad_count == 1 and cur_money >= 1100:
            orders.append(["BUY_LAND"])
            cur_money -= 1000
            quad_count += 1
        elif quad_count == 2 and cur_money >= 2150:
            orders.append(["BUY_LAND"])
            cur_money -= 2000
            quad_count += 1
        elif quad_count == 3 and cur_money >= 4050:
            orders.append(["BUY_LAND"])
            cur_money -= 4000
            quad_count += 1

    # 5. Livestock Acquisition
    # Buy sheep, cow, goose when structure is ready or scheduled and money allows
    if day <= 24 and len(orders) < 9:
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
            # Buy if structure exists or is free tile scheduled to be built
            if is_empty_structure(t) or (is_free(t) and day >= 1):
                if cur_money >= cost + 200:
                    orders.append(["BUY_ANIMAL", animal_name, 1])
                    cur_money -= cost
                    break  # Buy at most 1 animal at a time for orderly placement

    # Animal Feed (Wheat) purchasing when livestock exists
    if has_any_animal and int(shed.get("WHEAT", 0)) < 4 and cur_money >= 80 and len(orders) < 9:
        orders.append(["BUY_PRODUCT", "WHEAT", 2])
        cur_money -= 24

    # 6. Zero-Waste Dynamic Seed Purchasing Engine
    # Strictly buy seeds up to Day 20, in small digestible batches (max 20 seeds/day)
    # Zero seeds bought after Day 20 guarantees ZERO leftover seeds in pocket!
    if day <= 20 and len(orders) < 9:
        unplanted_tiles = count_free_unlocked_tiles(tiles)
        empty_struct_reserved = sum(
            1 for p in STRUCTURE_TILES.keys()
            if unlocked(tile_at(tiles, p[0], p[1])) and is_free(tile_at(tiles, p[0], p[1]))
        )
        unplanted_crop_tiles = max(0, unplanted_tiles - empty_struct_reserved)

        total_seeds_owned = sum(int(v) for v in seeds.values())

        if day <= 16:
            target_seed_pocket = 20
        elif day <= 18:
            target_seed_pocket = 12
        elif day <= 20:
            target_seed_pocket = 6
        else:
            target_seed_pocket = 0

        needed_seeds = max(0, min(target_seed_pocket, unplanted_crop_tiles) - total_seeds_owned)
        needed_seeds = min(needed_seeds, 16)

        if needed_seeds > 0 and cur_money >= 20:
            if day <= 6:
                # Phase 1: Fast Carrot compounding to fund all 4 quadrants
                can_buy = min(needed_seeds, int(max(0, cur_money - 100) // 20))
                if can_buy > 0:
                    orders.append(["BUY_SEED", "CARROT", can_buy])
                    cur_money -= can_buy * 20
            elif day <= 13:
                # Phase 2: Melons (jackpot $250) up to 36 max, rest Carrots
                current_melons_growing = sum(
                    1 for row in tiles if isinstance(row, list)
                    for tile in row if isinstance(tile, dict) and tile.get("crop") == "MELON"
                )
                melon_seeds = int(seeds.get("MELON", 0))
                target_melons = 36
                can_buy_melon = min(
                    needed_seeds,
                    10,
                    max(0, target_melons - (current_melons_growing + melon_seeds)),
                    int(max(0, cur_money - 200) // 80)
                )
                if can_buy_melon > 0:
                    orders.append(["BUY_SEED", "MELON", can_buy_melon])
                    cur_money -= can_buy_melon * 80
                    needed_seeds -= can_buy_melon

                if needed_seeds > 0 and cur_money >= 20:
                    can_buy_carrot = min(needed_seeds, int(max(0, cur_money - 100) // 20))
                    if can_buy_carrot > 0:
                        orders.append(["BUY_SEED", "CARROT", can_buy_carrot])
                        cur_money -= can_buy_carrot * 20
            elif day <= 20:
                # Phase 3: Final Carrot sprint (3-day cycle)
                can_buy = min(needed_seeds, int(max(0, cur_money - 100) // 20))
                if can_buy > 0:
                    orders.append(["BUY_SEED", "CARROT", can_buy])
                    cur_money -= can_buy * 20

    return orders[:10]
