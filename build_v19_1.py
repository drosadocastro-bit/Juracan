import re

with open("d:/Juracan/main_v7.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V4 — OODA-L agent.",
    "Orbit Wars V19.1 — V7 Spine + Surgical Vulture + Multi-Pass Coordination."
)
code = code.replace(
    "Patched locally as V7: V5 core restored, with a restrained 4-player tempo\nadjustment that boosts early neutral growth without outranking leader pressure.",
    "V19.1: V7 gold spine with refined surgical upgrades:\n"
    "  1. Multi-Pass Coordination (exhaustive 3-pass dedup)\n"
    "  2. Comet Harvesting (grab long-lived low-garrison comets)\n"
    "  3. Tactical Retreat (evacuate hopeless defenses to save ships)\n"
    "  4. Surgical Vulture (bonus to steal planets enemies are fighting over)"
)

# ═══════════════════════════════════════════════════════════════
# VULTURE LOGIC: Inject arrivals_by_target into Context
# ═══════════════════════════════════════════════════════════════
code = code.replace(
    '        "target_scores",',
    '        "target_scores", "arrivals_by_target",'
)

VULTURE_COMMITMENTS = """        self.arrivals_by_target = defaultdict(set)
        for fleet in w.fleets:
            hit = w.fleet_forecasts.get(fleet.id)
            if hit:
                target_id, eta = hit
                if fleet.owner != w.player:
                    self.arrivals_by_target[target_id].add(fleet.owner)
"""

code = code.replace(
    "    def _build_fleet_commitments(self):\n        w = self.world",
    "    def _build_fleet_commitments(self):\n        w = self.world\n" + VULTURE_COMMITMENTS
)

# ═══════════════════════════════════════════════════════════════
# UPGRADE 1: Multi-Pass Coordination
# ═══════════════════════════════════════════════════════════════
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
            # Keep the attacker with the lowest ETA (fastest arrival)
            best_attacker = min(attackers, key=lambda a: _dist(
                a[1][2].x, a[1][2].y, a[1][3].x, a[1][3].y))
            
            sid, move = best_attacker
            final_moves[sid] = move
            excluded_targets.add(target_id)
            sources_to_assign.remove(sid)

    for source_id, move in final_moves.items():
        decisions.append(move)"""

code = code.replace(OLD_SOURCE_BEST, NEW_SOURCE_BEST)

# Update _best_move_for_source signature
OLD_BEST_MOVE_SIG = "def _best_move_for_source(source, surplus, world, ctx):"
NEW_BEST_MOVE_SIG = "def _best_move_for_source(source, surplus, world, ctx, excluded_targets=None):"
code = code.replace(OLD_BEST_MOVE_SIG, NEW_BEST_MOVE_SIG)

# Add excluded_targets check
OLD_BLACKLIST_CHECK = """        # Respect blacklist from LEARN.
        if target.id in _MEMORY["blacklist"] and _MEMORY["blacklist"][target.id] > _MEMORY["turn"]:
            continue"""
NEW_BLACKLIST_CHECK = """        # Respect blacklist from LEARN.
        if target.id in _MEMORY["blacklist"] and _MEMORY["blacklist"][target.id] > _MEMORY["turn"]:
            continue
        # V19.1: skip targets already claimed by another source.
        if excluded_targets and target.id in excluded_targets:
            continue"""
code = code.replace(OLD_BLACKLIST_CHECK, NEW_BLACKLIST_CHECK)


# ═══════════════════════════════════════════════════════════════
# UPGRADE 2 & 4: Comet Harvesting + Surgical Vulture
# ═══════════════════════════════════════════════════════════════
OLD_COMET = """            # Comet penalty: avoid spending ships on planets about to leave.
            if t.id in w.comet_paths:
                remaining = _comet_remaining_turns(t, w.comet_paths)
                base -= 80.0 if remaining < 28 else 18.0"""

NEW_SCORING = """            # V19.1 UPGRADE 4: Surgical Vulture — bonus to steal planets enemies are fighting over.
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
                        base -= 10.0"""

code = code.replace(OLD_COMET, NEW_SCORING)


# ═══════════════════════════════════════════════════════════════
# UPGRADE 3: Tactical Retreat
# ═══════════════════════════════════════════════════════════════
OLD_EMERGENCY = """    threatened.sort(key=lambda t: t[0])  # soonest first

    used_surplus = defaultdict(int)
    for enemy_eta, deficit, target in threatened:"""

NEW_EMERGENCY = """    threatened.sort(key=lambda t: t[0])  # soonest first

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
            continue"""

code = code.replace(OLD_EMERGENCY, NEW_EMERGENCY)


with open("d:/Juracan/main_v19_1.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v19_1.py")
