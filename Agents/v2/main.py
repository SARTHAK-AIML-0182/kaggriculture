"""
Kaggriculture agent — full heuristic build.

HOW TO USE THIS FILE
---------------------
1. Submit this as-is first. DEBUG_SCHEMA=True means your very first turn
   will print the raw observation/configuration objects to stdout. Kaggle
   shows this in the episode logs / "debug" run output.
2. Copy that printed structure back to me (or read it yourself) and we'll
   correct any FIELD NAME GUESSES below (marked with # GUESS) to match
   the real schema exactly. Everything else (the strategy/logic) stays.
3. Once confirmed, set DEBUG_SCHEMA=False before your "real" submission,
   since excess printing can slow down episodes.

WHY IT WON'T CRASH EVEN IF A GUESS IS WRONG
--------------------------------------------
Every read from `observation` goes through `g()`, which tries several
plausible key names and falls back to a safe default instead of raising
a KeyError. Worst case: the agent behaves like a cautious no-op instead
of throwing an invalid-action error that could forfeit the game.
"""

import json

# ----------------------------------------------------------------------
# CONFIG — tune these constants once you're seeing real ratings
# ----------------------------------------------------------------------
DEBUG_SCHEMA = True          # print raw obs/config on turn 0, then stop
CASH_SAFETY_BUFFER = 50.0    # never spend below this cash level
LAND_ROI_MIN = 1.15          # only buy land if expected return > 15%
SELL_PRICE_MARGIN = 1.05     # sell if price >= 5% above rolling avg
HOLD_PRICE_MARGIN = 0.95     # hold (don't sell) if price <= 95% of avg
HIRE_CASH_MULTIPLE = 3.0     # only hire if cash > this * wage cost

# --- phase / endgame tuning ---------------------------------------------
TOTAL_TURNS = 720                  # 30-day season, per the game's own description
GROWTH_PHASE_END_FRACTION = 0.60   # first 60% of season: reinvest aggressively
INVEST_CUTOFF_FRACTION = 0.85      # stop buying land / hiring after this point —
                                    # not enough season left to earn the cost back
LIQUIDATION_START_FRACTION = 0.93  # start force-selling inventory regardless of
                                    # price once this fraction of the season is gone
MAX_SELL_BATCH_FRACTION = 0.40     # never dump more than this fraction of a crop's
                                    # inventory in one order, to avoid crashing our
                                    # own sale price via the supply/demand mechanic

# rolling price history per crop, kept across turns in this dict
_price_history = {}

# ----------------------------------------------------------------------
# Defensive getters — try multiple plausible key names
# ----------------------------------------------------------------------
def g(d, *keys, default=None):
    """Try each key in order on dict-like d; return default if none found."""
    if d is None:
        return default
    for k in keys:
        try:
            if hasattr(d, "get"):
                if k in d:
                    return d[k]
            elif hasattr(d, k):
                return getattr(d, k)
        except Exception:
            pass
    return default


def get_cash(obs):
    return g(obs, "cash", "bank", "money", "balance", default=0.0)


def get_day(obs):
    return g(obs, "day", "turn", "step", default=0)


def get_farm(obs):
    # GUESS: farms/town/market top-level structure per the dataset description
    return g(obs, "farm", "my_farm", "player_farm", default={})


def get_land_plots(farm):
    return g(farm, "land", "plots", "quadrants", default=[])


def get_crops(farm):
    return g(farm, "crops", "fields", default=[])


def get_market(obs):
    return g(obs, "market", "prices", default={})


def get_crop_price(market, crop_name):
    # market might be {"wheat": 4.2, ...} or {"wheat": {"price": 4.2}}
    val = g(market, crop_name, default=None)
    if isinstance(val, dict):
        return g(val, "price", "sell_price", default=0.0)
    if isinstance(val, (int, float)):
        return float(val)
    return 0.0


def get_opponent_farm(obs):
    # GUESS: two-player games in kaggle_environments usually expose both
    # players' state somewhere in the observation, often under something
    # like "opponent", "other_player", or a list indexed by player id.
    return g(obs, "opponent", "opponent_farm", "other_farm", default={})


