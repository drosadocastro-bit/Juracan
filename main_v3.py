"""
Orbit Wars heuristic agent.

The policy is intentionally lightweight enough for Kaggle's one second turn
budget: keep small local reserves, reinforce planets with incoming enemy fleets,
expand into high-value neutral planets, and attack weak enemy planets when the
route is clear.
"""

import math
from collections import defaultdict, namedtuple


Planet = namedtuple("Planet", "id owner x y radius ships production")
Fleet = namedtuple("Fleet", "id owner x y angle from_planet_id ships")

CENTER_X = 50.0
CENTER_Y = 50.0
BOARD_SIZE = 100.0
SUN_RADIUS = 10.0
ROTATION_LIMIT = 50.0
MAX_SPEED = 6.0
RAY_EPS = 1e-9


def _obs_get(obs, key, default=None):
    if isinstance(obs, dict):
        return obs.get(key, default)
    return getattr(obs, key, default)


def _as_planets(raw_planets):
    return [Planet(int(p[0]), int(p[1]), float(p[2]), float(p[3]),
                   float(p[4]), int(p[5]), int(p[6])) for p in raw_planets]


def _as_fleets(raw_fleets):
    return [Fleet(int(f[0]), int(f[1]), float(f[2]), float(f[3]),
                  float(f[4]), int(f[5]), int(f[6])) for f in raw_fleets]


def _dist(a_x, a_y, b_x, b_y):
    return math.hypot(a_x - b_x, a_y - b_y)


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
    comet_data = comet_paths.get(planet.id)
    if not comet_data:
        return 999
    path, index = comet_data
    return max(0, len(path) - int(index) - 1) if path else 0


def _line_hits_sun(ax, ay, bx, by):
    limit = SUN_RADIUS + 0.35
    return _segment_circle_distance_sq(ax, ay, bx, by, CENTER_X, CENTER_Y) <= limit * limit


def _path_is_clear(source, target, tx, ty, planets):
    if _line_hits_sun(source.x, source.y, tx, ty):
        return False

    full_dx = tx - source.x
    full_dy = ty - source.y
    full_len_sq = full_dx * full_dx + full_dy * full_dy
    if full_len_sq <= RAY_EPS:
        return False

    for p in planets:
        if p.id == source.id or p.id == target.id:
            continue

        along = ((p.x - source.x) * full_dx + (p.y - source.y) * full_dy) / full_len_sq
        if along <= 0.03 or along >= 0.97:
            continue

        radius = p.radius + 0.25
        if _segment_circle_distance_sq(source.x, source.y, tx, ty, p.x, p.y) <= radius * radius:
            return False

    return True


def _aim_solution(source, target, ships, angular_velocity, comet_paths, planets):
    eta = _dist(source.x, source.y, target.x, target.y) / _fleet_speed(ships)
    tx, ty = target.x, target.y

    for _ in range(4):
        tx, ty = _predict_position(target, eta, angular_velocity, comet_paths)
        eta = _dist(source.x, source.y, tx, ty) / _fleet_speed(ships)

    if not _path_is_clear(source, target, tx, ty, planets):
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
        best_distance = float("inf")
        for p in planets:
            if p.id == fleet.from_planet_id:
                continue

            tx, ty = _predict_position(p, turn, angular_velocity, comet_paths)
            radius = p.radius + 0.35
            distance_sq = _segment_circle_distance_sq(px, py, nx, ny, tx, ty)
            if distance_sq <= radius * radius:
                distance = _dist(px, py, tx, ty)
                if distance < best_distance:
                    best = p
                    best_distance = distance

        if best is not None:
            return best.id, turn

        px, py = nx, ny

    return None


def _fleet_commitments(fleets, planets, player, angular_velocity, comet_paths):
    friendly_to_enemy = defaultdict(int)
    friendly_to_mine = defaultdict(int)
    enemy_to_mine = defaultdict(int)
    enemy_eta = {}

    planet_by_id = {p.id: p for p in planets}
    for fleet in fleets:
        hit = _first_hit_for_fleet(fleet, planets, angular_velocity, comet_paths)
        if hit is None:
            continue

        target_id, eta = hit
        target = planet_by_id.get(target_id)
        if target is None:
            continue

        if fleet.owner == player:
            if target.owner == player:
                friendly_to_mine[target_id] += fleet.ships
            else:
                friendly_to_enemy[target_id] += fleet.ships
        elif target.owner == player:
            enemy_to_mine[target_id] += fleet.ships
            enemy_eta[target_id] = min(enemy_eta.get(target_id, eta), eta)

    return friendly_to_enemy, friendly_to_mine, enemy_to_mine, enemy_eta


