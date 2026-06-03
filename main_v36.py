"""
Orbit Wars V20 — Macro-Simulation Engine (Outcome Prediction).

Patched locally as V5: duel-aware opening, faster 2-player neutral expansion,
and preserved pending-decision memory for the LEARN phase.

V20: Macro-Simulation Engine over V19.1 backbone:
  1. Outcome Prediction (25-turn lookahead before launching)
  2. Multi-Pass Coordination with Aggregation (Double-Team attacks)
  3. Refined Surgical Vulture + Comet Harvesting

Architecture (adapted from the Julia OODA-L framework):
    OBSERVE  -> parse obs into a typed WorldState, cache fleet-landing forecasts.
    ORIENT   -> build Context: threat map, capturable targets, leader, reserves.
    DECIDE   -> priority cascade (EMERGENCY_DEFEND > INTERCEPT > REINFORCE > SNIPE >
                PRESSURE_LEADER > EXPAND > STOCKPILE). One action per source per turn
                except in EMERGENCY — kills the dribble-attack pattern that V2 fell into.
    ACT      -> invariant firewall validates every move before emit; each move is tagged.
    LEARN    -> within-game 3-strike memory (module-global). Tracks predicted vs actual
                outcomes between turns. On recurring failures: blacklist targets,
                inflate capture buffers, tighten path clearance.

Kaggle submissions are stateless across games, so LEARN operates turn-to-turn within a
single game and emits JSONL bitacora events to stderr (captured by `kaggle competitions
logs`) for human-in-the-loop tuning between submissions.
"""

import json
import math
import sys
from collections import defaultdict, namedtuple


# ============================================================
# CONSTANTS
# ============================================================

Planet = namedtuple("Planet", "id owner x y radius ships production")
Fleet = namedtuple("Fleet", "id owner x y angle from_planet_id ships")

CENTER_X = 50.0
CENTER_Y = 50.0
BOARD_SIZE = 100.0
SUN_RADIUS = 10.0
ROTATION_LIMIT = 50.0
MAX_SPEED = 6.0
RAY_EPS = 1e-9

# Decision tags for the bitacora.
TAG_EMERGENCY = "EMERGENCY_DEFEND"
TAG_INTERCEPT = "INTERCEPT"
TAG_DUEL_OPEN = "DUEL_OPENING"
TAG_REINFORCE = "REINFORCE"
TAG_SNIPE = "SNIPE_WEAK"
TAG_PRESSURE = "PRESSURE_LEADER"
TAG_EXPAND = "EXPAND_CHEAP"
TAG_STOCKPILE = "STOCKPILE"


# ============================================================
# GAME MEMORY (persists across turns within a single game)
# Kaggle resets the Python process between games, so this is
# effectively ephemeral per game — exactly what we want for the
# within-game LEARN phase.
# ============================================================

_MEMORY = {
    "turn": -1,
    "last_obs_step": -1,
    "pending_launches": [],   # [{target_id, need, eta, sent, step}]
    "strike_target": defaultdict(int),   # target_id -> failed attacks
    "blacklist": {},                     # target_id -> release_turn
    "capture_buffer_mult": 1.0,          # inflated on repeated under-captures
    "path_tolerance": 0.25,              # tightened on repeated intercepts
    "tracked_planets": {},               # last-seen planet state for diff
    "last_decisions": [],                # for debug / future replay
}


def _reset_memory():
    _MEMORY["turn"] = -1
    _MEMORY["last_obs_step"] = -1
    _MEMORY["pending_launches"] = []
    _MEMORY["strike_target"] = defaultdict(int)
    _MEMORY["blacklist"] = {}
    _MEMORY["capture_buffer_mult"] = 1.0
    _MEMORY["path_tolerance"] = 0.25
    _MEMORY["tracked_planets"] = {}
    _MEMORY["last_decisions"] = []


# ============================================================
# UTILITY MATH (preserved from V3 — battle-tested)
# ============================================================

def _obs_get(obs, key, default=None):
    if isinstance(obs, dict):
        return obs.get(key, default)
    return getattr(obs, key, default)


def _as_planets(raw):
    return [Planet(int(p[0]), int(p[1]), float(p[2]), float(p[3]),
                   float(p[4]), int(p[5]), int(p[6])) for p in raw]


def _as_fleets(raw):
    return [Fleet(int(f[0]), int(f[1]), float(f[2]), float(f[3]),
                  float(f[4]), int(f[5]), int(f[6])) for f in raw]


def _dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def _fleet_speed(ships):
    ships = max(1, int(ships))
    scale = min(1.0, max(0.0, math.log(ships) / math.log(1000.0)))
    return 1.0 + (MAX_SPEED - 1.0) * (scale ** 1.5)


