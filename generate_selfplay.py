"""
Phase 1: Self-play data generation for V11 RL training.

Runs games using kaggle_environments, extracts per-step board features
and action labels from the WINNING agent, and saves to selfplay_data.npz.

Usage:
    python generate_selfplay.py [--games 300] [--output selfplay_data.npz]
"""

import argparse
import math
import os
import sys
import time
from collections import namedtuple

import numpy as np
from kaggle_environments import make

# ---------------------
# Constants
# ---------------------
MAX_PLANETS = 40
GLOBAL_FEATURES = 15
PLANET_FEATURES = 12
BOARD_SIZE = 100.0
CENTER = 50.0
SUN_RADIUS = 10.0
ROTATION_LIMIT = 50.0

Planet = namedtuple("Planet", "id owner x y radius ships production")
Fleet = namedtuple("Fleet", "id owner x y angle from_planet_id ships")


def dist(ax, ay, bx, by):
    return math.hypot(ax - bx, ay - by)


def extract_state_features(obs, player):
    """Extract a fixed-size feature vector from a game observation.
    
    Returns:
        global_feats: np.array of shape (GLOBAL_FEATURES,)
        planet_feats: np.array of shape (MAX_PLANETS, PLANET_FEATURES)
        planet_ids: list of planet ids (length <= MAX_PLANETS)
        planet_owners: list of planet owners
    """
    step = obs.get("step", 0) if isinstance(obs, dict) else getattr(obs, "step", 0)
    raw_planets = obs.get("planets", []) if isinstance(obs, dict) else getattr(obs, "planets", [])
    raw_fleets = obs.get("fleets", []) if isinstance(obs, dict) else getattr(obs, "fleets", [])
    
    planets = [Planet(*p) for p in raw_planets]
    fleets = [Fleet(*f) for f in raw_fleets]
    
    # Global features
    my_ships = my_prod = my_count = 0
    enemy_ships = enemy_prod = enemy_count = 0
    neutral_ships = neutral_count = 0
    nearest_enemy = 999.0
    my_positions = []
    enemy_positions = []
    
    for p in planets:
        if p.owner == player:
            my_ships += p.ships
            my_prod += p.production
            my_count += 1
            my_positions.append((p.x, p.y))
        elif p.owner == -1:
            neutral_ships += p.ships
            neutral_count += 1
        else:
            enemy_ships += p.ships
            enemy_prod += p.production
            enemy_count += 1
            enemy_positions.append((p.x, p.y))
    
    if my_positions and enemy_positions:
        for mx, my in my_positions:
            for ex, ey in enemy_positions:
                d = dist(mx, my, ex, ey)
                if d < nearest_enemy:
                    nearest_enemy = d
    
    my_fships = enemy_fships = 0
    for f in fleets:
        if f.owner == player:
            my_fships += f.ships
        elif f.owner >= 0:
            enemy_fships += f.ships
    
    total_my = my_ships + my_fships
    total_enemy = enemy_ships + enemy_fships
    total_prod = my_prod + enemy_prod + 1
    total_planets = my_count + enemy_count + neutral_count + 1
    
    global_feats = np.array([
        step / 500.0,
        total_my / 500.0,
        my_prod / 30.0,
        my_count / 20.0,
        total_enemy / 500.0,
        enemy_prod / 30.0,
        enemy_count / 20.0,
        neutral_ships / 200.0,
        neutral_count / 20.0,
        my_fships / 200.0,
        enemy_fships / 200.0,
        my_prod / total_prod,
        total_my / max(1, total_my + total_enemy),
        my_count / total_planets,
        nearest_enemy / 100.0,
    ], dtype=np.float32)
    
    # Per-planet features
    planet_feats = np.zeros((MAX_PLANETS, PLANET_FEATURES), dtype=np.float32)
    planet_ids = []
    planet_owners = []
    
    # Compute incoming fleets per planet (simplified)
    incoming_friendly = {}
    incoming_enemy = {}
    # (We'd need fleet forecasting for this — approximate with distance)
    
    for i, p in enumerate(planets[:MAX_PLANETS]):
        planet_ids.append(p.id)
        planet_owners.append(p.owner)
        
        is_mine = 1.0 if p.owner == player else 0.0
        is_enemy = 1.0 if p.owner >= 0 and p.owner != player else 0.0
        is_neutral = 1.0 if p.owner == -1 else 0.0
        
        # Distance to nearest enemy planet
        d_enemy = 999.0
        for ep in planets:
            if ep.owner >= 0 and ep.owner != player:
                d = dist(p.x, p.y, ep.x, ep.y)
                if d < d_enemy:
                    d_enemy = d
        
        orbital_r = dist(p.x, p.y, CENTER, CENTER)
        is_orbiting = 1.0 if orbital_r + p.radius < ROTATION_LIMIT else 0.0
        
        planet_feats[i] = [
            is_mine,
            is_enemy,
            is_neutral,
            p.x / BOARD_SIZE,
            p.y / BOARD_SIZE,
            p.radius / 5.0,
            min(p.ships, 500) / 500.0,
            p.production / 5.0,
            min(d_enemy, 100.0) / 100.0,
            0.0,  # incoming_friendly placeholder
            0.0,  # incoming_enemy placeholder
            is_orbiting,
        ]
    
    return global_feats, planet_feats, planet_ids, planet_owners


