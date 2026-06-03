"""
Evolutionary Self-Play Engine for Orbit Wars.
Recursive self-learning via Darwinian parameter mutation.

1. Reads V49's "genome" (tunable heuristic constants).
2. Creates a mutant by perturbing each gene by ±5-20%.
3. Fights the mutant vs the current champion in a mini-gauntlet.
4. If the mutant wins, it becomes the new champion.
5. Repeats for N generations.

Usage:
    python evolve.py --generations 50 --duels 20
"""

import argparse
import copy
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import time

# ============================================================
# THE GENOME: All tunable constants in V49
# Each gene is (line_pattern, param_name, default_value, min_val, max_val)
# We use regex to find and replace these values in the source code.
# ============================================================

GENOME = [
    # === _score_targets: Global target valuation ===
    ("t.production * (GENE if t.owner == -1 else",    "neutral_prod_weight",    92.0,   60.0,  150.0),
    ("t.production * (92.0 if t.owner == -1 else GENE)", "enemy_prod_weight",  118.0,   70.0,  180.0),
    ("base += t.production * GENE",                    "duel_open_prod",         70.0,   30.0,  150.0),
    ("max(0.0, GENE - t.ships) * 2.2",                 "duel_open_ship_thresh",  18.0,   10.0,   30.0),
    ("base += t.production * GENE",                    "ffa_open_prod",          26.0,   10.0,   80.0),
    ("max(0.0, GENE - t.ships) * 0.9",                 "ffa_open_ship_thresh",   18.0,   10.0,   30.0),
    ("base += GENE",                                   "ffa_behind_bonus",      110.0,   50.0,  200.0),
    ("base += GENE  # leader",                         "leader_bonus",           72.0,   30.0,  150.0),
    ("base += GENE  # Elimination",                    "elimination_bonus",     160.0,   80.0,  250.0),
    ("max(0.0, GENE - t.ships) * 0.9  # weak",        "weak_target_thresh",     30.0,   15.0,   50.0),
    ("base += GENE  # conflict",                       "conflict_bonus",         45.0,   20.0,   80.0),
    ("score += GENE  # vulture",                       "vulture_bonus",          35.0,   15.0,   60.0),
    
    # === _best_move_for_source: Local scoring weights ===
    ("base - send * GENE - distance * 1.45",           "duel_send_penalty",       1.2,   0.5,    2.5),
    ("send * 1.2 - distance * GENE - eta",             "duel_dist_penalty",       1.45,  0.5,    3.0),
    ("distance * 1.45 - eta * GENE",                   "duel_eta_penalty",        2.0,   0.5,    4.0),
    ("score += GENE  # duel prod>=3",                  "duel_prod3_bonus",       45.0,  15.0,  100.0),
    ("score += GENE  # duel ships<=12",                "duel_ships12_bonus",     28.0,  10.0,   60.0),
    ("base - send * GENE - distance * 0.72",           "ffa_send_penalty",        1.55,  0.5,    3.0),
    ("send * 1.55 - distance * GENE - eta",            "ffa_dist_penalty",        0.72,  0.2,    2.0),
    ("distance * 0.72 - eta * GENE",                   "ffa_eta_penalty",         1.35,  0.5,    3.0),
    ("score += GENE  # ffa prod>=3",                   "ffa_prod3_bonus",        18.0,   5.0,   50.0),
    ("score += GENE  # ffa ships<=14",                 "ffa_ships14_bonus",      14.0,   5.0,   40.0),
    ("base - send * GENE - distance * 0.55",           "mid_send_penalty",        1.9,   0.8,    3.5),
    ("send * 1.9 - distance * GENE - eta",             "mid_dist_penalty",        0.55,  0.2,    1.5),
    ("distance * 0.55 - eta * GENE",                   "mid_eta_penalty",         1.2,   0.3,    3.0),
    
    # === Phase thresholds ===
    ("self.duel_opening = self.is_duel and w.step < GENE", "duel_open_end",      45,    25,     80),
    ("self.ffa_opening = (not self.is_duel) and w.step < GENE", "ffa_open_end",  72,    40,    120),
    
    # === Reserve tuning ===
    ("nearest_enemy < GENE:  # ffa reserve",           "ffa_reserve_dist",       18.0,  10.0,   35.0),
    ("nearest_enemy >= GENE:  # ffa behind",           "ffa_behind_dist",        28.0,  18.0,   45.0),
    
    # === Locality (Duel brain) ===
    ("LOCALITY_BONUS_MAX",                             "locality_bonus_max",     10.0,   3.0,   40.0),
    ("LOCALITY_RADIUS",                                "locality_radius",        30.0,  15.0,   60.0),
]


