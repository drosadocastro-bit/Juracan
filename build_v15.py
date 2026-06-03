"""Build main_v15.py with Adaptive Stance Engine."""

import json

# Read V14 ES params as baseline
with open("d:/Juracan/es_best_params.json") as f:
    baseline = json.load(f)

# Define stances
stances = {
    "VULTURE": dict(baseline, **{
        # Anti-turtle: expand hard, be efficient
        "neutral_base_mult": 115.0,
        "enemy_base_mult": 90.0,
        "capture_buffer_mult": 1.0,
        "min_fleet_early": 4,
        "min_fleet_late": 7,
        "early_reserve_step": 12,
    }),
    "FORTRESS": dict(baseline, **{
        # Anti-aggro: hold reserves, wait for them to crash
        "neutral_base_mult": 80.0,
        "enemy_base_mult": 120.0,
        "capture_buffer_mult": 1.2,
        "min_fleet_early": 5,
        "min_fleet_late": 8,
        "early_reserve_step": 20,
    }),
    "SURVIVOR": dict(baseline, **{
        # FFA default: conservative
        "ffa_neutral_bonus": 15.0,
        "ffa_behind_pressure": 110.0,
        "capture_buffer_mult": 1.1,
    })
}

# The injection logic
STANCE_LOGIC = """
# ============================================================
# V15 ADAPTIVE STANCE ENGINE
# ============================================================

_STANCES = """ + json.dumps(stances, indent=4) + """

def _determine_stance(world, ctx):
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
    
    if aggro_ratio > 1.5:
        return "FORTRESS"
    else:
        return "VULTURE"

# Global param access
_PARAMS = _STANCES["VULTURE"]
"""

with open("d:/Juracan/main_v7.py", encoding="utf-8") as f:
    code = f.read()

# Replace docstring
code = code.replace(
    "Orbit Wars V4 — OODA-L agent.",
    "Orbit Wars V15 — Adaptive Stance Engine."
).replace(
    "Patched locally as V7: V5 core restored, with a restrained 4-player tempo\nadjustment that boosts early neutral growth without outranking leader pressure.",
    "V15: Adaptive Stance Engine (Vulture, Fortress, Survivor) to counter Kaggle's TrueSkill matchmaking.\nDynamically profiles opponent aggression and swaps ES-evolved parameters."
)

# Inject Stance logic after imports
import_block = "from collections import defaultdict, namedtuple"
code = code.replace(import_block, import_block + "\n" + STANCE_LOGIC)

# Inject stance determination at the end of ORIENT (Context._build_power_table)
orient_hook = "self.ffa_behind = (\n            (not self.is_duel) and\n            70 <= w.step < 155 and\n            self.leader_owner != -1 and\n            my_power < leader_power * 0.80\n        )"
orient_injection = """self.ffa_behind = (
            (not self.is_duel) and
            70 <= w.step < 155 and
            self.leader_owner != -1 and
            my_power < leader_power * 0.80
        )
        
        # V15 Stance Determination
        global _PARAMS
        stance_name = _determine_stance(w, self)
        _PARAMS = _STANCES[stance_name]
        _MEMORY["capture_buffer_mult"] = max(_MEMORY.get("capture_buffer_mult", 1.0), _PARAMS.get("capture_buffer_mult", 1.0))
        
        # Log stance changes
        if w.step % 10 == 0:
            print(f"Turn {w.step} Stance: {stance_name} (aggro ratio)", file=sys.stderr)
"""
code = code.replace(orient_hook, orient_injection)

# Also fix the global declaration issue: we must declare `global _PARAMS` at the top of the function
# since we use it in the power calculation before the hook.
power_table_start = "def _build_power_table(self):\n        w = self.world"
code = code.replace(power_table_start, "def _build_power_table(self):\n        global _PARAMS\n        w = self.world")
# Now remove the redundant `global _PARAMS` from the injection
code = code.replace("global _PARAMS\n        stance_name", "stance_name")



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

with open("d:/Juracan/main_v15.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v15.py")
