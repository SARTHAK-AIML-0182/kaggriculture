from typing import Dict, List, Tuple, Any

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
    "MELON": 15,
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

STRUCTURE_TILES = {
    (3, 4): ("PASTURE", "SHEEP", "NW"),
    (6, 4): ("PASTURE", "COW", "NE"),
    (3, 5): ("COOP", "GOOSE", "SW"),
    (6, 5): ("PASTURE", "SHEEP", "SE"),
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

