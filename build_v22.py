import re

with open("d:/Juracan/main_v21.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V21 — Defensive Simulator Engine.",
    "Orbit Wars V22 — Hyperdrive & Kingmaker Engine."
)
code = code.replace(
    "V21: Defensive Simulator Engine:\n"
    "  1. Defensive Simulator (exact 25-turn lookahead for EMERGENCY_DEFEND)\n"
    "  2. Smart INTERCEPT (ignore doomed enemy attacks on neutrals)\n"
    "  3. Retains all V20 Offensive Simulation and Aggregation",
    "V22: Hyperdrive & Kingmaker Engine:\n"
    "  1. Fleet Speed Boosting (over-commit surplus to increase flight speed)\n"
    "  2. Anti-Leader Kingmaker Logic (1.5x score multiplier against game leader)\n"
    "  3. Retains all V21 Defensive Simulation"
)

# ═══════════════════════════════════════════════════════════════
# UPGRADE 1: Anti-Leader Kingmaker Logic
# ═══════════════════════════════════════════════════════════════

code = code.replace(
    '            self.target_scores[t.id] = base',
    '            # V22: Anti-Leader Kingmaker Logic\n'
    '            if t.owner == self.leader_owner and self.leader_owner != -1:\n'
    '                base *= 1.5\n'
    '            elif t.owner not in (-1, w.player):\n'
    '                base *= 0.8\n'
    '            self.target_scores[t.id] = base'
)

# ═══════════════════════════════════════════════════════════════
# UPGRADE 2: Fleet Speed Boosting & Recalculation
# ═══════════════════════════════════════════════════════════════

OLD_SEND_LOGIC = """        send = min(send, surplus)
        if send < _min_launch_size(step) or send < need:
            continue  # can't afford to capture — don't dribble"""

NEW_SEND_LOGIC = """        send = min(send, surplus)
        if send < _min_launch_size(step) or send < need:
            continue  # can't afford to capture — don't dribble
            
        # V22: Fleet Speed Boosting (Hyperdrive)
        if surplus > send:
            boost_multiplier = 1.3 if (target.owner == -1) else 1.15
            boosted_send = int(math.ceil(send * boost_multiplier))
            send = min(boosted_send, surplus)
            
            # Recalculate exact ETA based on the new, faster fleet size
            aim = _aim_solution(source, target, send,
                                world.angular_velocity, world.comet_paths,
                                world.planets, _MEMORY["path_tolerance"])
            if aim is None:
                continue
            angle, eta, _, _ = aim"""

code = code.replace(OLD_SEND_LOGIC, NEW_SEND_LOGIC)

with open("d:/Juracan/main_v22.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v22.py")
