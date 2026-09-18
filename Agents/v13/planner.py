from typing import Dict, List, Tuple, Any, Set
from state import GameState
from board import (
    manhattan,
    nearest_shed_tile,
    move_towards,
    unlocked,
    tile_at,
    is_free,
    is_plant,
    is_weed,
    is_pasture,
    is_coop,
    crop_ready_to_harvest,
    animal_ready_to_harvest,
    animal_has_fertilizer,
    animal_needs_care,
    animal_needs_feed,
    is_empty_structure,
    has_animal,
    STRUCTURE_TILES,
    ANIMALS_CONFIG,
    QUADRANT_SHED_TILES,
    QUADRANTS,
)
from economy import choose_crop


def build_task_queue(state: GameState) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    day = state.day
    tiles = state.tiles

    # General Farm Tiles (Crops, Weeds, Planting)
    for y, row in enumerate(tiles):
        if not isinstance(row, list):
            continue
        for x, tile in enumerate(row):
            if not unlocked(tile):
                continue

            pos = (x, y)
            # Reserved structure positions are handled via worker local animal engine
            if pos in STRUCTURE_TILES:
                continue

            if is_weed(tile):
                tasks.append({
                    "priority": 25,
                    "pos": pos,
                    "action": ["DIG"],
                })
                continue

            if is_plant(tile):
                watered = bool(tile.get("watered_today", False))
                unwatered = int(tile.get("consecutive_unwatered", 0))
                planted_day = int(tile.get("planted_day", day))
                age = day - planted_day
                crop = tile.get("crop", "")
                is_ongoing = (crop in ("TOMATO", "STRAWBERRY"))
                ready_to_harvest = crop_ready_to_harvest(tile, day)

                # Priority 1: Harvest Ready Crop
                if ready_to_harvest:
                    tasks.append({
                        "priority": 1,
                        "pos": pos,
                        "action": ["HARVEST"],
                    })

                # Priority 0 / 10: Water (urgent if unwatered >= 1 or planted today)
                if not watered and (not ready_to_harvest or is_ongoing):
                    prio = 0 if (unwatered >= 1 or age == 0) else 10
                    tasks.append({
                        "priority": prio,
                        "pos": pos,
                        "action": ["WATER"],
                    })

                continue

            if is_free(tile):
                # Plant up to Day 24 and within turns 0-21
                if day <= 24 and state.turn <= 21:
                    tasks.append({
                        "priority": 30,
                        "pos": pos,
                        "action": ["PLANT"],
                    })

    tasks.sort(key=lambda t: (t["priority"], t["pos"][1], t["pos"][0]))
    return tasks


