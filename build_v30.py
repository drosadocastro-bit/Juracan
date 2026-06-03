"""Build V30 — The Sentinel Heuristic."""

with open("d:/Juracan/main_v27_1.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V27.1 — Calibrated Fleet Doctrine.",
    "Orbit Wars V30 — The Sentinel Heuristic."
)
code = code.replace(
    "V27.1: Calibrated Fleet Doctrine — scale concentration minimums with game phase",
    "V30: The Sentinel Heuristic — V27.1 spine + strict Anti-Trap avoidance for neutral Ambush and enemy Reinforcements"
)

# ── Replace capture_need ──
OLD_CAPTURE_NEED = """    def capture_need(self, target, eta):
        w = self.world
        if target.owner == w.player:
            return 0
        if target.owner == -1:
            raw = target.ships + 1
        else:
            growth = int(math.ceil(max(0.0, eta - 1.0) * target.production))
            raw = target.ships + growth + 1
        already_sent = self.friendly_to_enemy.get(target.id, 0)
        remaining = max(0, raw - already_sent)
        return int(math.ceil(remaining * _MEMORY["capture_buffer_mult"]))"""

NEW_CAPTURE_NEED = """    def capture_need(self, target, eta):
        w = self.world
        if target.owner == w.player:
            return 0
        if target.owner == -1:
            raw = target.ships + 1
        else:
            growth = int(math.ceil(max(0.0, eta - 1.0) * target.production))
            raw = target.ships + growth + 1
            # Anti-Trap for enemy planets: add any enemy reinforcements arriving before our ETA
            enemy_reinforcements = 0
            for fleet in w.fleets:
                if fleet.owner == target.owner: # They are reinforcing their own planet
                    hit = w.fleet_forecasts.get(fleet.id)
                    if hit and hit[0] == target.id and hit[1] <= eta:
                        enemy_reinforcements += fleet.ships
            raw += enemy_reinforcements

        already_sent = self.friendly_to_enemy.get(target.id, 0)
        remaining = max(0, raw - already_sent)
        return int(math.ceil(remaining * _MEMORY["capture_buffer_mult"]))"""

code = code.replace(OLD_CAPTURE_NEED, NEW_CAPTURE_NEED)

# ── Add Anti-Trap Abort in _best_move_for_source ──
OLD_ABORT = """        if aim is None:
            continue
        angle, eta, _, _ = aim

        need = ctx.capture_need(target, eta)"""

NEW_ABORT = """        if aim is None:
            continue
        angle, eta, _, _ = aim

        # Anti-Trap: If the target is currently neutral, but an enemy is arriving BEFORE us and will capture it...
        enemy_capturing = False
        if target.owner == -1:
            for fleet in world.fleets:
                if fleet.owner != world.player:
                    hit = world.fleet_forecasts.get(fleet.id)
                    if hit and hit[0] == target.id and hit[1] <= eta: # They arrive before or same turn
                        if fleet.ships > target.ships:
                            enemy_capturing = True
                            break
        if enemy_capturing:
            continue

        need = ctx.capture_need(target, eta)"""

code = code.replace(OLD_ABORT, NEW_ABORT)

with open("d:/Juracan/main_v30.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v30.py")