def _reserve_for(planet, enemy_to_mine, enemy_eta, step, my_planet_count, nearest_enemy):
    if step < 12 and enemy_to_mine.get(planet.id, 0) <= 0:
        return 1

    if my_planet_count <= 2 and step < 60 and enemy_to_mine.get(planet.id, 0) <= 0:
        return max(1, planet.production // 2)

    if step < 90 and enemy_to_mine.get(planet.id, 0) <= 0:
        return max(2, planet.production)

    base = max(4, 2 + planet.production)
    if step >= 80:
        base = max(base, 7 + planet.production * 2)
    if step >= 130:
        base = max(base, 10 + planet.production * 3)
    if nearest_enemy < 25.0:
        base += 4
    elif nearest_enemy < 38.0:
        base += 2

    incoming = enemy_to_mine.get(planet.id, 0)
    if incoming <= 0:
        return base

    eta = enemy_eta.get(planet.id, 12)
    produced = int(max(0, eta - 1) * planet.production)
    return max(base, incoming + 3 - produced)


def _capture_need(target, eta, player):
    if target.owner == -1:
        return target.ships + 1
    if target.owner == player:
        return 0

    growth = int(math.ceil(max(0.0, eta - 1.0) * target.production))
    return target.ships + growth + 1


def _target_score(source, target, need, eta, player, comet_paths, leader_owner, owner_power):
    distance = max(1.0, _dist(source.x, source.y, target.x, target.y))
    production_value = target.production * (92.0 if target.owner == -1 else 118.0)
    ship_penalty = need * (2.35 if target.owner == -1 else 2.05)
    distance_penalty = distance * 0.55 + eta * 1.4
    comet_penalty = 0.0

    if target.id in comet_paths:
        remaining = _comet_remaining_turns(target, comet_paths)
        comet_penalty = 80.0 if remaining < eta + 18.0 else 18.0

    enemy_bonus = 28.0 if target.owner not in (-1, player) else 0.0
    if target.owner == leader_owner:
        enemy_bonus += 72.0
    elif target.owner not in (-1, player):
        enemy_bonus += min(42.0, owner_power.get(target.owner, 0.0) / 45.0)

    weak_bonus = max(0.0, 30.0 - target.ships) * 0.9
    return production_value + enemy_bonus + weak_bonus - ship_penalty - distance_penalty - comet_penalty


def _best_attack_from(source, surplus, targets, planets, player, angular_velocity,
                      comet_paths, friendly_to_enemy, committed, step, leader_owner, owner_power):
    best = None
    best_score = -1e18

    for target in targets:
        if target.id == source.id or target.owner == player:
            continue

        if target.id in comet_paths and _comet_remaining_turns(target, comet_paths) < 20:
            continue

        probe_ships = max(1, min(surplus, target.ships + 8))
        aim = _aim_solution(source, target, probe_ships, angular_velocity, comet_paths, planets)
        if aim is None:
            continue

        _, eta, _, _ = aim
        need = _capture_need(target, eta, player)
        need -= friendly_to_enemy.get(target.id, 0)
        need -= committed.get(target.id, 0)
        if need <= 0:
            continue

        buffer = max(2, int(math.ceil(need * (0.12 if target.owner == -1 else 0.20))))
        send = need + buffer
        if step >= 80:
            minimum = 6 if target.owner == -1 else max(10, target.production * 4)
            send = max(send, min(surplus, minimum))
        if send > surplus:
            continue

        aim = _aim_solution(source, target, send, angular_velocity, comet_paths, planets)
        if aim is None:
            continue

        angle, eta, _, _ = aim
        need = _capture_need(target, eta, player)
        need -= friendly_to_enemy.get(target.id, 0)
        need -= committed.get(target.id, 0)
        if need <= 0:
            continue

        buffer = max(2, int(math.ceil(need * (0.12 if target.owner == -1 else 0.20))))
        send = min(surplus, need + buffer)
        if step >= 80:
            minimum = 6 if target.owner == -1 else max(10, target.production * 4)
            send = max(send, min(surplus, minimum))
        if send <= 0:
            continue

        score = _target_score(source, target, need, eta, player, comet_paths, leader_owner, owner_power)
        score /= max(1, send)

        if score > best_score:
            best_score = score
            best = target, angle, send, score

    if best is None or best_score < -11.0:
        return None
    return best


def _fallback_attack_from(source, surplus, targets, planets, player, angular_velocity,
                          comet_paths, friendly_to_enemy, committed, step, leader_owner, owner_power):
    candidates = []
    for target in targets:
        if target.id == source.id or target.owner == player:
            continue
        if target.id in comet_paths and _comet_remaining_turns(target, comet_paths) < 18:
            continue

        probe_ships = max(1, min(surplus, target.ships + target.production + 8))
        aim = _aim_solution(source, target, probe_ships, angular_velocity, comet_paths, planets)
        if aim is None:
            continue

        angle, eta, _, _ = aim
        need = _capture_need(target, eta, player)
        need -= friendly_to_enemy.get(target.id, 0)
        need -= committed.get(target.id, 0)
        if need <= 0 or need > surplus:
            continue

        distance = _dist(source.x, source.y, target.x, target.y)
        owner_bias = 0.0 if target.owner == -1 else 18.0
        if target.owner == leader_owner:
            owner_bias += 64.0
        elif target.owner not in (-1, player):
            owner_bias += min(36.0, owner_power.get(target.owner, 0.0) / 55.0)

        payback = target.production * 75.0 + owner_bias - need * 1.35 - distance * 0.65 - eta * 1.2
        send = min(surplus, max(need + 1, int(math.ceil(need * 1.18))))
        if step >= 80:
            minimum = 6 if target.owner == -1 else max(10, target.production * 4)
            send = max(send, min(surplus, minimum))
        candidates.append((payback / max(1, send), target, angle, send))

    if not candidates:
        return None

    candidates.sort(reverse=True, key=lambda item: item[0])
    score, target, angle, send = candidates[0]
    if score < -18.0:
        return None
    return target, angle, int(send), score


def _reinforce_threats(my_planets, planets, player, angular_velocity, comet_paths,
                       surplus_by_id, friendly_to_mine, enemy_to_mine, enemy_eta):
    moves = []

    threatened = []
    for target in my_planets:
        incoming = enemy_to_mine.get(target.id, 0)
        if incoming <= 0:
            continue
        eta = enemy_eta.get(target.id, 12)
        projected = target.ships + int(max(0, eta - 1) * target.production)
        projected += friendly_to_mine.get(target.id, 0)
        need = incoming + 4 - projected
        if need > 0:
            threatened.append((eta, need, target))

    threatened.sort(key=lambda item: item[0])
    for _, need, target in threatened:
        supporters = sorted(
            (p for p in my_planets if p.id != target.id and surplus_by_id.get(p.id, 0) > 0),
            key=lambda p: _dist(p.x, p.y, target.x, target.y),
        )

        for source in supporters:
            if need <= 0:
                break
            available = surplus_by_id.get(source.id, 0)
            send = min(available, need)
            if send <= 0:
                continue

            aim = _aim_solution(source, target, send, angular_velocity, comet_paths, planets)
            if aim is None:
                continue

            angle, _, _, _ = aim
            moves.append([source.id, angle, int(send)])
            surplus_by_id[source.id] -= send
            need -= send

    return moves


def agent(obs):
    player = int(_obs_get(obs, "player", 0) or 0)
    step = int(_obs_get(obs, "step", 0) or 0)
    angular_velocity = float(_obs_get(obs, "angular_velocity", 0.0) or 0.0)
    planets = _as_planets(_obs_get(obs, "planets", []) or [])
    fleets = _as_fleets(_obs_get(obs, "fleets", []) or [])
    comet_paths = _build_comet_paths(obs)

    my_planets = [p for p in planets if p.owner == player]
    if not my_planets:
        return []

    targets = [p for p in planets if p.owner != player]
    if not targets:
        return []

    owner_power = defaultdict(float)
    for p in planets:
        if p.owner >= 0:
            owner_power[p.owner] += p.ships + p.production * 18.0
    for f in fleets:
        if f.owner >= 0:
            owner_power[f.owner] += f.ships

    enemy_owners = [owner for owner in owner_power if owner != player]
    leader_owner = max(enemy_owners, key=lambda owner: owner_power[owner]) if enemy_owners else -1

    friendly_to_enemy, friendly_to_mine, enemy_to_mine, enemy_eta = _fleet_commitments(
        fleets, planets, player, angular_velocity, comet_paths
    )

    surplus_by_id = {}
    for p in my_planets:
        nearest_enemy = min(
            (_dist(p.x, p.y, enemy.x, enemy.y) for enemy in planets if enemy.owner not in (-1, player)),
            default=999.0,
        )
        reserve = _reserve_for(p, enemy_to_mine, enemy_eta, step, len(my_planets), nearest_enemy)
        surplus_by_id[p.id] = max(0, p.ships - reserve)

    moves = _reinforce_threats(
        my_planets, planets, player, angular_velocity, comet_paths, surplus_by_id,
        friendly_to_mine, enemy_to_mine, enemy_eta
    )

    committed = defaultdict(int)
    sources = sorted(my_planets, key=lambda p: surplus_by_id.get(p.id, 0), reverse=True)

    for source in sources:
        if len(moves) >= 24:
            break

        launches_from_source = 0
        max_launches = 2 if step < 80 else 1
        while len(moves) < 24 and launches_from_source < max_launches:
            surplus = surplus_by_id.get(source.id, 0)
            if surplus <= 0:
                break

            attack = _best_attack_from(
                source, surplus, targets, planets, player, angular_velocity,
                comet_paths, friendly_to_enemy, committed, step, leader_owner, owner_power
            )
            if attack is None:
                attack = _fallback_attack_from(
                    source, surplus, targets, planets, player, angular_velocity,
                    comet_paths, friendly_to_enemy, committed, step, leader_owner, owner_power
                )
            if attack is None:
                break

            target, angle, send, _ = attack
            send = int(max(1, min(send, surplus_by_id[source.id])))
            if send <= 0:
                break

            moves.append([source.id, angle, send])
            surplus_by_id[source.id] -= send
            committed[target.id] += send
            launches_from_source += 1

    return moves
