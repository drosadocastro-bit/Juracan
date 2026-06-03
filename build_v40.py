"""
Build V40: The Aggressive Champion synthesis of safe V33/V34 upgrades onto V20 baseline.
"""

import pathlib
import sys

SRC = pathlib.Path("main_v20.py")
DST = pathlib.Path("main_v40.py")

if not SRC.exists():
    print(f"Error: {SRC} not found in current directory.")
    sys.exit(1)

src = SRC.read_text(encoding="utf-8")

# ── Update Docstrings & Title ──
src = src.replace(
    'Orbit Wars V20 — Macro-Simulation Engine (Outcome Prediction).',
    'Orbit Wars V40 — The Aggressive Champion.'
)

# ── Patch 1: Context __slots__ addition ──
P1_OLD = """    __slots__ = (
        "world",
        "friendly_to_enemy", "friendly_to_mine",
        "enemy_to_mine", "enemy_eta_to_mine",
        "owner_power", "leader_owner", "active_owners",
        "is_duel", "duel_opening", "ffa_opening", "ffa_behind",
        "surplus_by_id", "reserve_by_id",
        "target_scores", "arrivals_by_target", "arrivals_timeline",
    )"""

P1_NEW = """    __slots__ = (
        "world",
        "friendly_to_enemy", "friendly_to_mine",
        "enemy_to_mine", "enemy_eta_to_mine",
        "owner_power", "leader_owner", "active_owners",
        "is_duel", "duel_opening", "ffa_opening", "ffa_behind",
        "surplus_by_id", "reserve_by_id",
        "target_scores", "arrivals_by_target", "arrivals_timeline",
        "enemy_outflow", "crash_bonus",
    )"""

assert src.count(P1_OLD) == 1, "Patch 1 Context __slots__ not found or not unique"
src = src.replace(P1_OLD, P1_NEW)


# ── Patch 2: _build_fleet_commitments method replacement ──
P2_OLD = """    def _build_fleet_commitments(self):
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
                    self.arrivals_timeline[tid][eta] -= fleet.ships

        for fleet in w.fleets:
            hit = w.fleet_forecasts.get(fleet.id)
            if hit:
                target_id, eta = hit
                if fleet.owner != w.player:
                    self.arrivals_by_target[target_id].add(fleet.owner)

        self.friendly_to_enemy = defaultdict(int)
        self.friendly_to_mine = defaultdict(int)
        self.enemy_to_mine = defaultdict(int)
        self.enemy_eta_to_mine = {}

        for fleet in w.fleets:
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
                self.enemy_eta_to_mine[target_id] = min(prev, eta)"""

P2_NEW = """    def _build_fleet_commitments(self):
        w = self.world
        self.arrivals_by_target = defaultdict(set)
        self.arrivals_timeline = defaultdict(lambda: defaultdict(int)) # target_id -> {turn: net_ships}
        
        # track outflow from each enemy planet. Recently emptied
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
                self.enemy_outflow[fleet.from_planet_id] += fleet.ships

        for fleet in w.fleets:
            hit = w.fleet_forecasts.get(fleet.id)
            if hit:
                target_id, eta = hit
                if fleet.owner != w.player:
                    self.arrivals_by_target[target_id].add(fleet.owner)

        self.friendly_to_enemy = defaultdict(int)
        self.friendly_to_mine = defaultdict(int)
        self.enemy_to_mine = defaultdict(int)
        self.enemy_eta_to_mine = {}

        for fleet in w.fleets:
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

        # Crash-exploit detection (from V34).
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
                self.crash_bonus[tid] = best_bonus"""

assert src.count(P2_OLD) == 1, "Patch 2 _build_fleet_commitments not found or not unique"
src = src.replace(P2_OLD, P2_NEW)


# ── Patch 3: is_duel player count gating in _build_power_table ──
P3_OLD = """        self.is_duel = len(self.active_owners) <= 2
        self.duel_opening = self.is_duel and w.step < 45"""

P3_NEW = """        # Gate cleanly on initial player count to preserve FFA expansion.
        init_players = _MEMORY.get("_init_nplayers", len(self.active_owners))
        self.is_duel = init_players <= 2
        self.duel_opening = self.is_duel and w.step < 45"""

assert src.count(P3_OLD) == 1, "Patch 3 power table is_duel not found or not unique"
src = src.replace(P3_OLD, P3_NEW)


# ── Patch 4: Gated Vulture and Crash scoring in _best_move_for_source ──
P4_OLD = """        # Score inside the priority bucket.
        base = ctx.target_scores.get(target.id, 0.0)
        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))
        if ctx.duel_opening and target.owner == -1:"""

P4_NEW = """        # Score inside the priority bucket.
        base = ctx.target_scores.get(target.id, 0.0)
        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))

        # Gated bonuses for Vulture and Crash (must be local, scaling down with distance)
        if distance < 25.0:
            scale_factor = (25.0 - distance) / 25.0
            
            # Vulture Offense (from V33-clean2)
            if target.owner not in (-1, world.player):
                outflow = ctx.enemy_outflow.get(target.id, 0)
                if outflow >= 6:
                    total = outflow + max(0, target.ships)
                    ratio = outflow / max(1.0, float(total))
                    if ratio >= 0.4:
                        vulture_bonus = (ratio - 0.4) * 100.0
                        vulture_bonus *= (1.0 + 0.25 * target.production)
                        base += min(60.0, vulture_bonus) * scale_factor
            
            # Crash Exploit (from V34)
            crash = ctx.crash_bonus.get(target.id, 0.0)
            if crash > 0.0:
                base += min(80.0, crash) * scale_factor

        if ctx.duel_opening and target.owner == -1:"""

assert src.count(P4_OLD) == 1, "Patch 4 _best_move_for_source not found or not unique"
src = src.replace(P4_OLD, P4_NEW)


# ── Patch 5: agent entry point _init_nplayers recording ──
P5_OLD = """        # ORIENT
        ctx = Context(world)

        # DECIDE"""

P5_NEW = """        # Record game type once at first step so late-game 2-player endgame
        # in FFA does NOT get mis-classified as a duel.
        if "_init_nplayers" not in _MEMORY:
            raw_planets = _obs_get(obs, "planets", []) or []
            active_owners = {int(p[1]) for p in raw_planets if int(p[1]) >= 0}
            _MEMORY["_init_nplayers"] = len(active_owners)

        # ORIENT
        ctx = Context(world)

        # DECIDE"""

assert src.count(P5_OLD) == 1, "Patch 5 agent entry point not found or not unique"
src = src.replace(P5_OLD, P5_NEW)

DST.write_text(src, encoding="utf-8")
print(f"Success! Wrote {DST} ({DST.stat().st_size:,} bytes).")