def opponent_is_ahead(obs, my_cash):
    """
    Returns True/False/None (unknown). Used to decide whether to play
    more conservatively (protect a lead) or take more risk (behind and
    need to catch up) — rather than running one fixed risk profile
    regardless of how the match is actually going.
    """
    opp_farm = get_opponent_farm(obs)
    opp_cash = g(opp_farm, "cash", "bank", default=None)
    if opp_cash is None:
        return None  # unknown — don't guess when we have no signal
    return opp_cash > my_cash


def update_price_history(crop_name, price):
    hist = _price_history.setdefault(crop_name, [])
    hist.append(price)
    if len(hist) > 30:
        hist.pop(0)


def rolling_avg(crop_name):
    hist = _price_history.get(crop_name, [])
    if not hist:
        return None
    return sum(hist) / len(hist)


# ----------------------------------------------------------------------
# Phase awareness — the single biggest edge over naive bots
# ----------------------------------------------------------------------
def season_fraction(obs):
    """0.0 at season start, 1.0 at season end."""
    day = get_day(obs)
    return min(max(day / TOTAL_TURNS, 0.0), 1.0)


def in_growth_phase(frac):
    return frac < GROWTH_PHASE_END_FRACTION


def past_invest_cutoff(frac):
    # Once past this point, buying land / hiring can't earn back its cost
    # before the season ends — most naive bots keep "growing" mechanically
    # right up to the final turn and quietly bleed cash doing it.
    return frac >= INVEST_CUTOFF_FRACTION


def in_liquidation_phase(frac):
    # Force-sell window: anything left unsold at turn 720 is worth zero,
    # so price quality stops mattering and getting rid of inventory does.
    return frac >= LIQUIDATION_START_FRACTION


# ----------------------------------------------------------------------
# Tiered decision logic
# ----------------------------------------------------------------------
def decide_market_actions(obs, cash):
    """
    Tier: sell crops that are priced well above their rolling average.

    Two refinements over a naive "sell everything above average" rule:
      1. Batch throttling — never dump more than MAX_SELL_BATCH_FRACTION
         of a crop's inventory in one order. If the market reacts to
         supply/demand, one giant sell order can crash the very price
         you're trying to capture; smaller batches over several turns
         tend to realize a better average price.
      2. Endgame override — once in_liquidation_phase is true, price
         quality stops being the deciding factor. Sell everything,
         because unsold inventory at turn 720 is worth nothing.
    """
    actions = []
    market = get_market(obs)
    farm = get_farm(obs)
    inventory = g(farm, "inventory", "storage", default={})
    frac = season_fraction(obs)
    liquidating = in_liquidation_phase(frac)

    for crop_name, qty in (inventory.items() if hasattr(inventory, "items") else []):
        if not qty:
            continue
        price = get_crop_price(market, crop_name)
        update_price_history(crop_name, price)
        avg = rolling_avg(crop_name)

        should_sell = liquidating or (avg and price >= avg * SELL_PRICE_MARGIN)
        if not should_sell:
            continue

        if liquidating:
            sell_qty = qty  # dump it all — the season is ending, price no longer matters
        else:
            sell_qty = max(1, int(qty * MAX_SELL_BATCH_FRACTION))  # throttle to avoid self-crash

        actions.append({"type": "SELL", "crop": crop_name, "quantity": sell_qty})  # GUESS format
    return actions


def decide_planting(obs, cash):
    """
    Tier: plant the best-margin crop on any empty plot, if affordable.

    Refinement: don't plant at all once we're past the investment cutoff.
    A naive bot plants mechanically on every empty plot right up to the
    final turns, even though a newly planted crop may never mature (and
    the labor/seed cost is pure loss) before the season ends.
    """
    farm = get_farm(obs)
    plots = get_land_plots(farm)
    market = get_market(obs)
    actions = []

    frac = season_fraction(obs)
    if past_invest_cutoff(frac):
        return actions  # too late in the season for a new crop to pay off

    empty_plots = [p for p in plots if not g(p, "planted", "crop", default=None)]
    if not empty_plots or cash < CASH_SAFETY_BUFFER:
        return actions

    # crude margin estimate: current market price is our proxy for expected
    # sale value; you should replace this with real seed-cost/yield data
    # once you know it, from the competition's Data/Evaluation page.
    crop_options = list(market.keys()) if hasattr(market, "keys") else []
    if not crop_options:
        return actions

    best_crop = max(crop_options, key=lambda c: get_crop_price(market, c))
    plot = empty_plots[0]
    actions.append({
        "type": "PLANT",
        "plot": g(plot, "id", "index", default=0),
        "crop": best_crop,
    })  # GUESS format
    return actions


