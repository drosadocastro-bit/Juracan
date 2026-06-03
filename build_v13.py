"""Build main_v13.py by updating neural policy and adding ShipAllocator to V11 skeleton."""
import re

# Read V11
with open("d:/Juracan/main_v11.py") as f:
    v11 = f.read()

# Read new policy weights
with open("d:/Juracan/policy_embed.py") as f:
    policy_line = f.read().strip()
    b64_val = policy_line.split('"')[1]

# 1. Update docstring
v13 = v11.replace(
    "Orbit Wars V11",
    "Orbit Wars V13"
).replace(
    "V11 additions (on V10 base):",
    "V13 additions (on V11 base):\\n  - Diverse training data (500 mixed games)\\n  - Neural ShipAllocator for dynamic fleet sizing\\n  - FFA TargetScorer scaling reduced to prevent over-aggression"
)

# 2. Update POLICY_B64
v13 = re.sub(r'_POLICY_B64 = ".*?"', f'_POLICY_B64 = "{b64_val}"', v13)

# 3. Add ShipAllocator function after TargetScorer function
target_scorer_func = '''def _neural_target_score(global_feats, source_feats, target_feats):'''
allocator_func = '''def _neural_ship_allocator(global_feats, source_feats, target_feats, capture_ratio):
    """Predict ship fraction [0, 1, 2, 3] -> [skip, min, 50%, all]."""
    model = _load_policy_model()
    if model is None:
        return 3  # default to 'all'
    try:
        ratio_feat = np.array([min(capture_ratio, 5.0) / 5.0], dtype=np.float32)
        pair = np.concatenate([global_feats, source_feats, target_feats, ratio_feat]).reshape(1, -1)
        z1 = pair @ model['sa_W1'] + model['sa_b1']
        a1 = np.maximum(0, z1)
        z2 = a1 @ model['sa_W2'] + model['sa_b2']
        a2 = np.maximum(0, z2)
        z3 = a2 @ model['sa_W3'] + model['sa_b3']
        return int(np.argmax(z3[0]))
    except Exception:
        return 3

def _neural_target_score(global_feats, source_feats, target_feats):'''
v13 = v13.replace(target_scorer_func, allocator_func)

# 4. Modify DECIDE phase to use ShipAllocator
old_decide = '''        surplus = ctx.surplus_by_id.get(source.id, 0) - used_surplus[source.id]
        if surplus < _min_launch_size(world.step):
            continue

        best = _best_move_for_source(source, surplus, world, ctx)
        if best is not None:
            source_best[source.id] = best'''

new_decide = '''        surplus = ctx.surplus_by_id.get(source.id, 0) - used_surplus[source.id]
        if surplus < _min_launch_size(world.step):
            continue

        best = _best_move_for_source(source, surplus, world, ctx)
        if best is not None:
            _, tag, src, tgt, send, angle = best
            # V13: Use neural ship allocator
            if ctx._global_feats is not None:
                src_f = ctx._planet_feats_cache.get(src.id)
                tgt_f = ctx._planet_feats_cache.get(tgt.id)
                if src_f is not None and tgt_f is not None:
                    # Calculate heuristic capture ratio
                    aim = _aim_solution(src, tgt, send, world.angular_velocity, world.comet_paths, world.planets, _MEMORY["path_tolerance"])
                    eta = aim[1] if aim else 10.0
                    need = ctx.capture_need(tgt, eta)
                    ratio = send / max(1.0, float(need))
                    
                    alloc_class = _neural_ship_allocator(ctx._global_feats, src_f, tgt_f, ratio)
                    
                    if alloc_class == 0:
                        continue  # Skip attack
                    elif alloc_class == 1:
                        send = min(send, max(need, _min_launch_size(world.step)))
                    elif alloc_class == 2:
                        send = min(send, max(surplus // 2, need))
                    # else alloc_class == 3: keep send as surplus (all)
                    
                    best = (_, tag, src, tgt, int(send), angle)

            source_best[source.id] = best'''
v13 = v13.replace(old_decide, new_decide)

# Write to file
with open("d:/Juracan/main_v13.py", "w") as f:
    f.write(v13)
print("Built main_v13.py")
