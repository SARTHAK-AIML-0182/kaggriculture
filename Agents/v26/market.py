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

    # 1. Animal count calculation & town demands
    active_animals_on_tiles = sum(
        1 for p in STRUCTURE_TILES.keys()
        if has_animal(tile_at(tiles, p[0], p[1]))
    )
    has_any_animal = (active_animals_on_tiles > 0)
    feed_buffer = max(4, min(18, active_animals_on_tiles + 2))
    town_demands = extract_town_demands(unlocked_shops)

    # 2. Drip-Selling Engine (Guarantees zero unsold goods by Day 29)
    ordered_items = [item for item in SELL_PRIORITY_ORDER if item in town_demands]
    ordered_items.extend([item for item in SELL_PRIORITY_ORDER if item not in town_demands])

    for item in ordered_items:
        count = int(shed.get(item, 0))
        # Keep wheat as feed during season for livestock
        if item == "WHEAT" and has_any_animal and day < 28:
            count = max(0, count - feed_buffer)

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

    # 3. Worker Hiring (Scales with quadrants)
    quad_count = len(unlocked_quads) if unlocked_quads else 1
    target_hires = determine_target_hires(day, cur_money, quad_count)
    needed_hires = max(0, target_hires - hires_today)
    for _ in range(min(needed_hires, 8 - len(orders))):
        if cur_money >= 50:
            orders.append(["HIRE"])
            cur_money -= 50

    # 4. Strict Phased Land Expansion:
    # - Days 0-6: Strictly 1 quadrant (NW). DO NOT buy 2nd quadrant till Day 6!
    # - Day 7: Buy 2nd quadrant (NE, $1,000)
    # - Day 10: Buy 3rd quadrant (SW, $2,000)
    # - 4th quadrant (SE) remains locked!
    if len(orders) < 9:
        if day >= 7 and quad_count == 1 and cur_money >= 1050:
            orders.append(["BUY_LAND"])
            cur_money -= 1000
            quad_count += 1
        elif day >= 10 and quad_count == 2 and cur_money >= 2050:
            orders.append(["BUY_LAND"])
            cur_money -= 2000
            quad_count += 1

    # 5. Staged Livestock Acquisition Engine (18 Animals Total)
    if day <= 24 and len(orders) < 9:
        staged_structures = sorted(STRUCTURE_TILES.items(), key=lambda item: item[1][3])
        animals_bought_today = 0
        max_buys = 6 if day in (7, 10, 11) else 3
        # Reserve $2,050 on Days 8-10 to guarantee Land 2 purchase on Day 10!
        min_reserve = 2050 if (quad_count < 3 and day in (8, 9, 10)) else 100

        for struct_pos, (struct_type, animal_name, squad, avail_day) in staged_structures:
            if animals_bought_today >= max_buys or len(orders) >= 9:
                break
            if day < avail_day:
                continue

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
            # Buy when structure is built or free tile is scheduled to be built
            if is_empty_structure(t) or is_free(t):
                if cur_money >= cost + 120:
                    orders.append(["BUY_ANIMAL", animal_name, 1])
                    cur_money -= cost
                    animals_bought_today += 1

    # Animal Feed (Wheat) purchasing
    current_shed_wheat = int(shed.get("WHEAT", 0))
    if has_any_animal and current_shed_wheat < feed_buffer and cur_money >= 80 and len(orders) < 9:
        buy_qty = min(8, (feed_buffer + 4) - current_shed_wheat)
        if buy_qty > 0 and cur_money >= buy_qty * 12:
            orders.append(["BUY_PRODUCT", "WHEAT", buy_qty])
            cur_money -= buy_qty * 12

    # 6. Multi-Crop Seed Purchasing Engine (Melon, Strawberry, Tomato, Carrot)
    # Strictly buy seeds up to Day 18, capped to workforce planting capacity
    if day <= 18 and len(orders) < 9:
        unplanted_tiles = count_free_unlocked_tiles(tiles)
        empty_struct_reserved = sum(
            1 for p, info in STRUCTURE_TILES.items()
            if unlocked(tile_at(tiles, p[0], p[1])) and is_free(tile_at(tiles, p[0], p[1])) and day >= info[3]
        )
        unplanted_crop_tiles = max(0, unplanted_tiles - empty_struct_reserved)
        total_seeds_owned = sum(int(v) for v in seeds.values())

        if day <= 6:
            target_seed_pocket = 14
        elif day <= 10:
            target_seed_pocket = 16 if quad_count >= 2 else 12
        elif day <= 14:
            target_seed_pocket = 10
        elif day <= 16:
            target_seed_pocket = 6
        elif day <= 18:
            target_seed_pocket = 3
        else:
            target_seed_pocket = 0

        needed_seeds = max(0, min(target_seed_pocket, unplanted_crop_tiles) - total_seeds_owned)
        needed_seeds = min(needed_seeds, 10)

        if needed_seeds > 0 and cur_money >= 20:
            if day <= 6:
                # Phase 1: Fast Carrot compounding to fund Day 7 Land & Animals
                can_buy = min(needed_seeds, int(max(0, cur_money - 100) // 20))
                if can_buy > 0:
                    orders.append(["BUY_SEED", "CARROT", can_buy])
                    cur_money -= can_buy * 20

            elif day <= 10:
                # Phase 2: Multi-crop strategy (Melon, Strawberry, Tomato, Carrot)
                current_growing = {}
                for crop in ("MELON", "STRAWBERRY", "TOMATO"):
                    current_growing[crop] = sum(
                        1 for row in tiles if isinstance(row, list)
                        for tile in row if isinstance(tile, dict) and tile.get("crop") == crop
                    )

                # A. Melon ($250 jackpot, seed $80) up to 12
                target_melons = 12 if quad_count >= 2 else 6
                can_buy_melon = min(
                    needed_seeds,
                    3,
                    max(0, target_melons - (current_growing["MELON"] + int(seeds.get("MELON", 0)))),
                    int(max(0, cur_money - 200) // 80)
                )
                if can_buy_melon > 0:
                    orders.append(["BUY_SEED", "MELON", can_buy_melon])
                    cur_money -= can_buy_melon * 80
                    needed_seeds -= can_buy_melon

                # B. Strawberry ($150 ongoing, seed $50) up to 6
                target_strawberries = 6
                can_buy_straw = min(
                    needed_seeds,
                    2,
                    max(0, target_strawberries - (current_growing["STRAWBERRY"] + int(seeds.get("STRAWBERRY", 0)))),
                    int(max(0, cur_money - 150) // 50)
                )
                if can_buy_straw > 0:
                    orders.append(["BUY_SEED", "STRAWBERRY", can_buy_straw])
                    cur_money -= can_buy_straw * 50
                    needed_seeds -= can_buy_straw

                # C. Tomato ($90 ongoing, seed $30) up to 6
                target_tomatoes = 6
                can_buy_tomato = min(
                    needed_seeds,
                    2,
                    max(0, target_tomatoes - (current_growing["TOMATO"] + int(seeds.get("TOMATO", 0)))),
                    int(max(0, cur_money - 100) // 30)
                )
                if can_buy_tomato > 0:
                    orders.append(["BUY_SEED", "TOMATO", can_buy_tomato])
                    cur_money -= can_buy_tomato * 30
                    needed_seeds -= can_buy_tomato

                # D. Fill remaining seed budget with fast Carrots
                if needed_seeds > 0 and cur_money >= 20:
                    can_buy_carrot = min(needed_seeds, int(max(0, cur_money - 100) // 20))
                    if can_buy_carrot > 0:
                        orders.append(["BUY_SEED", "CARROT", can_buy_carrot])
                        cur_money -= can_buy_carrot * 20

            elif day <= 18:
                # Phase 3: Final Carrot sprint (3-day cycle, stop buying after day 18)
                can_buy = min(needed_seeds, int(max(0, cur_money - 100) // 20))
                if can_buy > 0:
                    orders.append(["BUY_SEED", "CARROT", can_buy])
                    cur_money -= can_buy * 20

            elif day <= 18:
                # Phase 3: Final Carrot sprint (3-day cycle, stop buying after day 18)
                can_buy = min(needed_seeds, int(max(0, cur_money - 100) // 20))
                if can_buy > 0:
                    orders.append(["BUY_SEED", "CARROT", can_buy])
                    cur_money -= can_buy * 20

    return orders[:10]