def decide_hiring(obs, cash):
    """
    Tier: hire labor if cash comfortably exceeds the wage cost.

    Refinement: same investment cutoff as planting — a wage paid on turn
    700 of 720 has almost no season left to generate value from the
    extra labor. Naive bots keep hiring on autopilot; we stop.
    """
    frac = season_fraction(obs)
    if past_invest_cutoff(frac):
        return []

    town = g(obs, "town", default={})
    wage = g(town, "wage", "hire_cost", "labor_cost", default=None)
    actions = []
    if wage and cash > wage * HIRE_CASH_MULTIPLE:
        actions.append({"type": "HIRE"})  # GUESS format
    return actions


def decide_land_purchase(obs, cash):
    """
    Tier: buy adjacent land if cash allows and ROI heuristic is favorable.

    Refinement: apply the same investment cutoff, but earlier and more
    strictly than hiring — land is the slowest-payback investment in the
    game (new plots also need planting + growth time on top of the
    purchase), so we stop buying land noticeably before the general
    cutoff to leave room for that follow-on time.
    """
    frac = season_fraction(obs)
    land_cutoff = INVEST_CUTOFF_FRACTION - 0.10  # stricter than the general cutoff
    if frac >= land_cutoff:
        return []

    town = g(obs, "town", default={})
    land_cost = g(town, "land_cost", "land_price", default=None)
    actions = []
    if land_cost and cash > land_cost * (1 + CASH_SAFETY_BUFFER / max(land_cost, 1)):
        if cash - land_cost > CASH_SAFETY_BUFFER:
            actions.append({"type": "BUY_LAND"})  # GUESS format
    return actions


# ----------------------------------------------------------------------
# Main agent entry point
# ----------------------------------------------------------------------
_debug_printed = False


def agent(observation, configuration):
    global _debug_printed

    if DEBUG_SCHEMA and not _debug_printed:
        try:
            print("=== RAW OBSERVATION ===")
            print(json.dumps(observation, default=str, indent=2)[:4000])
            print("=== RAW CONFIGURATION ===")
            print(json.dumps(configuration, default=str, indent=2)[:2000])
        except Exception as e:
            print("Debug print failed:", e)
        _debug_printed = True

    try:
        cash = get_cash(observation)
        ahead = opponent_is_ahead(observation, cash)  # True/False/None

        # Risk posture: if we know we're behind, loosen the cash safety
        # buffer slightly to enable catch-up plays; if ahead, tighten it
        # to protect the lead instead of chasing more upside we don't need.
        global CASH_SAFETY_BUFFER
        base_buffer = CASH_SAFETY_BUFFER
        if ahead is True:
            CASH_SAFETY_BUFFER = base_buffer * 1.5   # play safer, protect the lead
        elif ahead is False:
            CASH_SAFETY_BUFFER = base_buffer * 0.75  # take a bit more risk to catch up

        actions = []
        actions += decide_market_actions(observation, cash)
        actions += decide_planting(observation, cash)
        actions += decide_hiring(observation, cash)
        actions += decide_land_purchase(observation, cash)

        CASH_SAFETY_BUFFER = base_buffer  # restore for next turn's baseline

        if not actions:
            return {"type": "WAIT"}  # GUESS: safe no-op action name

        # Many kaggle_environments games expect ONE action per turn, not a list.
        # If that's the case here, just return actions[0] instead:
        # return actions[0]
        return actions

    except Exception as e:
        # Absolute last resort: never let an unhandled exception forfeit the game.
        print("Agent error, falling back to WAIT:", e)
        return {"type": "WAIT"}
