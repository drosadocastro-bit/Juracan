"""
Build V39: The Heuristic Juggernaut synthesis of V30-V38 upgrades onto V27.1 baseline.
"""

import pathlib
import sys

SRC = pathlib.Path("main_v27_1.py")
DST = pathlib.Path("main_v39.py")

if not SRC.exists():
    print(f"Error: {SRC} not found in current directory.")
    sys.exit(1)

src = SRC.read_text(encoding="utf-8")

# ── Update Docstrings & Title ──
src = src.replace(
    'Orbit Wars V20 — Macro-Simulation Engine (Outcome Prediction).',
    'Orbit Wars V39 — The Heuristic Juggernaut.'
)

# ── Patch 1: constants addition near MAX_SPEED ──
P1_OLD = """MAX_SPEED = 6.0
RAY_EPS = 1e-9"""

P1_NEW = """MAX_SPEED = 6.0
RAY_EPS = 1e-9

# V39: Present-value scoring constants.
PV_GAMMA = 0.99           # discount factor (1% drag per turn)
PV_HORIZON_MIN = 20       # never plan shorter than this even at game end
PV_WEIGHT = 0.45          # blend weight added to baseline heuristic base
DANGER_DIST_C = 6.0       # softening constant for inverse-distance sums
DANGER_DIST_CAP = 60.0    # ignore planets beyond this distance
DANGER_MULT_MIN = 0.55    # score multiplier floor
DANGER_MULT_MAX = 1.45    # score multiplier ceiling"""

assert src.count(P1_OLD) == 1, "Patch 1 anchor not found or not unique"
src = src.replace(P1_OLD, P1_NEW)

# ── Patch 2: tag SNIPE block to add TAG_VULTURE ──
P2_OLD = """TAG_SNIPE = "SNIPE_WEAK"
TAG_PRESSURE = "PRESSURE_LEADER\""""

P2_NEW = """TAG_SNIPE = "SNIPE_WEAK"
TAG_VULTURE = "SNIPE_VULTURE"
TAG_PRESSURE = "PRESSURE_LEADER\""""

assert src.count(P2_OLD) == 1, "Patch 2 anchor not found or not unique"
src = src.replace(P2_OLD, P2_NEW)

# ── Patch 3: Context __slots__ addition ──
P3_OLD = """    __slots__ = (
        "world",
        "friendly_to_enemy", "friendly_to_mine",
        "enemy_to_mine", "enemy_eta_to_mine",
        "owner_power", "leader_owner", "active_owners",
        "is_duel", "duel_opening", "ffa_opening", "ffa_behind",
        "surplus_by_id", "reserve_by_id",
        "target_scores", "arrivals_by_target", "arrivals_timeline",
    )"""

P3_NEW = """    __slots__ = (
        "world",
        "friendly_to_enemy", "friendly_to_mine",
        "enemy_to_mine", "enemy_eta_to_mine",
        "owner_power", "leader_owner", "active_owners",
        "is_duel", "duel_opening", "ffa_opening", "ffa_behind",
        "weakest_enemy_owner",
        "surplus_by_id", "reserve_by_id",
        "target_scores", "arrivals_by_target", "arrivals_timeline",
        "enemy_outflow", "crash_bonus", "danger_by_id",
    )"""

assert src.count(P3_OLD) == 1, "Patch 3 anchor not found or not unique"
src = src.replace(P3_OLD, P3_NEW)

# ── Patch 4: self.leader_owner & self.weakest_enemy_owner ──
P4_OLD = """        self.leader_owner = max(enemies, key=lambda o: power[o]) if enemies else -1
        leader_power = power.get(self.leader_owner, 0.0)"""

P4_NEW = """        self.leader_owner = max(enemies, key=lambda o: power[o]) if enemies else -1
        self.weakest_enemy_owner = (
            min(enemies, key=lambda o: power[o]) if len(enemies) >= 2 else -1
        )
        leader_power = power.get(self.leader_owner, 0.0)"""

assert src.count(P4_OLD) == 1, "Patch 4 anchor not found or not unique"
src = src.replace(P4_OLD, P4_NEW)

