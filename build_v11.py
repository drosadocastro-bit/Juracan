"""Build main_v11.py by injecting neural policy into V10 skeleton."""
import re

# Read V10
with open("d:/Juracan/main_v10.py") as f:
    v10 = f.read()

# Read policy weights
with open("d:/Juracan/policy_embed.py") as f:
    policy_line = f.read().strip()
    b64_val = policy_line.split('"')[1]

# 1. Update docstring
v11 = v10.replace(
    "Orbit Wars V10",
    "Orbit Wars V11"
).replace(
    "V10 additions:",
    "V11 additions (on V10 base):"
)

# 2. Add policy weights + loader after the value estimator section
policy_block = '''

# ============================================================
# POLICY MODEL (trained on 200 self-play games, 75.6% target acc)
# ============================================================

_POLICY_B64 = "''' + b64_val + '''"

_POLICY_MODEL = None

def _load_policy_model():
    global _POLICY_MODEL
    if _POLICY_MODEL is not None:
        return _POLICY_MODEL
    if not _HAS_NUMPY:
        return None
    try:
        raw = base64.b64decode(_POLICY_B64)
        buf = io.BytesIO(raw)
        data = np.load(buf)
        _POLICY_MODEL = {k: data[k] for k in data.files}
        return _POLICY_MODEL
    except Exception:
        return None


def _neural_target_score(global_feats, source_feats, target_feats):
    """Score a (source, target) pair using the trained TargetScorer.
    Returns attack probability [0,1] or None if model unavailable."""
    model = _load_policy_model()
    if model is None:
        return None
    try:
        pair = np.concatenate([global_feats, source_feats, target_feats]).reshape(1, -1)
        pair = (pair - model['feat_mean']) / (model['feat_std'] + 1e-8)
        z1 = pair @ model['ts_W1'] + model['ts_b1']
        a1 = np.maximum(0, z1)
        z2 = a1 @ model['ts_W2'] + model['ts_b2']
        a2 = np.maximum(0, z2)
        z3 = a2 @ model['ts_W3'] + model['ts_b3']
        return float(1.0 / (1.0 + np.exp(-np.clip(z3, -20, 20)))[0, 0])
    except Exception:
        return None


def _build_planet_features(planet, player, planets):
    """Build per-planet feature vector (12 dims) matching training format."""
    is_mine = 1.0 if planet.owner == player else 0.0
    is_enemy = 1.0 if planet.owner >= 0 and planet.owner != player else 0.0
    is_neutral = 1.0 if planet.owner == -1 else 0.0
    d_enemy = 999.0
    for ep in planets:
        if ep.owner >= 0 and ep.owner != player:
            d = _dist(planet.x, planet.y, ep.x, ep.y)
            if d < d_enemy:
                d_enemy = d
    orbital_r = _dist(planet.x, planet.y, CENTER_X, CENTER_Y)
    is_orb = 1.0 if orbital_r + planet.radius < ROTATION_LIMIT else 0.0
    return np.array([
        is_mine, is_enemy, is_neutral,
        planet.x / BOARD_SIZE, planet.y / BOARD_SIZE,
        planet.radius / 5.0, min(planet.ships, 500) / 500.0,
        planet.production / 5.0, min(d_enemy, 100.0) / 100.0,
        0.0, 0.0, is_orb,
    ], dtype=np.float32)


def _build_global_features(world):
    """Build global feature vector (15 dims) matching training format."""
    player = world.player
    my_ships = my_prod = my_count = 0
    enemy_ships = enemy_prod = enemy_count = 0
    neutral_ships = neutral_count = 0
    nearest_enemy = 999.0
    for p in world.planets:
        if p.owner == player:
            my_ships += p.ships; my_prod += p.production; my_count += 1
        elif p.owner == -1:
            neutral_ships += p.ships; neutral_count += 1
        else:
            enemy_ships += p.ships; enemy_prod += p.production; enemy_count += 1
    for p in world.my_planets:
        for e in world.enemy_planets:
            d = _dist(p.x, p.y, e.x, e.y)
            if d < nearest_enemy:
                nearest_enemy = d
    my_fships = enemy_fships = 0
    for f in world.fleets:
        if f.owner == player: my_fships += f.ships
        elif f.owner >= 0: enemy_fships += f.ships
    total_my = my_ships + my_fships
    total_enemy = enemy_ships + enemy_fships
    total_prod = my_prod + enemy_prod + 1
    total_planets = my_count + enemy_count + neutral_count + 1
    return np.array([
        world.step / 500.0, total_my / 500.0, my_prod / 30.0, my_count / 20.0,
        total_enemy / 500.0, enemy_prod / 30.0, enemy_count / 20.0,
        neutral_ships / 200.0, neutral_count / 20.0,
        my_fships / 200.0, enemy_fships / 200.0,
        my_prod / total_prod, total_my / max(1, total_my + total_enemy),
        my_count / total_planets, nearest_enemy / 100.0,
    ], dtype=np.float32)

'''