def create_mutant_genome(champion_genome, mutation_rate=0.15, mutation_strength=0.15):
    """Create a mutant by perturbing each gene with probability mutation_rate."""
    mutant = copy.deepcopy(champion_genome)
    for gene_name in mutant:
        if random.random() < mutation_rate:
            val = mutant[gene_name]
            # Gaussian perturbation
            delta = random.gauss(0, mutation_strength) * val
            new_val = val + delta
            # Find bounds
            for _, name, _, lo, hi in GENOME:
                if name == gene_name:
                    new_val = max(lo, min(hi, new_val))
                    break
            # Keep integers as integers
            if isinstance(val, int) or (isinstance(val, float) and val == int(val) and gene_name in ("duel_open_end", "ffa_open_end")):
                new_val = int(round(new_val))
            mutant[gene_name] = new_val
    return mutant


def inject_genome_into_source(source_path, output_path, genome_values):
    """Read the V49 source, replace all tunable constants, write to output."""
    with open(source_path, "r", encoding="utf-8") as f:
        code = f.read()

    # Direct, surgical replacements using exact patterns from V49
    replacements = {
        # _score_targets
        'base = t.production * (92.0 if t.owner == -1 else 118.0)':
            f'base = t.production * ({genome_values["neutral_prod_weight"]:.1f} if t.owner == -1 else {genome_values["enemy_prod_weight"]:.1f})',
        'base += t.production * 70.0':
            f'base += t.production * {genome_values["duel_open_prod"]:.1f}',
        'base += max(0.0, 18.0 - t.ships) * 2.2':
            f'base += max(0.0, {genome_values["duel_open_ship_thresh"]:.1f} - t.ships) * 2.2',
        'base += t.production * 26.0':
            f'base += t.production * {genome_values["ffa_open_prod"]:.1f}',
        'base += max(0.0, 18.0 - t.ships) * 0.9':
            f'base += max(0.0, {genome_values["ffa_open_ship_thresh"]:.1f} - t.ships) * 0.9',
        'base += 110.0':
            f'base += {genome_values["ffa_behind_bonus"]:.1f}',
        'base += 72.0':
            f'base += {genome_values["leader_bonus"]:.1f}',
        'base += 160.0  # Elimination drive':
            f'base += {genome_values["elimination_bonus"]:.1f}  # Elimination drive',
        'base += max(0.0, 30.0 - t.ships) * 0.9':
            f'base += max(0.0, {genome_values["weak_target_thresh"]:.1f} - t.ships) * 0.9',
        'base += 45.0':
            f'base += {genome_values["conflict_bonus"]:.1f}',
        'score += 35.0':
            f'score += {genome_values["vulture_bonus"]:.1f}',
            
        # _best_move_for_source: duel opening
        'score = base - send * 1.2 - distance * 1.45 - eta * 2.0':
            f'score = base - send * {genome_values["duel_send_penalty"]:.2f} - distance * {genome_values["duel_dist_penalty"]:.2f} - eta * {genome_values["duel_eta_penalty"]:.2f}',
        'score += 45.0\n            if target.ships <= 12':
            f'score += {genome_values["duel_prod3_bonus"]:.1f}\n            if target.ships <= 12',
        'score += 28.0\n            # In duels':
            f'score += {genome_values["duel_ships12_bonus"]:.1f}\n            # In duels',
            
        # _best_move_for_source: ffa opening
        'score = base - send * 1.55 - distance * 0.72 - eta * 1.35':
            f'score = base - send * {genome_values["ffa_send_penalty"]:.2f} - distance * {genome_values["ffa_dist_penalty"]:.2f} - eta * {genome_values["ffa_eta_penalty"]:.2f}',
        'score += 18.0\n            if target.ships <= 14':
            f'score += {genome_values["ffa_prod3_bonus"]:.1f}\n            if target.ships <= 14',
        'score += 14.0\n            score /= max(1.0':
            f'score += {genome_values["ffa_ships14_bonus"]:.1f}\n            score /= max(1.0',
        
        # _best_move_for_source: midgame 
        'score = base - send * 1.9 - distance * 0.55 - eta * 1.2':
            f'score = base - send * {genome_values["mid_send_penalty"]:.2f} - distance * {genome_values["mid_dist_penalty"]:.2f} - eta * {genome_values["mid_eta_penalty"]:.2f}',
            
        # Phase thresholds
        'self.is_duel and w.step < 45':
            f'self.is_duel and w.step < {int(genome_values["duel_open_end"])}',
        '(not self.is_duel) and w.step < 72':
            f'(not self.is_duel) and w.step < {int(genome_values["ffa_open_end"])}',
        
        # Reserve distances
        'if nearest_enemy < 18.0:\n                return max(3, planet.production + 1)':
            f'if nearest_enemy < {genome_values["ffa_reserve_dist"]:.1f}:\n                return max(3, planet.production + 1)',
        'if self.ffa_behind and incoming <= 0 and nearest_enemy >= 28.0:':
            f'if self.ffa_behind and incoming <= 0 and nearest_enemy >= {genome_values["ffa_behind_dist"]:.1f}:',
            
        # Locality constants
        'LOCALITY_BONUS_MAX = 10.0':
            f'LOCALITY_BONUS_MAX = {genome_values["locality_bonus_max"]:.1f}',
        'LOCALITY_RADIUS = 30.0':
            f'LOCALITY_RADIUS = {genome_values["locality_radius"]:.1f}',
    }
    
    for old, new in replacements.items():
        code = code.replace(old, new, 1)  # Replace only first occurrence
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(code)


