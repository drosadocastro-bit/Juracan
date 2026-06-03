"""build_v33_clean2.py — Vulture OFFENSE from V27.1 backbone.

Hypothesis (the ONE structural change in this version):
  Enemy planets that JUST launched a large fleet are transiently weak. V27.1
  rewards LOW current garrison statically but does not exploit transient
  emptying. We add a new signal: for each enemy planet, sum the ships in
  flight that originated from it (`outflow`). High outflow / (outflow+ships)
  ratio means the planet recently emptied to attack elsewhere — prime
  vulture target while it cannot defend.

Per forum: vulture-style play is the dominant ladder pattern. V27.1's
existing "Surgical Vulture" only handles multi-attacker conflicts; transient
post-launch weakness is genuinely orthogonal.

Scope: 3 micro-patches:
  P1: add `enemy_outflow` to Context.__slots__.
  P2: populate it in _build_fleet_commitments (one extra dict update).
  P3: apply a vulture-offense bonus in _score_targets, capped, scaled by
      production and ratio. Only triggers on enemy-owned planets with
      meaningful outflow.

The bonus is bounded above (+60) so it cannot dominate global score. It is
strictly additive (no veto, no behavior shift) — worst case it slightly
re-orders existing target priorities, never blocks an attack.
"""

SRC = "main_v27_1.py"
DST = "main_v33_clean2.py"

with open(SRC, "r", encoding="utf-8") as f:
    code = f.read()

# ---------- P1: add slot ----------
OLD_1 = '''        "surplus_by_id", "reserve_by_id",
        "target_scores", "arrivals_by_target", "arrivals_timeline",
    )'''
NEW_1 = '''        "surplus_by_id", "reserve_by_id",
        "target_scores", "arrivals_by_target", "arrivals_timeline",
        "enemy_outflow",
    )'''
assert OLD_1 in code, "P1 anchor not found"
code = code.replace(OLD_1, NEW_1, 1)

# ---------- P2: populate enemy_outflow in _build_fleet_commitments ----------
OLD_2 = '''    def _build_fleet_commitments(self):
        w = self.world
        self.arrivals_by_target = defaultdict(set)
        self.arrivals_timeline = defaultdict(lambda: defaultdict(int)) # target_id -> {turn: net_ships}
        for fleet in w.fleets:
            hit = w.fleet_forecasts.get(fleet.id)
            if hit:
                tid, eta = hit
                if fleet.owner == w.player:
                    self.arrivals_timeline[tid][eta] += fleet.ships
                else:
                    self.arrivals_timeline[tid][eta] -= fleet.ships'''
NEW_2 = '''    def _build_fleet_commitments(self):
        w = self.world
        self.arrivals_by_target = defaultdict(set)
        self.arrivals_timeline = defaultdict(lambda: defaultdict(int)) # target_id -> {turn: net_ships}
        # V33-clean2: track outflow from each enemy planet. Recently emptied
        # planets are vulture targets while their ships are in flight.
        self.enemy_outflow = defaultdict(int)  # planet_id -> ships in flight
        for fleet in w.fleets:
            hit = w.fleet_forecasts.get(fleet.id)
            if hit:
                tid, eta = hit
                if fleet.owner == w.player:
                    self.arrivals_timeline[tid][eta] += fleet.ships
                else:
                    self.arrivals_timeline[tid][eta] -= fleet.ships
            if fleet.owner not in (-1, w.player) and fleet.from_planet_id >= 0:
                self.enemy_outflow[fleet.from_planet_id] += fleet.ships'''
assert OLD_2 in code, "P2 anchor not found"
code = code.replace(OLD_2, NEW_2, 1)

# ---------- P3: vulture-offense bonus in _score_targets ----------
# Insert right after the existing "Weak-target bonus" line, before V19.1's
# conflict bonus.
OLD_3 = '''            # Weak-target bonus (garrison discount).
            base += max(0.0, 30.0 - t.ships) * 0.9
            # V19.1 UPGRADE 4: Surgical Vulture — bonus to steal planets enemies are fighting over.'''
NEW_3 = '''            # Weak-target bonus (garrison discount).
            base += max(0.0, 30.0 - t.ships) * 0.9
            # V33-clean2: VULTURE OFFENSE. Enemy planets that just launched are
            # transiently weak (their ships are in flight elsewhere). Bonus
            # scales with the fraction of their force that is currently away
            # and with the planet's production. Bounded above so it cannot
            # dominate base value.
            if t.owner not in (-1, w.player):
                outflow = self.enemy_outflow.get(t.id, 0)
                if outflow >= 6:
                    total = outflow + max(0, t.ships)
                    ratio = outflow / max(1.0, float(total))
                    if ratio >= 0.4:
                        # Bonus scales 0..60 with ratio in [0.4, 1.0]
                        # and additionally with production.
                        vulture_bonus = (ratio - 0.4) * 100.0
                        vulture_bonus *= (1.0 + 0.25 * t.production)
                        base += min(60.0, vulture_bonus)
            # V19.1 UPGRADE 4: Surgical Vulture — bonus to steal planets enemies are fighting over.'''
assert OLD_3 in code, "P3 anchor not found"
code = code.replace(OLD_3, NEW_3, 1)

with open(DST, "w", encoding="utf-8") as f:
    f.write(code)

print(f"Wrote {DST} ({len(code):,} bytes)")
print("Changes: 3 micro-patches (slot + outflow map + scoring bonus).")
