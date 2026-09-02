"""
Kaggriculture agent — v2, built against CONFIRMED mechanics.

Every mechanic referenced here (schema, daily hand reset, tile state machine,
crop lifespan, animal feed/care cycle, shed flow) was reverse-engineered
directly from a real episode replay, not guessed. See
kaggriculture_game_analysis.md for the full writeup.

REMAINING KNOWN UNCERTAINTIES (flagged inline with # ASSUMPTION):
- Exact turn at which a crop becomes harvestable (we approximate: attempt
  harvest once yield_units >= HARVEST_YIELD_THRESHOLD).
- Exact BUY_LAND cost (not directly exposed in observation) — we gate on a
  cash safety multiple instead of an exact price.
- Whether BUY_ANIMAL requires being at a built structure, or just deposits
  into shed like a purchase — we route it defensively either way.

DEBUG_SCHEMA prints the raw observation once, same as before, in case any
of these assumptions need correcting against a fresh replay.
"""

import json

# ----------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------
DEBUG_SCHEMA = False

TOTAL_TURNS = 720
TURNS_PER_DAY = 24
BOARD_SIZE = 10
QUADRANT_ORDER = ["NW", "NE", "SW", "SE"]

TARGET_CREW_SIZE = 10          # hands to maintain per day (winner used 8-12)
CASH_SAFETY_BUFFER = 150.0     # never spend below this
LAND_PURCHASE_CASH_MULTIPLE = 3.0   # only BUY_LAND if cash > this * buffer
HARVEST_YIELD_THRESHOLD = 1    # attempt harvest once a PLANT/animal tile shows yield_units >= this
CROP_LIFESPAN_SAFETY_MARGIN = 24    # try to harvest at least 1 day before max_lifespan_step
MAX_SELL_BATCH = 6              # per-product sell size, mirrors the winner's observed batching
INVEST_CUTOFF_FRACTION = 0.90   # stop hiring/buying land/animals past this point in the season
LIQUIDATION_START_FRACTION = 0.95  # force-sell everything past this point

DIRECTIONS = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}


# ----------------------------------------------------------------------
# Safe access helpers
# ----------------------------------------------------------------------
def g(d, *keys, default=None):
    if d is None:
        return default
    for k in keys:
        try:
            if hasattr(d, "get") and k in d:
                return d[k]
        except Exception:
            pass
    return default


def season_fraction(observation):
    step = g(observation, "step", default=0)
    return min(max(step / TOTAL_TURNS, 0.0), 1.0)


def is_day_start(observation):
    return g(observation, "hour", default=0) == 0


def move_toward(pos, target):
    """Greedy single-step movement toward target (no obstacle avoidance needed —
    hands/farmer can overlap tiles, confirmed from replay)."""
    px, py = pos
    tx, ty = target
    if px == tx and py == ty:
        return "PASS"
    if abs(tx - px) >= abs(ty - py):
        return "EAST" if tx > px else "WEST"
    return "SOUTH" if ty > py else "NORTH"


def find_nearest(tiles, pos, predicate):
    """Return (x, y) of the nearest tile satisfying predicate(tile), or None."""
    px, py = pos
    best, best_dist = None, None
    for y, row in enumerate(tiles):
        for x, cell in enumerate(row):
            if predicate(cell):
                dist = abs(x - px) + abs(y - py)
                if best_dist is None or dist < best_dist:
                    best, best_dist = (x, y), dist
    return best


# ----------------------------------------------------------------------
# Tile predicates (based on the confirmed state machine)
# ----------------------------------------------------------------------
def is_weed(cell):
    return isinstance(cell, dict) and cell.get("kind") == "WEED"


def is_empty(cell):
    return cell is None


def is_growing_crop(cell):
    return isinstance(cell, dict) and cell.get("kind") == "PLANT"


def is_unwatered_crop(cell):
    return is_growing_crop(cell) and not cell.get("watered_today", False)


