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



