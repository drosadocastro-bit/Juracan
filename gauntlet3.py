"""Gauntlet v3 — FFA-heavy, lean pool, paired bootstrap CI.

Lesson from calibration: pure 2P duels can't see Elo gaps that FFA exposes
(V28 tied V27.1 19-18-3 in duels but lost 21 Elo on the ladder). So:

  - Pool is just 4 behavioral bots (no legacy main_v*). Diverse styles only.
  - 4P FFA gets the bulk of the seeds (FFA is where ladder signal lives).
  - 2P duels still measured as a sanity check, but down-weighted.
  - All matches PAIRED: same seed + same opponents for challenger and ref.
    Each paired pair becomes one bootstrap sample. Reduces variance hugely.
  - Bootstrap CI on (challenger_score - reference_score). Ship only if CI > 0.

Usage:
  python gauntlet3.py --challenger main_vXX.py [--reference main_v27_1.py]
  python gauntlet3.py --challenger main_vXX.py --quick    # faster, less power
"""
import argparse
import math
import os
import random
import sys
import time

os.environ.setdefault("KAGGLE_ENV_LOG_LEVEL", "ERROR")
from kaggle_environments import make  # noqa: E402

# Diverse-style baselines.
BOT_POOL = ["starter_sniper.py", "bot_rusher.py", "bot_turtle.py", "bot_econ.py"]
# Strong anchors. Calibration showed pure-bot pool saturates: both V28 and V27.1
# swept the bots so the FFA gave no signal. We seed each FFA with one anchor
# so the game is actually contested. Anchors are ladder-proven snapshots.
ANCHOR_POOL = ["main_v20.py", "main_v25.py"]
# Full pool used for FFA (diversity + anchor forcing).
POOL = BOT_POOL + ANCHOR_POOL
# Duel pool: V-series agents near the current champion's Elo range.
# Weak bots are useless for duels — both agents sweep them, diff=0 every pair.
# These agents produce genuine contested 1v1 games.
DUEL_POOL = ["main_v25.py", "main_v28.py", "main_v27_1.py", "main_v30.py"]

# Default seed budgets. FFA is the costly + most informative path.
DEFAULTS = {
    "ffa_seeds": 30,    # 30 4P games per agent => 60 total
    "duel_seeds": 3,    # 3 seeds vs each of 4 opps => 12 duels per agent
    "weight_ffa": 0.75,
    "weight_duel": 0.25,
}
QUICK = {
    "ffa_seeds": 12,
    "duel_seeds": 2,
    "weight_ffa": 0.75,
    "weight_duel": 0.25,
}


def log(msg):
    print(msg, flush=True)


def run_match(agents, seed):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/" + a for a in agents])
    final = env.steps[-1]
    return [final[i].reward for i in range(len(agents))]


def bootstrap_ci(samples, n_iter=2000, seed=0, alpha=0.05):
    if not samples:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(samples)
    means = []
    for _ in range(n_iter):
        rs_sum = 0.0
        for _ in range(n):
            rs_sum += samples[rng.randrange(n)]
        means.append(rs_sum / n)
    means.sort()
    lo_idx = int((alpha / 2) * n_iter)
    hi_idx = int((1 - alpha / 2) * n_iter)
    return means[lo_idx], means[hi_idx]


def run_duels(challenger, reference, pool, seeds_per_opp):
    """Per (opp, seed), play both (challenger vs opp) and (reference vs opp)
    on the SAME seed. Yields paired margin samples.
    """
    paired = []  # one per (opp, seed): challenger_margin - reference_margin
    total = len(pool) * seeds_per_opp
    idx = 0
    for opp in pool:
        for seed in range(100, 100 + seeds_per_opp):
            idx += 1
            t0 = time.time()
            cr = run_match([challenger, opp], seed)
            rr = run_match([reference, opp], seed)
            c_margin = cr[0] - cr[1]
            r_margin = rr[0] - rr[1]
            paired.append(c_margin - r_margin)
            log(f"  duel [{idx:3d}/{total}] vs {opp:20s} seed={seed}  "
                f"c={c_margin:+d} r={r_margin:+d} -> diff={c_margin - r_margin:+d}  "
                f"({time.time()-t0:.1f}s)")
    return paired


