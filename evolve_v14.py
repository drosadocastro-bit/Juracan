"""
V14 Evolutionary Strategy — tune V7's heuristic parameters via tournament selection.

Instead of training neural networks, we parameterize V7's key decision knobs
and evolve them through self-play tournaments. This approach directly optimizes
for winning rather than imitating past decisions.

Key insight from analysis: winners have LOW aggression (2-3%), send BIGGER fleets,
and maintain strong reserves.
"""
import argparse
import copy
import json
import math
import os
import random
import sys
import time

import numpy as np
from kaggle_environments import make

# ============================================================
# PARAMETER SPACE — the knobs we evolve
# ============================================================

DEFAULT_PARAMS = {
    # Target scoring weights
    "neutral_base_mult": 92.0,       # base value multiplier for neutral planets
    "enemy_base_mult": 118.0,        # base value multiplier for enemy planets
    "duel_neutral_bonus": 70.0,      # extra production bonus in duel opening
    "duel_garrison_bonus": 2.2,      # per-ship bonus for low-garrison neutrals in duel
    "ffa_neutral_bonus": 26.0,       # extra production bonus in FFA opening
    "ffa_garrison_bonus": 0.9,       # per-ship bonus for low-garrison neutrals in FFA
    "ffa_high_prod_bonus": 24.0,     # bonus for high-prod low-garrison in FFA
    "leader_pressure": 72.0,         # bonus for attacking the leader
    "ffa_behind_pressure": 110.0,    # extra bonus when behind in FFA
    "weak_garrison_bonus": 0.9,      # per-ship bonus for targets with <30 ships
    
    # Reserve parameters
    "early_reserve_step": 12,        # below this step, minimal reserves
    "duel_open_step": 22,            # duel opening phase boundary
    "ffa_open_step": 72,             # FFA opening phase boundary
    "ffa_close_enemy_dist": 18.0,    # FFA close-enemy distance threshold
    "ffa_close_reserve_prod_mult": 1,  # production multiplier for close-enemy reserve
    "ffa_close_reserve_base": 3,     # base reserve for close enemies in FFA
    "mid_reserve_step": 90,          # step at which midgame reserves kick in
    "late_reserve_step": 80,         # step for late-game reserve boost
    "endgame_reserve_step": 130,     # step for endgame reserve boost
    "late_reserve_prod_mult": 2,     # production multiplier for late reserves
    "endgame_reserve_prod_mult": 3,  # production multiplier for endgame reserves
    "close_threat_dist": 25.0,       # close-threat distance for reserve boost
    "mid_threat_dist": 38.0,         # mid-threat distance for reserve boost
    "close_threat_bonus": 4,         # reserve boost for close threats
    "mid_threat_bonus": 2,           # reserve boost for mid threats
    
    # Fleet sizing
    "min_fleet_early": 3,            # minimum fleet size before step 30
    "min_fleet_mid": 5,              # minimum fleet size steps 30-90
    "min_fleet_late": 6,             # minimum fleet size after step 90
    
    # Aggression control
    "ffa_behind_threshold": 0.80,    # power ratio threshold for "behind"
    "ffa_behind_start": 70,          # step when behind-checking starts
    "ffa_behind_end": 155,           # step when behind-checking ends
    "power_projection_mult": 18.0,   # production -> power conversion for rankings
}

PARAM_RANGES = {
    "neutral_base_mult": (60.0, 140.0),
    "enemy_base_mult": (80.0, 160.0),
    "duel_neutral_bonus": (30.0, 120.0),
    "duel_garrison_bonus": (0.5, 5.0),
    "ffa_neutral_bonus": (10.0, 50.0),
    "ffa_garrison_bonus": (0.3, 2.0),
    "ffa_high_prod_bonus": (10.0, 50.0),
    "leader_pressure": (30.0, 150.0),
    "ffa_behind_pressure": (50.0, 180.0),
    "weak_garrison_bonus": (0.3, 2.0),
    "early_reserve_step": (8, 20),
    "duel_open_step": (15, 35),
    "ffa_open_step": (50, 100),
    "ffa_close_enemy_dist": (12.0, 28.0),
    "mid_reserve_step": (60, 120),
    "late_reserve_step": (60, 110),
    "endgame_reserve_step": (100, 180),
    "late_reserve_prod_mult": (1, 4),
    "endgame_reserve_prod_mult": (2, 5),
    "close_threat_dist": (15.0, 35.0),
    "mid_threat_dist": (25.0, 50.0),
    "close_threat_bonus": (2, 8),
    "mid_threat_bonus": (1, 5),
    "min_fleet_early": (2, 6),
    "min_fleet_mid": (3, 8),
    "min_fleet_late": (4, 10),
    "ffa_behind_threshold": (0.60, 0.95),
    "power_projection_mult": (10.0, 30.0),
}


