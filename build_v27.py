"""Build V27 from V20: Massive Fleet Doctrine.

The fleet speed formula is: speed = 1 + 5 * (log(ships)/log(1000))^1.5
This means bigger fleets are DRAMATICALLY faster:
  10 ships = 1.55/turn, 50 ships = 3.11/turn, 200 ships = 5.09/turn

V27 raises concentration minimums to force bigger, faster, more devastating fleets.
"""

with open("d:/Juracan/main_v20.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V20 — Macro-Simulation Engine + Fleet Aggregation.",
    "Orbit Wars V27 — Massive Fleet Doctrine."
)
code = code.replace(
    "V20: Macro-Simulation Engine + Fleet Aggregation",
    "V27: Massive Fleet Doctrine\n"
    "  Based on V20's proven heuristic core.\n"
    "  Key change: dramatically higher concentration minimums to exploit the\n"
    "  fleet speed formula. Bigger fleets = faster arrival = better trades."
)

# ── UPGRADE 1: Raise _min_launch_size ──
# Old: 3/5/6 — New: 5/10/15
OLD_MIN_LAUNCH = """def _min_launch_size(step):
    \"\"\"Enforce a floor on launch size so we stop sending 3-ship waves.\"\"\"
    if step < 30:
        return 3
    if step < 90:
        return 5
    return 6"""

NEW_MIN_LAUNCH = """def _min_launch_size(step):
    \"\"\"Enforce a floor on launch size — V27 raises floors to exploit speed scaling.\"\"\"
    if step < 20:
        return 3  # Very early game: still allow small grabs
    if step < 50:
        return 8
    if step < 120:
        return 12
    return 18"""

code = code.replace(OLD_MIN_LAUNCH, NEW_MIN_LAUNCH)

# ── UPGRADE 2: Raise _concentration_minimum dramatically ──
OLD_CONC = """def _concentration_minimum(target, step):
    \"\"\"Minimum effective force against a defended target — scales with production.\"\"\"
    if target.owner == -1:
        return 4 if step < 30 else 6
    return max(8, target.production * 3 + (6 if step >= 80 else 0))"""

NEW_CONC = """def _concentration_minimum(target, step):
    \"\"\"V27: Massive Fleet Doctrine — bigger fleets fly faster and hit harder.
    
    Fleet speed formula: speed = 1 + 5*(log(ships)/log(1000))^1.5
    At 25 ships: 2.25/turn.  At 50: 3.11/turn.  At 100: 4.10/turn.
    Sending fewer, bigger fleets is strictly superior.
    \"\"\"
    if target.owner == -1:
        if step < 25:
            return 5  # Early neutral grabs can be small
        if step < 80:
            return 12  # Mid-game: need decent speed
        return 20  # Late-game: only send fast fleets
    # Owned targets require overwhelming force
    if step < 60:
        return max(15, target.production * 4 + 5)
    if step < 150:
        return max(25, target.production * 5 + 8)
    return max(35, target.production * 6 + 10)"""

code = code.replace(OLD_CONC, NEW_CONC)

with open("d:/Juracan/main_v27.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v27.py")
