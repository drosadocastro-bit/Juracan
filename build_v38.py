"""
Build V38: V27.1 + elimination drive.

Structural change: add weakest_enemy_owner to Context and give a large bonus
(+160) to all planets owned by the weakest enemy in FFA.

Goal: make V27.1 focus-fire on eliminating the weakest player in 3P+ FFA,
converting a 3-way into a cleaner 2-way as fast as possible.

Currently V27.1 gives +72 for leader planets and +min(42, power/45) for other
enemies — the latter gives a *stronger* enemy a *larger* bonus, which is
counter-productive for elimination. This patch replaces that with:
  - weakest enemy (+160) > leader (+72) > middle enemy (~5-42 power-based)
"""

import pathlib, sys

SRC = pathlib.Path("main_v27_1.py")
DST = pathlib.Path("main_v38.py")

src = SRC.read_text(encoding="utf-8")

# ── Patch 1: add weakest_enemy_owner slot ───────────────────────────────────
P1_OLD = '        "is_duel", "duel_opening", "ffa_opening", "ffa_behind",'
P1_NEW = '        "is_duel", "duel_opening", "ffa_opening", "ffa_behind", "weakest_enemy_owner",'
assert src.count(P1_OLD) == 1, f"P1 anchor not found or not unique"
src = src.replace(P1_OLD, P1_NEW)

# ── Patch 2: compute weakest_enemy_owner after leader_owner ─────────────────
P2_OLD = """\
        self.leader_owner = max(enemies, key=lambda o: power[o]) if enemies else -1
        leader_power = power.get(self.leader_owner, 0.0)"""
P2_NEW = """\
        self.leader_owner = max(enemies, key=lambda o: power[o]) if enemies else -1
        self.weakest_enemy_owner = (
            min(enemies, key=lambda o: power[o]) if len(enemies) >= 2 else -1
        )
        leader_power = power.get(self.leader_owner, 0.0)"""
assert src.count(P2_OLD) == 1, f"P2 anchor not found or not unique"
src = src.replace(P2_OLD, P2_NEW)

# ── Patch 3: elimination bonus in _score_targets ────────────────────────────
# Guard: weakest_enemy_owner >= 0 avoids matching neutral planets (owner=-1)
# Opening gate: not ffa_opening avoids competing with early neutral expansion
P3_OLD = """\
        if t.owner == self.leader_owner:
                base += 72.0
            elif t.owner not in (-1, w.player):
                base += min(42.0, self.owner_power.get(t.owner, 0.0) / 45.0)"""
P3_NEW = """\
        if t.owner == self.leader_owner:
                base += 72.0
            elif (not self.ffa_opening) and self.weakest_enemy_owner >= 0 and t.owner == self.weakest_enemy_owner:
                base += 160.0  # Elimination drive: focus-fire to remove weakest player (FFA, post-opening)
            elif t.owner not in (-1, w.player):
                base += min(42.0, self.owner_power.get(t.owner, 0.0) / 45.0)"""
assert src.count(P3_OLD) == 1, f"P3 anchor not found or not unique"
src = src.replace(P3_OLD, P3_NEW)

DST.write_text(src, encoding="utf-8")
print(f"Wrote {DST} ({DST.stat().st_size:,} bytes)")
print("V38: V27.1 + elimination drive (weakest_enemy_owner +160 post-opening, with bug fixes).")