def mutate_params(params, sigma=0.15):
    """Gaussian mutation of parameters within their valid ranges."""
    new = dict(params)
    for key, (lo, hi) in PARAM_RANGES.items():
        if key not in new:
            continue
        val = new[key]
        spread = (hi - lo) * sigma
        val += random.gauss(0, spread)
        val = max(lo, min(hi, val))
        if isinstance(params[key], int):
            val = int(round(val))
        new[key] = val
    return new


def crossover(p1, p2):
    """Uniform crossover between two parameter sets."""
    child = {}
    for key in p1:
        child[key] = p1[key] if random.random() < 0.5 else p2[key]
    return child


def generate_agent_code(params):
    """Read V7 and inject evolved parameters, write to temp file."""
    with open("d:/Juracan/main_v7.py", encoding="utf-8") as f:
        code = f.read()
    
    # Inject parameters as a config dict at the top
    config_block = f"\n_ES_PARAMS = {json.dumps(params)}\n"
    
    # Replace hardcoded values with parameterized versions
    replacements = [
        # Target scoring
        ('t.production * (92.0 if t.owner == -1 else 118.0)',
         f't.production * ({params["neutral_base_mult"]} if t.owner == -1 else {params["enemy_base_mult"]})'),
        ('base += t.production * 70.0',
         f'base += t.production * {params["duel_neutral_bonus"]}'),
        ('base += max(0.0, 18.0 - t.ships) * 2.2',
         f'base += max(0.0, 18.0 - t.ships) * {params["duel_garrison_bonus"]}'),
        ('base += t.production * 26.0',
         f'base += t.production * {params["ffa_neutral_bonus"]}'),
        ('base += max(0.0, 18.0 - t.ships) * 0.9\n                if t.production >= 3 and t.ships <= 16:\n                    base += 24.0',
         f'base += max(0.0, 18.0 - t.ships) * {params["ffa_garrison_bonus"]}\n                if t.production >= 3 and t.ships <= 16:\n                    base += {params["ffa_high_prod_bonus"]}'),
        ('base += 110.0',
         f'base += {params["ffa_behind_pressure"]}'),
        ('base += 72.0',
         f'base += {params["leader_pressure"]}'),
        ('base += max(0.0, 30.0 - t.ships) * 0.9',
         f'base += max(0.0, 30.0 - t.ships) * {params["weak_garrison_bonus"]}'),
        
        # Min fleet sizes
        ('if step < 30:\n        return 3\n    if step < 90:\n        return 5\n    return 6',
         f'if step < 30:\n        return {params["min_fleet_early"]}\n    if step < 90:\n        return {params["min_fleet_mid"]}\n    return {params["min_fleet_late"]}'),
        
        # Power projection
        ('power[p.owner] += p.ships + p.production * 18.0',
         f'power[p.owner] += p.ships + p.production * {params["power_projection_mult"]}'),
    ]
    
    for old, new in replacements:
        if old in code:
            code = code.replace(old, new, 1)
    
    return code


