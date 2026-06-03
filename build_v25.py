with open("d:/Juracan/main_v20.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V20 — Macro-Simulation Engine + Fleet Aggregation.",
    "Orbit Wars V25 — Back to Basics (V20 + Soft Endgame Deceleration)."
)
code = code.replace(
    "V20: Macro-Simulation Engine + Fleet Aggregation",
    "V25: Scientific Minimalism\n"
    "  1. Based entirely on V20's successful heuristic core.\n"
    "  2. Added Soft Endgame Deceleration: raises defensive reserve in the final\n"
    "     40 turns of an FFA game to save ships, without entirely stopping attacks."
)

# ── Inject Soft Endgame Deceleration ──
OLD_RESERVE = """        # Standing reserve grows with time and threat proximity.
        base = max(4, 2 + planet.production)
        if step >= 80:
            base = max(base, 7 + planet.production * 2)
        if step >= 130:
            base = max(base, 10 + planet.production * 3)
        if nearest_enemy < 25.0:"""

NEW_RESERVE = """        # Standing reserve grows with time and threat proximity.
        base = max(4, 2 + planet.production)
        if step >= 80:
            base = max(base, 7 + planet.production * 2)
        if step >= 130:
            base = max(base, 10 + planet.production * 3)
            
        # V25: Soft Endgame Deceleration (FFA only)
        if step >= 460 and not self.is_duel:
            base = max(base, 15 + planet.production * 4)
            
        if nearest_enemy < 25.0:"""

code = code.replace(OLD_RESERVE, NEW_RESERVE)

with open("d:/Juracan/main_v25.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v25.py")
