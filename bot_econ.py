"""bot_econ — pure economic expansion baseline.

Style: only captures neutrals, never engages enemies. Prefers high-production
low-garrison planets. Picks targets by production/(ships+1) efficiency.
Demonstrates a player that ignores combat entirely — punishes agents that
over-invest in defense.
"""
import math


def _f(obs, k, d=None):
    return obs.get(k, d) if isinstance(obs, dict) else getattr(obs, k, d)


def agent(obs):
    player = _f(obs, "player", 0)
    raw_planets = _f(obs, "planets", []) or []
    planets = [tuple(p) for p in raw_planets]
    my_planets = [p for p in planets if int(p[1]) == player]
    neutrals = [p for p in planets if int(p[1]) == -1]
    if not my_planets or not neutrals:
        return []

    moves = []
    for mine in my_planets:
        garrison = int(mine[5])
        if garrison < 4:
            continue
        affordable = [t for t in neutrals if int(t[5]) + 1 <= garrison - 1]
        if not affordable:
            continue
        # Highest production per ship invested, lightly discounted by distance.
        def efficiency(t):
            ships = int(t[5])
            prod = int(t[6])
            d = math.hypot(float(mine[2]) - float(t[2]),
                           float(mine[3]) - float(t[3]))
            return prod / (ships + 1 + d * 0.02)
        tgt = max(affordable, key=efficiency)
        need = int(tgt[5]) + 1
        send = min(garrison - 1, max(need, 4))
        angle = math.atan2(float(tgt[3]) - float(mine[3]),
                           float(tgt[2]) - float(mine[2]))
        moves.append([int(mine[0]), angle, send])
    return moves
