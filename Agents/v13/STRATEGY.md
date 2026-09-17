# STRATEGY.md - Kaggriculture Agent v13 Methodology & Architecture

## Overview & Goal
The **v13 Kaggriculture Agent** is an autonomous simulation AI designed for the Kaggle Kaggriculture environment, targeting **≥$150,000 final liquid cash** by Turn 720 (Day 30).

---

## Key Strategic Principles

### 1. Rapid Land Expansion ($1,000 → $2,000 → $4,000)
- Capital compounds across land. The agent automatically issues `["BUY_LAND"]` market orders as cash thresholds ($1,000 for Quad 2, $2,000 for Quad 3, $4,000 for Quad 4) are met.
- Goal: Unlock all 4 quadrants (100 tiles total) by Day 8–12.

### 2. Multi-Worker Spatial Task Queue & Pathfinding
- Hired hands are assigned to specific 5x5 sub-quadrants (`NW`, `NE`, `SW`, `SE`) to eliminate cross-map movement waste.
- Unified task queue ordered strictly by economic priority:
  1. `HARVEST` mature crops & animal yields
  2. `FEED` unfed animals & `CARE` cared animals
  3. `WATER` unwatered crops (0 grace period on planting day)
  4. `DIG` weeds (same-day cleanup)
  5. `COLLECT_FERTILIZER` & `FERTILIZE` Melons (ages 6–10)
  6. `PLANT` / `PLACE` on empty tiles
  7. `DROP` at nearest shed tile when inventory $\ge 8$ or turn $\ge 22$

### 3. Glut-Aware Price Seller & Town Arbitrage
- Matches market price elasticity profiles (§1.4):
  - High-elasticity goods (`MELON` sq 3.60, `WOOL` sq 3.20, `MILK` lin 1.60, `STRAWBERRY` lin 1.60): Drip-sell in batches of $\le 5$ units/turn to avoid price crashes to $1.
  - Low-elasticity goods (`WHEAT` log 0.20, `EGG` log 0.20): Bulk-sell in larger quantities.
- Town Shop Solver: Prioritizes selling items matching active town shop demands (`obs["town"]["unlocked_shops"]`).

### 4. Free Organic Fertilizer Engine
- Pasture animals generate free daily `FERTILIZER` gathered via `COLLECT_FERTILIZER`.
- Free fertilizer is applied to growing Melons between ages 6 and 10 to force maximum yield of 6 units/tile.

### 5. Phase 4 Total Liquidation (Days 26–30)
- Stops long-cycle planting on Day 25.
- Stops worker hiring and land expansion on Day 26.
- Shifts 100% of worker tasks to harvesting remaining crops and emptying shed storage into liquid cash by Turn 719.
