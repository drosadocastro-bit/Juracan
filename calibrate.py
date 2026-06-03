"""Fast calibration: does the new gauntlet predict V28's known regression?

V28 scored 693.3 on ladder. V27.1 scored 714.7. If our local framework is
calibrated, V28 should not win clearly vs V27.1 here either.

This is intentionally small + focused so we get an answer fast. Prints
progress line-by-line with flush.
"""
import sys
import math
import os
import random
import time

os.environ.setdefault("KAGGLE_ENV_LOG_LEVEL", "ERROR")
from kaggle_environments import make  # noqa


def run(agents, seed):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/" + a for a in agents])
    final = env.steps[-1]
    return [final[i].reward for i in range(len(agents))]


def log(msg):
    print(msg, flush=True)


def bootstrap_ci(samples, n=1000, seed=0):
    rng = random.Random(seed)
    if not samples:
        return (0.0, 0.0)
    n_s = len(samples)
    vals = []
    for _ in range(n):
        rs = [samples[rng.randrange(n_s)] for _ in range(n_s)]
        vals.append(sum(rs) / n_s)
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


def head_to_head(a, b, seeds):
    """Returns margins (a_reward - b_reward), one per seed."""
    out = []
    for i, s in enumerate(seeds):
        t0 = time.time()
        r = run([a, b], s)
        margin = r[0] - r[1]
        out.append(margin)
        log(f"  [{i+1:2d}/{len(seeds)}] seed={s} margin={margin:+d}  ({time.time()-t0:.1f}s)")
    return out


def main():
    log("=" * 64)
    log("CALIBRATION: V28 vs V27.1 — ladder says V28 loses (693 < 714)")
    log("=" * 64)

    seeds = list(range(42, 62))  # 20 seeds, both player orders

    log(f"\n[A] V28 in slot 0, V27.1 in slot 1  ({len(seeds)} seeds)")
    a_margins = head_to_head("main_v28.py", "main_v27_1.py", seeds)

    log(f"\n[B] V27.1 in slot 0, V28 in slot 1  ({len(seeds)} seeds)")
    b_margins = head_to_head("main_v27_1.py", "main_v28.py", seeds)

    # Combine: from V28's perspective, both samples are margins of V28 - V27.1.
    v28_margins = a_margins + [-m for m in b_margins]

    wins = sum(1 for m in v28_margins if m > 0)
    losses = sum(1 for m in v28_margins if m < 0)
    ties = sum(1 for m in v28_margins if m == 0)
    n = len(v28_margins)
    wr = wins / n * 100

    mean = sum(v28_margins) / n
    lo, hi = bootstrap_ci(v28_margins, n=2000)

    log("\n" + "=" * 64)
    log(f"RESULT  ({n} games, both slot orders)")
    log(f"  V28 record vs V27.1:  {wins}-{losses}-{ties}  ({wr:.1f}% win rate)")
    log(f"  Mean margin:          {mean:+.3f}")
    log(f"  95% bootstrap CI:     [{lo:+.3f}, {hi:+.3f}]")
    log("")
    if wr > 55 and lo > 0:
        log("  VERDICT: V28 BEATS V27.1 locally -> gauntlet still broken")
        log("           ladder says V28 < V27.1, so local prediction is wrong")
    elif wr < 45 or hi < 0:
        log("  VERDICT: V28 LOSES locally -> gauntlet matches ladder reality")
    else:
        log("  VERDICT: indecisive — V28 ~= V27.1 locally.")
        log("           Ladder says V28 < V27.1 by ~21 points; we should see a")
        log("           weak loss for V28. Tied result means low signal.")
    log("=" * 64)


if __name__ == "__main__":
    main()
