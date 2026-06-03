"""bot_rusher — aggressive baseline.

Style: send every spare ship at the nearest enemy planet (or richest neutral
if no enemy exists). No reserves, no defense, no coordination. Designed to
punish agents that hoard.
"""
import math


def _f(obs, k, d=None):
    return obs.get(k, d) if isinstance(obs, dict) else getattr(obs, k, d)


def agent(obs):
    player = _f(obs, "player", 0)
    raw_planets = _f(obs, "planets", []) or []
    planets = [tuple(p) for p in raw_planets]
    my_planets = [p for p in planets if int(p[1]) == player]
    enemies = [p for p in planets if int(p[1]) not in (-1, player)]
    neutrals = [p for p in planets if int(p[1]) == -1]
    if not my_planets:
        return []

    moves = []
    # Prefer enemy targets; fall back to richest neutral.
    targets = enemies if enemies else neutrals
    if not targets:
        return moves

    for mine in my_planets:
        garrison = int(mine[5])
        if garrison < 2:
            continue
        if enemies:
            tgt = min(enemies, key=lambda t: math.hypot(float(mine[2]) - float(t[2]),
                                                       float(mine[3]) - float(t[3])))
        else:
            tgt = max(neutrals, key=lambda t: int(t[6]) * 100 - int(t[5]))
        send = max(2, garrison - 1)  # leave 1 ship behind
        angle = math.atan2(float(tgt[3]) - float(mine[3]),
                           float(tgt[2]) - float(mine[2]))
        moves.append([int(mine[0]), angle, send])
    return moves
