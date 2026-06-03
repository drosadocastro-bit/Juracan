"""V24 full gauntlet — V7, V20, V23, V23.1."""
from kaggle_environments import make

# ── Round 1: Duels vs V7 and V20 ──
print("=" * 60)
print("V24 vs V7: 2-player duel (6 seeds)")
print("=" * 60)
duel_v7 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v24.py", "d:/Juracan/main_v7.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V24" if r0 > r1 else ("V7" if r1 > r0 else "TIE")
    duel_v7.append(w)
    print(f"  seed={seed}: V24={r0} V7={r1} winner={w}")
print(f"\nDuel vs V7: V24={duel_v7.count('V24')}, V7={duel_v7.count('V7')}, TIE={duel_v7.count('TIE')}")

print("\n" + "=" * 60)
print("V24 vs V20: 2-player duel (6 seeds)")
print("=" * 60)
duel_v20 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v24.py", "d:/Juracan/main_v20.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V24" if r0 > r1 else ("V20" if r1 > r0 else "TIE")
    duel_v20.append(w)
    print(f"  seed={seed}: V24={r0} V20={r1} winner={w}")
print(f"\nDuel vs V20: V24={duel_v20.count('V24')}, V20={duel_v20.count('V20')}, TIE={duel_v20.count('TIE')}")

# ── Round 2: Duels vs V23 and V23.1 ──
print("\n" + "=" * 60)
print("V24 vs V23: 2-player duel (6 seeds)")
print("=" * 60)
duel_v23 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v24.py", "d:/Juracan/main_v23.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V24" if r0 > r1 else ("V23" if r1 > r0 else "TIE")
    duel_v23.append(w)
    print(f"  seed={seed}: V24={r0} V23={r1} winner={w}")
print(f"\nDuel vs V23: V24={duel_v23.count('V24')}, V23={duel_v23.count('V23')}, TIE={duel_v23.count('TIE')}")

print("\n" + "=" * 60)
print("V24 vs V23.1: 2-player duel (6 seeds)")
print("=" * 60)
duel_v231 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v24.py", "d:/Juracan/main_v23_1.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V24" if r0 > r1 else ("V23.1" if r1 > r0 else "TIE")
    duel_v231.append(w)
    print(f"  seed={seed}: V24={r0} V23.1={r1} winner={w}")
print(f"\nDuel vs V23.1: V24={duel_v231.count('V24')}, V23.1={duel_v231.count('V23.1')}, TIE={duel_v231.count('TIE')}")

# ── Round 3: FFA ──
print("\n" + "=" * 60)
print("V24 vs V23.1 vs V20 vs V7: 4-player FFA (6 seeds)")
print("=" * 60)
ffa = []
names = ["V24", "V23.1", "V20", "V7"]
for seed in [42, 99, 137, 256, 512, 777]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v24.py", "d:/Juracan/main_v23_1.py",
             "d:/Juracan/main_v20.py", "d:/Juracan/main_v7.py"])
    final = env.steps[-1]
    rewards = [final[i].reward for i in range(4)]
    wi = rewards.index(max(rewards))
    w = names[wi]
    ffa.append(w)
    print(f"  seed={seed}: rewards={rewards} winner={w}")
print(f"\nFFA Record:")
for n in names:
    print(f"  {n}: {ffa.count(n)}/6")

# ── Summary ──
print("\n" + "=" * 60)
print("V24 GAUNTLET SUMMARY")
print("=" * 60)
print(f"  vs V7:    {duel_v7.count('V24')}-{duel_v7.count('V7')}")
print(f"  vs V20:   {duel_v20.count('V24')}-{duel_v20.count('V20')}")
print(f"  vs V23:   {duel_v23.count('V24')}-{duel_v23.count('V23')}")
print(f"  vs V23.1: {duel_v231.count('V24')}-{duel_v231.count('V23.1')}")
print(f"  FFA:      V24={ffa.count('V24')}/6")