# ── Patch 5: _build_fleet_commitments method replacement ──
P5_OLD = """    def _build_fleet_commitments(self):
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

P5_NEW = """    def _build_fleet_commitments(self):
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
                self.crash_bonus[tid] = best_bonus"""

assert src.count(P5_OLD) == 1, "Patch 5 anchor not found or not unique"
src = src.replace(P5_OLD, P5_NEW)

# ── Patch 6: _score_targets() call in Context.__init__ ──
P6_OLD = """        self._build_reserves_and_surplus()
        self._score_targets()"""

P6_NEW = """        self._build_reserves_and_surplus()
        self._compute_danger_map()
        self._score_targets()"""

assert src.count(P6_OLD) == 1, "Patch 6 anchor not found or not unique"
src = src.replace(P6_OLD, P6_NEW)

# ── Patch 7: Context method additions before capture_need ──
P7_OLD = """    def capture_need(self, target, eta):"""

P7_NEW = """    def _compute_danger_map(self):
        \"\"\"Per-planet ally_str / (ally_str + enemy_str) using inverse-distance
        weighting. Higher = friendlier neighborhood.\"\"\"
        w = self.world
        self.danger_by_id = {}
        my_planets = w.my_planets
        enemy_planets = [p for p in w.planets if p.owner not in (-1, w.player)]
        for t in w.planets:
            if t.owner == w.player:
                continue
            ally_str = DANGER_DIST_C
            enemy_str = DANGER_DIST_C
            for p in my_planets:
                d = _dist(p.x, p.y, t.x, t.y)
                if d > DANGER_DIST_CAP:
                    continue
                ally_str += p.ships / max(1.0, d)
            for p in enemy_planets:
                d = _dist(p.x, p.y, t.x, t.y)
                if d > DANGER_DIST_CAP:
                    continue
                enemy_str += p.ships / max(1.0, d)
            total = ally_str + enemy_str
            self.danger_by_id[t.id] = ally_str / total if total > 0 else 0.5

    def present_value(self, target, eta):
        \"\"\"Discounted future production from arrival until game end.\"\"\"
        horizon = max(PV_HORIZON_MIN, 500 - self.world.step)
        if eta >= horizon:
            return 0.0
        # (gamma^eta - gamma^horizon) / (1 - gamma)
        try:
            decay_arrival = PV_GAMMA ** eta
            decay_horizon = PV_GAMMA ** horizon
        except OverflowError:
            return 0.0
        return target.production * (decay_arrival - decay_horizon) / (1.0 - PV_GAMMA)

    def danger_multiplier(self, target):
        \"\"\"Score multiplier from the spatial danger map. V33.1: applies only
        to neutral targets — for enemy-owned planets the multiplier is 1.0
        because we WANT to invade enemy territory, especially in duels.\"\"\"
        if target.owner != -1:
            return 1.0
        d = self.danger_by_id.get(target.id, 0.5)
        return DANGER_MULT_MIN + d * (DANGER_MULT_MAX - DANGER_MULT_MIN)

    def _predict_source_survival(self, source, send_ships, horizon=20):
        \"\"\"V33-clean: anti-vulture defense.

        Simulate the SOURCE planet's garrison over `horizon` turns assuming
        we launch `send_ships` right now. Returns the minimum projected
        garrison (negative => source falls => bad launch).
        \"\"\"
        ships = source.ships - send_ships
        if ships < 0:
            return -200.0  # would over-launch, shouldn't happen but defensive
        timeline = self.arrivals_timeline.get(source.id, {})
        sorted_events = sorted(timeline.items())
        min_ships = ships
        last_t = 0
        for t, net in sorted_events:
            if t > horizon:
                break
            # Produce continuously until this event lands.
            ships += (t - last_t) * source.production
            ships += net
            if ships < 0:
                # Source falls at turn t. Deeper = worse, earlier = worse.
                return -100.0 - (horizon - t)
            min_ships = min(min_ships, ships)
            last_t = t
        return float(min_ships)

    def capture_need(self, target, eta):"""

assert src.count(P7_OLD) == 1, "Patch 7 anchor not found or not unique"
src = src.replace(P7_OLD, P7_NEW)

# ── Patch 8: capture_need implementation modification ──
P8_OLD = """    def capture_need(self, target, eta):
        \"\"\"How many ships required to actually capture `target` at arrival `eta`.

        Accounts for production growth during transit and for friendly fleets
        already committed. Inflated by any learned capture-buffer multiplier.
        \"\"\"
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

P8_NEW = """    def capture_need(self, target, eta):
        \"\"\"How many ships required to actually capture `target` at arrival `eta`.

        Accounts for production growth during transit and for friendly fleets
        already committed. Inflated by any learned capture-buffer multiplier.
        \"\"\"
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

assert src.count(P8_OLD) == 1, "Patch 8 anchor not found or not unique"
src = src.replace(P8_OLD, P8_NEW)

# ── Patch 9: _score_targets scoring additions ──
P9_OLD = """            if t.owner == self.leader_owner:
                base += 72.0
            elif t.owner not in (-1, w.player):
                base += min(42.0, self.owner_power.get(t.owner, 0.0) / 45.0)
            # Weak-target bonus (garrison discount).
            base += max(0.0, 30.0 - t.ships) * 0.9
            # V19.1 UPGRADE 4: Surgical Vulture — bonus to steal planets enemies are fighting over."""

