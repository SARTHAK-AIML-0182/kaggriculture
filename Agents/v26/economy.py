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
    Adaptive Workforce Hiring Strategy:
    - Days 0-6 (1 Quadrant, 24 tiles): 3 hired hands (4 workers total)
    - Days 7-9 (2 Quadrants, 48 tiles): 4 hired hands (5 workers total)
    - Days 10-30 (3 Quadrants, 72 tiles): 5-6 hired hands (6-7 workers total)
    """
    if day >= 29:
        return 4 if money >= 400 else 2

    if quad_count == 1:
        # Days 0-6 on NW quadrant: 3 hires ($200) or 2 hires ($100)
        if money >= 600:
            return 3
        elif money >= 300:
            return 2
        return 1

    elif quad_count == 2:
        # Days 7-9 on NW + NE: 4 hires ($350)
        for target in (4, 3, 2):
            if money >= get_cumulative_hire_cost(target) + 200:
                return target
        return 2

    else:
        # Day 10+ on NW + NE + SW: 5-6 hires ($600-$1000)
        max_target = 6 if money >= 2500 else 5
        for target in range(max_target, 2, -1):
            if money >= get_cumulative_hire_cost(target) + 200:
                return target
        return 3


def choose_crop(day: int, seeds: Dict[str, int]) -> str:
    """
    Multi-Crop Selection Engine (Melon, Strawberry, Tomato, Carrot):
    - Days 0-6: CARROT (rapid 3-day turnaround to compound cash for Day 7 Land & Animals)
    - Days 7-14: MELON (base $250 jackpot), STRAWBERRY (ongoing $150), TOMATO (ongoing $90), CARROT
    - Days 15-20: CARROT (3-day cycle)
    - Days > 20: CARROT
    """
    # Always plant any high-value seeds in pocket first before they expire
    for crop in ["MELON", "STRAWBERRY", "TOMATO", "CARROT", "WHEAT"]:
        if day <= LAST_PLANT_DAY.get(crop, 20) and int(seeds.get(crop, 0)) > 0:
            return crop

    if day <= 6:
        preferred = ["CARROT", "WHEAT"]
    elif day <= 10:
        preferred = ["MELON", "STRAWBERRY", "TOMATO", "CARROT", "WHEAT"]
    elif day <= 20:
        preferred = ["CARROT", "WHEAT"]
    else:
        preferred = ["CARROT"]

    for crop in preferred:
        if day <= LAST_PLANT_DAY.get(crop, 20) and int(seeds.get(crop, 0)) > 0:
            return crop

    for crop in preferred:
        if day <= LAST_PLANT_DAY.get(crop, 20):
            return crop

    return "CARROT"
