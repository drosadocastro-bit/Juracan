"""Expanded gauntlet harness — defeats non-transitivity blindness.

Per istinetz/Komil Parmar feedback (kaggle discussion):
"X beats Z beats Y beats X" is real. 6-seed gauntlets cannot distinguish
versions reliably. This harness runs:

  - 20 duel seeds vs each prior version (V32, V30, V27.1, V20)
  - 20 FFA seeds with rotated lineups (challenger always in slot 0, but
    opponents permute through positions so we don't bake in slot bias)
  - Vs starter_sniper as a sanity floor

Usage: python gauntlet.py --challenger main_v33.py [--quick]
  --quick: 6 seeds per matchup (legacy mode)
"""
import argparse
import os
import sys
import time
from collections import Counter, defaultdict

# Silence loud Kaggle env loader warnings on import.
os.environ.setdefault("KAGGLE_ENV_LOG_LEVEL", "ERROR")

from kaggle_environments import make  # noqa: E402

DEFAULTS = {
    "challenger": "main_v33_1.py",
    "duel_opponents": ["main_v32.py", "main_v33.py", "main_v30.py", "main_v27_1.py"],
    "ffa_pool": ["main_v32.py", "main_v33.py", "main_v30.py", "main_v27_1.py", "main_v20.py"],
    "floor_opponent": "starter_sniper.py",
    "duel_seeds": list(range(42, 62)),       # 20 seeds
    "ffa_seeds": list(range(100, 120)),      # 20 seeds
    "floor_seeds": list(range(200, 212)),    # 12 seeds vs starter
}


def _label(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def _run_match(agents: list, seed: int):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/" + a for a in agents])
    final = env.steps[-1]
    return [final[i].reward for i in range(len(agents))]


def duel(challenger: str, opponent: str, seeds: list):
    results = []
    for s in seeds:
        r = _run_match([challenger, opponent], s)
        results.append(r[0] - r[1])  # +ve = challenger win
    wins = sum(1 for d in results if d > 0)
    losses = sum(1 for d in results if d < 0)
    ties = sum(1 for d in results if d == 0)
    return wins, losses, ties


def ffa(challenger: str, opponents: list, seeds: list):
    """FFA: challenger in slot 0, opponents fill 1..3.
    Rotate so each opponent appears in each non-zero slot equally often.
    """
    place_counter = Counter()
    win_by_opponent_set = defaultdict(int)
    n_opps = 3  # 4-player game
    for i, s in enumerate(seeds):
        # Build an opponent triple, rotating through the pool.
        triple = [opponents[(i + k) % len(opponents)] for k in range(n_opps)]
        agents = [challenger] + triple
        rewards = _run_match(agents, s)
        ranks = sorted(range(4), key=lambda k: -rewards[k])
        place_counter[ranks.index(0) + 1] += 1  # challenger's 1-indexed place
        if ranks.index(0) == 0:
            win_by_opponent_set[",".join(_label(a) for a in triple)] += 1
    return place_counter, win_by_opponent_set


def floor(challenger: str, baseline: str, seeds: list):
    return duel(challenger, baseline, seeds)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--challenger", default=DEFAULTS["challenger"])
    ap.add_argument("--quick", action="store_true",
                    help="6 seeds per matchup instead of 20")
    args = ap.parse_args()

    challenger = args.challenger
    if args.quick:
        duel_seeds = DEFAULTS["duel_seeds"][:6]
        ffa_seeds = DEFAULTS["ffa_seeds"][:6]
        floor_seeds = DEFAULTS["floor_seeds"][:6]
    else:
        duel_seeds = DEFAULTS["duel_seeds"]
        ffa_seeds = DEFAULTS["ffa_seeds"]
        floor_seeds = DEFAULTS["floor_seeds"]

    print(f"\n{'='*70}")
    print(f"GAUNTLET — challenger: {challenger}")
    print(f"{'='*70}")
    t0 = time.time()

    # 1. Floor check: should crush starter
    print(f"\n[1] Floor check vs {DEFAULTS['floor_opponent']} ({len(floor_seeds)} seeds)")
    fw, fl, ft = floor(challenger, DEFAULTS["floor_opponent"], floor_seeds)
    pct = 100.0 * fw / max(1, fw + fl + ft)
    print(f"    {fw}-{fl}-{ft}  ({pct:.0f}% win)  {'PASS' if pct >= 90 else 'FAIL (floor regression!)'}")

    # 2. Duels vs each prior version
    print(f"\n[2] Duels ({len(duel_seeds)} seeds each)")
    duel_summary = {}
    for opp in DEFAULTS["duel_opponents"]:
        w, l, t = duel(challenger, opp, duel_seeds)
        duel_summary[_label(opp)] = (w, l, t)
        pct = 100.0 * w / max(1, w + l + t)
        marker = "WIN " if w > l else ("LOSS" if l > w else "TIE ")
        print(f"    vs {_label(opp):14s}  {w:2d}-{l:2d}-{t:2d}  ({pct:.0f}%)  {marker}")

    # 3. FFA with rotated opponents
    print(f"\n[3] 4P FFA ({len(ffa_seeds)} seeds, rotated lineups from pool)")
    places, _ = ffa(challenger, DEFAULTS["ffa_pool"], ffa_seeds)
    total = sum(places.values())
    for place in (1, 2, 3, 4):
        n = places.get(place, 0)
        pct = 100.0 * n / max(1, total)
        bar = "#" * int(pct / 5)
        print(f"    place {place}: {n:2d}/{total} ({pct:4.0f}%) {bar}")
    avg_place = sum(p * n for p, n in places.items()) / max(1, total)
    print(f"    avg place: {avg_place:.2f}  (1.0 = always wins, 2.5 = random in 4P)")

    elapsed = time.time() - t0
    print(f"\n{'='*70}")
    print(f"SUMMARY  ({elapsed:.0f}s)")
    print(f"  Floor:    {fw}-{fl}-{ft}")
    for opp, (w, l, t) in duel_summary.items():
        print(f"  vs {opp:14s}  {w:2d}-{l:2d}-{t:2d}")
    print(f"  FFA avg place: {avg_place:.2f}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