def extract_actions(obs, player, planet_ids):
    """Extract which (source, target) pairs the player attacked this turn.
    
    Returns a set of (source_planet_id, target_planet_id) pairs.
    We infer target from fleet angle + nearest planet in that direction.
    """
    raw_planets = obs.get("planets", []) if isinstance(obs, dict) else getattr(obs, "planets", [])
    raw_fleets = obs.get("fleets", []) if isinstance(obs, dict) else getattr(obs, "fleets", [])
    
    planets = [Planet(*p) for p in raw_planets]
    fleets = [Fleet(*f) for f in raw_fleets]
    
    actions = set()
    
    # Find NEW fleets owned by this player (they were launched this turn)
    for f in fleets:
        if f.owner != player:
            continue
        # Match fleet to nearest target planet in its direction
        best_target = None
        best_score = float("inf")
        fx, fy = f.x, f.y
        ux = math.cos(f.angle)
        uy = math.sin(f.angle)
        
        for p in planets:
            if p.id == f.from_planet_id:
                continue
            dx = p.x - fx
            dy = p.y - fy
            d = math.hypot(dx, dy)
            if d < 1.0:
                continue
            # How well does the fleet angle align with this planet?
            dot = (dx * ux + dy * uy) / d
            if dot > 0.9:  # roughly aimed at this planet
                score = d * (1.0 - dot + 0.01)
                if score < best_score:
                    best_score = score
                    best_target = p.id
        
        if best_target is not None:
            actions.add((f.from_planet_id, best_target))
    
    return actions


