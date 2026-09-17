from typing import Dict, List, Any, Set
from economy import determine_target_hires

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


