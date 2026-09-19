from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field

@dataclass
class GameState:
    player: int = 0
    day: int = 0         # 0-indexed 0..29
    step: int = 0        # 0..719
    turn: int = 0        # 0..23
    money: float = 3000.0
    farmer_pos: Tuple[int, int] = (4, 4)
    farmer_inventory: int = 0
    farmer_inv_items: Dict[str, int] = field(default_factory=dict)
    hands_pos: List[Tuple[int, int]] = field(default_factory=list)
    hand_inventories: List[int] = field(default_factory=list)
    hand_inv_items: List[Dict[str, int]] = field(default_factory=list)
    unlocked_quadrants: List[str] = field(default_factory=lambda: ["NW"])
    tiles: List[List[Any]] = field(default_factory=list)
    shed: Dict[str, int] = field(default_factory=dict)
    seeds: Dict[str, int] = field(default_factory=dict)
    animals: Dict[str, int] = field(default_factory=dict)
    market_prices: Dict[str, float] = field(default_factory=dict)
    market_inventory: Dict[str, float] = field(default_factory=dict)
    unlocked_shops: List[Dict[str, Any]] = field(default_factory=list)
    hires_today: int = 0

    @classmethod
    def from_obs(cls, obs: Dict[str, Any]) -> "GameState":
        player_idx = int(obs.get("player", 0))
        farms = obs.get("farms", [])
        if not farms or player_idx >= len(farms):
            return cls(player=player_idx)

        farm = farms[player_idx]
        step = int(obs.get("step", 0))
        day = int(obs.get("day", step // 24))
        turn = step % 24
        money = float(farm.get("money", 0.0))

        farmer_raw = farm.get("farmer", [4, 4])
        farmer_pos = (int(farmer_raw[0]), int(farmer_raw[1])) if isinstance(farmer_raw, (list, tuple)) else (4, 4)

        raw_hands = farm.get("hands", [])
        hands_pos: List[Tuple[int, int]] = []
        hand_inventories: List[int] = []
        hand_inv_items: List[Dict[str, int]] = []

        private = obs.get("private", {})
        raw_inventories = private.get("inventories", [])
        farmer_inv_items = dict(raw_inventories[0]) if (isinstance(raw_inventories, list) and len(raw_inventories) > 0 and isinstance(raw_inventories[0], dict)) else {}
        farmer_inventory = sum(farmer_inv_items.values())

        for idx, h in enumerate(raw_hands):
            if isinstance(h, (list, tuple)) and len(h) >= 2:
                hands_pos.append((int(h[0]), int(h[1])))
                if isinstance(raw_inventories, list) and (idx + 1) < len(raw_inventories) and isinstance(raw_inventories[idx + 1], dict):
                    inv_dict = dict(raw_inventories[idx + 1])
                    hand_inv_items.append(inv_dict)
                    hand_inventories.append(sum(inv_dict.values()))
                else:
                    hand_inv_items.append({})
                    hand_inventories.append(0)
            elif isinstance(h, dict):
                pos = h.get("pos", [4, 4])
                hands_pos.append((int(pos[0]), int(pos[1])))
                inv = dict(h.get("items", {}))
                hand_inv_items.append(inv)
                hand_inventories.append(sum(inv.values()))

        unlocked_quadrants = farm.get("unlocked_quadrants", ["NW"])
        if not isinstance(unlocked_quadrants, list):
            unlocked_quadrants = ["NW"]

        tiles = farm.get("tiles", [])

        shed = private.get("shed", {}) if isinstance(private.get("shed"), dict) else {}
        seeds = private.get("seeds", {}) if isinstance(private.get("seeds"), dict) else {}
        animals = private.get("animals", {}) if isinstance(private.get("animals"), dict) else {}

        market_info = obs.get("market", {})
        market_prices = market_info.get("prices", {}) if isinstance(market_info, dict) else {}
        market_inventory = market_info.get("inventory", {}) if isinstance(market_info, dict) else {}

        town_info = obs.get("town", {})
        unlocked_shops = town_info.get("unlocked_shops", []) if isinstance(town_info, dict) else []

        hires_today = int(farm.get("hires_today", 0))

        return cls(
            player=player_idx,
            day=day,
            step=step,
            turn=turn,
            money=money,
            farmer_pos=farmer_pos,
            farmer_inventory=farmer_inventory,
            farmer_inv_items=farmer_inv_items,
            hands_pos=hands_pos,
            hand_inventories=hand_inventories,
            hand_inv_items=hand_inv_items,
            unlocked_quadrants=unlocked_quadrants,
            tiles=tiles,
            shed=shed,
            seeds=seeds,
            animals=animals,
            market_prices=market_prices,
            market_inventory=market_inventory,
            unlocked_shops=unlocked_shops,
            hires_today=hires_today
        )