def run_game(agents, seed, game_type="duel"):
    """Run one game and extract training data from the winning agent."""
    num_agents = 2 if game_type == "duel" else 4
    
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    
    if game_type == "duel":
        env.run(agents[:2])
    else:
        agent_list = agents[:num_agents]
        while len(agent_list) < 4:
            agent_list.append("random")
        env.run(agent_list)
    
    final = env.steps[-1]
    
    # Find winner
    rewards = [final[i].reward for i in range(num_agents)]
    max_reward = max(rewards)
    if max_reward <= 0:
        return []  # No winner — skip
    
    winners = [i for i, r in enumerate(rewards) if r == max_reward]
    if len(winners) != 1:
        return []  # Tie — skip
    
    winner = winners[0]
    
    # Extract training samples from winner's perspective
    samples = []
    prev_fleet_ids = set()
    
    for step_idx in range(1, len(env.steps)):
        step_data = env.steps[step_idx]
        obs = step_data[winner]["observation"]
        if obs is None:
            continue
        
        raw_fleets = obs.get("fleets", []) if isinstance(obs, dict) else getattr(obs, "fleets", [])
        
        # Extract state features
        global_feats, planet_feats, planet_ids, planet_owners = \
            extract_state_features(obs, winner)
        
        # Find new fleets (launched this step by winner)
        current_fleet_ids = set()
        new_fleets = []
        for f_raw in raw_fleets:
            fid = int(f_raw[0])
            current_fleet_ids.add(fid)
            if fid not in prev_fleet_ids and int(f_raw[1]) == winner:
                new_fleets.append(Fleet(*f_raw))
        
        # Build action labels: for each (source_idx, target_idx), did we attack?
        raw_planets = obs.get("planets", []) if isinstance(obs, dict) else getattr(obs, "planets", [])
        planets = [Planet(*p) for p in raw_planets]
        
        attacked_pairs = set()  # (source_idx_in_padded, target_idx_in_padded)
        ships_sent = {}  # (source_idx, target_idx) -> ships
        
        for f in new_fleets:
            # Find source planet index
            source_idx = None
            for i, pid in enumerate(planet_ids):
                if pid == f.from_planet_id:
                    source_idx = i
                    break
            if source_idx is None:
                continue
            
            # Find target planet (nearest in fleet direction)
            best_target_idx = None
            best_score = float("inf")
            ux = math.cos(f.angle)
            uy = math.sin(f.angle)
            
            for i, p in enumerate(planets[:MAX_PLANETS]):
                if p.id == f.from_planet_id:
                    continue
                dx = p.x - f.x
                dy = p.y - f.y
                d = math.hypot(dx, dy)
                if d < 1.0:
                    continue
                dot = (dx * ux + dy * uy) / d
                if dot > 0.85:
                    score = d * (1.0 - dot + 0.01)
                    if score < best_score:
                        best_score = score
                        # Find index in planet_ids
                        for j, pid in enumerate(planet_ids):
                            if pid == p.id:
                                best_target_idx = j
                                break
            
            if best_target_idx is not None:
                attacked_pairs.add((source_idx, best_target_idx))
                key = (source_idx, best_target_idx)
                ships_sent[key] = ships_sent.get(key, 0) + f.ships
        
        # Build training pairs: for each owned planet, score each potential target
        my_planet_indices = [i for i, o in enumerate(planet_owners) if o == winner]
        target_indices = [i for i, o in enumerate(planet_owners) if o != winner]
        
        if not my_planet_indices or not target_indices:
            prev_fleet_ids = current_fleet_ids
            continue
        
        for src_idx in my_planet_indices:
            for tgt_idx in target_indices:
                # Features: global + source planet + target planet
                pair_feats = np.concatenate([
                    global_feats,
                    planet_feats[src_idx],
                    planet_feats[tgt_idx],
                ])
                
                # Label: 1 if attacked, 0 if not
                label = 1.0 if (src_idx, tgt_idx) in attacked_pairs else 0.0
                
                # Ship fraction (for allocation training)
                if (src_idx, tgt_idx) in ships_sent:
                    src_planet = planets[src_idx] if src_idx < len(planets) else None
                    if src_planet and src_planet.ships > 0:
                        frac = ships_sent[(src_idx, tgt_idx)] / max(1, src_planet.ships + ships_sent[(src_idx, tgt_idx)])
                    else:
                        frac = 0.5
                else:
                    frac = 0.0
                
                samples.append((pair_feats, label, frac))
        
        prev_fleet_ids = current_fleet_ids
    
    return samples


