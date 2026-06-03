"""V32 FFA-Gated Vulture — gauntlet vs V31, V30, V27.1."""
from kaggle_environments import make

print("=" * 60)
print("V32 vs V30: 2-player duel (6 seeds)")
print("=" * 60)
duel_v30 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v32.py", "d:/Juracan/main_v30.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V32" if r0 > r1 else ("V30" if r1 > r0 else "TIE")
    duel_v30.append(w)
    print(f"  seed={seed}: V32={r0} V30={r1} winner={w}")
print(f"\nDuel vs V30: V32={duel_v30.count('V32')}, V30={duel_v30.count('V30')}, TIE={duel_v30.count('TIE')}")

print("\n" + "=" * 60)
print("V32 vs V31: 2-player duel (6 seeds) — must match or beat V30 baseline")
print("=" * 60)
duel_v31 = []
for seed in range(42, 48):
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v32.py", "d:/Juracan/main_v31.py"])
    final = env.steps[-1]
    r0, r1 = final[0].reward, final[1].reward
    w = "V32" if r0 > r1 else ("V31" if r1 > r0 else "TIE")
    duel_v31.append(w)
    print(f"  seed={seed}: V32={r0} V31={r1} winner={w}")
print(f"\nDuel vs V31: V32={duel_v31.count('V32')}, V31={duel_v31.count('V31')}, TIE={duel_v31.count('TIE')}")

print("\n" + "=" * 60)
print("V32 vs V31 vs V30 vs V27.1: 4-player FFA (6 seeds)")
print("=" * 60)
ffa = []
names = ["V32", "V31", "V30", "V27.1"]
for seed in [42, 99, 137, 256, 512, 777]:
    env = make("orbit_wars", debug=False, configuration={"seed": seed})
    env.run(["d:/Juracan/main_v32.py", "d:/Juracan/main_v31.py",
             "d:/Juracan/main_v30.py", "d:/Juracan/main_v27_1.py"])
    final = env.steps[-1]
    rewards = [final[i].reward for i in range(4)]
    wi = rewards.index(max(rewards))
    w = names[wi]
    ffa.append(w)
    print(f"  seed={seed}: rewards={rewards} winner={w}")

print(f"\nFFA Record:")
for n in names:
    print(f"  {n}: {ffa.count(n)}/6")

print("\n" + "=" * 60)
print("V32 GAUNTLET SUMMARY")
print("=" * 60)
print(f"  vs V30 (duel): {duel_v30.count('V32')}-{duel_v30.count('V30')} (TIE={duel_v30.count('TIE')})")
print(f"  vs V31 (duel): {duel_v31.count('V32')}-{duel_v31.count('V31')} (TIE={duel_v31.count('TIE')})")
print(f"  FFA:           V32={ffa.count('V32')}/6")
