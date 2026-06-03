"""Build V27.1 — Calibrated Fleet Doctrine.

V27 was too aggressive with concentration minimums in the early game,
causing us to miss expansion windows. V27.1 keeps V20's early tempo
but ramps up concentration much harder in mid/late game.
"""

with open("d:/Juracan/main_v20.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V20 — Macro-Simulation Engine + Fleet Aggregation.",
    "Orbit Wars V27.1 — Calibrated Fleet Doctrine."
)
code = code.replace(
    "V20: Macro-Simulation Engine + Fleet Aggregation",
    "V27.1: Calibrated Fleet Doctrine\n"
    "  V20 core with calibrated concentration minimums.\n"
    "  Early game: V20 tempo (grab neutrals fast with small fleets).\n"
    "  Mid/Late game: bigger fleets to exploit speed scaling."
)

# ── Calibrated _min_launch_size — gentler early, firmer late ──
OLD_MIN_LAUNCH = """def _min_launch_size(step):
    \"\"\"Enforce a floor on launch size so we stop sending 3-ship waves.\"\"\"
    if step < 30:
        return 3
    if step < 90:
        return 5
    return 6"""

NEW_MIN_LAUNCH = """def _min_launch_size(step):
    \"\"\"V27.1: Gentle early ramp, firm late-game floor.\"\"\"
    if step < 30:
        return 3  # Keep V20's early expansion tempo
    if step < 80:
        return 6
    if step < 150:
        return 10
    return 14"""

code = code.replace(OLD_MIN_LAUNCH, NEW_MIN_LAUNCH)

# ── Calibrated _concentration_minimum — V20 early, heavier mid/late ──
OLD_CONC = """def _concentration_minimum(target, step):
    \"\"\"Minimum effective force against a defended target — scales with production.\"\"\"
    if target.owner == -1:
        return 4 if step < 30 else 6
    return max(8, target.production * 3 + (6 if step >= 80 else 0))"""

NEW_CONC = """def _concentration_minimum(target, step):
    \"\"\"V27.1: Calibrated Fleet Doctrine — scale concentration with game phase.
    
    Fleet speed: 1 + 5*(log(ships)/log(1000))^1.5
    25 ships=2.25/turn, 50=3.11, 100=4.10, 200=5.09
    \"\"\"
    if target.owner == -1:
        if step < 30:
            return 4  # V20 early tempo preserved
        if step < 100:
            return 8  # Slightly bigger neutral grabs
        return 15  # Late-game: only fast fleets
    # Owned targets: scale harder with game progression
    if step < 60:
        return max(10, target.production * 3 + 4)
    if step < 150:
        return max(20, target.production * 4 + 8)
    return max(30, target.production * 5 + 10)"""

code = code.replace(OLD_CONC, NEW_CONC)

with open("d:/Juracan/main_v27_1.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v27_1.py")
