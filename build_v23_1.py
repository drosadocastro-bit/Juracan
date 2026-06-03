with open("d:/Juracan/main_v23.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V23 — Proactive Defense (V20 Heuristic Restored).",
    "Orbit Wars V23.1 — Soft Kingmaker Tuning."
)
code = code.replace(
    "V23: Proactive Defense:\n"
    "  1. Restores V20's paranoid heuristic defense (sees ALL threats, not just 25-turn window)\n"
    "  2. Keeps V22 Fleet Speed Boosting + Kingmaker\n"
    "  3. Keeps V20 Offensive Simulation + Smart INTERCEPT",
    "V23.1: Soft Kingmaker Tuning:\n"
    "  1. Kingmaker softened from 1.5x to 1.2x (less over-aggression vs leader)\n"
    "  2. Non-leader penalty removed (was 0.8x, now 1.0x)\n"
    "  3. Speed Boost on neutrals softened from 1.3x to 1.2x\n"
    "  4. Retains V20 heuristic defense + V20 offensive simulation"
)

# ── Soften Kingmaker from 1.5x to 1.2x and remove the 0.8x non-leader penalty ──
code = code.replace(
    "            # V22: Anti-Leader Kingmaker Logic\n"
    "            if t.owner == self.leader_owner and self.leader_owner != -1:\n"
    "                base *= 1.5\n"
    "            elif t.owner not in (-1, w.player):\n"
    "                base *= 0.8",
    "            # V23.1: Soft Kingmaker (1.2x leader, no non-leader penalty)\n"
    "            if t.owner == self.leader_owner and self.leader_owner != -1:\n"
    "                base *= 1.2"
)

# ── Soften neutral speed boost from 1.3x to 1.2x ──
code = code.replace(
    "            boost_multiplier = 1.3 if (target.owner == -1) else 1.15",
    "            boost_multiplier = 1.2 if (target.owner == -1) else 1.12"
)

with open("d:/Juracan/main_v23_1.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v23_1.py")