def run_tournament(candidates, seeds, opponent_agents):
    """Run a round-robin tournament. Each candidate plays against each opponent on each seed."""
    scores = [0.0] * len(candidates)
    temp_dir = "d:/Juracan/__es_temp"
    os.makedirs(temp_dir, exist_ok=True)
    
    # Write candidate files
    agent_files = []
    for i, params in enumerate(candidates):
        code = generate_agent_code(params)
        path = os.path.join(temp_dir, f"candidate_{i}.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        agent_files.append(path)
    
    total_games = 0
    for seed in seeds:
        for opp_path in opponent_agents:
            for i, agent_path in enumerate(agent_files):
                try:
                    # Duel
                    env = make("orbit_wars", debug=False, configuration={"seed": seed})
                    env.run([agent_path, opp_path])
                    final = env.steps[-1]
                    r0, r1 = final[0].reward, final[1].reward
                    if r0 > r1:
                        scores[i] += 3.0  # win
                    elif r0 == r1:
                        scores[i] += 1.0  # tie
                    total_games += 1
                except Exception as e:
                    print(f"  Game error: {e}", file=sys.stderr)
    
    # Also run FFA among top candidates
    if len(agent_files) >= 4:
        for seed in seeds[:2]:
            try:
                env = make("orbit_wars", debug=False, configuration={"seed": seed})
                agents = agent_files[:4]
                env.run(agents)
                final = env.steps[-1]
                rewards = [final[j].reward for j in range(4)]
                max_r = max(rewards)
                for j in range(4):
                    if rewards[j] == max_r:
                        scores[j] += 5.0  # FFA win is worth more
                total_games += 1
            except Exception:
                pass
    
    return scores, total_games


def main():
    parser = argparse.ArgumentParser(description="Evolve V7 parameters")
    parser.add_argument("--generations", type=int, default=20)
    parser.add_argument("--population", type=int, default=12)
    parser.add_argument("--seeds", type=int, default=4)
    parser.add_argument("--output", default="d:/Juracan/es_best_params.json")
    args = parser.parse_args()
    
    opponents = [
        "d:/Juracan/main_v7.py",
        "d:/Juracan/main_v10.py",
        "random",
    ]
    
    seeds = list(range(42, 42 + args.seeds))
    
    # Initialize population
    population = [DEFAULT_PARAMS]  # V7 defaults as baseline
    for _ in range(args.population - 1):
        population.append(mutate_params(DEFAULT_PARAMS, sigma=0.25))
    
    best_ever = DEFAULT_PARAMS
    best_ever_score = -1
    
    t0 = time.time()
    
    print(f"=== Evolutionary Strategy: {args.generations} gens, {args.population} pop, {args.seeds} seeds ===")
    
    for gen in range(args.generations):
        gen_t = time.time()
        scores, n_games = run_tournament(population, seeds, opponents)
        
        # Sort by score
        ranked = sorted(range(len(population)), key=lambda i: scores[i], reverse=True)
        
        best_idx = ranked[0]
        best_score = scores[best_idx]
        
        if best_score > best_ever_score:
            best_ever_score = best_score
            best_ever = dict(population[best_idx])
        
        elapsed = time.time() - gen_t
        total_elapsed = time.time() - t0
        
        print(f"  Gen {gen+1:2d}: best={best_score:.1f} avg={sum(scores)/len(scores):.1f} "
              f"games={n_games} time={elapsed:.0f}s total={total_elapsed:.0f}s")
        
        # Print key parameter diffs from default for top candidate
        top = population[best_idx]
        diffs = []
        for k in sorted(PARAM_RANGES):
            if abs(top[k] - DEFAULT_PARAMS[k]) > 0.01:
                diffs.append(f"{k}={top[k]:.2f}")
        if diffs:
            print(f"         top diffs: {', '.join(diffs[:6])}")
        
        # Selection: keep top 40%, breed the rest
        elite_n = max(2, len(population) * 2 // 5)
        elites = [population[ranked[i]] for i in range(elite_n)]
        
        new_pop = list(elites)  # keep elites
        while len(new_pop) < args.population:
            if random.random() < 0.7:
                # Crossover + mutation
                p1 = random.choice(elites)
                p2 = random.choice(elites)
                child = crossover(p1, p2)
                child = mutate_params(child, sigma=0.12)
            else:
                # Pure mutation from elite
                parent = random.choice(elites)
                child = mutate_params(parent, sigma=0.18)
            new_pop.append(child)
        
        population = new_pop
    
    # Save best
    with open(args.output, "w") as f:
        json.dump(best_ever, f, indent=2)
    
    print(f"\n=== EVOLUTION COMPLETE ===")
    print(f"Best score: {best_ever_score:.1f}")
    print(f"Total time: {time.time() - t0:.0f}s")
    print(f"Saved to: {args.output}")
    
    # Print final diffs
    print("\nEvolved parameter changes from V7 defaults:")
    for k in sorted(PARAM_RANGES):
        old = DEFAULT_PARAMS[k]
        new = best_ever[k]
        if abs(new - old) > 0.01:
            print(f"  {k}: {old} -> {new:.3f}")


if __name__ == "__main__":
    main()
