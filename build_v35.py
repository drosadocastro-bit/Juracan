"""build_v35.py — Dynamic profitability scaling from V27.1 backbone.

Hypothesis (single structural change):
  V27.1 scores targets with a STATIC production multiplier:
      base = production * 92.0   (neutral)
      base = production * 118.0  (enemy)

  This treats a planet captured at turn 10 with 490 turns left to farm
  identically to one captured at turn 490 with 10 turns left — economically
  wrong. The top public agent (LB-1224, score 1224) uses:
      value = production * max(1, remaining_turns - arrival_turns)

  V35 applies the same principle at the decision layer (where ETA is known):
      base *= max(0.10, (remaining - eta) / remaining)

  Effect by game phase:
    - Early (turn 0, eta=10): factor=0.98 — nearly unchanged.
    - Mid  (turn 200, eta=25): factor=0.92 — mild discount.
    - Late (turn 350, eta=40): factor=0.73 — meaningful, prefers nearby targets.
    - Endgame (turn 430, eta=40): factor=0.43 — heavy, only cheap/close targets.
    - Final (turn 470, eta=25): factor=0.17 — almost nothing worth attacking.

  This naturally produces:
    1. Preference for short-ETA captures in all phases.
    2. Aggressive mid-game (still worth expanding).
    3. Defensive late-game (conserve ships, stop overextending).

  No other behavior changes. One line of code + a comment.
"""

SRC = "main_v27_1.py"
DST = "main_v35.py"

with open(SRC, "r", encoding="utf-8") as f:
    code = f.read()

# Single patch: after `base = ctx.target_scores.get(target.id, 0.0)`,
# apply the dynamic profitability discount before scoring.
OLD = '''        # Score inside the priority bucket.
        base = ctx.target_scores.get(target.id, 0.0)
        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))'''

NEW = '''        # Score inside the priority bucket.
        base = ctx.target_scores.get(target.id, 0.0)
        # V35: Dynamic profitability. Structurally mirrors LB-1224's
        # `value = production * (remaining - arrival_turns)`. A capture that
        # arrives when only 10 turns remain is worth 50x less than one that
        # arrives with 500 turns left. Floor at 0.10 to preserve emergency/
        # intercept signals even in the last few turns.
        _remaining = max(1, 500 - step)
        base *= max(0.10, (_remaining - eta) / _remaining)
        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))'''

assert OLD in code, "Anchor not found — check V27.1 source"
code = code.replace(OLD, NEW, 1)

with open(DST, "w", encoding="utf-8") as f:
    f.write(code)

print(f"Wrote {DST} ({len(code):,} bytes)")
print("V35: V27.1 + dynamic profitability (1 patch, ~5 lines).")
