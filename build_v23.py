with open("d:/Juracan/main_v22.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V22 — Hyperdrive & Kingmaker Engine.",
    "Orbit Wars V23 — Proactive Defense (V20 Heuristic Restored)."
)
code = code.replace(
    "V22: Hyperdrive & Kingmaker Engine:\n"
    "  1. Fleet Speed Boosting (over-commit surplus to increase flight speed)\n"
    "  2. Anti-Leader Kingmaker Logic (1.5x score multiplier against game leader)\n"
    "  3. Retains all V21 Defensive Simulation",
    "V23: Proactive Defense:\n"
    "  1. Restores V20's paranoid heuristic defense (sees ALL threats, not just 25-turn window)\n"
    "  2. Keeps V22 Fleet Speed Boosting + Kingmaker\n"
    "  3. Keeps V20 Offensive Simulation + Smart INTERCEPT"
)

# ═══════════════════════════════════════════════════════════════
# Swap V21's simulated defense back to V20's heuristic defense
# ═══════════════════════════════════════════════════════════════

OLD_DEFENSE = """    # ------- Priority 0: EMERGENCY_DEFEND -------
    # V21: Exact Defensive Simulation
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

NEW_DEFENSE = """    # ------- Priority 0: EMERGENCY_DEFEND -------
    # V23: Restored V20's paranoid heuristic defense.
    # Counts ALL incoming enemies regardless of distance, ensuring we start
    # reinforcing early for long-range threats that a 25-turn simulator misses.
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

code = code.replace(OLD_DEFENSE, NEW_DEFENSE)

with open("d:/Juracan/main_v23.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v23.py")