def main():
    parser = argparse.ArgumentParser(description="Generate self-play data")
    parser.add_argument("--games", type=int, default=500, help="Number of games to run")
    parser.add_argument("--output", default="selfplay_data.npz", help="Output file")
    parser.add_argument("--start-seed", type=int, default=1000, help="Starting seed")
    args = parser.parse_args()
    
    agents = {
        "v11": "d:/Juracan/main_v11.py",
        "v10": "d:/Juracan/main_v10.py",
        "v8": "d:/Juracan/main_v8.py",
        "v7": "d:/Juracan/main_v7.py",
        "v5": "d:/Juracan/main_v5.py",
        "starter": "d:/Juracan/starter_sniper.py",
        "random": "random",
    }
    
    # Game schedule: mix of opponent types and formats
    schedule = []
    n = args.games
    
    # 20% V11 vs V11
    for i in range(int(n * 0.20)):
        schedule.append(("duel", [agents["v11"], agents["v11"]], args.start_seed + i))
        
    # 10% V11 vs V10
    base = len(schedule)
    for i in range(int(n * 0.10)):
        schedule.append(("duel", [agents["v11"], agents["v10"]], args.start_seed + base + i))
    
    # 15% V11 vs V7
    base = len(schedule)
    for i in range(int(n * 0.15)):
        schedule.append(("duel", [agents["v11"], agents["v7"]], args.start_seed + base + i))
        
    # 15% V11 vs V5
    base = len(schedule)
    for i in range(int(n * 0.15)):
        schedule.append(("duel", [agents["v11"], agents["v5"]], args.start_seed + base + i))
    
    # 10% V11 vs random
    base = len(schedule)
    for i in range(int(n * 0.10)):
        schedule.append(("duel", [agents["v11"], agents["random"]], args.start_seed + base + i))
    
    # 30% 4-player FFA (diverse mixes)
    base = len(schedule)
    for i in range(int(n * 0.30)):
        mix = [agents["v11"]]
        if i % 3 == 0:
            mix.extend([agents["v10"], agents["v7"], agents["v5"]])
        elif i % 3 == 1:
            mix.extend([agents["v8"], agents["v7"], agents["starter"]])
        else:
            mix.extend([agents["v10"], agents["random"], agents["random"]])
        schedule.append(("ffa", mix, args.start_seed + base + i))
    
    all_feats = []
    all_labels = []
    all_fracs = []
    
    total_games = len(schedule)
    wins = 0
    t0 = time.time()
    
    print(f"Generating self-play data: {total_games} games")
    print(f"Schedule: {int(n*0.20)} v11-v11, {int(n*0.10)} v11-v10, {int(n*0.15)} v11-v7, {int(n*0.15)} v11-v5, {int(n*0.10)} v11-rnd, {int(n*0.30)} ffa")
    
    for game_idx, (game_type, agent_list, seed) in enumerate(schedule):
        try:
            samples = run_game(agent_list, seed, game_type)
            if samples:
                wins += 1
                for feats, label, frac in samples:
                    all_feats.append(feats)
                    all_labels.append(label)
                    all_fracs.append(frac)
            
            if (game_idx + 1) % 10 == 0:
                elapsed = time.time() - t0
                rate = (game_idx + 1) / elapsed * 3600
                pos = len(all_labels)
                pos_rate = sum(1 for l in all_labels if l > 0.5)
                print(f"  [{game_idx+1}/{total_games}] "
                      f"wins={wins} samples={pos} "
                      f"positive_rate={pos_rate/max(1,pos)*100:.1f}% "
                      f"rate={rate:.0f} games/hr "
                      f"elapsed={elapsed:.0f}s")
        except Exception as e:
            print(f"  Game {game_idx} failed: {e}", file=sys.stderr)
    
    elapsed = time.time() - t0
    
    if not all_feats:
        print("ERROR: No data collected!")
        return
    
    feats_arr = np.array(all_feats, dtype=np.float32)
    labels_arr = np.array(all_labels, dtype=np.float32)
    fracs_arr = np.array(all_fracs, dtype=np.float32)
    
    np.savez_compressed(
        args.output,
        features=feats_arr,
        labels=labels_arr,
        ship_fracs=fracs_arr,
    )
    
    pos_count = int(np.sum(labels_arr > 0.5))
    neg_count = len(labels_arr) - pos_count
    
    print(f"\n=== DATA GENERATION COMPLETE ===")
    print(f"Games: {total_games} played, {wins} had a winner")
    print(f"Total samples: {len(labels_arr)}")
    print(f"Positive (attacked): {pos_count} ({pos_count/len(labels_arr)*100:.1f}%)")
    print(f"Negative (held): {neg_count} ({neg_count/len(labels_arr)*100:.1f}%)")
    print(f"Feature shape: {feats_arr.shape}")
    print(f"Time: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"Saved to: {args.output}")


if __name__ == "__main__":
    main()