def _segment_circle_distance_sq(ax, ay, bx, by, cx, cy):
    dx = bx - ax
    dy = by - ay
    denom = dx * dx + dy * dy
    if denom <= RAY_EPS:
        return (ax - cx) ** 2 + (ay - cy) ** 2
    t = ((cx - ax) * dx + (cy - ay) * dy) / denom
    t = max(0.0, min(1.0, t))
    px = ax + t * dx
    py = ay + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2


def _is_orbiting(planet):
    return _dist(planet.x, planet.y, CENTER_X, CENTER_Y) + planet.radius < ROTATION_LIMIT


def _rotate_point(x, y, turns, angular_velocity):
    if abs(angular_velocity) <= RAY_EPS or turns <= 0.0:
        return x, y
    dx = x - CENTER_X
    dy = y - CENTER_Y
    angle = angular_velocity * turns
    ca = math.cos(angle)
    sa = math.sin(angle)
    return CENTER_X + dx * ca - dy * sa, CENTER_Y + dx * sa + dy * ca


def _build_comet_paths(obs):
    comet_paths = {}
    raw_groups = _obs_get(obs, "comets", []) or []
    for group in raw_groups:
        if isinstance(group, dict):
            planet_ids = group.get("planet_ids", []) or []
            paths = group.get("paths", []) or []
            path_index = int(group.get("path_index", 0) or 0)
        else:
            planet_ids = getattr(group, "planet_ids", []) or []
            paths = getattr(group, "paths", []) or []
            path_index = int(getattr(group, "path_index", 0) or 0)
        for i, planet_id in enumerate(planet_ids):
            if i < len(paths):
                comet_paths[int(planet_id)] = (paths[i], path_index)
    return comet_paths


def _predict_position(planet, turns, angular_velocity, comet_paths):
    comet_data = comet_paths.get(planet.id)
    if comet_data:
        path, index = comet_data
        if path:
            target_index = int(round(index + max(0.0, turns)))
            target_index = min(len(path) - 1, max(0, target_index))
            point = path[target_index]
            return float(point[0]), float(point[1])
    if _is_orbiting(planet):
        return _rotate_point(planet.x, planet.y, turns, angular_velocity)
    return planet.x, planet.y


def _comet_remaining_turns(planet, comet_paths):
    data = comet_paths.get(planet.id)
    if not data:
        return 999
    path, index = data
    return max(0, len(path) - int(index) - 1) if path else 0


def _line_hits_sun(ax, ay, bx, by):
    limit = SUN_RADIUS + 0.35
    return _segment_circle_distance_sq(ax, ay, bx, by, CENTER_X, CENTER_Y) <= limit * limit


def _path_is_clear(source, target, tx, ty, planets, tolerance=0.25):
    if _line_hits_sun(source.x, source.y, tx, ty):
        return False
    dx = tx - source.x
    dy = ty - source.y
    length_sq = dx * dx + dy * dy
    if length_sq <= RAY_EPS:
        return False
    for p in planets:
        if p.id == source.id or p.id == target.id:
            continue
        along = ((p.x - source.x) * dx + (p.y - source.y) * dy) / length_sq
        if along <= 0.03 or along >= 0.97:
            continue
        radius = p.radius + tolerance
        if _segment_circle_distance_sq(source.x, source.y, tx, ty, p.x, p.y) <= radius * radius:
            return False
    return True


def _aim_solution(source, target, ships, angular_velocity, comet_paths, planets, tolerance):
    eta = _dist(source.x, source.y, target.x, target.y) / _fleet_speed(ships)
    tx, ty = target.x, target.y
    for _ in range(4):
        tx, ty = _predict_position(target, eta, angular_velocity, comet_paths)
        eta = _dist(source.x, source.y, tx, ty) / _fleet_speed(ships)
    if not _path_is_clear(source, target, tx, ty, planets, tolerance):
        return None
    return math.atan2(ty - source.y, tx - source.x), eta, tx, ty


def _first_hit_for_fleet(fleet, planets, angular_velocity, comet_paths, horizon=45):
    speed = _fleet_speed(fleet.ships)
    ux = math.cos(fleet.angle)
    uy = math.sin(fleet.angle)
    px = fleet.x
    py = fleet.y
    for turn in range(1, horizon + 1):
        nx = fleet.x + ux * speed * turn
        ny = fleet.y + uy * speed * turn
        if nx < 0.0 or nx > BOARD_SIZE or ny < 0.0 or ny > BOARD_SIZE:
            return None
        if _line_hits_sun(px, py, nx, ny):
            return None
        best = None
        best_dist = float("inf")
        for p in planets:
            if p.id == fleet.from_planet_id:
                continue
            tx, ty = _predict_position(p, turn, angular_velocity, comet_paths)
            radius = p.radius + 0.35
            d_sq = _segment_circle_distance_sq(px, py, nx, ny, tx, ty)
            if d_sq <= radius * radius:
                d = _dist(px, py, tx, ty)
                if d < best_dist:
                    best = p
                    best_dist = d
        if best is not None:
            return best.id, turn
        px, py = nx, ny
    return None