P9_NEW = """            if t.owner == self.leader_owner:
                base += 72.0
            elif (not self.ffa_opening) and self.weakest_enemy_owner >= 0 and t.owner == self.weakest_enemy_owner:
                base += 160.0  # Elimination drive: focus-fire to remove weakest player (FFA, post-opening)
            elif t.owner not in (-1, w.player):
                base += min(42.0, self.owner_power.get(t.owner, 0.0) / 45.0)
            # Weak-target bonus (garrison discount).
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
            # V34: Crash-exploit — bonus for planets where two enemy fleets from
            # different owners will collide, leaving the survivor weakened and the
            # planet transiently vulnerable. Capped at 80 to stay additive.
            crash = self.crash_bonus.get(t.id, 0.0)
            if crash > 0.0:
                base += min(80.0, crash)
            # V19.1 UPGRADE 4: Surgical Vulture — bonus to steal planets enemies are fighting over."""

assert src.count(P9_OLD) == 1, "Patch 9 anchor not found or not unique"
src = src.replace(P9_OLD, P9_NEW)

# ── Patch 10: _best_move_for_source loop logic replacement ──
P10_OLD = """        angle, eta, _, _ = aim

        need = ctx.capture_need(target, eta)
        if need <= 0:
            continue  # someone else already has it covered

        # Concentration minimum — kill the dribble.
        send = max(need, _concentration_minimum(target, step))
        # Add buffer proportional to uncertainty.
        buffer = max(2, int(math.ceil(need * (0.15 if target.owner == -1 else 0.25))))
        send = need + buffer if need + buffer > send else send
        send = min(send, surplus)
        if send < _min_launch_size(step) or send < need:
            continue  # can't afford to capture — don't dribble"""

P10_NEW = """        angle, eta, _, _ = aim

        # Anti-Trap detection: largest enemy fleet that will flip this neutral
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

        # Count distinct active players (anyone holding a planet).
        active_players = {p.owner for p in world.planets if p.owner >= 0}
        ffa_active = len(active_players) >= 3

        # V32: if a captor exists but we're in a duel, revert to V30 strict abort.
        if captor_fleet is not None and not ffa_active:
            continue

        vulture_mode = False
        if captor_fleet is not None and ffa_active:
            # Post-combat residual the captor leaves on the planet (becomes the
            # new garrison; owner flips to captor_fleet.owner).
            residual = max(0, captor_fleet.ships - target.ships)
            # Aim for arrival 3 turns after combat — gives combat resolution
            # slack and 2t of production accumulation.
            desired_eta = captor_eta + 3
            growth = int(math.ceil(max(0.0, desired_eta - captor_eta) * target.production))
            vulture_need = residual + growth + 3  # small buffer
            v_send = max(vulture_need, _min_launch_size(step))
            v_send = min(v_send, surplus)
            if v_send >= max(vulture_need, _min_launch_size(step)):
                v_aim = _aim_solution(source, target, v_send,
                                      world.angular_velocity, world.comet_paths,
                                      world.planets, _MEMORY["path_tolerance"])
                if v_aim is not None:
                    v_angle, v_eta, _, _ = v_aim
                    # Must land strictly AFTER combat (>= captor_eta + 2) and
                    # not so late that captor production overwhelms us.
                    if captor_eta + 2 <= v_eta <= captor_eta + 10:
                        # Recompute need against the late arrival (more growth).
                        actual_growth = int(math.ceil(max(0.0, v_eta - captor_eta) * target.production))
                        actual_need = residual + actual_growth + 3
                        if v_send >= actual_need:
                            angle = v_angle
                            eta = v_eta
                            send = int(v_send)
                            need = actual_need
                            vulture_mode = True
            if not vulture_mode:
                continue  # vulture infeasible — fall back to V30 Anti-Trap abort

        if not vulture_mode:
            need = ctx.capture_need(target, eta)
            if need <= 0:
                continue  # someone else already has it covered

            # Concentration minimum — kill the dribble.
            send = max(need, _concentration_minimum(target, step))
            # Add buffer proportional to uncertainty.
            buffer = max(2, int(math.ceil(need * (0.15 if target.owner == -1 else 0.25))))
            send = need + buffer if need + buffer > send else send
            send = min(send, surplus)
            if send < _min_launch_size(step) or send < need:
                continue  # can't afford to capture — don't dribble"""