def is_harvestable_crop(cell, current_step):
    if not is_growing_crop(cell):
        return False
    yield_units = cell.get("yield_units", 0)
    max_life = cell.get("max_lifespan_step")
    urgent = max_life is not None and (max_life - current_step) <= CROP_LIFESPAN_SAFETY_MARGIN
    return yield_units >= HARVEST_YIELD_THRESHOLD or urgent


def is_animal_tile(cell):
    return isinstance(cell, dict) and cell.get("kind") in ("PASTURE", "COOP") and "animal" in cell


def is_empty_structure(cell):
    return isinstance(cell, dict) and cell.get("kind") in ("PASTURE", "COOP") and "animal" not in cell


def animal_needs_feed(cell):
    return is_animal_tile(cell) and not cell.get("fed_today", False)


def animal_needs_care(cell):
    return is_animal_tile(cell) and not cell.get("cared_today", False)


def animal_has_fertilizer(cell):
    return is_animal_tile(cell) and cell.get("fertilizer_available", False)


def animal_harvestable(cell):
    return is_animal_tile(cell) and cell.get("yield_units", 0) >= HARVEST_YIELD_THRESHOLD


# ----------------------------------------------------------------------
# Per-unit (farmer or hand) decision logic
# ----------------------------------------------------------------------
def decide_unit_action(pos, tiles, current_step, seeds_available, best_crop):
    """
    Priority order (derived directly from the analysis):
      1. Clear weeds — free, and reclaims a plantable tile.
      2. Harvest urgent/ready crops or animal products — avoid losing them.
      3. Feed/care any animal missing today's feed/care.
      4. Collect available fertilizer.
      5. Water any unwatered growing crop.
      6. Plant an empty tile if we have seed stock.
      7. Otherwise, idle toward the farm center (ready for next priority).
    """
    x, y = pos
    here = tiles[y][x]

    # 1. If standing on a weed, clear it immediately.
    if is_weed(here):
        return "DIG"

    # 2. If standing on something harvestable, harvest.
    if is_harvestable_crop(here, current_step) or animal_harvestable(here):
        return "HARVEST"

    # 3. If standing on an animal needing feed/care.
    if animal_needs_feed(here):
        return "FEED"
    if animal_needs_care(here):
        return "CARE"

    # 4. Fertilizer available here.
    if animal_has_fertilizer(here):
        return "COLLECT_FERTILIZER"

    # 5. Standing on unwatered crop.
    if is_unwatered_crop(here):
        return "WATER"

    # 6. Standing on empty tile and we have seeds.
    if is_empty(here) and seeds_available:
        return ["PLANT", best_crop]

    # Otherwise: find the nearest actionable tile and move toward it.
    target = (
        find_nearest(tiles, pos, is_weed)
        or find_nearest(tiles, pos, lambda c: is_harvestable_crop(c, current_step) or animal_harvestable(c))
        or find_nearest(tiles, pos, animal_needs_feed)
        or find_nearest(tiles, pos, animal_needs_care)
        or find_nearest(tiles, pos, animal_has_fertilizer)
        or find_nearest(tiles, pos, is_unwatered_crop)
        or (find_nearest(tiles, pos, is_empty) if seeds_available else None)
    )
    if target:
        return move_toward(pos, target)

    return "PASS"