# ============================================================
# BITACORA (stderr JSONL; Kaggle captures into agent logs)
# ============================================================

def _log(event, **fields):
    try:
        record = {"turn": _MEMORY.get("turn", -1), "event": event}
        record.update(fields)
        sys.stderr.write(json.dumps(record) + "\n")
    except Exception:
        pass  # never let logging crash the agent


# ============================================================
# OBSERVE — parse obs into typed state + cached forecasts
# ============================================================

class WorldState:
    __slots__ = (
        "player", "step", "angular_velocity",
        "planets", "fleets", "planet_by_id",
        "my_planets", "enemy_planets", "neutral_planets",
        "comet_paths", "fleet_forecasts",
    )

    def __init__(self, obs):
        self.player = int(_obs_get(obs, "player", 0) or 0)
        self.step = int(_obs_get(obs, "step", 0) or 0)
        self.angular_velocity = float(_obs_get(obs, "angular_velocity", 0.0) or 0.0)
        self.planets = _as_planets(_obs_get(obs, "planets", []) or [])
        self.fleets = _as_fleets(_obs_get(obs, "fleets", []) or [])
        self.comet_paths = _build_comet_paths(obs)
        self.planet_by_id = {p.id: p for p in self.planets}

        self.my_planets = [p for p in self.planets if p.owner == self.player]
        self.enemy_planets = [p for p in self.planets
                              if p.owner not in (-1, self.player)]
        self.neutral_planets = [p for p in self.planets if p.owner == -1]

        # Cache: for every fleet in flight, what planet will it hit and when?
        self.fleet_forecasts = {}
        for fleet in self.fleets:
            hit = _first_hit_for_fleet(fleet, self.planets,
                                       self.angular_velocity, self.comet_paths)
            if hit is not None:
                self.fleet_forecasts[fleet.id] = hit  # (target_id, eta_turns)


# ============================================================
# ORIENT — build Context: threat, capture, leader, reserves
# ============================================================

