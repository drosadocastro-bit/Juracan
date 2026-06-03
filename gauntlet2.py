"""Expanded gauntlet v2 — diverse pool + Elo + bootstrap CI.

Why this exists:
  The previous 6–20-seed gauntlet was non-predictive of ladder Elo. V28→V32
  all showed positive local results, all regressed on Kaggle. Two fixes:

  1. Diverse opponent pool. Real ladder agents include rushers, turtles,
     economic players, and snipers — not just OODA-L descendants. We mix
     hand-coded behavior baselines with our best legacy versions.

  2. Bootstrap-CI gate. Per Kaggle thread 698478 ("X beats Z beats Y beats X"),
     improvements are non-transitive. We resample matches with replacement
     1000× to estimate a 95% CI on the challenger's average margin over the
     reference. Ship only when CI > 0 (strictly positive).

Usage:
  python gauntlet2.py --challenger main_v33.py
  python gauntlet2.py --challenger main_v33.py --reference main_v27_1.py
  python gauntlet2.py --challenger main_v33.py --quick   # fewer seeds for fast iteration
"""
import argparse
import math
import os
import random
import time
from collections import Counter, defaultdict

os.environ.setdefault("KAGGLE_ENV_LOG_LEVEL", "ERROR")
from kaggle_environments import make  # noqa: E402

# ---- pool configuration ---------------------------------------------------
# Behavioral baselines: hand-coded distinct styles.
BEHAVIOR_POOL = ["starter_sniper.py", "bot_rusher.py", "bot_turtle.py", "bot_econ.py"]

# Legacy snapshots: high-water-mark versions we trust as approximations of
# different agent generations on the ladder.
LEGACY_POOL = ["main_v20.py", "main_v27_1.py", "main_v30.py"]

FULL_POOL = BEHAVIOR_POOL + LEGACY_POOL

# Ladder seems ~70% 4P / 30% 2P per forum discussion 698659.
WEIGHT_4P = 0.70
WEIGHT_2P = 0.30

# Match counts.
SEEDS_FULL = list(range(42, 72))      # 30 seeds
SEEDS_QUICK = list(range(42, 52))     # 10 seeds


