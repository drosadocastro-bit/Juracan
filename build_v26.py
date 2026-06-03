with open("d:/Juracan/main_v25.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V25 — Back to Basics (V20 + Soft Endgame Deceleration).",
    "Orbit Wars V26 — Hybrid Juggernaut (V7/V20 DNA + Aggregation + Anti-Snipe)."
)
code = code.replace(
    "V25: Scientific Minimalism\n"
    "  1. Based entirely on V20's successful heuristic core.\n"
    "  2. Added Soft Endgame Deceleration: raises defensive reserve in the final\n"
    "     40 turns of an FFA game to save ships, without entirely stopping attacks.",
    "V26: Hybrid Juggernaut\n"
    "  1. V20 core + V25's Soft Endgame Deceleration.\n"
    "  2. Smart Fleet Aggregation: distant targets (>35 dist) require a decisive\n"
    "     force (>= 2x capture need) to launch. Otherwise stockpile.\n"
    "  3. Anti-Snipe Firewall: before launching, check if the source planet\n"
    "     becomes vulnerable to known incoming threats. If yes, hold back."
)

# ═══════════════════════════════════════════════════════════════
# UPGRADE 1: Smart Fleet Aggregation
# ═══════════════════════════════════════════════════════════════
# In _best_move_for_source, after we compute `send`, add a check:
# if the target is far away and we're not sending a decisive force, skip.

OLD_DRIBBLE_CHECK = """        send = min(send, surplus)
        if send < _min_launch_size(step) or send < need:
            continue  # can't afford to capture — don't dribble"""

NEW_DRIBBLE_CHECK = """        send = min(send, surplus)
        if send < _min_launch_size(step) or send < need:
            continue  # can't afford to capture — don't dribble
            
        # V26: Smart Fleet Aggregation — distant targets require decisive force.
        # This prevents launching tiny fleets that arrive slowly and get eaten.
        distance = _dist(source.x, source.y, target.x, target.y)
        if distance > 35.0 and target.owner != -1 and step > 30:
            if send < need * 2:
                continue  # Not enough for a decisive strike — stockpile"""

code = code.replace(OLD_DRIBBLE_CHECK, NEW_DRIBBLE_CHECK)

# ═══════════════════════════════════════════════════════════════
# UPGRADE 2: Anti-Snipe Firewall
# ═══════════════════════════════════════════════════════════════
# In the ACT phase, before finalizing a non-emergency launch, check:
# "If I send these ships, will my source planet survive its incoming threats?"

OLD_ACT_RESERVE = """        # I4: respect reserves (except emergency).
        if priority == PRI_EMERGENCY:
            max_send = actual_available
        else:
            reserve = ctx.reserve_by_id.get(source.id, 0)
            max_send = max(0, actual_available - reserve)"""

NEW_ACT_RESERVE = """        # I4: respect reserves (except emergency).
        if priority == PRI_EMERGENCY:
            max_send = actual_available
        else:
            reserve = ctx.reserve_by_id.get(source.id, 0)
            max_send = max(0, actual_available - reserve)
            
            # V26: Anti-Snipe Firewall — if this source has incoming enemies,
            # ensure we keep enough ships to survive the attack after launching.
            incoming_to_source = ctx.enemy_to_mine.get(source.id, 0)
            if incoming_to_source > 0:
                eta_threat = ctx.enemy_eta_to_mine.get(source.id, 12)
                produced_before_hit = int(max(0, eta_threat - 1) * planet_now.production)
                ships_after_launch = actual_available - max_send
                survival = ships_after_launch + produced_before_hit + ctx.friendly_to_mine.get(source.id, 0)
                if survival < incoming_to_source:
                    # Launching would expose us — reduce max_send to stay safe.
                    safe_send = actual_available - (incoming_to_source - produced_before_hit - ctx.friendly_to_mine.get(source.id, 0))
                    max_send = max(0, min(max_send, safe_send))"""

code = code.replace(OLD_ACT_RESERVE, NEW_ACT_RESERVE)

with open("d:/Juracan/main_v26.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v26.py")
