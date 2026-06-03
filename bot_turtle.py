"""bot_turtle — defensive accumulator baseline.

Style: hoard ships until garrison >= production * 30, then launch a single
overwhelming strike at the weakest reachable planet. Punishes agents that
spread thin.
"""
import math


def _f(obs, k, d=None):
    return obs.get(k, d) if isinstance(obs, dict) else getattr(obs, k, d)


def agent(obs):
    player = _f(obs, "player", 0)
    raw_planets = _f(obs, "planets", []) or []
    planets = [tuple(p) for p in raw_planets]
    my_planets = [p for p in planets if int(p[1]) == player]
    others = [p for p in planets if int(p[1]) != player]
    if not my_planets or not others:
        return []

    moves = []
    for mine in my_planets:
        garrison = int(mine[5])
        production = int(mine[6])
        threshold = max(30, production * 30)
        if garrison < threshold:
            continue
        # Pick weakest reachable target (ships per distance).
        def score(t):
            d = math.hypot(float(mine[2]) - float(t[2]),
                           float(mine[3]) - float(t[3]))
            return int(t[5]) + d * 0.3
        tgt = min(others, key=score)
        send = garrison - 2
        if send < int(tgt[5]) + 1:
            continue  # not yet strong enough
        angle = math.atan2(float(tgt[3]) - float(mine[3]),
                           float(tgt[2]) - float(mine[2]))
        moves.append([int(mine[0]), angle, send])
    return moves
