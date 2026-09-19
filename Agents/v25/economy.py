from typing import Dict, List, Any
from board import LAST_PLANT_DAY

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

    # Days 0-1: Fast start (4-5 hands funded by $3,000 starting cash)
    if day <= 1:
        return 5 if money >= 1200 else (4 if money >= 600 else 2)

    # Days 2 to 28: Strong workforce of 5 hands (cost $600/day)
    for target in range(5, 1, -1):
        cost = get_cumulative_hire_cost(target)
        if money >= cost + 150:
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
