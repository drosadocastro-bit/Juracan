"""Build main_v16.py with refined Adaptive Stance Engine (Golden Opening)."""

import json

# Read V14 ES params as baseline
with open("d:/Juracan/es_best_params.json") as f:
    baseline = json.load(f)

# Override the fatal flaw from ES
baseline["min_fleet_early"] = 3

# Define stances as gentle nudges from baseline
stances = {
    "BASELINE": baseline,
    "VULTURE": dict(baseline, **{
        # Anti-turtle: expand a bit more, hit weak targets
        "neutral_base_mult": baseline["neutral_base_mult"] + 5.0,
        "enemy_base_mult": baseline["enemy_base_mult"] - 5.0,
        "capture_buffer_mult": 1.0,  # Trust our math
    }),
    "FORTRESS": dict(baseline, **{
        # Anti-aggro: hold reserves, wait for them to crash
        "neutral_base_mult": baseline["neutral_base_mult"] - 10.0,
        "enemy_base_mult": baseline["enemy_base_mult"] + 10.0,
        "capture_buffer_mult": 1.15, # Pad captures because they intercept
        "min_fleet_mid": baseline["min_fleet_mid"] + 1,
        "min_fleet_late": baseline["min_fleet_late"] + 1,
    }),
    "SURVIVOR": dict(baseline, **{
        # FFA default: conservative
        "ffa_neutral_bonus": max(15.0, baseline["ffa_neutral_bonus"] - 10.0),
        "capture_buffer_mult": 1.1,
    })
}

# The injection logic
STANCE_LOGIC = """
# ============================================================
# V17 ADAPTIVE STANCE ENGINE
# ============================================================

_STANCES = """ + json.dumps(stances, indent=4) + """

def _determine_stance(world, ctx):
    # The "Golden Opening" - lock in baseline for perfect expansion (applies to Duels and FFAs)
    if world.step < 35:
        return "BASELINE"
        
    if not ctx.is_duel:
        return "SURVIVOR"
    
    # In a duel, profile the opponent
    enemy_id = ctx.leader_owner
    if enemy_id == -1:
        return "VULTURE"
        
    enemy_fleets = sum(1 for f in world.fleets if f.owner == enemy_id)
    enemy_planets = sum(1 for p in world.planets if p.owner == enemy_id)
    
    # If they have many fleets flying relative to their size, they are aggro
    aggro_ratio = enemy_fleets / max(1, enemy_planets)
    
    if aggro_ratio > 1.2:  # Lowered threshold to detect aggro earlier
        return "FORTRESS"
    else:
        return "VULTURE"

# Global param access
_PARAMS = _STANCES["BASELINE"]
"""

with open("d:/Juracan/main_v7.py", encoding="utf-8") as f:
    code = f.read()

# Replace docstring
code = code.replace(
    "Orbit Wars V4 — OODA-L agent.",
    "Orbit Wars V17 — Refined Adaptive Stance Engine (Bugfix)."
).replace(
    "Patched locally as V7: V5 core restored, with a restrained 4-player tempo\nadjustment that boosts early neutral growth without outranking leader pressure.",
    "V17: Adaptive Stance Engine with 'Golden Opening'. Fixed bug where FFA games skipped the golden opening.\nDynamically swaps stances to counter Kaggle's TrueSkill matchmaking."
)

# Inject Stance logic after imports
import_block = "from collections import defaultdict, namedtuple"
code = code.replace(import_block, import_block + "\n" + STANCE_LOGIC)

# Inject stance determination at the end of ORIENT (Context._build_power_table)
power_table_start = "def _build_power_table(self):\n        w = self.world"
code = code.replace(power_table_start, "def _build_power_table(self):\n        global _PARAMS\n        w = self.world")

orient_hook = "self.ffa_behind = (\n            (not self.is_duel) and\n            70 <= w.step < 155 and\n            self.leader_owner != -1 and\n            my_power < leader_power * 0.80\n        )"
orient_injection = """self.ffa_behind = (
            (not self.is_duel) and
            70 <= w.step < 155 and
            self.leader_owner != -1 and
            my_power < leader_power * 0.80
        )
        
        # V16 Stance Determination
        stance_name = _determine_stance(w, self)
        _PARAMS = _STANCES[stance_name]
        _MEMORY["capture_buffer_mult"] = max(_MEMORY.get("capture_buffer_mult", 1.0), _PARAMS.get("capture_buffer_mult", 1.0))
        
        # Log stance changes
        if w.step % 10 == 0:
            print(f"Turn {w.step} Stance: {stance_name}", file=sys.stderr)
"""
code = code.replace(orient_hook, orient_injection)


# Replace hardcoded values with parameterized versions
replacements = [
    # Target scoring
    ('t.production * (92.0 if t.owner == -1 else 118.0)',
     't.production * (_PARAMS["neutral_base_mult"] if t.owner == -1 else _PARAMS["enemy_base_mult"])'),
    ('base += t.production * 70.0',
     'base += t.production * _PARAMS["duel_neutral_bonus"]'),
    ('base += max(0.0, 18.0 - t.ships) * 2.2',
     'base += max(0.0, 18.0 - t.ships) * _PARAMS["duel_garrison_bonus"]'),
    ('base += t.production * 26.0',
     'base += t.production * _PARAMS["ffa_neutral_bonus"]'),
    ('base += max(0.0, 18.0 - t.ships) * 0.9\n                if t.production >= 3 and t.ships <= 16:\n                    base += 24.0',
     'base += max(0.0, 18.0 - t.ships) * _PARAMS["ffa_garrison_bonus"]\n                if t.production >= 3 and t.ships <= 16:\n                    base += _PARAMS["ffa_high_prod_bonus"]'),
    ('base += 110.0',
     'base += _PARAMS["ffa_behind_pressure"]'),
    ('base += 72.0',
     'base += _PARAMS["leader_pressure"]'),
    ('base += max(0.0, 30.0 - t.ships) * 0.9',
     'base += max(0.0, 30.0 - t.ships) * _PARAMS["weak_garrison_bonus"]'),
    
    # Min fleet sizes
    ('if step < 30:\n        return 3\n    if step < 90:\n        return 5\n    return 6',
     'if step < 30:\n        return _PARAMS["min_fleet_early"]\n    if step < 90:\n        return _PARAMS["min_fleet_mid"]\n    return _PARAMS["min_fleet_late"]'),
    
    # Power projection
    ('power[p.owner] += p.ships + p.production * 18.0',
     'power[p.owner] += p.ships + p.production * _PARAMS["power_projection_mult"]'),
    
    # Reserves
    ('if step < 12 and incoming <= 0:',
     'if step < _PARAMS["early_reserve_step"] and incoming <= 0:'),
    ('if step < 22:',
     'if step < _PARAMS["duel_open_step"]:'),
]

for old, new in replacements:
    code = code.replace(old, new)

with open("d:/Juracan/main_v17.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v17.py")
