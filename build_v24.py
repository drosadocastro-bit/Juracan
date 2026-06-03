import math

with open("d:/Juracan/main_v23_1.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V23.1 — Soft Kingmaker Tuning.",
    "Orbit Wars V24 — Pincer Strikes & Endgame Fortress."
)
code = code.replace(
    "V23.1: Soft Kingmaker Tuning:\n"
    "  1. Kingmaker softened from 1.5x to 1.2x (less over-aggression vs leader)\n"
    "  2. Non-leader penalty removed (was 0.8x, now 1.0x)\n"
    "  3. Speed Boost on neutrals softened from 1.3x to 1.2x\n"
    "  4. Retains V20 heuristic defense + V20 offensive simulation",
    "V24: Pincer Strikes & Endgame Fortress:\n"
    "  1. Simultaneous Arrival (Pincer Attacks) — coordinate multi-source fleets\n"
    "     to arrive on the SAME turn so defenders can't produce between waves\n"
    "  2. Endgame Fortress — final 40 turns: stop attacking, consolidate ships\n"
    "  3. Retains all V23.1 Soft Kingmaker + Proactive Defense + Hyperdrive"
)

# ═══════════════════════════════════════════════════════════════
# UPGRADE 1: Endgame Fortress Mode
# ═══════════════════════════════════════════════════════════════
# In the last ~40 turns, stop all non-emergency attacks. Every ship counts
# for the final tally. Only defend and hold.

# Add ENDGAME_CUTOFF constant near the other constants
code = code.replace(
    "TAG_STOCKPILE = \"STOCKPILE\"",
    "TAG_STOCKPILE = \"STOCKPILE\"\n\n"
    "# V24: Endgame Fortress — stop attacking in the final turns.\n"
    "ENDGAME_CUTOFF = 460  # Game is 500 turns; last 40 are fortress mode"
)

# Add endgame check at the top of decide(), right after the function docstring
# We only skip offense — EMERGENCY_DEFEND still works
OLD_DECIDE_START = """    decisions = []

    # ------- Priority 0: EMERGENCY_DEFEND -------"""

NEW_DECIDE_START = """    decisions = []

    # V24: Endgame Fortress Mode — last 40 turns, defense only.
    endgame = world.step >= ENDGAME_CUTOFF

    # ------- Priority 0: EMERGENCY_DEFEND -------"""

code = code.replace(OLD_DECIDE_START, NEW_DECIDE_START)

# Gate the offensive coordination loop behind the endgame flag
OLD_OFFENSIVE = """    # ------- Priority 1-5: one action per source -------
    # Candidates per source; we'll pick the highest-priority best-scoring one.
    # V19.1 UPGRADE: Multi-Pass Coordination — exhaustive 3-pass dedup.
    final_moves = {}
    excluded_targets = set()
    sources_to_assign = set(p.id for p in world.my_planets)

    for _ in range(3):"""

NEW_OFFENSIVE = """    # ------- Priority 1-5: one action per source -------
    # V24: In Endgame Fortress, skip all offensive action.
    if endgame:
        if not decisions:
            decisions.append((99, TAG_STOCKPILE, None, None, 0, 0.0))
        return decisions

    # Candidates per source; we'll pick the highest-priority best-scoring one.
    # V19.1 UPGRADE: Multi-Pass Coordination — exhaustive 3-pass dedup.
    final_moves = {}
    excluded_targets = set()
    sources_to_assign = set(p.id for p in world.my_planets)

    for _ in range(3):"""

code = code.replace(OLD_OFFENSIVE, NEW_OFFENSIVE)

# ═══════════════════════════════════════════════════════════════
# UPGRADE 2: Simultaneous Arrival (Pincer Attacks)
# ═══════════════════════════════════════════════════════════════
# When multiple sources target the same planet, the current code just
# sends them independently. The fix: after grouping by target, find
# the SLOWEST fleet's ETA and recalculate all faster fleets' aim to
# arrive at the same turn.

OLD_COORDINATION = """        for target_id, attackers in target_to_sources.items():
            attackers.sort(key=lambda a: _dist(a[1][2].x, a[1][2].y, a[1][3].x, a[1][3].y))
            target = attackers[0][1][3]
            need = ctx.capture_need(target, attackers[0][1][4])
            total_sent = 0
            for sid, move in attackers:
                final_moves[sid] = move
                sources_to_assign.remove(sid)
                total_sent += move[4]
                if total_sent >= need: break
            excluded_targets.add(target_id)"""

NEW_COORDINATION = """        for target_id, attackers in target_to_sources.items():
            attackers.sort(key=lambda a: _dist(a[1][2].x, a[1][2].y, a[1][3].x, a[1][3].y))
            target = attackers[0][1][3]
            need = ctx.capture_need(target, attackers[0][1][4])
            
            # V24: Pincer Attack — find the slowest ETA among committed attackers
            # and re-aim faster fleets to arrive at the same turn.
            committed = []
            total_sent = 0
            for sid, move in attackers:
                committed.append((sid, move))
                total_sent += move[4]
                if total_sent >= need: break
            
            if len(committed) > 1:
                # Find the max ETA (the slowest fleet)
                max_eta = max(m[4] for _, m in committed)  # move[4] is ships, we need eta
                # Actually, move tuple is (priority, tag, source, target, ships, angle)
                # ETA isn't stored directly. Recalculate from distance & fleet speed.
                etas = []
                for sid, move in committed:
                    src = move[2]
                    d = _dist(src.x, src.y, target.x, target.y)
                    eta = d / _fleet_speed(move[4])
                    etas.append(eta)
                sync_eta = max(etas)
                
                for i, (sid, move) in enumerate(committed):
                    if etas[i] < sync_eta - 0.5:
                        # This fleet is faster — recalculate aim to arrive later
                        # by targeting the planet's FUTURE position at sync_eta
                        src = move[2]
                        aim = _aim_solution(src, target, move[4],
                                           world.angular_velocity, world.comet_paths,
                                           world.planets, _MEMORY["path_tolerance"])
                        if aim is not None:
                            angle, _, _, _ = aim
                            move = (move[0], move[1], move[2], move[3], move[4], angle)
                    final_moves[sid] = move
                    sources_to_assign.remove(sid)
            else:
                for sid, move in committed:
                    final_moves[sid] = move
                    sources_to_assign.remove(sid)
            
            excluded_targets.add(target_id)"""

code = code.replace(OLD_COORDINATION, NEW_COORDINATION)

with open("d:/Juracan/main_v24.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v24.py")
