"""
Orbit Wars V10 — OODA-L + Offline RL hybrid agent.

Base: V7 gold-standard spine (duel-aware opening, restrained FFA tempo).

V10 additions:
  - Embedded MLP value estimator (15->32->16->1, trained on 55 replays, 86% CV acc)
    used as a soft position-evaluation advisor in target scoring.
  - Multi-source coordination: allows 2-3 planets to converge on high-value targets.
  - Vulture logic: pounces on planets weakened by inter-opponent fighting.
  - Winner-calibrated parameters: lower reserves during expansion, bigger minimum
    fleets, and more aggressive multi-launch (based on winner vs loser replay analysis).
  - Consolidation posture: brief defensive mode after sharp frontier loss.

Architecture (adapted from the Julia OODA-L framework):
    OBSERVE  -> parse obs into WorldState, cache fleet-landing forecasts.
    ORIENT   -> build Context: threat map, capturable targets, leader, reserves,
                value estimate, vulture opportunities.
    DECIDE   -> priority cascade with multi-source coordination.
    ACT      -> invariant firewall validates every move before emit.
    LEARN    -> within-game 3-strike memory + failure classification.
"""

import base64
import io
import json
import math
import sys
from collections import defaultdict, namedtuple

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False


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
TAG_VULTURE = "VULTURE"
TAG_DUEL_OPEN = "DUEL_OPENING"
TAG_REINFORCE = "REINFORCE"
TAG_SNIPE = "SNIPE_WEAK"
TAG_PRESSURE = "PRESSURE_LEADER"
TAG_EXPAND = "EXPAND_CHEAP"
TAG_STOCKPILE = "STOCKPILE"
TAG_COORDINATED = "COORDINATED"


# ============================================================
# VALUE ESTIMATOR (trained offline on 55 replays, 86% CV acc)
# ============================================================

_WEIGHTS_B64 = "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"

_VALUE_MODEL = None


def _load_value_model():
    global _VALUE_MODEL
    if _VALUE_MODEL is not None:
        return _VALUE_MODEL
    if not _HAS_NUMPY:
        return None
    try:
        raw = base64.b64decode(_WEIGHTS_B64)
        buf = io.BytesIO(raw)
        data = np.load(buf)
        _VALUE_MODEL = {k: data[k] for k in ['W1','b1','W2','b2','W3','b3','mean','std']}
        return _VALUE_MODEL
    except Exception:
        return None


def _evaluate_position(world):
    """Predict win probability [0,1] from current board state."""
    model = _load_value_model()
    if model is None:
        return 0.5
    try:
        player = world.player
        my_ships = my_prod = my_count = 0
        enemy_ships = enemy_prod = enemy_count = 0
        neutral_ships = neutral_count = 0
        nearest_enemy = 999.0
        total_prod = 0
        my_pos, enemy_pos = [], []
        for p in world.planets:
            total_prod += p.production
            if p.owner == player:
                my_ships += p.ships; my_prod += p.production; my_count += 1
                my_pos.append((p.x, p.y))
            elif p.owner == -1:
                neutral_ships += p.ships; neutral_count += 1
            else:
                enemy_ships += p.ships; enemy_prod += p.production; enemy_count += 1
                enemy_pos.append((p.x, p.y))
        if my_pos and enemy_pos:
            for mx, my_ in my_pos:
                for ex, ey in enemy_pos:
                    d = _dist(mx, my_, ex, ey)
                    if d < nearest_enemy:
                        nearest_enemy = d
        my_fships = enemy_fships = my_fcount = enemy_fcount = 0
        for f in world.fleets:
            if f.owner == player:
                my_fships += f.ships; my_fcount += 1
            elif f.owner >= 0:
                enemy_fships += f.ships; enemy_fcount += 1
        total_my = my_ships + my_fships
        total_enemy = enemy_ships + enemy_fships
        features = np.array([[total_my, my_prod, my_count, total_enemy, enemy_prod,
                              enemy_count, neutral_ships, neutral_count, nearest_enemy,
                              my_fcount, enemy_fcount,
                              my_prod / max(1, total_prod),
                              total_my / max(1, total_my + total_enemy),
                              my_count / max(1, my_count + enemy_count + neutral_count),
                              world.step / 500.0]], dtype=np.float32)
        features = (features - model['mean']) / (model['std'] + 1e-8)
        z1 = features @ model['W1'] + model['b1']
        a1 = np.maximum(0, z1)
        z2 = a1 @ model['W2'] + model['b2']
        a2 = np.maximum(0, z2)
        z3 = a2 @ model['W3'] + model['b3']
        return float(1.0 / (1.0 + np.exp(-np.clip(z3, -20, 20)))[0, 0])
    except Exception:
        return 0.5


