with open("d:/Juracan/main_v24.py", encoding="utf-8") as f:
    code = f.read()

# ── Update docstring ──
code = code.replace(
    "Orbit Wars V24 — Pincer Strikes & Endgame Fortress.",
    "Orbit Wars V24.1 — Context-Aware Fortress & Pincer Strikes."
)
code = code.replace(
    "V24: Pincer Strikes & Endgame Fortress:\n"
    "  1. Simultaneous Arrival (Pincer Attacks) — coordinate multi-source fleets\n"
    "     to arrive on the SAME turn so defenders can't produce between waves\n"
    "  2. Endgame Fortress — final 40 turns: stop attacking, consolidate ships\n"
    "  3. Retains all V23.1 Soft Kingmaker + Proactive Defense + Hyperdrive",
    "V24.1: Context-Aware Fortress & Pincer Strikes:\n"
    "  1. Endgame Fortress is now FFA-only. In duels, we NEVER stop attacking.\n"
    "  2. Retains Pincer Attacks (Simultaneous Arrival)\n"
    "  3. Retains V23.1 Soft Kingmaker + Proactive Defense + Hyperdrive"
)

# ── Update Endgame Flag ──
OLD_ENDGAME = "    # V24: Endgame Fortress Mode — last 40 turns, defense only.\n    endgame = world.step >= ENDGAME_CUTOFF"

NEW_ENDGAME = "    # V24.1: Context-Aware Fortress — FFA only.\n    endgame = world.step >= ENDGAME_CUTOFF and not ctx.is_duel"

code = code.replace(OLD_ENDGAME, NEW_ENDGAME)

with open("d:/Juracan/main_v24_1.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v24_1.py")