def run_mini_gauntlet(challenger_path, reference_path, duel_seeds=20):
    """Run a fast mini-gauntlet and return the combined mean score."""
    cmd = [
        sys.executable, "gauntlet3.py",
        "--challenger", challenger_path,
        "--reference", reference_path,
        "--duel-seeds", str(duel_seeds),
        "--ffa-seeds", "5",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, cwd=os.getcwd())
        output = result.stdout + result.stderr
        
        # Parse the COMBINED weighted mean from gauntlet output
        for line in output.split("\n"):
            if "COMBINED weighted" in line:
                # Example: "  COMBINED weighted     mean=+0.067  CI=[-0.183, +0.317]"
                match = re.search(r"mean=([+-]?\d+\.\d+)", line)
                if match:
                    return float(match.group(1))
        
        # Fallback: check for VERDICT
        if "REJECT" in output:
            return -1.0
        return 0.0
    except subprocess.TimeoutExpired:
        print("  [TIMEOUT] Gauntlet timed out.")
        return -0.5
    except Exception as e:
        print(f"  [ERROR] Gauntlet failed: {e}")
        return -1.0


def main():
    parser = argparse.ArgumentParser(description="Evolutionary Self-Play for Orbit Wars")
    parser.add_argument("--generations", type=int, default=50, help="Number of generations")
    parser.add_argument("--duels", type=int, default=20, help="Duel seeds per mini-gauntlet")
    parser.add_argument("--mutation-rate", type=float, default=0.25, help="Probability of mutating each gene")
    parser.add_argument("--mutation-strength", type=float, default=0.12, help="Gaussian std as fraction of value")
    parser.add_argument("--source", type=str, default="main_v49.py", help="Base agent source file")
    args = parser.parse_args()

    # Initialize champion genome with V49's defaults
    champion_genome = {}
    for _, name, default, _, _ in GENOME:
        champion_genome[name] = default

    champion_path = args.source
    os.makedirs("evolution", exist_ok=True)
    
    # Save initial genome
    with open("evolution/gen_0_genome.json", "w") as f:
        json.dump(champion_genome, f, indent=2)

    print("=" * 72)
    print(f"EVOLUTIONARY SELF-PLAY ENGINE")
    print(f"  Generations: {args.generations}")
    print(f"  Duels/gauntlet: {args.duels}")
    print(f"  Mutation rate: {args.mutation_rate}")
    print(f"  Mutation strength: {args.mutation_strength}")
    print(f"  Base source: {args.source}")
    print(f"  Genome size: {len(GENOME)} genes")
    print("=" * 72)

    best_score = 0.0
    wins = 0
    
    for gen in range(1, args.generations + 1):
        t0 = time.time()
        print(f"\n--- Generation {gen}/{args.generations} ---")
        
        # Create mutant
        mutant_genome = create_mutant_genome(
            champion_genome, 
            mutation_rate=args.mutation_rate,
            mutation_strength=args.mutation_strength
        )
        
        # Show mutations
        mutations = []
        for name in mutant_genome:
            if mutant_genome[name] != champion_genome[name]:
                old = champion_genome[name]
                new = mutant_genome[name]
                pct = ((new - old) / old * 100) if old != 0 else 0
                mutations.append(f"  {name}: {old:.2f} -> {new:.2f} ({pct:+.1f}%)")
        
        if not mutations:
            print("  No mutations this generation (clone). Skipping.")
            continue
            
        print(f"  Mutations ({len(mutations)} genes):")
        for m in mutations:
            print(m)
        
        # Inject mutant genome into source code
        mutant_path = f"evolution/mutant_gen{gen}.py"
        inject_genome_into_source(args.source, mutant_path, mutant_genome)
        
        # Fight!
        print(f"  Fighting mutant vs champion ({args.duels} duels + 5 FFA)...")
        score = run_mini_gauntlet(mutant_path, champion_path, duel_seeds=args.duels)
        elapsed = time.time() - t0
        
        print(f"  Score: {score:+.3f} ({elapsed:.0f}s)")
        
        if score > 0.0:
            # MUTANT WINS! It becomes the new champion.
            wins += 1
            champion_genome = mutant_genome
            champion_path = f"evolution/champion_gen{gen}.py"
            shutil.copy(mutant_path, champion_path)
            best_score = score
            
            print(f"  >>> MUTANT WINS! New champion: gen {gen} (score: {score:+.3f}) <<<")
            print(f"  Total champion changes: {wins}")
            
            # Save champion genome
            with open(f"evolution/champion_gen{gen}_genome.json", "w") as f:
                json.dump(champion_genome, f, indent=2)
        else:
            print(f"  Champion survives. (score: {score:+.3f})")
            # Clean up failed mutant
            try:
                os.remove(mutant_path)
            except OSError:
                pass
    
    # Final report
    print("\n" + "=" * 72)
    print("EVOLUTION COMPLETE")
    print(f"  Generations: {args.generations}")
    print(f"  Champion changes: {wins}")
    print(f"  Final champion: {champion_path}")
    print(f"  Best score: {best_score:+.3f}")
    print("=" * 72)
    
    # Save final champion as main_v54.py
    if wins > 0:
        shutil.copy(champion_path, "main_v54.py")
        print(f"\nFinal evolved agent saved as main_v54.py")
        with open("evolution/final_genome.json", "w") as f:
            json.dump(champion_genome, f, indent=2)
    else:
        print("\nNo improvements found. V49 remains the champion.")


if __name__ == "__main__":
    main()
