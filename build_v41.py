"""
Build V41: The Optimized Juggernaut synthesis.
"""

import pathlib
import sys

SRC = pathlib.Path("main_v39.py")
DST = pathlib.Path("main_v41.py")

if not SRC.exists():
    print(f"Error: {SRC} not found in current directory.")
    sys.exit(1)

src = SRC.read_text(encoding="utf-8")

# ── Update Docstrings & Title ──
src = src.replace(
    'Orbit Wars V39 — The Heuristic Juggernaut.',
    'Orbit Wars V41 — The Optimized Juggernaut.'
)

# ── Patch 1: Remove Vulture/Crash/Elimination from global _score_targets ──
P1_OLD = """            if t.owner == self.leader_owner:
                base += 72.0
            elif (not self.ffa_opening) and self.weakest_enemy_owner >= 0 and t.owner == self.weakest_enemy_owner:
                base += 160.0  # Elimination drive: focus-fire to remove weakest player (FFA, post-opening)
            elif t.owner not in (-1, w.player):
                base += min(42.0, self.owner_power.get(t.owner, 0.0) / 45.0)
            # Weak-target bonus (garrison discount).
            base += max(0.0, 30.0 - t.ships) * 0.9
            # V33-clean2: VULTURE OFFENSE. Enemy planets that just launched are
            # transiently weak (their ships are in flight elsewhere). Bonus
            # scales with the fraction of their force that is currently away
            # and with the planet's production. Bounded above so it cannot
            # dominate base value.
            if t.owner not in (-1, w.player):
                outflow = self.enemy_outflow.get(t.id, 0)
                if outflow >= 6:
                    total = outflow + max(0, t.ships)
                    ratio = outflow / max(1.0, float(total))
                    if ratio >= 0.4:
                        # Bonus scales 0..60 with ratio in [0.4, 1.0]
                        # and additionally with production.
                        vulture_bonus = (ratio - 0.4) * 100.0
                        vulture_bonus *= (1.0 + 0.25 * t.production)
                        base += min(60.0, vulture_bonus)
            # V34: Crash-exploit — bonus for planets where two enemy fleets from
            # different owners will collide, leaving the survivor weakened and the
            # planet transiently vulnerable. Capped at 80 to stay additive.
            crash = self.crash_bonus.get(t.id, 0.0)
            if crash > 0.0:
                base += min(80.0, crash)"""

P1_NEW = """            if t.owner == self.leader_owner:
                base += 72.0
            elif t.owner not in (-1, w.player):
                base += min(42.0, self.owner_power.get(t.owner, 0.0) / 45.0)
            # Weak-target bonus (garrison discount).
            base += max(0.0, 30.0 - t.ships) * 0.9"""

assert src.count(P1_OLD) == 1, "Patch 1 not found or not unique"
src = src.replace(P1_OLD, P1_NEW)

# ── Patch 2: Inject Neighborhood Gated Vulture, Crash, and Elimination in _best_move_for_source ──
P2_OLD = """        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))
        if ctx.duel_opening and target.owner == -1:"""

P2_NEW = """        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))

        # Gated bonuses for Vulture, Crash, and Elimination (must be local, scaling down with distance)
        if distance < 45.0:
            scale_factor = (45.0 - distance) / 45.0
            
            # Vulture Offense (from V33-clean2)
            if target.owner not in (-1, world.player):
                outflow = ctx.enemy_outflow.get(target.id, 0)
                if outflow >= 6:
                    total = outflow + max(0, target.ships)
                    ratio = outflow / max(1.0, float(total))
                    if ratio >= 0.4:
                        vulture_bonus = (ratio - 0.4) * 100.0
                        vulture_bonus *= (1.0 + 0.25 * target.production)
                        base += min(60.0, vulture_bonus) * scale_factor
            
            # Crash Exploit (from V34)
            crash = ctx.crash_bonus.get(target.id, 0.0)
            if crash > 0.0:
                base += min(80.0, crash) * scale_factor

        # Elimination Drive (from V38: post-opening FFA, focus weakest player)
        if distance < 60.0:
            if (not ctx.ffa_opening) and ctx.weakest_enemy_owner >= 0 and target.owner == ctx.weakest_enemy_owner:
                elim_factor = (60.0 - distance) / 60.0
                base += 160.0 * elim_factor

        if ctx.duel_opening and target.owner == -1:"""

assert src.count(P2_OLD) == 1, "Patch 2 not found or not unique"
src = src.replace(P2_OLD, P2_NEW)

DST.write_text(src, encoding="utf-8")
print(f"Success! Wrote {DST} ({DST.stat().st_size:,} bytes).")
