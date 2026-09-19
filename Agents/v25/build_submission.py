import os
import re

MODULE_FILES = [
    "state.py",
    "board.py",
    "economy.py",
    "market.py",
    "planner.py",
    "actions.py",
    "agent.py"
]

def build():
    v25_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(v25_dir)
    
    code_lines = [
        "from typing import Dict, List, Tuple, Any, Optional, Set",
        "from dataclasses import dataclass, field",
        "import math",
        "from collections import deque",
        "",
        "# ==============================================================================",
        "# Kaggriculture v25 Autonomous Engine",
        "# (10 Cows, 2 Geese, 2 Quadrants, Fast Cultivation, 6 Workers)",
        "# ==============================================================================",
        ""
    ]
    
    imported_modules = {"state", "board", "economy", "market", "planner", "actions", "agent"}
    
    for filename in MODULE_FILES:
        filepath = os.path.join(v25_dir, filename)
        if not os.path.exists(filepath):
            continue
            
        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        code_lines.append(f"# --- Module: {filename} ---")
        in_multiline_import = False
        for line in lines:
            stripped = line.strip()
            if in_multiline_import:
                if ")" in stripped:
                    in_multiline_import = False
                continue

            if stripped.startswith("from ") or stripped.startswith("import "):
                tokens = stripped.replace(",", " ").replace("(", " ").split()
                if any(mod in tokens for mod in imported_modules):
                    if "(" in stripped and ")" not in stripped:
                        in_multiline_import = True
                    continue
                if any(mod in stripped for mod in ["typing", "dataclasses", "math", "collections"]):
                    if "(" in stripped and ")" not in stripped:
                        in_multiline_import = True
                    continue
            code_lines.append(line.rstrip())
        code_lines.append("\n")

    compiled_code = "\n".join(code_lines)
    
    # Save to v25/main.py
    v25_main = os.path.join(v25_dir, "main.py")
    with open(v25_main, "w", encoding="utf-8") as f:
        f.write(compiled_code)
    print(f"Successfully compiled {v25_main}")

if __name__ == "__main__":
    build()
