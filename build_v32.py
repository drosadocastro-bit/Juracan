"""Build V32 — FFA-Gated Vulture.

V32 = V31 spine, but the vulture follow-up only activates when 3+ distinct
players still hold planets. In 1v1 duels we revert to V30's strict Anti-Trap
abort, since duel test data (V31 vs V30: 2-3-1) showed vulture adds variance
without consistent gain when there is no third party softening neutrals.
"""

with open("d:/Juracan/main_v31.py", encoding="utf-8") as f:
    code = f.read()

# ── 1. Header ──
code = code.replace(
    "Orbit Wars V31 — Vulture Follow-Up.",
    "Orbit Wars V32 — FFA-Gated Vulture."
)
code = code.replace(
    "V31: Vulture Follow-Up — V30 spine + opportunistic second-wave captures on neutrals an enemy is about to flip",
    "V32: FFA-Gated Vulture — V31 vulture restricted to games with 3+ active players; duels revert to V30 strict abort"
)

# ── 2. Gate the captor detection on FFA player count ──
OLD = """        # Anti-Trap detection: largest enemy fleet that will flip this neutral
        # before us. We only treat the largest as the captor — smaller enemy
        # fleets arriving alongside would be absorbed in their own combat.
        captor_fleet = None
        captor_eta = None
        if target.owner == -1:
            for fleet in world.fleets:
                if fleet.owner == world.player:
                    continue
                hit = world.fleet_forecasts.get(fleet.id)
                if not (hit and hit[0] == target.id and hit[1] <= eta):
                    continue
                if fleet.ships <= target.ships:
                    continue
                if captor_fleet is None or fleet.ships > captor_fleet.ships:
                    captor_fleet = fleet
                    captor_eta = hit[1]

        vulture_mode = False
        if captor_fleet is not None:"""

NEW = """        # Anti-Trap detection: largest enemy fleet that will flip this neutral
        # before us. We only treat the largest as the captor — smaller enemy
        # fleets arriving alongside would be absorbed in their own combat.
        captor_fleet = None
        captor_eta = None
        if target.owner == -1:
            for fleet in world.fleets:
                if fleet.owner == world.player:
                    continue
                hit = world.fleet_forecasts.get(fleet.id)
                if not (hit and hit[0] == target.id and hit[1] <= eta):
                    continue
                if fleet.ships <= target.ships:
                    continue
                if captor_fleet is None or fleet.ships > captor_fleet.ships:
                    captor_fleet = fleet
                    captor_eta = hit[1]

        # V32: count distinct active players (anyone holding a planet).
        active_players = {p.owner for p in world.planets if p.owner >= 0}
        ffa_active = len(active_players) >= 3

        # V32: if a captor exists but we're in a duel, revert to V30 strict abort.
        if captor_fleet is not None and not ffa_active:
            continue

        vulture_mode = False
        if captor_fleet is not None and ffa_active:"""

assert OLD in code, "Captor detection block not found"
code = code.replace(OLD, NEW)

with open("d:/Juracan/main_v32.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v32.py")
