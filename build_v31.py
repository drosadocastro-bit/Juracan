"""Build V31 — Vulture Follow-Up.

V31 = V30 spine + convert Anti-Trap aborts on neutral planets into opportunistic
second-wave captures. When an enemy fleet will eat a neutral before us, instead
of cancelling we re-aim a smaller, slower wave to land 3-8 turns AFTER combat,
catching the captor's depleted garrison plus a few turns of production.

Rationale: V30 leaves free EV on the table — every Anti-Trap abort is a planet
that just changed hands at a known, small ship count. A timed follow-up is a
near-cost-free capture that V12 once had and the V19→V30 rewrite dropped.
"""

with open("d:/Juracan/main_v30.py", encoding="utf-8") as f:
    code = f.read()

# ── 1. Update docstring header ──
code = code.replace(
    "Orbit Wars V30 — The Sentinel Heuristic.",
    "Orbit Wars V31 — Vulture Follow-Up."
)
code = code.replace(
    "V30: The Sentinel Heuristic — V27.1 spine + strict Anti-Trap avoidance for neutral Ambush and enemy Reinforcements",
    "V31: Vulture Follow-Up — V30 spine + opportunistic second-wave captures on neutrals an enemy is about to flip"
)

# ── 2. Add TAG_VULTURE constant next to TAG_SNIPE ──
OLD_TAGS = 'TAG_SNIPE = "SNIPE_WEAK"\nTAG_PRESSURE = "PRESSURE_LEADER"'
NEW_TAGS = 'TAG_SNIPE = "SNIPE_WEAK"\nTAG_VULTURE = "SNIPE_VULTURE"\nTAG_PRESSURE = "PRESSURE_LEADER"'
assert OLD_TAGS in code, "TAG_SNIPE block not found"
code = code.replace(OLD_TAGS, NEW_TAGS)

# ── 3. Replace the Anti-Trap abort with Vulture follow-up ──
OLD_ANTITRAP = """        # Anti-Trap: If the target is currently neutral, but an enemy is arriving BEFORE us and will capture it...
        enemy_capturing = False
        if target.owner == -1:
            for fleet in world.fleets:
                if fleet.owner != world.player:
                    hit = world.fleet_forecasts.get(fleet.id)
                    if hit and hit[0] == target.id and hit[1] <= eta: # They arrive before or same turn
                        if fleet.ships > target.ships:
                            enemy_capturing = True
                            break
        if enemy_capturing:
            continue

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
            continue  # can't afford to capture — don't dribble"""

NEW_ANTITRAP = """        # Anti-Trap detection: largest enemy fleet that will flip this neutral
        # before us. We only treat the largest as the captor — smaller enemy
        # fleets arriving alongside would be absorbed in their own combat.
        captor_fleet = None
        captor_eta = None
        if target.owner == -1:
            for fleet in world.fleets:
                if fleet.owner == world.player:
                    continue
                hit = world.fleet_forecasts.get(fleet.id)
                if not (hit and hit[0] == target.id and hit[1] <= eta):
                    continue
                if fleet.ships <= target.ships:
                    continue
                if captor_fleet is None or fleet.ships > captor_fleet.ships:
                    captor_fleet = fleet
                    captor_eta = hit[1]

        vulture_mode = False
        if captor_fleet is not None:
            # Post-combat residual the captor leaves on the planet (becomes the
            # new garrison; owner flips to captor_fleet.owner).
            residual = max(0, captor_fleet.ships - target.ships)
            # Aim for arrival 3 turns after combat — gives combat resolution
            # slack and 2t of production accumulation.
            desired_eta = captor_eta + 3
            growth = int(math.ceil(max(0.0, desired_eta - captor_eta) * target.production))
            vulture_need = residual + growth + 3  # small buffer
            v_send = max(vulture_need, _min_launch_size(step))
            v_send = min(v_send, surplus)
            if v_send >= max(vulture_need, _min_launch_size(step)):
                v_aim = _aim_solution(source, target, v_send,
                                      world.angular_velocity, world.comet_paths,
                                      world.planets, _MEMORY["path_tolerance"])
                if v_aim is not None:
                    v_angle, v_eta, _, _ = v_aim
                    # Must land strictly AFTER combat (>= captor_eta + 2) and
                    # not so late that captor production overwhelms us.
                    if captor_eta + 2 <= v_eta <= captor_eta + 10:
                        # Recompute need against the late arrival (more growth).
                        actual_growth = int(math.ceil(max(0.0, v_eta - captor_eta) * target.production))
                        actual_need = residual + actual_growth + 3
                        if v_send >= actual_need:
                            angle = v_angle
                            eta = v_eta
                            send = int(v_send)
                            need = actual_need
                            vulture_mode = True
            if not vulture_mode:
                continue  # vulture infeasible — fall back to V30 Anti-Trap abort

        if not vulture_mode:
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
                continue  # can't afford to capture — don't dribble"""

assert OLD_ANTITRAP in code, "Anti-Trap block not found"
code = code.replace(OLD_ANTITRAP, NEW_ANTITRAP)

# ── 4. Classify vulture moves as SNIPE priority with strong score bonus ──
OLD_CLASSIFY = """        # Classify the action.
        if target.owner == world.player:
            continue  # already ours
        if _is_intercept_opportunity(target, eta, ctx, world):
            priority = PRI_INTERCEPT
            tag = TAG_INTERCEPT"""

NEW_CLASSIFY = """        # Classify the action.
        if target.owner == world.player:
            continue  # already ours
        if vulture_mode:
            priority = PRI_SNIPE
            tag = TAG_VULTURE
        elif _is_intercept_opportunity(target, eta, ctx, world):
            priority = PRI_INTERCEPT
            tag = TAG_INTERCEPT"""

assert OLD_CLASSIFY in code, "Classify block not found"
code = code.replace(OLD_CLASSIFY, NEW_CLASSIFY)

# ── 5. Vulture score bonus inside the duel/ffa/late-game branches ──
# Apply a flat +35 bonus AFTER score normalization. We tack it on at the end of
# the scoring section by inserting before the V20 simulation gate.
OLD_SCORE_TAIL = """        # V20: Simulate only if this move is a candidate for the top spot.
        if (priority, -score) < best_rank or score > best_rank[1] - 40.0:"""

NEW_SCORE_TAIL = """        # V31: Vulture follow-ups are near-free captures; reward them.
        if vulture_mode:
            score += 35.0

        # V20: Simulate only if this move is a candidate for the top spot.
        if (priority, -score) < best_rank or score > best_rank[1] - 40.0:"""

assert OLD_SCORE_TAIL in code, "Score tail not found"
code = code.replace(OLD_SCORE_TAIL, NEW_SCORE_TAIL)

with open("d:/Juracan/main_v31.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v31.py")
