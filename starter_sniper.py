import math


def agent(obs):
    moves = []
    player = obs.get("player", 0) if isinstance(obs, dict) else obs.player
    raw_planets = obs.get("planets", []) if isinstance(obs, dict) else obs.planets
    planets = [tuple(p) for p in raw_planets]
    my_planets = [p for p in planets if int(p[1]) == player]
    targets = [p for p in planets if int(p[1]) != player]

    if not targets:
        return moves

    for mine in my_planets:
        nearest = min(targets, key=lambda t: math.hypot(float(mine[2]) - float(t[2]), float(mine[3]) - float(t[3])))
        ships_needed = int(nearest[5]) + 1
        if int(mine[5]) >= ships_needed:
            angle = math.atan2(float(nearest[3]) - float(mine[3]), float(nearest[2]) - float(mine[2]))
            moves.append([int(mine[0]), angle, ships_needed])

    return moves