# ----------------------------------------------------------------------
# Market/economy decisions
# ----------------------------------------------------------------------
def decide_market_orders(observation, my_farm, cash, seeds, shed):
    orders = []
    frac = season_fraction(observation)
    liquidating = frac >= LIQUIDATION_START_FRACTION
    past_invest_cutoff = frac >= INVEST_CUTOFF_FRACTION

    # --- Daily rehire, highest priority on the first turn of the day ---
    if is_day_start(observation) and not past_invest_cutoff:
        current_hands = len(g(my_farm, "hands", default=[]))
        need = max(0, TARGET_CREW_SIZE - current_hands)
        for _ in range(min(need, 10)):  # respect 10 orders/turn cap
            orders.append(["HIRE"])

    remaining_slots = 10 - len(orders)
    if remaining_slots <= 0:
        return orders

    # --- Sell shed surplus, diversified and batched (or dump if liquidating) ---
    if hasattr(shed, "items"):
        for item, qty in shed.items():
            if remaining_slots <= 0:
                break
            if not qty:
                continue
            sell_qty = qty if liquidating else min(qty, MAX_SELL_BATCH)
            if sell_qty > 0:
                orders.append(["SELL", item, sell_qty])
                remaining_slots -= 1

    if past_invest_cutoff:
        return orders  # no new investment this late in the season

    # --- Replenish seeds if running low and cash allows ---
    if remaining_slots > 0 and hasattr(seeds, "items"):
        for crop, qty in seeds.items():
            if remaining_slots <= 0:
                break
            if qty < 5 and cash > CASH_SAFETY_BUFFER:
                orders.append(["BUY_SEED", crop, 10])
                remaining_slots -= 1
                break  # one seed restock per turn is plenty

    # --- Buy next land quadrant opportunistically ---
    if remaining_slots > 0:
        owned = g(my_farm, "unlocked_quadrants", default=[])
        if len(owned) < len(QUADRANT_ORDER) and cash > CASH_SAFETY_BUFFER * LAND_PURCHASE_CASH_MULTIPLE:
            orders.append(["BUY_LAND"])
            remaining_slots -= 1

    return orders


# ----------------------------------------------------------------------
# Main agent
# ----------------------------------------------------------------------
_debug_printed = False
_first_crop_planted = {}  # simple memo, not strictly required


def agent(observation, configuration):
    global _debug_printed

    if DEBUG_SCHEMA and not _debug_printed:
        try:
            print("=== RAW OBSERVATION ===")
            print(json.dumps(observation, default=str, indent=2)[:4000])
        except Exception as e:
            print("Debug print failed:", e)
        _debug_printed = True

    try:
        me = g(observation, "player", default=0)
        farms = g(observation, "farms", default=[])
        my_farm = farms[me] if len(farms) > me else {}
        current_step = g(observation, "step", default=0)

        private = g(observation, "private", default={})
        shed = g(private, "shed", default={})
        seeds = g(private, "seeds", default={})
        cash = g(my_farm, "money", default=0.0)
        tiles = g(my_farm, "tiles", default=[[None] * BOARD_SIZE for _ in range(BOARD_SIZE)])

        seeds_available = any(v > 0 for v in seeds.values()) if hasattr(seeds, "values") else False
        # Prefer whichever seed we currently hold most of, as a simple default;
        # a real ranking would weigh market price, but this is a safe start.
        best_crop = None
        if hasattr(seeds, "items"):
            positive = {k: v for k, v in seeds.items() if v > 0}
            if positive:
                best_crop = max(positive, key=positive.get)

        # --- Farmer action ---
        farmer_pos = g(my_farm, "farmer", default=[4, 4])
        farmer_action = decide_unit_action(farmer_pos, tiles, current_step, seeds_available, best_crop)

        # --- Each hand's action ---
        hands = g(my_farm, "hands", default=[])
        hand_actions = []
        for hand_pos in hands:
            act = decide_unit_action(hand_pos, tiles, current_step, seeds_available, best_crop)
            hand_actions.append(act if isinstance(act, list) else [act])

        # --- Market orders ---
        market_orders = decide_market_orders(observation, my_farm, cash, seeds, shed)

        action = {
            "farmer": farmer_action if isinstance(farmer_action, list) else [farmer_action],
            "hands": hand_actions,
            "market": market_orders,
        }
        return action

    except Exception as e:
        print("Agent error, falling back to PASS:", e)
        # Mirror the game's own default so a crash never produces an invalid action.
        return {"farmer": ["PASS"], "hands": [], "market": []}
