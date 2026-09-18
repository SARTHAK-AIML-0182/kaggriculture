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
    v13_dir = os.path.dirname(os.path.abspath(__file__))
    agents_dir = os.path.dirname(v13_dir)
    
    code_lines = [
        "from typing import Dict, List, Tuple, Any, Optional, Set",
        "from dataclasses import dataclass, field",
        "import math",
        "from collections import deque",
        "",
        "# ==============================================================================",
        "# Kaggriculture v13 Autonomous Engine (Target: ≥$150,000 Revenue by Day 30)",
        "# ==============================================================================",
        ""
    ]
    
    imported_modules = {"state", "board", "economy", "market", "planner", "actions", "agent"}
    
    for filename in MODULE_FILES:
        filepath = os.path.join(v13_dir, filename)
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
    
    # Save to v13/main.py
    v13_main = os.path.join(v13_dir, "main.py")
    with open(v13_main, "w", encoding="utf-8") as f:
        f.write(compiled_code)
    print(f"Successfully compiled {v13_main}")
    
    # Sync to root Agents/main.py
    root_main = os.path.join(agents_dir, "main.py")
    with open(root_main, "w", encoding="utf-8") as f:
        f.write(compiled_code)
    print(f"Successfully synced {root_main}")

if __name__ == "__main__":
    build()
