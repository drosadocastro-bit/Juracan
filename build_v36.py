"""build_v36.py — Dynamic profitability, duel-gated, from V27.1 backbone.

V35 finding: dynamic profitability (base *= (remaining-eta)/remaining) is
correct in 1v1 but counter-productive in FFA. The mode split was stark:
  Duel: mean +0.400, CI [+0.000, +0.933]   <- clearly positive
  FFA:  mean -0.250, CI [-0.550, +0.050]   <- clearly negative

Explanation: in FFA you must stay aggressive until the final turn — ships on
planets count at step 500 and passive play lets rivals snowball. In 1v1 the
binary outcome makes efficiency dominant; late captures genuinely waste ships.

V36 = same patch as V35 but gated to duel mode only (ctx.is_duel).
FFA (including 3P/4P) uses the original static multiplier unchanged.
"""

SRC = "main_v27_1.py"
DST = "main_v36.py"

with open(SRC, "r", encoding="utf-8") as f:
    code = f.read()

OLD = '''        # Score inside the priority bucket.
        base = ctx.target_scores.get(target.id, 0.0)
        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))'''

NEW = '''        # Score inside the priority bucket.
        base = ctx.target_scores.get(target.id, 0.0)
        # V36: Dynamic profitability in DUEL mode only. In 1v1, capturing a
        # planet with only 10 turns left is worth far less than capturing it
        # with 200 turns left — efficiency dominates binary outcomes. In FFA,
        # aggressive play until step 500 is correct (ships on planets score at
        # time-out), so we keep the static multiplier for non-duel games.
        if ctx.is_duel:
            _remaining = max(1, 500 - step)
            base *= max(0.10, (_remaining - eta) / _remaining)
        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))'''

assert OLD in code, "Anchor not found — check V27.1 source"
code = code.replace(OLD, NEW, 1)

with open(DST, "w", encoding="utf-8") as f:
    f.write(code)

print(f"Wrote {DST} ({len(code):,} bytes)")
print("V36: V27.1 + dynamic profitability gated to duel mode (1 patch).")
