"""build_v34.py — Crash-exploit from V27.1 backbone.

Hypothesis (single structural change):
  Enemy fleets from DIFFERENT owners sometimes converge on the same planet
  within a few turns. They partially cancel each other (fleet-vs-fleet resolves
  first), leaving the garrison transiently weakened. V27.1 has no signal for
  this: arrivals_by_target tracks owner SETS but _score_targets only uses it
  for "is there a conflict?" not for the precise post-crash state.

  V34 adds:
    1. A per-planet crash-detection pass that finds pairs of non-player fleets
       from DIFFERENT owners converging within CRASH_ETA_WINDOW=3 turns.
    2. A `crash_bonus` score added to those planets, scaled by production and
       inverse of surviving ships (the fewer survivors, the bigger the bonus).

  This is orthogonal to V27.1's "Surgical Vulture" (line 543), which triggers
  only on multi-attacker conflicts regardless of inter-enemy timing.

  Reference: romantamrazov's LB-1224 agent uses CRASH_EXPLOIT_VALUE_MULT=1.18
  and CRASH_EXPLOIT_ETA_WINDOW=3 with CRASH_EXPLOIT_MIN_TOTAL_SHIPS=7.
  Our implementation follows the same detection logic adapted to V27.1's data
  structures.

Patches:
  P1 — add `crash_bonus` to Context.__slots__
  P2 — populate crash_bonus in _build_fleet_commitments (detection pass)
  P3 — apply crash_bonus in _score_targets
"""

SRC = "main_v27_1.py"
DST = "main_v34.py"

with open(SRC, "r", encoding="utf-8") as f:
    code = f.read()

# ---------- P1: add slot ----------
OLD_1 = '''        "surplus_by_id", "reserve_by_id",
        "target_scores", "arrivals_by_target", "arrivals_timeline",
    )'''
NEW_1 = '''        "surplus_by_id", "reserve_by_id",
        "target_scores", "arrivals_by_target", "arrivals_timeline",
        "crash_bonus",
    )'''
assert OLD_1 in code, "P1 anchor not found"
code = code.replace(OLD_1, NEW_1, 1)

# ---------- P2: crash detection at end of _build_fleet_commitments ----------
# Insert before the final blank line that ends the method, right after the
# existing enemy_eta_to_mine loop. We'll anchor on the closing of that loop.
OLD_2 = '''        for fleet in w.fleets:
            hit = w.fleet_forecasts.get(fleet.id)
            if hit is None:
                continue
            target_id, eta = hit
            target = w.planet_by_id.get(target_id)
            if target is None:
                continue

            if fleet.owner == w.player:
                if target.owner == w.player:
                    self.friendly_to_mine[target_id] += fleet.ships
                else:
                    self.friendly_to_enemy[target_id] += fleet.ships
            elif target.owner == w.player:
                self.enemy_to_mine[target_id] += fleet.ships
                prev = self.enemy_eta_to_mine.get(target_id, eta)
                self.enemy_eta_to_mine[target_id] = min(prev, eta)


    def _build_power_table(self):'''
NEW_2 = '''        for fleet in w.fleets:
            hit = w.fleet_forecasts.get(fleet.id)
            if hit is None:
                continue
            target_id, eta = hit
            target = w.planet_by_id.get(target_id)
            if target is None:
                continue

            if fleet.owner == w.player:
                if target.owner == w.player:
                    self.friendly_to_mine[target_id] += fleet.ships
                else:
                    self.friendly_to_enemy[target_id] += fleet.ships
            elif target.owner == w.player:
                self.enemy_to_mine[target_id] += fleet.ships
                prev = self.enemy_eta_to_mine.get(target_id, eta)
                self.enemy_eta_to_mine[target_id] = min(prev, eta)

        # V34: Crash-exploit detection.
        # Build a detailed enemy-arrival map (eta, owner, ships) per planet.
        # Any planet where two DIFFERENT enemy owners converge within 3 turns
        # will see a fleet-vs-fleet cancellation — the survivor is weakened,
        # making the planet a prime opportunistic target.
        _CRASH_ETA_WINDOW = 3
        _CRASH_MIN_SHIPS = 7
        _enemy_arrivals = defaultdict(list)  # planet_id -> [(eta, owner, ships)]
        for fleet in w.fleets:
            hit = w.fleet_forecasts.get(fleet.id)
            if hit and fleet.owner not in (-1, w.player):
                _enemy_arrivals[hit[0]].append((hit[1], fleet.owner, int(fleet.ships)))

        self.crash_bonus = {}
        for tid, events in _enemy_arrivals.items():
            if len(events) < 2:
                continue
            target = w.planet_by_id.get(tid)
            if target is None or target.owner == w.player:
                continue
            events.sort()
            best_bonus = 0.0
            for i in range(len(events)):
                eta_a, owner_a, ships_a = events[i]
                for j in range(i + 1, len(events)):
                    eta_b, owner_b, ships_b = events[j]
                    if eta_b - eta_a > _CRASH_ETA_WINDOW:
                        break
                    if owner_a == owner_b:
                        continue
                    if ships_a + ships_b < _CRASH_MIN_SHIPS:
                        continue
                    # Survivors of the fleet-vs-fleet fight
                    survivor_ships = abs(ships_a - ships_b)
                    # Bonus: scales with production, discounted by survivor strength.
                    # A clean crash (equal fleets) is the most valuable scenario.
                    bonus = 40.0 + target.production * 14.0
                    bonus -= survivor_ships * 0.7
                    best_bonus = max(best_bonus, max(10.0, bonus))
            if best_bonus > 0.0:
                self.crash_bonus[tid] = best_bonus


    def _build_power_table(self):'''
assert OLD_2 in code, "P2 anchor not found"
code = code.replace(OLD_2, NEW_2, 1)

# ---------- P3: apply crash_bonus in _score_targets ----------
# Insert right before the existing Surgical Vulture block.
OLD_3 = '''            # Weak-target bonus (garrison discount).
            base += max(0.0, 30.0 - t.ships) * 0.9
            # V19.1 UPGRADE 4: Surgical Vulture — bonus to steal planets enemies are fighting over.'''
NEW_3 = '''            # Weak-target bonus (garrison discount).
            base += max(0.0, 30.0 - t.ships) * 0.9
            # V34: Crash-exploit — bonus for planets where two enemy fleets from
            # different owners will collide, leaving the survivor weakened and the
            # planet transiently vulnerable. Capped at 80 to stay additive.
            crash = self.crash_bonus.get(t.id, 0.0)
            if crash > 0.0:
                base += min(80.0, crash)
            # V19.1 UPGRADE 4: Surgical Vulture — bonus to steal planets enemies are fighting over.'''
assert OLD_3 in code, "P3 anchor not found"
code = code.replace(OLD_3, NEW_3, 1)

with open(DST, "w", encoding="utf-8") as f:
    f.write(code)

print(f"Wrote {DST} ({len(code):,} bytes)")
print("V34: V27.1 + crash-exploit (3 patches: slot + detection pass + scoring bonus).")