def run_ffa(challenger, reference, pool, n_seeds, rng_seed=12345):
    """Per seed, sample a triple = 1 strong anchor + 2 random bots.
    Play TWO games (challenger in slot 0, then reference in slot 0) with
    same seed + same triple => paired. Sample = challenger_reward - reference_reward.
    """
    rng = random.Random(rng_seed)
    paired = []
    for i in range(n_seeds):
        anchor = rng.choice(ANCHOR_POOL)
        two_bots = rng.sample(BOT_POOL, 2)
        triple = [anchor] + two_bots
        rng.shuffle(triple)  # randomise positional order
        seed = 200 + i
        t0 = time.time()
        cr = run_match([challenger] + triple, seed)
        rr = run_match([reference] + triple, seed)
        diff = cr[0] - rr[0]
        paired.append(diff)
        triple_lbl = ",".join(t.replace(".py", "").replace("starter_", "s_").replace("bot_", "")
                              for t in triple)
        log(f"  ffa  [{i+1:3d}/{n_seeds}] seed={seed} triple=[{triple_lbl}]  "
            f"c={cr[0]:+d} r={rr[0]:+d} -> diff={diff:+d}  ({time.time()-t0:.1f}s)")
    return paired


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--challenger", required=True)
    ap.add_argument("--reference", default="main_v27_1.py")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--ffa-seeds", type=int, default=None,
                    help="Override number of FFA seeds (default 30, quick 12)")
    ap.add_argument("--duel-seeds", type=int, default=None,
                    help="Override number of duel seeds per opponent (default 3, quick 2)")
    args = ap.parse_args()

    cfg = dict(QUICK if args.quick else DEFAULTS)
    if args.ffa_seeds is not None:
        cfg["ffa_seeds"] = args.ffa_seeds
    if args.duel_seeds is not None:
        cfg["duel_seeds"] = args.duel_seeds

    log("=" * 72)
    log(f"GAUNTLET v3 (paired)  challenger={args.challenger}  reference={args.reference}")
    log(f"  FFA pool: {POOL}")
    log(f"  Duel pool: {DUEL_POOL}")
    log(f"  FFA seeds: {cfg['ffa_seeds']}   duel seeds/opp: {cfg['duel_seeds']}")
    log(f"  weights: ffa={cfg['weight_ffa']}  duel={cfg['weight_duel']}")
    log("=" * 72)
    t_total = time.time()

    log("\n[1] 4P FFA  (paired)")
    ffa_diffs = run_ffa(args.challenger, args.reference, POOL, cfg["ffa_seeds"])

    log("\n[2] 2P duels  (paired)")
    duel_diffs = run_duels(args.challenger, args.reference, DUEL_POOL, cfg["duel_seeds"])

    # ----- aggregate -----
    n_ffa = len(ffa_diffs)
    n_duel = len(duel_diffs)
    ffa_mean = sum(ffa_diffs) / max(1, n_ffa)
    duel_mean = sum(duel_diffs) / max(1, n_duel)
    ffa_lo, ffa_hi = bootstrap_ci(ffa_diffs)
    duel_lo, duel_hi = bootstrap_ci(duel_diffs)

    # Combined: weighted concat, normalised so each component sums to its weight.
    combined = []
    for d in ffa_diffs:
        combined.append(d * cfg["weight_ffa"] * len(ffa_diffs + duel_diffs) / max(1, n_ffa))
    for d in duel_diffs:
        combined.append(d * cfg["weight_duel"] * len(ffa_diffs + duel_diffs) / max(1, n_duel))
    c_mean = sum(combined) / max(1, len(combined))
    c_lo, c_hi = bootstrap_ci(combined)

    log("\n" + "=" * 72)
    log(f"RESULT  ({time.time()-t_total:.0f}s)")
    log(f"  FFA  ({n_ffa} pairs)  mean={ffa_mean:+.3f}  CI=[{ffa_lo:+.3f}, {ffa_hi:+.3f}]")
    log(f"  Duel ({n_duel} pairs)  mean={duel_mean:+.3f}  CI=[{duel_lo:+.3f}, {duel_hi:+.3f}]")
    log(f"  COMBINED weighted     mean={c_mean:+.3f}  CI=[{c_lo:+.3f}, {c_hi:+.3f}]")

    if c_lo > 0:
        v = "SHIP   — challenger strictly beats reference (CI > 0)"
    elif c_hi < 0:
        v = "REJECT — challenger strictly worse (CI < 0)"
    else:
        v = "HOLD   — CI straddles zero (no clear signal)"
    log(f"  VERDICT: {v}")
    log("=" * 72)


if __name__ == "__main__":
    main()
