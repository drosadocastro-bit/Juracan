"""
Build main_v19.py — V7 spine with three surgical upgrades:
  1. Multi-Source Coordination (dedup attacks on same target)
  2. Comet Harvesting (bonus long-lived low-garrison comets)
  3. Tactical Retreat (evacuate hopeless defenses)
"""

with open("d:/Juracan/main_v7.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V4 — OODA-L agent.",
    "Orbit Wars V19 — V7 Spine + Surgical Upgrades."
)
code = code.replace(
    "Patched locally as V7: V5 core restored, with a restrained 4-player tempo\nadjustment that boosts early neutral growth without outranking leader pressure.",
    "V19: V7 gold spine with three surgical upgrades:\n"
    "  1. Multi-Source Coordination (dedup overkill on same target)\n"
    "  2. Comet Harvesting (grab long-lived low-garrison comets)\n"
    "  3. Tactical Retreat (evacuate hopeless defenses to save ships)"
)

# ═══════════════════════════════════════════════════════════════
# UPGRADE 1: Multi-Source Coordination
# ═══════════════════════════════════════════════════════════════
# Replace the simple source_best loop with a deduplication pass.

OLD_SOURCE_BEST = """    # ------- Priority 1-5: one action per source -------
    # Candidates per source; we'll pick the highest-priority best-scoring one.
    source_best = {}

    for source in world.my_planets:
        surplus = ctx.surplus_by_id.get(source.id, 0) - used_surplus[source.id]
        if surplus < _min_launch_size(world.step):
            continue

        best = _best_move_for_source(source, surplus, world, ctx)
        if best is not None:
            source_best[source.id] = best

    for source_id, move in source_best.items():
        decisions.append(move)"""

NEW_SOURCE_BEST = """    # ------- Priority 1-5: one action per source -------
    # Candidates per source; we'll pick the highest-priority best-scoring one.
    # V19 UPGRADE 1: Multi-Source Coordination — dedup attacks on the same target.
    source_best = {}
    excluded_targets = set()

    for source in world.my_planets:
        surplus = ctx.surplus_by_id.get(source.id, 0) - used_surplus[source.id]
        if surplus < _min_launch_size(world.step):
            continue

        best = _best_move_for_source(source, surplus, world, ctx, excluded_targets)
        if best is not None:
            source_best[source.id] = best

    # Dedup: if multiple sources target the same planet, keep the best one.
    target_to_sources = defaultdict(list)
    for source_id, move in source_best.items():
        target_id = move[3].id  # move = (pri, tag, source, target, ships, angle)
        target_to_sources[target_id].append((source_id, move))

    final_moves = {}
    freed_sources = []
    for target_id, attackers in target_to_sources.items():
        if len(attackers) <= 1:
            for sid, move in attackers:
                final_moves[sid] = move
            continue
        # Keep the attacker with the lowest ETA (fastest arrival)
        best_attacker = min(attackers, key=lambda a: _dist(
            a[1][2].x, a[1][2].y, a[1][3].x, a[1][3].y))
        final_moves[best_attacker[0]] = best_attacker[1]
        excluded_targets.add(target_id)
        for sid, move in attackers:
            if sid != best_attacker[0]:
                freed_sources.append(sid)

    # Re-route freed sources to their second-best target
    for source_id in freed_sources:
        source = world.planet_by_id.get(source_id)
        if source is None:
            continue
        surplus = ctx.surplus_by_id.get(source_id, 0) - used_surplus[source_id]
        if surplus < _min_launch_size(world.step):
            continue
        best = _best_move_for_source(source, surplus, world, ctx, excluded_targets)
        if best is not None:
            final_moves[source_id] = best

    for source_id, move in final_moves.items():
        decisions.append(move)"""

code = code.replace(OLD_SOURCE_BEST, NEW_SOURCE_BEST)

# Update _best_move_for_source signature to accept excluded_targets
OLD_BEST_MOVE_SIG = "def _best_move_for_source(source, surplus, world, ctx):"
NEW_BEST_MOVE_SIG = "def _best_move_for_source(source, surplus, world, ctx, excluded_targets=None):"
code = code.replace(OLD_BEST_MOVE_SIG, NEW_BEST_MOVE_SIG)

# Add excluded_targets check inside _best_move_for_source
OLD_BLACKLIST_CHECK = """        # Respect blacklist from LEARN.
        if target.id in _MEMORY["blacklist"] and _MEMORY["blacklist"][target.id] > _MEMORY["turn"]:
            continue"""
NEW_BLACKLIST_CHECK = """        # Respect blacklist from LEARN.
        if target.id in _MEMORY["blacklist"] and _MEMORY["blacklist"][target.id] > _MEMORY["turn"]:
            continue
        # V19: skip targets already claimed by another source in the coordination pass.
        if excluded_targets and target.id in excluded_targets:
            continue"""
code = code.replace(OLD_BLACKLIST_CHECK, NEW_BLACKLIST_CHECK)


# ═══════════════════════════════════════════════════════════════
# UPGRADE 2: Comet Harvesting
# ═══════════════════════════════════════════════════════════════
# Replace the blanket comet penalty with a conditional.

OLD_COMET = """            # Comet penalty: avoid spending ships on planets about to leave.
            if t.id in w.comet_paths:
                remaining = _comet_remaining_turns(t, w.comet_paths)
                base -= 80.0 if remaining < 28 else 18.0"""

NEW_COMET = """            # V19 UPGRADE 2: Comet Harvesting — grab long-lived low-garrison comets.
            if t.id in w.comet_paths:
                remaining = _comet_remaining_turns(t, w.comet_paths)
                if remaining < 15:
                    base -= 120.0  # Too short-lived, heavy penalty
                elif remaining < 28:
                    if t.production >= 2 and t.ships <= 6:
                        base += 15.0  # Quick grab opportunity (conservative)
                    else:
                        base -= 50.0  # Not worth it
                else:
                    # Long-lived comet: slight bonus, don't over-prioritize
                    if t.production >= 3 and t.ships <= 8:
                        base += 10.0
                    else:
                        base -= 10.0"""

code = code.replace(OLD_COMET, NEW_COMET)


# ═══════════════════════════════════════════════════════════════
# UPGRADE 3: Tactical Retreat
# ═══════════════════════════════════════════════════════════════
# Before rallying supporters, check if defense is hopeless.

OLD_EMERGENCY = """    threatened.sort(key=lambda t: t[0])  # soonest first

    used_surplus = defaultdict(int)
    for enemy_eta, deficit, target in threatened:"""

NEW_EMERGENCY = """    threatened.sort(key=lambda t: t[0])  # soonest first

    used_surplus = defaultdict(int)

    # V19 UPGRADE 3: Tactical Retreat — evacuate hopeless defenses.
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
            continue"""

code = code.replace(OLD_EMERGENCY, NEW_EMERGENCY)


with open("d:/Juracan/main_v19.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v19.py")
