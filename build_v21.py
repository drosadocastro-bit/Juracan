import re

with open("d:/Juracan/main_v20.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V20 — Macro-Simulation Engine (Outcome Prediction).",
    "Orbit Wars V21 — Defensive Simulator Engine."
)
code = code.replace(
    "V20: Macro-Simulation Engine over V19.1 backbone:\n"
    "  1. Outcome Prediction (25-turn lookahead before launching)\n"
    "  2. Multi-Pass Coordination with Aggregation (Double-Team attacks)\n"
    "  3. Refined Surgical Vulture + Comet Harvesting",
    "V21: Defensive Simulator Engine:\n"
    "  1. Defensive Simulator (exact 25-turn lookahead for EMERGENCY_DEFEND)\n"
    "  2. Smart INTERCEPT (ignore doomed enemy attacks on neutrals)\n"
    "  3. Retains all V20 Offensive Simulation and Aggregation"
)

# ═══════════════════════════════════════════════════════════════
# UPGRADE 1: Defensive Simulator
# ═══════════════════════════════════════════════════════════════

DEFENSIVE_SIMULATOR = """
    def _simulate_defense(self, planet, horizon=25):
        timeline = self.arrivals_timeline.get(planet.id, {})
        sim_ships = float(planet.ships)
        min_ships = sim_ships
        last_t = 0
        failure_turn = 999
        
        sorted_events = sorted(timeline.items())
        for t, net in sorted_events:
            if t >= horizon: break
            sim_ships += (t - last_t) * planet.production
            sim_ships += net
            if sim_ships < min_ships:
                min_ships = sim_ships
                if min_ships < 0 and failure_turn == 999:
                    failure_turn = t
            last_t = t
            
        return float(min_ships), failure_turn
"""

code = code.replace(
    '    def _score_targets(self):',
    DEFENSIVE_SIMULATOR + '\n\n    def _score_targets(self):'
)

# ═══════════════════════════════════════════════════════════════
# UPGRADE 2: EMERGENCY_DEFEND Overhaul
# ═══════════════════════════════════════════════════════════════

OLD_EMERGENCY = """    # A planet is about to fall if (garrison + production until ETA) < incoming enemies.
    # Rally support from nearest planets until the deficit is closed.
    threatened = []
    for p in world.my_planets:
        incoming = ctx.enemy_to_mine.get(p.id, 0)
        if incoming <= 0:
            continue
        eta = ctx.enemy_eta_to_mine.get(p.id, 12)
        defenders = p.ships + int(max(0, eta - 1) * p.production)
        defenders += ctx.friendly_to_mine.get(p.id, 0)
        deficit = incoming + 2 - defenders  # +2 cushion
        if deficit > 0:
            threatened.append((eta, deficit, p))"""

NEW_EMERGENCY = """    # V21: Exact Defensive Simulation
    # A planet is about to fall if its simulated minimum ships drops below zero.
    # Rally support from nearest planets until the deficit is closed.
    threatened = []
    for p in world.my_planets:
        if ctx.enemy_to_mine.get(p.id, 0) <= 0:
            continue
        min_ships, failure_turn = ctx._simulate_defense(p, horizon=25)
        if min_ships < 0:
            deficit = int(math.ceil(abs(min_ships))) + 2  # +2 cushion
            threatened.append((failure_turn, deficit, p))"""

code = code.replace(OLD_EMERGENCY, NEW_EMERGENCY)

# ═══════════════════════════════════════════════════════════════
# UPGRADE 3: Smart INTERCEPT Logic
# ═══════════════════════════════════════════════════════════════

OLD_INTERCEPT = """        # We want to land BEFORE the enemy fleet would capture the planet.
        if my_eta < enemy_eta + 2:
            return True"""

NEW_INTERCEPT = """        # V21: Does the neutral survive anyway?
        defenders = target.ships + int(max(0, enemy_eta - 1) * target.production)
        if defenders >= fleet.ships:
            continue # Enemy will crash and fail, let them!
            
        # We want to land BEFORE the enemy fleet would capture the planet.
        if my_eta < enemy_eta + 2:
            return True"""

code = code.replace(OLD_INTERCEPT, NEW_INTERCEPT)

with open("d:/Juracan/main_v21.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v21.py")