def _label(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def _run_match(agent_paths, seed):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/" + a for a in agent_paths])
    final = env.steps[-1]
    return [final[i].reward for i in range(len(agent_paths))]


def _duel(a, b, seeds):
    """Returns list of margins (a_reward - b_reward), one per seed."""
    out = []
    for s in seeds:
        r = _run_match([a, b], s)
        out.append(r[0] - r[1])
    return out


def _ffa(challenger, pool, seeds, rng):
    """Challenger in slot 0, 3 random opponents from pool per seed.

    Returns list of (place, reward, opponents_label). Place is 1..4 (1=best).
    """
    out = []
    for s in seeds:
        triple = rng.sample(pool, 3)
        rewards = _run_match([challenger] + triple, s)
        ranks = sorted(range(4), key=lambda k: -rewards[k])
        place = ranks.index(0) + 1
        out.append((place, rewards[0], ",".join(_label(t) for t in triple)))
    return out


def _winrate(margins):
    if not margins:
        return 0.0
    w = sum(1 for m in margins if m > 0)
    return w / len(margins)


def _elo_from_winrate(wr):
    """Convert a win rate vs an opponent into Elo difference."""
    wr = min(0.99, max(0.01, wr))
    return -400.0 * math.log10(1.0 / wr - 1.0)


def _bootstrap_ci(samples, fn, n=1000, seed=0):
    """95% CI of fn(samples) by bootstrap resampling."""
    rng = random.Random(seed)
    if not samples:
        return (0.0, 0.0)
    n_s = len(samples)
    vals = []
    for _ in range(n):
        resample = [samples[rng.randrange(n_s)] for _ in range(n_s)]
        vals.append(fn(resample))
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--challenger", required=True)
    ap.add_argument("--reference", default="main_v27_1.py",
                    help="Reference agent for CI comparison (default: V27.1)")
    ap.add_argument("--quick", action="store_true",
                    help="10 seeds per matchup instead of 30")
    args = ap.parse_args()

    challenger = args.challenger
    reference = args.reference
    seeds = SEEDS_QUICK if args.quick else SEEDS_FULL
    n_seeds = len(seeds)

    print(f"\n{'='*72}")
    print(f"GAUNTLET v2 — {challenger}  (ref: {reference})  [{n_seeds} seeds/matchup]")
    print(f"{'='*72}")
    t0 = time.time()

    # ------- 2P duels: challenger vs each pool member -------
    print(f"\n[1] 2P duels — challenger vs pool")
    duel_results = {}      # opp -> list of margins (challenger - opp)
    ref_duel_results = {}  # same for reference
    for opp in FULL_POOL:
        c_margins = _duel(challenger, opp, seeds)
        r_margins = _duel(reference, opp, seeds)
        duel_results[opp] = c_margins
        ref_duel_results[opp] = r_margins
        c_wr = _winrate(c_margins)
        r_wr = _winrate(r_margins)
        delta = c_wr - r_wr
        marker = "WIN " if delta > 0.05 else ("LOSS" if delta < -0.05 else "tie ")
        print(f"    vs {_label(opp):18s}  challenger {c_wr*100:5.1f}%   ref {r_wr*100:5.1f}%  delta {delta*100:+5.1f}%  {marker}")

    # ------- 4P FFA: challenger and reference each play, with rotated triples -------
    print(f"\n[2] 4P FFA — random triples from pool")
    rng = random.Random(12345)
    c_ffa = _ffa(challenger, FULL_POOL, seeds, random.Random(12345))
    r_ffa = _ffa(reference, FULL_POOL, seeds, random.Random(12345))  # same lineups
    c_avg_place = sum(p for p, _, _ in c_ffa) / len(c_ffa)
    r_avg_place = sum(p for p, _, _ in r_ffa) / len(r_ffa)
    c_win_pct = sum(1 for p, _, _ in c_ffa if p == 1) / len(c_ffa) * 100
    r_win_pct = sum(1 for p, _, _ in r_ffa if p == 1) / len(r_ffa) * 100
    print(f"    challenger:  win {c_win_pct:5.1f}%   avg place {c_avg_place:.2f}")
    print(f"    reference :  win {r_win_pct:5.1f}%   avg place {r_avg_place:.2f}")

    # ------- Aggregate margin: pooled 2P + 4P weighted -------
    # Use challenger reward - reference reward on the SAME seed.
    # 2P: per opp, take avg margin across seeds.
    # 4P: per seed, take challenger reward - reference reward (same triple).
    pooled_samples = []  # one sample per (matchup, seed)
    for opp in FULL_POOL:
        for i in range(n_seeds):
            margin_c = duel_results[opp][i]
            margin_r = ref_duel_results[opp][i]
            pooled_samples.append((margin_c - margin_r) * WEIGHT_2P / len(FULL_POOL))

    for i in range(n_seeds):
        c_reward = c_ffa[i][1]
        r_reward = r_ffa[i][1]
        pooled_samples.append((c_reward - r_reward) * WEIGHT_4P)

    avg = sum(pooled_samples) / max(1, len(pooled_samples))
    lo, hi = _bootstrap_ci(pooled_samples, lambda xs: sum(xs) / max(1, len(xs)), n=1000)

    # ------- Verdict -------
    elapsed = time.time() - t0
    print(f"\n{'='*72}")
    print(f"VERDICT  ({elapsed:.0f}s)")
    print(f"  Weighted mean margin (challenger - reference): {avg:+.4f}")
    print(f"  95% bootstrap CI: [{lo:+.4f}, {hi:+.4f}]")
    if lo > 0:
        verdict = "SHIP  — CI strictly positive"
    elif hi < 0:
        verdict = "REJECT — CI strictly negative (regression)"
    else:
        verdict = "HOLD  — CI straddles zero (insufficient evidence)"
    print(f"  -> {verdict}")
    print(f"{'='*72}\n")


if __name__ == "__main__":
    main()