# Insert policy block after the GAME MEMORY section header
insert_marker = "# ============================================================\n# GAME MEMORY"
v11 = v11.replace(insert_marker, policy_block + "\n" + insert_marker)

# 3. Modify _score_targets to use neural scorer as bonus
old_score = '''    def _score_targets(self):
        """Pre-score every non-owned planet as an attack candidate."""
        w = self.world
        self.target_scores = {}
        for t in w.planets:
            if t.owner == w.player:
                continue
            if t.id in _MEMORY["blacklist"] and _MEMORY["blacklist"][t.id] > _MEMORY["turn"]:
                continue
            base = t.production * (92.0 if t.owner == -1 else 118.0)'''

new_score = '''    def _score_targets(self):
        """Pre-score targets: heuristic base + neural bonus (V11)."""
        w = self.world
        self.target_scores = {}

        # V11: precompute global features for neural scorer
        if _HAS_NUMPY:
            self._global_feats = _build_global_features(w)
            self._planet_feats_cache = {}
            for p in w.planets:
                self._planet_feats_cache[p.id] = _build_planet_features(p, w.player, w.planets)
        else:
            self._global_feats = None

        for t in w.planets:
            if t.owner == w.player:
                continue
            if t.id in _MEMORY["blacklist"] and _MEMORY["blacklist"][t.id] > _MEMORY["turn"]:
                continue
            base = t.production * (92.0 if t.owner == -1 else 118.0)'''

v11 = v11.replace(old_score, new_score)

# 4. Add neural bonus right before the final assignment
old_assign = '''            self.target_scores[t.id] = base'''
new_assign = '''            # V11: neural target scorer bonus
            if self._global_feats is not None and not self.duel_opening:
                # Average neural score across owned planets as sources
                neural_scores = []
                for src in w.my_planets[:8]:  # limit for speed
                    src_f = self._planet_feats_cache.get(src.id)
                    tgt_f = self._planet_feats_cache.get(t.id)
                    if src_f is not None and tgt_f is not None:
                        ns = _neural_target_score(self._global_feats, src_f, tgt_f)
                        if ns is not None:
                            neural_scores.append(ns)
                if neural_scores:
                    avg_neural = sum(neural_scores) / len(neural_scores)
                    # Scale to heuristic range: neural 0.5 = neutral, 1.0 = +150 bonus
                    base += (avg_neural - 0.25) * 200.0

            self.target_scores[t.id] = base'''

v11 = v11.replace(old_assign, new_assign)

# 5. Add neural feats to Context slots
v11 = v11.replace(
    '"target_scores", "win_prob", "consolidating",',
    '"target_scores", "win_prob", "consolidating",\n        "_global_feats", "_planet_feats_cache",'
)

with open("d:/Juracan/main_v11.py", "w") as f:
    f.write(v11)

print(f"V11 written: {len(v11)} chars")
print(f"Policy embed: {len(b64_val)} chars")