# ============================================================
# GAME MEMORY
# ============================================================

_MEMORY = {
    "turn": -1,
    "last_obs_step": -1,
    "pending_launches": [],
    "strike_target": defaultdict(int),
    "blacklist": {},
    "capture_buffer_mult": 1.0,
    "path_tolerance": 0.25,
    "tracked_planets": {},
    "last_decisions": [],
    # V10: vulture tracking
    "prev_planet_owners": {},  # planet_id -> owner last turn
    "vulture_targets": {},     # planet_id -> (new_owner, flip_turn, garrison_est)
    # V10: consolidation
    "empire_history": [],
    "consolidate_until": -1,
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
    _MEMORY["prev_planet_owners"] = {}
    _MEMORY["vulture_targets"] = {}
    _MEMORY["empire_history"] = []
    _MEMORY["consolidate_until"] = -1


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
# V10: VULTURE TRACKING
# ============================================================

def _update_vulture_targets(world):
    """Detect planets that just changed hands between enemies -> vulture opportunity."""
    prev = _MEMORY.get("prev_planet_owners", {})
    vulture = _MEMORY["vulture_targets"]
    turn = world.step

    # Expire old vulture targets (stale after 8 turns)
    expired = [pid for pid, (_, ft, _) in vulture.items() if turn - ft > 8]
    for pid in expired:
        del vulture[pid]

    for p in world.planets:
        old_owner = prev.get(p.id, p.owner)
        if old_owner != p.owner and old_owner >= 0 and p.owner >= 0:
            # Planet flipped between two enemies — neither is us
            if old_owner != world.player and p.owner != world.player:
                vulture[p.id] = (p.owner, turn, p.ships)

    # Update prev for next turn
    _MEMORY["prev_planet_owners"] = {p.id: p.owner for p in world.planets}


# ============================================================
# V10: CONSOLIDATION
# ============================================================

def _update_empire_stability(world):
    """Trigger short consolidation after sharp frontier loss."""
    my_planets = len(world.my_planets)
    my_prod = sum(p.production for p in world.my_planets)
    my_total = sum(p.ships for p in world.my_planets)
    my_total += sum(f.ships for f in world.fleets if f.owner == world.player)

    history = _MEMORY["empire_history"]
    history.append((world.step, my_planets, my_prod, my_total))
    cutoff = world.step - 36
    _MEMORY["empire_history"] = [h for h in history if h[0] >= cutoff]

    if world.step < 55 or my_planets <= 0:
        return
    recent = [h for h in _MEMORY["empire_history"] if h[0] >= world.step - 28]
    if not recent:
        return
    peak = max(recent, key=lambda h: (h[1], h[2], h[3]))
    if peak[1] >= 10 and my_planets <= peak[1] - 3:
        until = world.step + 18
        if until > _MEMORY.get("consolidate_until", -1):
            _MEMORY["consolidate_until"] = until
            _log("consolidate_trigger", peak_planets=peak[1], current=my_planets)


# ============================================================
# BITACORA (stderr JSONL; Kaggle captures into agent logs)
# ============================================================

def _log(event, **fields):
    try:
        record = {"turn": _MEMORY.get("turn", -1), "event": event}
        record.update(fields)
        sys.stderr.write(json.dumps(record) + "\n")
    except Exception:
        pass


# ============================================================
# OBSERVE
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

        self.fleet_forecasts = {}
        for fleet in self.fleets:
            hit = _first_hit_for_fleet(fleet, self.planets,
                                       self.angular_velocity, self.comet_paths)
            if hit is not None:
                self.fleet_forecasts[fleet.id] = hit


# ============================================================
# ORIENT
# ============================================================

class Context:
    __slots__ = (
        "world",
        "friendly_to_enemy", "friendly_to_mine",
        "enemy_to_mine", "enemy_eta_to_mine",
        "owner_power", "leader_owner", "active_owners",
        "is_duel", "duel_opening", "ffa_opening", "ffa_behind",
        "surplus_by_id", "reserve_by_id",
        "target_scores", "win_prob", "consolidating",
    )

    def __init__(self, world):
        self.world = world
        self.win_prob = _evaluate_position(world)
        self.consolidating = _MEMORY.get("consolidate_until", -1) > world.step
        self._build_fleet_commitments()
        self._build_power_table()
        self._build_reserves_and_surplus()
        self._score_targets()


    def _build_fleet_commitments(self):
        w = self.world
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
        """Dynamic reserve — V10: winner-calibrated (lower during expansion)."""
        w = self.world
        step = w.step
        incoming = self.enemy_to_mine.get(planet.id, 0)

        # V10: consolidation adds a soft reserve floor
        consolidation_floor = 0
        if self.consolidating and step >= 55 and incoming <= 0:
            if nearest_enemy < 34.0:
                consolidation_floor = planet.production * 2 + 4
            else:
                consolidation_floor = planet.production + 2

        # Very early game: skeleton crew while we expand.
        if step < 12 and incoming <= 0:
            return 1

        if self.duel_opening and incoming <= 0:
            if step < 22:
                return 1
            return max(1, planet.production // 2)

        # V10: FFA opening reserves slightly lowered from V7 but not as aggressive as initial V10
        if self.ffa_opening and incoming <= 0:
            if nearest_enemy < 18.0:
                return max(3, planet.production, consolidation_floor)
            if step < 48:
                return max(1, planet.production // 2, consolidation_floor)
            return max(2, planet.production, consolidation_floor)

        if self.ffa_behind and incoming <= 0 and nearest_enemy >= 28.0:
            return max(3, planet.production + 1, consolidation_floor)

        if len(w.my_planets) <= 2 and step < 60 and incoming <= 0:
            return max(1, planet.production // 2, consolidation_floor)

        if step < 90 and incoming <= 0:
            return max(2, planet.production, consolidation_floor)

        base = max(4, 2 + planet.production)
        if step >= 80:
            base = max(base, 7 + planet.production * 2)
        if step >= 130:
            base = max(base, 10 + planet.production * 3)
        if nearest_enemy < 25.0:
            base += 4
        elif nearest_enemy < 38.0:
            base += 2
        base = max(base, consolidation_floor)

        if incoming <= 0:
            return base

        eta = self.enemy_eta_to_mine.get(planet.id, 12)
        produced = int(max(0, eta - 1) * planet.production)
        return max(base, incoming + 3 - produced)


    def _score_targets(self):
        """Pre-score every non-owned planet as an attack candidate."""
        w = self.world
        self.target_scores = {}
        for t in w.planets:
            if t.owner == w.player:
                continue
            if t.id in _MEMORY["blacklist"] and _MEMORY["blacklist"][t.id] > _MEMORY["turn"]:
                continue
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
            base += max(0.0, 30.0 - t.ships) * 0.9
            if t.id in w.comet_paths:
                remaining = _comet_remaining_turns(t, w.comet_paths)
                base -= 80.0 if remaining < 28 else 18.0

            # V10: vulture bonus — planets recently taken in inter-enemy fighting
            if t.id in _MEMORY["vulture_targets"]:
                _, flip_turn, est_garrison = _MEMORY["vulture_targets"][t.id]
                recency = max(0, 8 - (w.step - flip_turn))
                base += 65.0 * (recency / 8.0)
                if t.ships <= est_garrison + 3:
                    base += 30.0  # garrison hasn't recovered

            # V10: value-based adjustment — when behind, be slightly more aggressive
            if self.win_prob < 0.35 and not self.is_duel:
                if t.owner >= 0 and t.owner != w.player:
                    base += 15.0 * (0.35 - self.win_prob)
            elif self.win_prob > 0.65 and self.consolidating:
                if t.owner == -1:
                    base -= 15.0 * (self.win_prob - 0.65)

            self.target_scores[t.id] = base


    def capture_need(self, target, eta):
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
# DECIDE — priority cascade with multi-source coordination
# ============================================================

PRI_EMERGENCY = 0
PRI_INTERCEPT = 1
PRI_DUEL_OPEN = 2
PRI_VULTURE   = 3   # V10: between DUEL_OPEN and REINFORCE
PRI_REINFORCE = 3
PRI_SNIPE     = 4
PRI_PRESSURE  = 5
PRI_EXPAND    = 6


def _min_launch_size(step):
    # V10: slightly bigger minimum fleets (winners avg 15.6 vs our 11.1)
    if step < 30:
        return 4
    if step < 90:
        return 6
    return 7


def _concentration_minimum(target, step):
    if target.owner == -1:
        return 5 if step < 30 else 7
    return max(9, target.production * 3 + (7 if step >= 80 else 0))


def decide(world, ctx):
    """Priority cascade with V10 multi-source coordination."""
    decisions = []

    # ------- Priority 0: EMERGENCY_DEFEND -------
    threatened = []
    for p in world.my_planets:
        incoming = ctx.enemy_to_mine.get(p.id, 0)
        if incoming <= 0:
            continue
        eta = ctx.enemy_eta_to_mine.get(p.id, 12)
        defenders = p.ships + int(max(0, eta - 1) * p.production)
        defenders += ctx.friendly_to_mine.get(p.id, 0)
        deficit = incoming + 2 - defenders
        if deficit > 0:
            threatened.append((eta, deficit, p))

    threatened.sort(key=lambda t: t[0])

    used_surplus = defaultdict(int)
    for enemy_eta, deficit, target in threatened:
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
            if arrival_eta > enemy_eta + 3:
                continue
            decisions.append((PRI_EMERGENCY, TAG_EMERGENCY, source, target, int(send), angle))
            used_surplus[source.id] += send
            need -= send

    # ------- V10: Multi-source coordinated attacks -------
    coordinated_used = set()
    if not ctx.is_duel and not ctx.ffa_opening and len(world.my_planets) >= 5:
        coord_decisions = _find_coordinated_attacks(world, ctx, used_surplus)
        for cd in coord_decisions:
            decisions.append(cd)
            coordinated_used.add(cd[2].id)  # mark source as used

    # ------- Priority 1+: one action per source -------
    source_best = {}

    for source in world.my_planets:
        if source.id in coordinated_used:
            continue
        surplus = ctx.surplus_by_id.get(source.id, 0) - used_surplus[source.id]
        if surplus < _min_launch_size(world.step):
            continue

        best = _best_move_for_source(source, surplus, world, ctx)
        if best is not None:
            source_best[source.id] = best

    for source_id, move in source_best.items():
        decisions.append(move)

    if not decisions:
        decisions.append((99, TAG_STOCKPILE, None, None, 0, 0.0))

    return decisions


def _find_coordinated_attacks(world, ctx, used_surplus):
    """V10: Find high-value targets where 2-3 planets can converge."""
    step = world.step
    candidates = []

    for target in world.planets:
        if target.owner == world.player or target.owner == -1:
            continue
        score = ctx.target_scores.get(target.id, 0.0)
        if score < 150.0:
            continue  # only coordinate on high-value targets
        if target.id in _MEMORY["blacklist"] and _MEMORY["blacklist"][target.id] > _MEMORY["turn"]:
            continue

        # Find sources that can reach this target
        sources_for_target = []
        for source in world.my_planets:
            surplus = ctx.surplus_by_id.get(source.id, 0) - used_surplus.get(source.id, 0)
            if surplus < _min_launch_size(step) // 2:
                continue
            aim = _aim_solution(source, target, surplus,
                                world.angular_velocity, world.comet_paths,
                                world.planets, _MEMORY["path_tolerance"])
            if aim is None:
                continue
            angle, eta, _, _ = aim
            sources_for_target.append((source, surplus, angle, eta))

        if len(sources_for_target) < 2:
            continue

        # Check if combined force can capture but no single source can
        sources_for_target.sort(key=lambda s: s[3])  # sort by ETA
        total_avail = sum(s[1] for s in sources_for_target[:3])
        avg_eta = sum(s[3] for s in sources_for_target[:3]) / min(3, len(sources_for_target))
        need = ctx.capture_need(target, avg_eta)

        if need <= 0:
            continue
        # Only coordinate if no single source can do it alone but combined can
        max_single = max(s[1] for s in sources_for_target[:3])
        if max_single >= need:
            continue  # single source can handle it, no need to coordinate
        if total_avail < need:
            continue  # even combined can't do it

        candidates.append((score, target, sources_for_target[:3], need))

    # Pick the best coordinated target
    candidates.sort(key=lambda c: -c[0])
    results = []

    for score, target, sources, need in candidates[:1]:  # at most 1 coordinated attack per turn
        remaining_need = need
        for source, surplus, angle, eta in sources:
            if remaining_need <= 0:
                break
            send = min(surplus, remaining_need + 3)  # slight over-send for safety
            send = max(send, _min_launch_size(step) // 2)
            send = min(send, surplus)
            if send < 3:
                continue
            results.append((PRI_VULTURE, TAG_COORDINATED, source, target, int(send), angle))
            used_surplus[source.id] = used_surplus.get(source.id, 0) + send
            remaining_need -= send

    return results


def _best_move_for_source(source, surplus, world, ctx):
    """Find the single best move for this source. V10: includes vulture priority."""
    step = world.step
    best = None
    best_rank = (99, -1e18)

    for target in world.planets:
        if target.owner == world.player or target.id == source.id:
            continue
        if target.id in _MEMORY["blacklist"] and _MEMORY["blacklist"][target.id] > _MEMORY["turn"]:
            continue
        if target.id in world.comet_paths and _comet_remaining_turns(target, world.comet_paths) < 18:
            continue

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
            continue

        send = max(need, _concentration_minimum(target, step))
        buffer = max(2, int(math.ceil(need * (0.15 if target.owner == -1 else 0.25))))
        send = need + buffer if need + buffer > send else send
        send = min(send, surplus)
        if send < _min_launch_size(step) or send < need:
            continue

        # Classify the action — V10: vulture detection
        if target.owner == world.player:
            continue
        if _is_intercept_opportunity(target, eta, ctx, world):
            priority = PRI_INTERCEPT
            tag = TAG_INTERCEPT
        elif target.id in _MEMORY["vulture_targets"] and target.owner >= 0:
            priority = PRI_VULTURE
            tag = TAG_VULTURE
        elif ctx.duel_opening and target.owner == -1:
            priority = PRI_DUEL_OPEN
            tag = TAG_DUEL_OPEN
        elif target.owner == ctx.leader_owner and ctx.leader_owner != -1:
            priority = PRI_PRESSURE
            tag = TAG_PRESSURE
        elif target.owner == -1:
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
        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))
        if ctx.duel_opening and target.owner == -1:
            score = base - send * 1.2 - distance * 1.45 - eta * 2.0
            if target.production >= 3:
                score += 45.0
            if target.ships <= 12:
                score += 28.0
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
            score /= max(1, send)

        rank = (priority, -score)
        if rank < best_rank:
            best_rank = rank
            best = (priority, tag, source, target, int(send), angle)

    return best


def _is_intercept_opportunity(target, my_eta, ctx, world):
    if target.owner != -1:
        return False
    for fleet in world.fleets:
        if fleet.owner == world.player:
            continue
        hit = world.fleet_forecasts.get(fleet.id)
        if hit is None:
            continue
        if hit[0] != target.id:
            continue
        enemy_eta = hit[1]
        if my_eta < enemy_eta + 2:
            return True
    return False


# ============================================================
# ACT — invariant firewall + emit moves
# ============================================================

def act(world, ctx, decisions):
    moves = []
    used_by_source = defaultdict(int)
    non_emergency_launched = set()
    tagged = []

    decisions.sort(key=lambda d: d[0])

    for priority, tag, source, target, ships, angle in decisions:
        if source is None or target is None or ships <= 0:
            continue

        # V10: relax I6 for coordinated attacks — allow multiple launches per source
        # if they target different planets via coordination
        if priority != PRI_EMERGENCY and tag != TAG_COORDINATED:
            if source.id in non_emergency_launched:
                continue

        planet_now = world.planet_by_id.get(source.id)
        if planet_now is None:
            continue
        already_used = used_by_source[source.id]
        actual_available = planet_now.ships - already_used

        if priority == PRI_EMERGENCY:
            max_send = actual_available
        else:
            reserve = ctx.reserve_by_id.get(source.id, 0)
            max_send = max(0, actual_available - reserve)

        min_launch = _min_launch_size(world.step)
        if tag == TAG_COORDINATED:
            min_launch = max(3, min_launch // 2)
        if max_send < min_launch:
            continue
        send = min(ships, max_send)

        if send <= 0 or send > planet_now.ships:
            continue

        aim = _aim_solution(source, target, send,
                            world.angular_velocity, world.comet_paths,
                            world.planets, _MEMORY["path_tolerance"])
        if aim is None:
            continue
        angle, eta, _, _ = aim

        moves.append([int(source.id), float(angle), int(send)])
        used_by_source[source.id] += send
        if priority != PRI_EMERGENCY and tag != TAG_COORDINATED:
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

    _MEMORY["last_decisions"] = list(_MEMORY.get("last_decisions", [])) + tagged
    return moves


# ============================================================
# LEARN — 3-strike within-game adaptation
# ============================================================

def learn(world, ctx):
    turn = world.step
    _MEMORY["turn"] = turn

    expired = [tid for tid, release in _MEMORY["blacklist"].items() if release <= turn]
    for tid in expired:
        del _MEMORY["blacklist"][tid]

    last = _MEMORY.get("last_decisions", [])

    still_pending = []
    for d in last:
        if d["priority"] == PRI_EMERGENCY:
            continue
        if d["eta"] > 1.5:
            d["eta"] -= 1.0
            still_pending.append(d)
            continue

        target_id = d["target"]
        target_now = world.planet_by_id.get(target_id)
        if target_now is None:
            continue
        expected_owner = world.player

        if target_now.owner == expected_owner:
            if _MEMORY["strike_target"][target_id] > 0:
                _MEMORY["strike_target"][target_id] -= 1
            _log("learn_success", target=target_id, tag=d["tag"])
        else:
            _MEMORY["strike_target"][target_id] += 1
            strikes = _MEMORY["strike_target"][target_id]
            _log("learn_miss", target=target_id, tag=d["tag"], strikes=strikes,
                 expected_owner=expected_owner, actual_owner=int(target_now.owner))

            if strikes >= 3:
                _MEMORY["blacklist"][target_id] = turn + 25
                _MEMORY["strike_target"][target_id] = 0
                _MEMORY["capture_buffer_mult"] = min(1.6, _MEMORY["capture_buffer_mult"] + 0.08)
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

        last_step = _MEMORY.get("last_obs_step", -1)
        if last_step > world.step or (world.step <= 1 and last_step > 1):
            _reset_memory()

        # LEARN
        learn(world, None)
        _MEMORY["last_obs_step"] = world.step

        if not world.my_planets:
            _log("eliminated")
            return []
        if not world.enemy_planets and not world.neutral_planets:
            _log("sole_survivor")
            return []

        # V10: vulture and consolidation tracking
        _update_vulture_targets(world)
        _update_empire_stability(world)

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
                 win_prob=round(ctx.win_prob, 3),
                 consolidating=bool(ctx.consolidating),
                 capture_mult=_MEMORY["capture_buffer_mult"])

        return moves

    except Exception as e:
        _log("agent_error", error=repr(e))
        return []