assert src.count(P10_OLD) == 1, "Patch 10 anchor not found or not unique"
src = src.replace(P10_OLD, P10_NEW)

# ── Patch 11: TAG_SNIPE action classification ──
P11_OLD = """        # Classify the action.
        if target.owner == world.player:
            continue  # already ours
        if _is_intercept_opportunity(target, eta, ctx, world):
            priority = PRI_INTERCEPT
            tag = TAG_INTERCEPT"""

P11_NEW = """        # Classify the action.
        if target.owner == world.player:
            continue  # already ours
        if vulture_mode:
            priority = PRI_SNIPE
            tag = TAG_VULTURE
        elif _is_intercept_opportunity(target, eta, ctx, world):
            priority = PRI_INTERCEPT
            tag = TAG_INTERCEPT"""

assert src.count(P11_OLD) == 1, "Patch 11 anchor not found or not unique"
src = src.replace(P11_OLD, P11_NEW)

# ── Patch 12: Scoring inside priority bucket ──
P12_OLD = """        # Score inside the priority bucket.
        base = ctx.target_scores.get(target.id, 0.0)
        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))"""

P12_NEW = """        # Score inside the priority bucket.
        base = ctx.target_scores.get(target.id, 0.0)
        # V37: Dynamic profitability in true-duel mode only.
        # Gate on _MEMORY["_init_nplayers"] (recorded at step 0) — NOT
        # ctx.is_duel — so this never fires in the 2P endgame of a 4P FFA.
        if _MEMORY.get("_init_nplayers", 4) <= 2:
            _remaining = max(1, 500 - step)
            base *= max(0.10, (_remaining - eta) / _remaining)

        # V33: present-value bonus weighted by spatial danger map.
        pv = ctx.present_value(target, eta)
        danger_mult = ctx.danger_multiplier(target)
        base += pv * PV_WEIGHT * danger_mult

        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))"""

assert src.count(P12_OLD) == 1, "Patch 12 anchor not found or not unique"
src = src.replace(P12_OLD, P12_NEW)

# ── Patch 13: V20 outcome simulation block ──
P13_OLD = """        # V20: Simulate only if this move is a candidate for the top spot.
        if (priority, -score) < best_rank or score > best_rank[1] - 40.0:
            survival = ctx._predict_outcome(target, send, eta)
            if survival < 0:
                score -= 150.0
            else:
                score += min(60.0, survival / 1.5)
        rank = (priority, -score)"""

P13_NEW = """        # V31: Vulture follow-ups are near-free captures; reward them.
        if vulture_mode:
            score += 35.0

        # V20: Simulate only if this move is a candidate for the top spot.
        if (priority, -score) < best_rank or score > best_rank[1] - 40.0:
            survival = ctx._predict_outcome(target, send, eta)
            if survival < 0:
                score -= 150.0
            else:
                score += min(60.0, survival / 1.5)
            # V33-clean: anti-vulture defense. Penalise launches that doom
            # the source planet. EMERGENCY launches bypass this — when our
            # planet is already under attack we may need to launch anyway.
            if priority != PRI_EMERGENCY:
                src_survival = ctx._predict_source_survival(source, send)
                if src_survival < 0:
                    score -= 180.0  # heavier than target penalty: losing
                                    # an OWNED planet is strictly worse than
                                    # failing to capture a new one.
                elif src_survival < 3:
                    score -= 40.0   # uncomfortable but survivable
        rank = (priority, -score)"""

assert src.count(P13_OLD) == 1, "Patch 13 anchor not found or not unique"
src = src.replace(P13_OLD, P13_NEW)

# ── Patch 14: Step 0 initialization in agent ──
P14_OLD = """        # ORIENT
        ctx = Context(world)

        # DECIDE"""

P14_NEW = """        # ORIENT
        ctx = Context(world)

        # V37: Record game type once at step 0 so late-game 2-player endgame
        # in FFA does NOT get mis-classified as a duel (is_duel flips to True
        # whenever only 2 owners remain, even inside a 4P game).
        if world.step == 0:
            _MEMORY["_init_nplayers"] = len(ctx.active_owners)

        # DECIDE"""

assert src.count(P14_OLD) == 1, "Patch 14 anchor not found or not unique"
src = src.replace(P14_OLD, P14_NEW)

DST.write_text(src, encoding="utf-8")
print(f"Success! Wrote {DST} ({DST.stat().st_size:,} bytes).")