class Context:
    __slots__ = (
        "world",
        "friendly_to_enemy", "friendly_to_mine",
        "enemy_to_mine", "enemy_eta_to_mine",
        "owner_power", "leader_owner", "active_owners",
        "is_duel", "duel_opening", "ffa_opening", "ffa_behind",
        "surplus_by_id", "reserve_by_id",
        "target_scores", "arrivals_by_target", "arrivals_timeline",
    )

    def __init__(self, world):
        self.world = world
        self._build_fleet_commitments()
        self._build_power_table()
        self._build_reserves_and_surplus()
        self._score_targets()


    def _build_fleet_commitments(self):
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
                self.enemy_eta_to_mine[target_id] = min(prev, eta)


    def _build_power_table(self):
        w = self.world
        power = defaultdict(float)
        for p in w.planets:
            if p.owner >= 0:
                power[p.owner] += p.ships + p.production * 18.0
        for f in w.fleets:
            if f.owner >= 0:
                power[f.owner] += f.ships
        self.owner_power = dict(power)
        self.active_owners = sorted(power)
        self.is_duel = len(self.active_owners) <= 2
        self.duel_opening = self.is_duel and w.step < 45
        enemies = [o for o in power if o != w.player]
        self.leader_owner = max(enemies, key=lambda o: power[o]) if enemies else -1
        leader_power = power.get(self.leader_owner, 0.0)
        my_power = power.get(w.player, 0.0)
        self.ffa_opening = (not self.is_duel) and w.step < 72
        self.ffa_behind = (
            (not self.is_duel) and
            70 <= w.step < 155 and
            self.leader_owner != -1 and
            my_power < leader_power * 0.80
        )


    def _build_reserves_and_surplus(self):
        w = self.world
        self.reserve_by_id = {}
        self.surplus_by_id = {}
        for p in w.my_planets:
            nearest_enemy = min(
                (_dist(p.x, p.y, e.x, e.y) for e in w.enemy_planets),
                default=999.0,
            )
            reserve = self._reserve_for(p, nearest_enemy)
            self.reserve_by_id[p.id] = reserve
            self.surplus_by_id[p.id] = max(0, p.ships - reserve)


    def _reserve_for(self, planet, nearest_enemy):
        """Dynamic reserve — escalates with game progress and proximity to threat.

        V2's reserves were too low mid-game, causing home planets to flip after a
        single coordinated attack. V4 keeps a meaningful reserve even in STOCKPILE
        phases.
        """
        w = self.world
        step = w.step
        incoming = self.enemy_to_mine.get(planet.id, 0)

        # Very early game: skeleton crew while we expand.
        if step < 12 and incoming <= 0:
            return 1

        # In a 2-player duel, falling behind on neutral production in the first
        # forty turns is usually fatal. Keep the midgame hold behavior, but do
        # not let the opening reserve suppress expansion.
        if self.duel_opening and incoming <= 0:
            if step < 22:
                return 1
            return max(1, planet.production // 2)

        # 4-player opening: spend a little more on growth, but do not repeat
        # V6's full tempo shift. Nearby enemies still force a real garrison.
        if self.ffa_opening and incoming <= 0:
            if nearest_enemy < 18.0:
                return max(3, planet.production + 1)
            if step < 48:
                return max(1, planet.production // 2)
            return max(2, planet.production)

        # If the FFA leader is snowballing, V5's late reserve ramp can leave too
        # many ships parked. Loosen only distant, non-threatened planets.
        if self.ffa_behind and incoming <= 0 and nearest_enemy >= 28.0:
            return max(3, planet.production + 1)

        # Small empire, early-mid: keep production-based reserve.
        if len(w.my_planets) <= 2 and step < 60 and incoming <= 0:
            return max(1, planet.production // 2)

        if step < 90 and incoming <= 0:
            return max(2, planet.production)

        # Standing reserve grows with time and threat proximity.
        base = max(4, 2 + planet.production)
        if step >= 80:
            base = max(base, 7 + planet.production * 2)
        if step >= 130:
            base = max(base, 10 + planet.production * 3)
        if nearest_enemy < 25.0:
            base += 4
        elif nearest_enemy < 38.0:
            base += 2

        if incoming <= 0:
            return base

        # Threat override: hold enough to survive the incoming wave.
        eta = self.enemy_eta_to_mine.get(planet.id, 12)
        produced = int(max(0, eta - 1) * planet.production)
        return max(base, incoming + 3 - produced)



    def _predict_outcome(self, target, send_ships, arrival_eta, horizon=25):
        w = self.world
        eta = int(round(arrival_eta))
        timeline = self.arrivals_timeline.get(target.id, {})
        
        # 1. State at Arrival
        ships = target.ships
        if target.owner != -1:
            ships += int(max(0, eta - 1) * target.production)
        
        sorted_events = sorted(timeline.items())
        for t, net in sorted_events:
            if t >= eta: break
            ships += net
            if ships < 0: ships = abs(ships)
        
        # Our landing
        sim_ships = send_ships - ships
        if sim_ships <= 0: return -50.0
        
        # 2. Retention Window
        min_ships = sim_ships
        last_t = eta
        for t, net in sorted_events:
            if t < eta: continue
            if t >= eta + horizon: break
            # Production until this event
            sim_ships += (t - last_t) * target.production
            sim_ships += net
            if sim_ships < 0:
                return -100.0 - (t - eta)
            min_ships = min(min_ships, sim_ships)
            last_t = t
            
        return float(min_ships + target.production * (eta + horizon - last_t))


    def _score_targets(self):
        """Pre-score every non-owned planet as an attack candidate."""
        w = self.world
        self.target_scores = {}
        for t in w.planets:
            if t.owner == w.player:
                continue
            if t.id in _MEMORY["blacklist"] and _MEMORY["blacklist"][t.id] > _MEMORY["turn"]:
                continue
            # Static value of capturing this planet.
            base = t.production * (92.0 if t.owner == -1 else 118.0)
            if self.duel_opening and t.owner == -1:
                base += t.production * 70.0
                base += max(0.0, 18.0 - t.ships) * 2.2
            if self.ffa_opening and t.owner == -1:
                base += t.production * 26.0
                base += max(0.0, 18.0 - t.ships) * 0.9
                if t.production >= 3 and t.ships <= 16:
                    base += 24.0
            if self.ffa_behind and t.owner == self.leader_owner:
                base += 110.0
            if t.owner == self.leader_owner:
                base += 72.0
            elif t.owner not in (-1, w.player):
                base += min(42.0, self.owner_power.get(t.owner, 0.0) / 45.0)
            # Weak-target bonus (garrison discount).
            base += max(0.0, 30.0 - t.ships) * 0.9
            # V19.1 UPGRADE 4: Surgical Vulture — bonus to steal planets enemies are fighting over.
            enemy_attackers = self.arrivals_by_target.get(t.id, set())
            is_conflict = len(enemy_attackers) >= 2
            if t.owner != -1:
                # If owner is in a fight with at least one attacker
                for attacker_owner in enemy_attackers:
                    if attacker_owner != t.owner:
                        is_conflict = True
                        break
            
            if is_conflict:
                base += 45.0
            
            # V19.1 UPGRADE 2: Comet Harvesting — grab long-lived low-garrison comets.
            if t.id in w.comet_paths:
                remaining = _comet_remaining_turns(t, w.comet_paths)
                if remaining < 15:
                    base -= 120.0  # Too short-lived
                elif remaining < 28:
                    if t.production >= 2 and t.ships <= 6:
                        base += 15.0  # Quick grab opportunity
                    else:
                        base -= 50.0
                else:
                    if t.production >= 3 and t.ships <= 8:
                        base += 10.0
                    else:
                        base -= 10.0
            self.target_scores[t.id] = base


    def capture_need(self, target, eta):
        """How many ships required to actually capture `target` at arrival `eta`.

        Accounts for production growth during transit and for friendly fleets
        already committed. Inflated by any learned capture-buffer multiplier.
        """
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
        return int(math.ceil(remaining * _MEMORY["capture_buffer_mult"]))


# ============================================================
# DECIDE — priority cascade
# ============================================================
# Priority order. Lower number = more urgent. Only the highest-priority
# actionable move is taken per source planet per turn, except in EMERGENCY
# where a source may launch multiple defensive waves. This is the single
# biggest behavioral change vs V2/V3: no more dribble-spam of tiny fleets.

PRI_EMERGENCY = 0
PRI_INTERCEPT = 1
PRI_DUEL_OPEN = 2
PRI_REINFORCE = 3
PRI_SNIPE     = 4
PRI_PRESSURE  = 5
PRI_EXPAND    = 6


def _min_launch_size(step):
    """V27.1: Gentle early ramp, firm late-game floor."""
    if step < 30:
        return 3  # Keep V20's early expansion tempo
    if step < 80:
        return 6
    if step < 150:
        return 10
    return 14


def _concentration_minimum(target, step):
    """V27.1: Calibrated Fleet Doctrine — scale concentration with game phase.
    
    Fleet speed: 1 + 5*(log(ships)/log(1000))^1.5
    25 ships=2.25/turn, 50=3.11, 100=4.10, 200=5.09
    """
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
    return max(30, target.production * 5 + 10)


def decide(world, ctx):
    """Return a list of (priority, tag, source, target, ships, angle) tuples.

    Each source planet emits at most one action per priority level. EMERGENCY
    can use multiple sources; the rest pick one best move per source.
    """
    decisions = []

    # ------- Priority 0: EMERGENCY_DEFEND -------
    # A planet is about to fall if (garrison + production until ETA) < incoming enemies.
    # Rally support from nearest planets until the deficit is closed.
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
            threatened.append((eta, deficit, p))

    threatened.sort(key=lambda t: t[0])  # soonest first

    used_surplus = defaultdict(int)

    # V19.1 UPGRADE 3: Tactical Retreat — evacuate hopeless defenses.
    total_surplus = sum(ctx.surplus_by_id.get(p.id, 0) for p in world.my_planets)
    retreat_targets = set()
    for enemy_eta, deficit, target in threatened:
        if deficit > total_surplus * 2.0 and target.ships >= _min_launch_size(world.step):
            # Defense is hopeless — evacuate garrison to nearest friendly
            nearest_ally = min(
                (p for p in world.my_planets if p.id != target.id),
                key=lambda p: _dist(p.x, p.y, target.x, target.y),
                default=None,
            )
            if nearest_ally is not None:
                evac_ships = max(_min_launch_size(world.step), target.ships - 1)
                aim = _aim_solution(target, nearest_ally, evac_ships,
                                    world.angular_velocity, world.comet_paths,
                                    world.planets, _MEMORY["path_tolerance"])
                if aim is not None:
                    angle, _, _, _ = aim
                    decisions.append((PRI_EMERGENCY, "TACTICAL_RETREAT", target, nearest_ally, int(evac_ships), angle))
                    used_surplus[target.id] += evac_ships
                    retreat_targets.add(target.id)
                    _log("retreat", source=int(target.id), dest=int(nearest_ally.id), ships=int(evac_ships))
                    continue

    for enemy_eta, deficit, target in threatened:
        if target.id in retreat_targets:
            continue
        supporters = sorted(
            (s for s in world.my_planets if s.id != target.id and
             ctx.surplus_by_id.get(s.id, 0) - used_surplus[s.id] > 0),
            key=lambda s: _dist(s.x, s.y, target.x, target.y),
        )
        need = deficit
        emergency_min = max(3, _min_launch_size(world.step) - 1)
        for source in supporters:
            if need <= 0:
                break
            avail = ctx.surplus_by_id.get(source.id, 0) - used_surplus[source.id]
            if avail < emergency_min:
                continue
            send = min(avail, max(need, emergency_min))
            aim = _aim_solution(source, target, send,
                                world.angular_velocity, world.comet_paths,
                                world.planets, _MEMORY["path_tolerance"])
            if aim is None:
                continue
            angle, arrival_eta, _, _ = aim
            # Don't launch if the fleet arrives long after the enemy strike.
            # A bit of overshoot is fine (recapture timing), but > enemy_eta + 3
            # is pure waste.
            if arrival_eta > enemy_eta + 3:
                continue
            decisions.append((PRI_EMERGENCY, TAG_EMERGENCY, source, target, int(send), angle))
            used_surplus[source.id] += send
            need -= send

    # ------- Priority 1-5: one action per source -------
    # Candidates per source; we'll pick the highest-priority best-scoring one.
    # V19.1 UPGRADE: Multi-Pass Coordination — exhaustive 3-pass dedup.
    final_moves = {}
    excluded_targets = set()
    sources_to_assign = set(p.id for p in world.my_planets)

    for _ in range(3):
        if not sources_to_assign:
            break
        
        source_best = {}
        for source_id in list(sources_to_assign):
            source = world.planet_by_id.get(source_id)
            surplus = ctx.surplus_by_id.get(source_id, 0) - used_surplus[source_id]
            if surplus < _min_launch_size(world.step):
                sources_to_assign.remove(source_id)
                continue

            best = _best_move_for_source(source, surplus, world, ctx, excluded_targets)
            if best is not None:
                source_best[source_id] = best
            else:
                sources_to_assign.remove(source_id)

        if not source_best:
            break

        # Group by target
        target_to_sources = defaultdict(list)
        for sid, move in source_best.items():
            target_id = move[3].id
            target_to_sources[target_id].append((sid, move))

        for target_id, attackers in target_to_sources.items():
            attackers.sort(key=lambda a: _dist(a[1][2].x, a[1][2].y, a[1][3].x, a[1][3].y))
            target = attackers[0][1][3]
            need = ctx.capture_need(target, attackers[0][1][4])
            total_sent = 0
            for sid, move in attackers:
                final_moves[sid] = move
                sources_to_assign.remove(sid)
                total_sent += move[4]
                if total_sent >= need: break
            excluded_targets.add(target_id)

    for source_id, move in final_moves.items():
        decisions.append(move)

    if not decisions:
        decisions.append((99, TAG_STOCKPILE, None, None, 0, 0.0))

    return decisions


def _best_move_for_source(source, surplus, world, ctx, excluded_targets=None):
    """Find the single best (highest-priority, best-scoring) move for this source."""
    step = world.step
    best = None
    best_rank = (99, -1e18)  # (priority, -score) — lower is better

    for target in world.planets:
        if target.owner == world.player or target.id == source.id:
            continue
        # Respect blacklist from LEARN.
        if target.id in _MEMORY["blacklist"] and _MEMORY["blacklist"][target.id] > _MEMORY["turn"]:
            continue
        # V19.1: skip targets already claimed by another source.
        if excluded_targets and target.id in excluded_targets:
            continue
        # Skip comets that will leave before we arrive.
        if target.id in world.comet_paths and _comet_remaining_turns(target, world.comet_paths) < 18:
            continue

        # Probe aim with capture-sized fleet.
        probe = max(_min_launch_size(step),
                    min(surplus, target.ships + target.production * 2 + 8))
        aim = _aim_solution(source, target, probe,
                            world.angular_velocity, world.comet_paths,
                            world.planets, _MEMORY["path_tolerance"])
        if aim is None:
            continue
        angle, eta, _, _ = aim

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
            continue  # can't afford to capture — don't dribble

        # Classify the action.
        if target.owner == world.player:
            continue  # already ours
        if _is_intercept_opportunity(target, eta, ctx, world):
            priority = PRI_INTERCEPT
            tag = TAG_INTERCEPT
        elif ctx.duel_opening and target.owner == -1:
            priority = PRI_DUEL_OPEN
            tag = TAG_DUEL_OPEN
        elif target.owner == ctx.leader_owner and ctx.leader_owner != -1:
            priority = PRI_PRESSURE
            tag = TAG_PRESSURE
        elif target.owner == -1:
            # Cheap neutral vs expensive neutral.
            if target.ships <= 8 and _dist(source.x, source.y, target.x, target.y) < 30:
                priority = PRI_EXPAND
                tag = TAG_EXPAND
            else:
                priority = PRI_SNIPE
                tag = TAG_SNIPE
        else:
            priority = PRI_SNIPE
            tag = TAG_SNIPE

        # Score inside the priority bucket.
        base = ctx.target_scores.get(target.id, 0.0)
        # V36: Dynamic profitability in DUEL mode only. In 1v1, capturing a
        # planet with only 10 turns left is worth far less than capturing it
        # with 200 turns left — efficiency dominates binary outcomes. In FFA,
        # aggressive play until step 500 is correct (ships on planets score at
        # time-out), so we keep the static multiplier for non-duel games.
        if ctx.is_duel:
            _remaining = max(1, 500 - step)
            base *= max(0.10, (_remaining - eta) / _remaining)
        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))
        if ctx.duel_opening and target.owner == -1:
            score = base - send * 1.2 - distance * 1.45 - eta * 2.0
            if target.production >= 3:
                score += 45.0
            if target.ships <= 12:
                score += 28.0
            # In duels, raw tempo matters more than pure efficiency.
            score /= math.sqrt(max(1, send))
        elif ctx.ffa_opening and target.owner == -1:
            score = base - send * 1.55 - distance * 0.72 - eta * 1.35
            if target.production >= 3:
                score += 18.0
            if target.ships <= 14:
                score += 14.0
            score /= max(1.0, math.sqrt(max(1, send)) * 1.35)
        else:
            score = base - send * 1.9 - distance * 0.55 - eta * 1.2
            score /= max(1, send)  # efficiency-normalized

        # V20: Simulate only if this move is a candidate for the top spot.
        if (priority, -score) < best_rank or score > best_rank[1] - 40.0:
            survival = ctx._predict_outcome(target, send, eta)
            if survival < 0:
                score -= 150.0
            else:
                score += min(60.0, survival / 1.5)
        rank = (priority, -score)
        if rank < best_rank:
            best_rank = rank
            best = (priority, tag, source, target, int(send), angle)

    return best


def _is_intercept_opportunity(target, my_eta, ctx, world):
    """True if an enemy fleet is about to capture this neutral and we can beat it."""
    if target.owner != -1:
        return False
    # Check for enemy fleets targeting this neutral.
    for fleet in world.fleets:
        if fleet.owner == world.player:
            continue
        hit = world.fleet_forecasts.get(fleet.id)
        if hit is None:
            continue
        if hit[0] != target.id:
            continue
        enemy_eta = hit[1]
        # We want to land BEFORE the enemy fleet would capture the planet.
        if my_eta < enemy_eta + 2:
            return True
    return False


# ============================================================
# ACT — invariant firewall + emit moves
# ============================================================
# Strategic invariants (hard constraints checked per move):
#   I1. Never launch more ships than the source planet currently holds.
#   I2. Never launch across the sun.
#   I3. Never launch when path-clear check fails (recomputed w/ learned tolerance).
#   I4. Never drop a source planet below its dynamic reserve, except EMERGENCY.
#   I5. Never launch below the min-launch floor (no 1-3 ship dribbles).
#   I6. At most one non-emergency launch per source per turn.

def act(world, ctx, decisions):
    moves = []
    used_by_source = defaultdict(int)
    non_emergency_launched = set()
    tagged = []

    # Sort: emergencies first, then by priority.
    decisions.sort(key=lambda d: d[0])

    for priority, tag, source, target, ships, angle in decisions:
        if source is None or target is None or ships <= 0:
            continue

        # I6: one non-emergency launch per source per turn.
        if priority != PRI_EMERGENCY and source.id in non_emergency_launched:
            continue

        # Recompute what's actually available after previous commits.
        planet_now = world.planet_by_id.get(source.id)
        if planet_now is None:
            continue
        already_used = used_by_source[source.id]
        actual_available = planet_now.ships - already_used

        # I4: respect reserves (except emergency).
        if priority == PRI_EMERGENCY:
            max_send = actual_available
        else:
            reserve = ctx.reserve_by_id.get(source.id, 0)
            max_send = max(0, actual_available - reserve)

        if max_send < _min_launch_size(world.step):
            continue  # I5
        send = min(ships, max_send)

        # I1: never exceed available.
        if send <= 0 or send > planet_now.ships:
            continue

        # I2 + I3: revalidate aim with current settings.
        aim = _aim_solution(source, target, send,
                            world.angular_velocity, world.comet_paths,
                            world.planets, _MEMORY["path_tolerance"])
        if aim is None:
            continue
        angle, eta, _, _ = aim

        moves.append([int(source.id), float(angle), int(send)])
        used_by_source[source.id] += send
        if priority != PRI_EMERGENCY:
            non_emergency_launched.add(source.id)

        tagged.append({
            "tag": tag,
            "priority": priority,
            "source": int(source.id),
            "target": int(target.id),
            "ships": int(send),
            "eta": float(eta),
            "target_owner": int(target.owner),
        })

    if tagged:
        _log("act", moves=tagged)

    # Carry forward pending decisions from LEARN, then append this turn's actions.
    # V4 accidentally overwrote older in-flight commitments here, which made the
    # LEARN phase mostly short-memory. V5 keeps the chain alive.
    _MEMORY["last_decisions"] = list(_MEMORY.get("last_decisions", [])) + tagged
    return moves


# ============================================================
# LEARN — 3-strike within-game adaptation
# ============================================================
# Each turn we check:
#   - Did attacks launched ~ETA turns ago actually capture the target?
#   - Did defensive recalls arrive before the attacker?
#   - Were there fleets of ours that hit a non-target planet or got sunk?
# Repeated failures under similar conditions increment strike counters;
# after three strikes, we apply a behavior change.

def learn(world, ctx):
    turn = world.step
    _MEMORY["turn"] = turn

    # Release expired blacklist entries.
    expired = [tid for tid, release in _MEMORY["blacklist"].items() if release <= turn]
    for tid in expired:
        del _MEMORY["blacklist"][tid]

    # Evaluate outcomes of launches we logged previously.
    tracked = _MEMORY.get("tracked_planets", {})
    last = _MEMORY.get("last_decisions", [])

    # An attack "should have" landed by now if its eta was < 1.5 turns.
    still_pending = []
    for d in last:
        if d["priority"] == PRI_EMERGENCY:
            continue  # defensive, different success criteria
        if d["eta"] > 1.5:
            # Still in flight, carry forward. Reduce ETA by one.
            d["eta"] -= 1.0
            still_pending.append(d)
            continue

        target_id = d["target"]
        target_now = world.planet_by_id.get(target_id)
        if target_now is None:
            continue
        expected_owner = world.player

        # Did we capture it?
        if target_now.owner == expected_owner:
            # Success: reduce strike counter for this target.
            if _MEMORY["strike_target"][target_id] > 0:
                _MEMORY["strike_target"][target_id] -= 1
            _log("learn_success", target=target_id, tag=d["tag"])
        else:
            # Miss. Possible causes:
            #   a) Fleet was intercepted mid-flight.
            #   b) Target had more defenders than we estimated.
            #   c) Target moved unexpectedly (orbiting / comet).
            _MEMORY["strike_target"][target_id] += 1
            strikes = _MEMORY["strike_target"][target_id]
            _log("learn_miss", target=target_id, tag=d["tag"], strikes=strikes,
                 expected_owner=expected_owner, actual_owner=int(target_now.owner))

            # 3-STRIKE RULE: apply behavior change.
            if strikes >= 3:
                _MEMORY["blacklist"][target_id] = turn + 25
                _MEMORY["strike_target"][target_id] = 0
                # Global adaptations: if we've had 3 strikes somewhere, opponents
                # are clearly better than we estimated — pad capture buffers.
                _MEMORY["capture_buffer_mult"] = min(1.6, _MEMORY["capture_buffer_mult"] + 0.08)
                # Tighten path tolerance slightly — maybe we're clipping planets.
                _MEMORY["path_tolerance"] = min(0.55, _MEMORY["path_tolerance"] + 0.05)
                _log("learn_rewrite", target=target_id,
                     blacklist_until=turn + 25,
                     capture_mult=_MEMORY["capture_buffer_mult"],
                     path_tolerance=_MEMORY["path_tolerance"])

    _MEMORY["last_decisions"] = still_pending
    _MEMORY["tracked_planets"] = {p.id: (p.owner, p.ships) for p in world.planets}


# ============================================================
# AGENT ENTRY POINT
# ============================================================

def agent(obs):
    try:
        # OBSERVE
        world = WorldState(obs)

        # Kaggle normally gives each game a fresh process, but local batch tests
        # reuse the module. Reset if a new episode starts in the same process.
        last_step = _MEMORY.get("last_obs_step", -1)
        if last_step > world.step or (world.step <= 1 and last_step > 1):
            _reset_memory()

        # LEARN (from last turn's commitments vs this turn's reality)
        learn(world, None)
        _MEMORY["last_obs_step"] = world.step

        # Early bailouts.
        if not world.my_planets:
            _log("eliminated")
            return []
        if not world.enemy_planets and not world.neutral_planets:
            _log("sole_survivor")
            return []

        # ORIENT
        ctx = Context(world)

        # DECIDE
        decisions = decide(world, ctx)

        # ACT
        moves = act(world, ctx, decisions)

        if world.step % 25 == 0:
            _log("tick",
                 step=world.step,
                 my_planets=len(world.my_planets),
                 my_ships=sum(p.ships for p in world.my_planets),
                 leader=int(ctx.leader_owner),
                 capture_mult=_MEMORY["capture_buffer_mult"])

        return moves

    except Exception as e:
        # Safety: never crash the Kaggle runner. Fall back to no-op.
        _log("agent_error", error=repr(e))
        return []
