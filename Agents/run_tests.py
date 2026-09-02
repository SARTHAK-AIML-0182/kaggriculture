import sys
import json
from kaggle_environments import make

SEEDS = [12345, 101, 102, 103, 104, 105, 106, 107, 108, 109]

MATCHUPS = [
    ("main.py vs starter", ["main.py", "starter"]),
    ("main.py vs random", ["main.py", "random"]),
    ("main.py vs main.py", ["main.py", "main.py"]),
]

results = []

print("Starting Kaggriculture Test Suite across 10 seeds and 3 matchups...\n", flush=True)

for name, agents in MATCHUPS:
    print(f"=== Running Matchup: {name} ===", flush=True)
    for seed in SEEDS:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
        try:
            env.run(agents)
            
            final_step = env.steps[-1]
            p0_state = final_step[0]
            p1_state = final_step[1]
            
            p0_reward = float(p0_state.get("reward", 0.0) or 0.0)
            p1_reward = float(p1_state.get("reward", 0.0) or 0.0)
            
            p0_status = p0_state.get("status", "UNKNOWN")
            p1_status = p1_state.get("status", "UNKNOWN")
            
            timeout_occurred = (p0_status == "TIMEOUT" or p1_status == "TIMEOUT")
            crashed = (p0_status == "ERROR" or p1_status == "ERROR")
            
            p0_obs = p0_state.get("observation", {})
            p0_farms = p0_obs.get("farms", [{}])
            p0_farm = p0_farms[0] if p0_farms else {}
            p0_private = p0_obs.get("private", {})
            
            p0_money = float(p0_farm.get("money", p0_reward))
            p0_shed = p0_private.get("shed", {})
            unsold_items = {k: v for k, v in p0_shed.items() if v > 0}
            unsold_remaining = len(unsold_items) > 0
            
            noop_count = 0
            for step in env.steps:
                action = step[0].get("action", {})
                if isinstance(action, dict):
                    farmer_act = action.get("farmer", ["PASS"])
                    if farmer_act == ["PASS"]:
                        noop_count += 1
            
            res = {
                "matchup": name,
                "seed": seed,
                "p0_reward": p0_reward,
                "p1_reward": p1_reward,
                "p0_status": p0_status,
                "p1_status": p1_status,
                "timeout": timeout_occurred,
                "crashed": crashed,
                "unsold_items": unsold_items,
                "unsold_remaining": unsold_remaining,
                "p0_money": p0_money,
                "money_non_positive": (p0_money <= 0),
                "noop_count": noop_count
            }
            results.append(res)
            print(f"Seed {seed:5d} | P0 Reward: {p0_reward:8.1f} | P1 Reward: {p1_reward:8.1f} | P0 Status: {p0_status} | P1 Status: {p1_status} | Unsold: {unsold_items} | No-Ops: {noop_count}", flush=True)
            
        except Exception as e:
            print(f"Seed {seed:5d} | EXCEPTION: {e}", flush=True)
            results.append({
                "matchup": name,
                "seed": seed,
                "p0_reward": None,
                "p1_reward": None,
                "p0_status": "CRASHED",
                "p1_status": "CRASHED",
                "timeout": False,
                "crashed": True,
                "unsold_items": {},
                "unsold_remaining": False,
                "p0_money": 0,
                "money_non_positive": True,
                "noop_count": 0,
                "error": str(e)
            })

with open("test_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nTest execution complete. Output saved to test_results.json.", flush=True)
