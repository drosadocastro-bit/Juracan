"""Build V33 — Present-Value Scoring + Spatial Danger Map.

Two changes over V32, both motivated by Kaggle discussion thread 699003
(istinetz, rank 56) which reports each idea is worth ~50-80 elo on its own:

1. **Present value (PV) bonus**: every captured planet is worth its discounted
   stream of future production. We add this on top of V32's heuristic base.

       pv = production * (gamma^arrival - gamma^horizon) / (1 - gamma)
       gamma = 0.99
       horizon = max(20, 500 - current_step)

   This naturally devalues captures in the final turns (horizon shrinks),
   penalises slow arrivals (smaller gamma^arrival), and rewards high-production
   targets.

2. **Spatial danger map**: per target, ally power vs enemy power weighted by
   inverse distance. A score multiplier of (0.5 + danger) keeps the PV bonus
   in [0.5x, 1.5x] range:

       ally_str  = c + sum(ally.ships  / max(1, dist))
       enemy_str = c + sum(enemy.ships / max(1, dist))
       danger    = ally_str / (ally_str + enemy_str)

   Targets deep in our territory are valued more (we can hold them); targets
   in enemy territory are valued less (they'll be retaken).

Both terms are *added* to V32's existing scoring rather than replacing it.
This preserves V32's duel ladder behavior unless PV+danger genuinely disagree.
"""

with open("d:/Juracan/main_v32.py", encoding="utf-8") as f:
    code = f.read()

# ── 1. Header docstring update ──
code = code.replace(
    "Orbit Wars V32 — FFA-Gated Vulture.",
    "Orbit Wars V33 — PV Scoring + Danger Map."
)
code = code.replace(
    "V32: FFA-Gated Vulture — V31 vulture restricted to games with 3+ active players; duels revert to V30 strict abort",
    "V33: PV Scoring + Danger Map — V32 spine + present-value target valuation and spatial ally/enemy danger weighting per istinetz writeup",
)

# ── 2. Add module-level PV constants near MAX_SPEED ──
OLD_CONSTS = """MAX_SPEED = 6.0
RAY_EPS = 1e-9"""
NEW_CONSTS = """MAX_SPEED = 6.0
RAY_EPS = 1e-9

# V33: Present-value scoring constants.
PV_GAMMA = 0.99           # discount factor (1% drag per turn)
PV_HORIZON_MIN = 20       # never plan shorter than this even at game end
PV_WEIGHT = 0.45          # blend weight added to V32 heuristic base
DANGER_DIST_C = 6.0       # softening constant for inverse-distance sums
DANGER_DIST_CAP = 60.0    # ignore planets beyond this distance
DANGER_MULT_MIN = 0.55    # score multiplier floor
DANGER_MULT_MAX = 1.45    # score multiplier ceiling"""
assert OLD_CONSTS in code
code = code.replace(OLD_CONSTS, NEW_CONSTS)

# ── 3. Extend Context __slots__ to hold danger map ──
OLD_SLOTS = """        "target_scores", "arrivals_by_target", "arrivals_timeline","""
NEW_SLOTS = """        "target_scores", "danger_by_id", "arrivals_by_target", "arrivals_timeline","""
assert OLD_SLOTS in code, "Context __slots__ line not found"
code = code.replace(OLD_SLOTS, NEW_SLOTS)

# ── 4. Hook _compute_danger_map call right before _score_targets ──
# Find the line that calls _score_targets in __init__.
OLD_INIT_TAIL = """            self.target_scores[t.id] = base


    def capture_need(self, target, eta):"""
NEW_INIT_TAIL = """            self.target_scores[t.id] = base


    def _compute_danger_map(self):
        \"\"\"Per-planet ally_str / (ally_str + enemy_str) using inverse-distance
        weighting. Higher = friendlier neighborhood.\"\"\"
        w = self.world
        self.danger_by_id = {}
        my_planets = w.my_planets
        enemy_planets = [p for p in w.planets if p.owner not in (-1, w.player)]
        for t in w.planets:
            if t.owner == w.player:
                continue
            ally_str = DANGER_DIST_C
            enemy_str = DANGER_DIST_C
            for p in my_planets:
                d = _dist(p.x, p.y, t.x, t.y)
                if d > DANGER_DIST_CAP:
                    continue
                ally_str += p.ships / max(1.0, d)
            for p in enemy_planets:
                d = _dist(p.x, p.y, t.x, t.y)
                if d > DANGER_DIST_CAP:
                    continue
                enemy_str += p.ships / max(1.0, d)
            total = ally_str + enemy_str
            self.danger_by_id[t.id] = ally_str / total if total > 0 else 0.5

    def present_value(self, target, eta):
        \"\"\"Discounted future production from arrival until game end.\"\"\"
        horizon = max(PV_HORIZON_MIN, 500 - self.world.step)
        if eta >= horizon:
            return 0.0
        # (gamma^eta - gamma^horizon) / (1 - gamma)
        try:
            decay_arrival = PV_GAMMA ** eta
            decay_horizon = PV_GAMMA ** horizon
        except OverflowError:
            return 0.0
        return target.production * (decay_arrival - decay_horizon) / (1.0 - PV_GAMMA)

    def danger_multiplier(self, target):
        \"\"\"Score multiplier in [DANGER_MULT_MIN, DANGER_MULT_MAX] from the
        spatial danger map. 1.0 = neutral, >1 = friendly territory.\"\"\"
        d = self.danger_by_id.get(target.id, 0.5)
        # Map [0,1] -> [min, max] linearly.
        return DANGER_MULT_MIN + d * (DANGER_MULT_MAX - DANGER_MULT_MIN)

    def capture_need(self, target, eta):"""
assert OLD_INIT_TAIL in code, "_score_targets tail not found"
code = code.replace(OLD_INIT_TAIL, NEW_INIT_TAIL)

# ── 5. Invoke _compute_danger_map at end of Context.__init__ ──
# Find the end of _score_targets call in __init__. The init ends with self._score_targets().
# Easiest hook: insert after the line that calls _score_targets.
OLD_CALL = "        self._score_targets()"
NEW_CALL = "        self._compute_danger_map()\n        self._score_targets()"
assert code.count(OLD_CALL) == 1, "Expected single _score_targets() call"
code = code.replace(OLD_CALL, NEW_CALL)

# ── 6. Add PV bonus + danger multiplier in _best_move_for_source scoring ──
OLD_SCORE_BLOCK = """        # Score inside the priority bucket.
        base = ctx.target_scores.get(target.id, 0.0)
        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))"""
NEW_SCORE_BLOCK = """        # Score inside the priority bucket.
        base = ctx.target_scores.get(target.id, 0.0)
        # V33: present-value bonus weighted by spatial danger map.
        pv = ctx.present_value(target, eta)
        danger_mult = ctx.danger_multiplier(target)
        base += pv * PV_WEIGHT * danger_mult
        distance = max(1.0, _dist(source.x, source.y, target.x, target.y))"""
assert OLD_SCORE_BLOCK in code, "Score block not found"
code = code.replace(OLD_SCORE_BLOCK, NEW_SCORE_BLOCK)

with open("d:/Juracan/main_v33.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Built main_v33.py")
