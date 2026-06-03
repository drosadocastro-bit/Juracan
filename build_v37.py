"""build_v37.py — Duel profitability with correct game-mode detection.

V36 regression (645, bottomed at 504): `ctx.is_duel` is True whenever only
2 active owners remain — including the ENDGAME of a 4-player FFA when the
two weakest players have been eliminated. So V36 applied the late-game
profitability discount exactly during FFA endgame pushes, making it passive
when it should have been finishing opponents.

V37 fix: record initial player count at step 0 in _MEMORY["_init_nplayers"].
Use that permanently for the profitability gate instead of ctx.is_duel.
A game that started with 2 players is always a true duel; a game that started
with 4 players stays FFA logic even when only 2 survive.

One patch in agent() to record the count at step 0.
One patch in _best_move_for_source to gate on _MEMORY["_init_nplayers"] <= 2.
"""

SRC = "main_v27_1.py"
DST = "main_v37.py"

with open(SRC, "r", encoding="utf-8") as f:
    code = f.read()

# ---------- P1: record initial player count in agent() at step 0 ----------
OLD_1 = '''        # ORIENT
        ctx = Context(world)

        # DECIDE'''
NEW_1 = '''        # ORIENT
        ctx = Context(world)

        # V37: Record game type once at step 0 so late-game 2-player endgame
        # in FFA does NOT get mis-classified as a duel (is_duel flips to True
        # whenever only 2 owners remain, even inside a 4P game).
        if world.step == 0:
            _MEMORY["_init_nplayers"] = len(ctx.active_owners)

        # DECIDE'''
assert OLD_1 in code, "P1 anchor not found"
code = code.replace(OLD_1, NEW_1, 1)

# ---------- P2: profitability gate using _init_nplayers ----------
OLD_2 = '''        # Score inside the priority bucket.
        base = ctx.target_scores.get(target.id, 0.0)
        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))'''
NEW_2 = '''        # Score inside the priority bucket.
        base = ctx.target_scores.get(target.id, 0.0)
        # V37: Dynamic profitability in true-duel mode only.
        # Gate on _MEMORY["_init_nplayers"] (recorded at step 0) — NOT
        # ctx.is_duel — so this never fires in the 2P endgame of a 4P FFA.
        if _MEMORY.get("_init_nplayers", 4) <= 2:
            _remaining = max(1, 500 - step)
            base *= max(0.10, (_remaining - eta) / _remaining)
        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))'''
assert OLD_2 in code, "P2 anchor not found"
code = code.replace(OLD_2, NEW_2, 1)

with open(DST, "w", encoding="utf-8") as f:
    f.write(code)

print(f"Wrote {DST} ({len(code):,} bytes)")
print("V37: V27.1 + duel profitability with correct _init_nplayers gate.")