def solve_worker_actions(
    state: GameState,
    tasks: List[Dict[str, Any]]
) -> Tuple[List[str], List[List[str]]]:
    workers: List[Tuple[int, int]] = [state.farmer_pos]
    workers.extend(state.hands_pos)

    available_seeds = {k: int(v) for k, v in state.seeds.items() if int(v) > 0}
    actions: List[List[str]] = [["PASS"] for _ in workers]
    used_tasks: Set[int] = set()

    unlocked_quads = state.unlocked_quadrants if state.unlocked_quadrants else ["NW"]

    for worker_idx, worker_pos in enumerate(workers):
        # Determine worker inventory items
        if worker_idx == 0:
            w_inv = state.farmer_inv_items
        else:
            h_idx = worker_idx - 1
            w_inv = state.hand_inv_items[h_idx] if h_idx < len(state.hand_inv_items) else {}

        # 1. Local Quadrant Livestock Engine
        assigned_quad = unlocked_quads[worker_idx % len(unlocked_quads)]
        q_xmin, q_xmax, q_ymin, q_ymax = QUADRANTS.get(assigned_quad, (0, 9, 0, 9))
        local_shed_tile = QUADRANT_SHED_TILES.get(assigned_quad, (4, 4))

        # Check if this worker's quadrant hosts a structure tile
        local_struct_pos = None
        local_struct_type = None
        local_animal_name = None
        for spos, (stype, aname, squad) in STRUCTURE_TILES.items():
            if squad == assigned_quad:
                local_struct_pos = spos
                local_struct_type = stype
                local_animal_name = aname
                break

        handled_animal = False
        if local_struct_pos and unlocked(tile_at(state.tiles, local_struct_pos[0], local_struct_pos[1])):
            stile = tile_at(state.tiles, local_struct_pos[0], local_struct_pos[1])
            
            # A. If carrying this animal, walk to empty structure & place
            if w_inv.get(local_animal_name, 0) > 0:
                if worker_pos != local_struct_pos:
                    actions[worker_idx] = move_towards(worker_pos, local_struct_pos)
                else:
                    actions[worker_idx] = ["PLACE", local_animal_name]
                handled_animal = True

            # B. If structure is free, construct it!
            elif is_free(stile):
                if worker_pos != local_struct_pos:
                    actions[worker_idx] = move_towards(worker_pos, local_struct_pos)
                else:
                    actions[worker_idx] = ["BUILD_" + local_struct_type]
                handled_animal = True

            # C. If structure is empty and animal is waiting in shed, pick it up!
            elif is_empty_structure(stile) and int(state.shed.get(local_animal_name, 0)) > 0:
                if worker_pos != local_shed_tile:
                    actions[worker_idx] = move_towards(worker_pos, local_shed_tile)
                else:
                    actions[worker_idx] = ["PICKUP", local_animal_name, 1]
                handled_animal = True

            # D. If animal is on tile, perform daily care, feed, fertilizer, and harvest!
            elif has_animal(stile):
                if animal_ready_to_harvest(stile):
                    if worker_pos != local_struct_pos:
                        actions[worker_idx] = move_towards(worker_pos, local_struct_pos)
                    else:
                        actions[worker_idx] = ["HARVEST"]
                    handled_animal = True
                elif animal_needs_feed(stile):
                    if w_inv.get("WHEAT", 0) > 0:
                        if worker_pos != local_struct_pos:
                            actions[worker_idx] = move_towards(worker_pos, local_struct_pos)
                        else:
                            actions[worker_idx] = ["FEED"]
                        handled_animal = True
                    elif int(state.shed.get("WHEAT", 0)) > 0:
                        if worker_pos != local_shed_tile:
                            actions[worker_idx] = move_towards(worker_pos, local_shed_tile)
                        else:
                            actions[worker_idx] = ["PICKUP", "WHEAT", 1]
                        handled_animal = True
                elif animal_has_fertilizer(stile):
                    if worker_pos != local_struct_pos:
                        actions[worker_idx] = move_towards(worker_pos, local_struct_pos)
                    else:
                        actions[worker_idx] = ["COLLECT_FERTILIZER"]
                    handled_animal = True
                elif animal_needs_care(stile):
                    if worker_pos != local_struct_pos:
                        actions[worker_idx] = move_towards(worker_pos, local_struct_pos)
                    else:
                        actions[worker_idx] = ["CARE"]
                    handled_animal = True

        if handled_animal:
            continue

        # 2. General Quadrant Crop Tasks
        best_idx = None
        best_key = None

        for task_idx, task in enumerate(tasks):
            if task_idx in used_tasks:
                continue

            target = task["pos"]
            tx, ty = target
            action_op = task["action"][0]

            # If task is PLANT, ensure we have seeds
            if action_op == "PLANT":
                current_crop = choose_crop(state.day, available_seeds)
                if available_seeds.get(current_crop, 0) <= 0:
                    continue

            # Strong quadrant locality keeps workers focused on their 24 tiles
            out_of_bounds_penalty = 0 if (q_xmin <= tx <= q_xmax and q_ymin <= ty <= q_ymax) else 50
            dist = manhattan(worker_pos, target)
            key = (int(task["priority"]) + out_of_bounds_penalty, dist, ty, tx)

            if best_key is None or key < best_key:
                best_key = key
                best_idx = task_idx

        if best_idx is None:
            continue

        task = tasks[best_idx]
        target = task["pos"]
        task_action = task["action"]

        if worker_pos != target:
            actions[worker_idx] = move_towards(worker_pos, target)
            if task_action[0] == "PLANT":
                current_crop = choose_crop(state.day, available_seeds)
                if available_seeds.get(current_crop, 0) > 0:
                    available_seeds[current_crop] -= 1
        else:
            if task_action[0] == "PLANT":
                current_crop = choose_crop(state.day, available_seeds)
                if available_seeds.get(current_crop, 0) > 0:
                    available_seeds[current_crop] -= 1
                    actions[worker_idx] = ["PLANT", current_crop]
                else:
                    actions[worker_idx] = ["PASS"]
            else:
                actions[worker_idx] = task_action

        used_tasks.add(best_idx)

    farmer_action = actions[0] if actions else ["PASS"]
    hand_actions = actions[1:] if len(actions) > 1 else []

    return farmer_action, hand_actions
